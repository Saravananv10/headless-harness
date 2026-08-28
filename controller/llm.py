"""OpenAI-compatible LLM client for controller reasoning."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from controller.exceptions import LLMClientError

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Protocol for controller LLM backends."""

    def complete(self, messages: Sequence[dict[str, str]], *, temperature: float = 0.2) -> str:
        ...


@dataclass
class OpenAICompatibleClient:
    """Minimal OpenAI-compatible chat completions client (stdlib only)."""

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 300.0

    @classmethod
    def from_env(cls) -> OpenAICompatibleClient:
        base_url = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
        api_key = os.environ.get("OPENAI_API_KEY", "")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        timeout = float(os.environ.get("HARNESS_CONTROLLER_LLM_TIMEOUT", "300"))
        if not base_url or not api_key:
            raise LLMClientError(
                "OPENAI_BASE_URL and OPENAI_API_KEY must be set for controller LLM"
            )
        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout,
        )

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.2,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        body: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": temperature,
        }
        
        max_retries = 5
        base_delay = 2.0
        
        for attempt in range(1, max_retries + 1):
            request = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code in (500, 502, 503, 504, 429) and attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "LLM HTTP %d (attempt %d/%d): %s. Retrying in %.1fs...",
                        exc.code, attempt, max_retries, detail[:100], delay
                    )
                    time.sleep(delay)
                    continue
                raise LLMClientError(f"LLM HTTP {exc.code}: {detail}") from exc
            except (urllib.error.URLError, TimeoutError, ConnectionResetError, OSError) as exc:
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "LLM request failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        attempt, max_retries, exc, delay
                    )
                    time.sleep(delay)
                    continue
                raise LLMClientError(f"LLM request failed: {exc}") from exc
            except (KeyError, IndexError, json.JSONDecodeError) as exc:
                raise LLMClientError(f"Unexpected LLM response shape: {exc}") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"Missing message content in LLM response: {payload}") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMClientError("LLM returned empty content")
        return content


class DeterministicLLMClient:
    """Test double that returns queued responses in order."""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[list[dict[str, str]]] = []

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.2,
    ) -> str:
        del temperature
        self.calls.append(list(messages))
        if self._index >= len(self._responses):
            raise LLMClientError("DeterministicLLMClient response queue exhausted")
        response = self._responses[self._index]
        self._index += 1
        return response


class CallableLLMClient:
    """Test double that delegates to a callable."""

    def __init__(self, fn: Callable[[Sequence[dict[str, str]]], str]) -> None:
        self._fn = fn

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.2,
    ) -> str:
        del temperature
        return self._fn(messages)
