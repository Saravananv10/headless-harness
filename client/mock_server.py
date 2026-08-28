"""Offline mock of chakra.v1.AgentService for client development and tests."""

from __future__ import annotations

import logging
import time
from concurrent import futures

import grpc

from client.generated import chakra_pb2, chakra_pb2_grpc

logger = logging.getLogger(__name__)


class MockAgentServicer(chakra_pb2_grpc.AgentServiceServicer):
    """Minimal servicer that echoes streaming text and supports sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[str]] = {}

    def Chat(self, request_iterator, context):  # noqa: N802
        session_id = ""
        pending_tool_prompt = ""
        for client_msg in request_iterator:
            which = client_msg.WhichOneof("payload")
            if which == "request":
                req = client_msg.request
                session_id = req.session_id or ""
                message = req.message.strip()

                if message == "phase2:force_error":
                    yield chakra_pb2.ServerMessage(
                        error=chakra_pb2.ErrorResponse(
                            message="forced mock error",
                            code="INTERNAL",
                        )
                    )
                    return

                if message == "phase2:tool_flow":
                    pending_tool_prompt = "prompt-tool-approval-1"
                    yield chakra_pb2.ServerMessage(
                        tool_start=chakra_pb2.ToolCallStart(
                            tool_name="shell",
                            arguments_json='{"command":"echo mock"}',
                            tool_use_id="tool-1",
                        )
                    )
                    yield chakra_pb2.ServerMessage(
                        action_required=chakra_pb2.ActionRequired(
                            prompt_id=pending_tool_prompt,
                            question="Approve shell?",
                            type=chakra_pb2.ActionRequired.CONFIRM_COMMAND,
                        )
                    )
                    continue

                if message == "phase2:long_stream":
                    chunks = ["stream ", "in ", "progress ", "for ", "cancel "]
                    for chunk in chunks:
                        if not context.is_active():
                            return
                        yield chakra_pb2.ServerMessage(
                            text_chunk=chakra_pb2.TextChunk(text=chunk)
                        )
                        time.sleep(0.1)
                    yield chakra_pb2.ServerMessage(
                        done=chakra_pb2.FinalResponse(
                            full_text="".join(chunks).strip(),
                            prompt_tokens=1,
                            completion_tokens=len(chunks),
                        )
                    )
                    return

                history = self._sessions.get(session_id, [])
                prior = f" (prior turns: {len(history)})" if history else ""
                text = f"Echo: {message}{prior}"
                for word in text.split():
                    yield chakra_pb2.ServerMessage(
                        text_chunk=chakra_pb2.TextChunk(text=word + " ")
                    )
                if session_id:
                    history = history + [message]
                    self._sessions[session_id] = history
                yield chakra_pb2.ServerMessage(
                    done=chakra_pb2.FinalResponse(
                        full_text=text,
                        prompt_tokens=1,
                        completion_tokens=len(text.split()),
                    )
                )
                return
            if which == "input":
                user_input = client_msg.input
                if pending_tool_prompt and user_input.prompt_id == pending_tool_prompt:
                    approved = user_input.reply.strip().lower() in {"y", "yes"}
                    yield chakra_pb2.ServerMessage(
                        tool_result=chakra_pb2.ToolCallResult(
                            tool_name="shell",
                            output="mock command executed" if approved else "mock command denied",
                            is_error=not approved,
                            tool_use_id="tool-1",
                        )
                    )
                    yield chakra_pb2.ServerMessage(
                        done=chakra_pb2.FinalResponse(
                            full_text="tool flow complete",
                            prompt_tokens=1,
                            completion_tokens=3,
                        )
                    )
                    return
                yield chakra_pb2.ServerMessage(text_chunk=chakra_pb2.TextChunk(text="(ack) "))
            if which == "cancel":
                if not context.is_active():
                    return
                return


def serve(host: str = "localhost", port: int = 50051) -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    chakra_pb2_grpc.add_AgentServiceServicer_to_server(MockAgentServicer(), server)
    bind = f"{host}:{port}"
    server.add_insecure_port(bind)
    server.start()
    logger.info("Mock Chakra gRPC server listening on %s", bind)
    return server


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    server = serve()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
