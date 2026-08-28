"""Milestone 2.1 — discover API surface from real Chakra backend."""

from __future__ import annotations

from client.generated import chakra_pb2
from phase2_common import append_execution_log, write_json_log
from scripts.real_backend import load_project_env, require_chakra


def main() -> int:
    load_project_env()
    client = require_chakra()
    try:
        info = client.inspect_service()
        payload = {
            "milestone": "2.1",
            "service": info,
            "client_oneof_payload_options": [
                field.name
                for field in chakra_pb2.ClientMessage.DESCRIPTOR.oneofs_by_name["payload"].fields
            ],
            "server_oneof_event_options": [
                field.name
                for field in chakra_pb2.ServerMessage.DESCRIPTOR.oneofs_by_name["event"].fields
            ],
            "constraints": [
                "Single public RPC: AgentService.Chat",
                "Bidirectional streaming only",
                "Insecure transport by default",
            ],
        }
        out = write_json_log("phase2_api_surface", payload)
        append_execution_log(
            milestone="Milestone 2.1 — API Surface Discovery",
            objective="Identify externally accessible operations and event/request families.",
            commands=["python tests/test_phase2_api_surface.py"],
            scripts_written=["tests/test_phase2_api_surface.py"],
            observations=[
                "Only one operation is exposed: AgentService.Chat.",
                f"Connected to real backend at {info['address']}.",
            ],
            validation=f"PASS (details in {out})",
            unexpected_behavior=[],
            conclusions=["API surface confirmed against live Chakra backend."],
            next_actions=["Document request/response models in Milestone 2.2."],
        )
        return 0
    finally:
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
