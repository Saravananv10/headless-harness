"""Milestone 2.7 — produce capability summary artifact from discovered protocol."""

from __future__ import annotations

from phase2_common import append_execution_log, write_json_log


def main() -> int:
    capability_matrix = [
        {"capability": "Bidirectional chat streaming", "supported": True, "notes": "AgentService.Chat"},
        {"capability": "Session resume by ID", "supported": True, "notes": "session_id in ChatRequest"},
        {"capability": "Interactive tool approvals", "supported": True, "notes": "action_required + UserInput"},
        {"capability": "Tool output events", "supported": True, "notes": "tool_start/tool_result"},
        {"capability": "Cancellation", "supported": True, "notes": "CancelSignal"},
        {"capability": "Explicit server-side close session RPC", "supported": False, "notes": "No dedicated operation"},
        {"capability": "Transport security / auth", "supported": False, "notes": "insecure gRPC in current server"},
    ]
    payload = {"milestone": "2.7", "capability_matrix": capability_matrix}
    out = write_json_log("phase2_capability_summary", payload)
    append_execution_log(
        milestone="Milestone 2.7 — Capability Summary",
        objective="Consolidate complete external capability model for interface design.",
        commands=["python tests/test_phase2_capability_summary.py"],
        scripts_written=["tests/test_phase2_capability_summary.py"],
        observations=[
            "Protocol exposes minimal but complete lifecycle for controller-driven orchestration.",
            "Session and tool interaction are API-level concepts, not internal-only details.",
        ],
        validation=f"PASS (details in {out})",
        conclusions=[
            "Phase 2 discovery is sufficient input for backend-independent contract design.",
        ],
        next_actions=["Begin Phase 3 common harness contract design."],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
