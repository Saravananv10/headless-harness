"""Controller action model and parsing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from controller.exceptions import InvalidActionError


class ActionType(str, Enum):
    """Actions the controller can instruct the execution engine to perform."""

    SEND_MESSAGE = "send_message"
    COMPLETE = "complete"


@dataclass(frozen=True)
class ControllerAction:
    """Validated controller decision."""

    action: ActionType
    reasoning: str = ""
    message: str | None = None
    summary: str | None = None

    def validate(self) -> None:
        if self.action == ActionType.SEND_MESSAGE:
            if not self.message or not self.message.strip():
                raise InvalidActionError("send_message requires a non-empty message")
        elif self.action == ActionType.COMPLETE:
            if not self.summary or not self.summary.strip():
                raise InvalidActionError("complete requires a non-empty summary")


@dataclass(frozen=True)
class InterventionDecision:
    """Response to a harness intervention prompt."""

    response: str
    reasoning: str = ""


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)
    match = _JSON_BLOCK_RE.search(text)
    if match:
        return json.loads(match.group(1))
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        return json.loads(stripped[start : end + 1])
    raise InvalidActionError("No JSON object found in controller response")


def parse_controller_action(raw: str) -> ControllerAction:
    """Parse and validate a controller LLM response into an executable action."""
    try:
        data = _extract_json_object(raw)
    except json.JSONDecodeError as exc:
        raise InvalidActionError(f"Invalid JSON: {exc}") from exc

    action_raw = str(data.get("action", "")).strip().lower()
    try:
        action_type = ActionType(action_raw)
    except ValueError as exc:
        raise InvalidActionError(f"Unknown action: {action_raw!r}") from exc

    action = ControllerAction(
        action=action_type,
        reasoning=str(data.get("reasoning", "")).strip(),
        message=str(data.get("message", "")).strip() or None,
        summary=str(data.get("summary", "")).strip() or None,
    )
    action.validate()
    return action


def parse_intervention_decision(raw: str) -> InterventionDecision:
    """Parse intervention response from controller LLM output."""
    try:
        data = _extract_json_object(raw)
    except json.JSONDecodeError:
        reply = raw.strip()
        if not reply:
            raise InvalidActionError("Empty intervention response")
        return InterventionDecision(response=reply)

    response = str(data.get("response", data.get("message", ""))).strip()
    if not response:
        raise InvalidActionError("Intervention response must include 'response'")
    return InterventionDecision(
        response=response,
        reasoning=str(data.get("reasoning", "")).strip(),
    )


def action_to_dict(action: ControllerAction) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "action": action.action.value,
        "reasoning": action.reasoning,
    }
    if action.message is not None:
        payload["message"] = action.message
    if action.summary is not None:
        payload["summary"] = action.summary
    return payload
