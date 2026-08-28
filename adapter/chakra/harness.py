"""ChakraHarness — production adapter implementing the common Harness contract."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from client.chakra_client import ChakraClient
from client.config import ChakraConfig

from adapter.chakra.config import apply_connection_env, resolve_chakra_config
from adapter.chakra.session import (
    close_harness_session,
    create_harness_session,
    resume_harness_session,
    to_session_status,
)
from adapter.chakra.stream import ChakraTurnStream
from interface.capabilities import HarnessCapabilities, HarnessCapability
from interface.exceptions import (
    HarnessConnectionError,
    HarnessNotConnectedError,
    HarnessSessionError,
)
from interface.harness import Harness, TurnStream
from interface.models.requests import (
    ConnectionConfig,
    CreateSessionRequest,
    ResumeSessionRequest,
    SendMessageRequest,
)
from interface.models.responses import ConnectionInfo, SessionCloseResult, SessionStatus
from interface.models.session import HarnessSession

logger = logging.getLogger(__name__)

ChakraClientFactory = Callable[[ChakraConfig], ChakraClient]


class ChakraHarness(Harness):
    """
    Harness adapter for the Chakra gRPC backend.

    All Chakra-specific protocol handling is isolated to adapter/chakra and client/.
    Higher layers must depend on this class (or Harness), never on ChakraClient.
    """

    ADAPTER_NAME = "chakra"

    def __init__(
        self,
        *,
        client_factory: ChakraClientFactory | None = None,
        default_timeout_seconds: float = 600.0,
    ) -> None:
        self._client_factory = client_factory or (lambda cfg: ChakraClient(cfg))
        self._client: ChakraClient | None = None
        self._config: ChakraConfig | None = None
        self._connect_timeout_seconds = 50.0
        self._default_turn_timeout_seconds = default_timeout_seconds
        self._sessions: dict[str, HarnessSession] = {}

    def connect(self, config: ConnectionConfig | None = None) -> ConnectionInfo:
        chakra_config, timeout = resolve_chakra_config(config)
        self._connect_timeout_seconds = timeout
        apply_connection_env(chakra_config)
        self._config = chakra_config

        try:
            client = self._client_factory(chakra_config)
            client.connect(timeout_seconds=self._connect_timeout_seconds)
            self._client = client
            logger.info("ChakraHarness connected to %s", chakra_config.address)
            return ConnectionInfo(
                connected=True,
                endpoint=chakra_config.address,
                adapter_name=self.ADAPTER_NAME,
                metadata={"service": chakra_config.service_name},
            )
        except Exception as exc:
            raise HarnessConnectionError(str(exc)) from exc

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.disconnect()
            self._client = None
        self._sessions.clear()
        logger.info("ChakraHarness disconnected")

    def connection_info(self) -> ConnectionInfo:
        connected = self._client is not None and self._client.is_connected()
        endpoint = self._config.address if self._config else None
        return ConnectionInfo(
            connected=connected,
            endpoint=endpoint,
            adapter_name=self.ADAPTER_NAME,
        )

    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(
            supported=frozenset(
                {
                    HarnessCapability.CONNECT,
                    HarnessCapability.DISCONNECT,
                    HarnessCapability.STREAMING,
                    HarnessCapability.SESSIONS,
                    HarnessCapability.SESSION_RESUME,
                    HarnessCapability.TOOL_EXECUTION,
                    HarnessCapability.INTERACTIVE_APPROVAL,
                    HarnessCapability.CANCELLATION,
                    HarnessCapability.MODEL_OVERRIDE,
                    HarnessCapability.WORKING_DIRECTORY,
                }
            )
        )

    def create_session(
        self, request: CreateSessionRequest | None = None
    ) -> HarnessSession:
        self._require_connected()
        session = create_harness_session(request)
        self._sessions[session.session_id] = session
        logger.debug("Created harness session %s", session.session_id)
        return session

    def resume_session(self, request: ResumeSessionRequest) -> HarnessSession:
        self._require_connected()
        existing = self._sessions.get(request.session_id)
        if existing is not None:
            if request.working_directory is not None:
                existing.working_directory = request.working_directory
            if request.model:
                existing.metadata["model"] = request.model
            existing.metadata.update(request.metadata)
            logger.debug("Resumed harness session %s", existing.session_id)
            return existing

        session = resume_harness_session(request)
        self._sessions[session.session_id] = session
        logger.debug("Resumed harness session %s", session.session_id)
        return session

    def send_turn(
        self, session: HarnessSession, request: SendMessageRequest
    ) -> TurnStream:
        self._require_connected()
        self._require_active_session(session)
        session.turn_count += 1
        timeout = float(request.options.get("timeout_seconds", self._default_turn_timeout_seconds))
        assert self._client is not None
        on_raw = session.metadata.get("raw_event_sink")
        return ChakraTurnStream(
            self._client,
            session,
            request,
            timeout_seconds=timeout,
            on_raw_event=on_raw if callable(on_raw) else None,
        )

    def get_session_status(self, session: HarnessSession) -> SessionStatus:
        self._require_connected()
        return to_session_status(session)

    def close_session(self, session: HarnessSession) -> SessionCloseResult:
        self._require_connected()
        result = close_harness_session(session)
        self._sessions.pop(session.session_id, None)
        logger.debug("Closed harness session %s", session.session_id)
        return result

    def _require_connected(self) -> None:
        if self._client is None or not self._client.is_connected():
            raise HarnessNotConnectedError("ChakraHarness is not connected")

    def _require_active_session(self, session: HarnessSession) -> None:
        if not session.is_active():
            raise HarnessSessionError(f"Session {session.session_id} is closed")
        if session.session_id not in self._sessions:
            self._sessions[session.session_id] = session
