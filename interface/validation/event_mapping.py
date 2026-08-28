"""Documented mapping from Phase 2 observed backend events to harness events.

Adapters (Phase 4) implement this translation. The mapping lives outside the
core contract so higher layers never depend on backend event names.
"""

from __future__ import annotations

PHASE2_BACKEND_EVENT_TO_HARNESS_EVENT: dict[str, str] = {
    "text_chunk": "text_delta",
    "tool_start": "tool_started",
    "tool_result": "tool_completed",
    "action_required": "intervention_required",
    "done": "turn_completed",
    "error": "turn_failed",
}

PHASE2_BACKEND_REQUEST_TO_HARNESS_REQUEST: dict[str, str] = {
    "request": "send_message",
    "input": "intervention_response",
    "cancel": "interrupt",
}
