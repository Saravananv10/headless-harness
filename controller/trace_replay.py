"""Replay helpers — reconstruct a conversation timeline from Phase 5 traces."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ReplayTurn:
    turn_id: str | None = None
    user_message: str = ""
    assistant_text: str = ""
    tool_requests: list[dict[str, Any]] = field(default_factory=list)
    tool_responses: list[dict[str, Any]] = field(default_factory=list)
    agent_events: list[dict[str, Any]] = field(default_factory=list)
    verification_results: list[dict[str, Any]] = field(default_factory=list)
    completion_markers: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ConversationReplay:
    """Reconstructed conversation from ordered trace records."""

    run_id: str | None
    timeline: list[dict[str, Any]]
    turns: list[ReplayTurn]
    completion_markers: list[dict[str, Any]]
    assistant_messages: list[str]
    tool_pairs: list[dict[str, Any]]
    raw_event_count: int
    normalized_event_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "raw_event_count": self.raw_event_count,
            "normalized_event_count": self.normalized_event_count,
            "assistant_messages": list(self.assistant_messages),
            "completion_markers": list(self.completion_markers),
            "tool_pairs": list(self.tool_pairs),
            "turns": [
                {
                    "turn_id": t.turn_id,
                    "user_message": t.user_message,
                    "assistant_text": t.assistant_text,
                    "tool_requests": t.tool_requests,
                    "tool_responses": t.tool_responses,
                    "agent_events": t.agent_events,
                    "verification_results": t.verification_results,
                    "completion_markers": t.completion_markers,
                    "errors": t.errors,
                }
                for t in self.turns
            ],
            "timeline": list(self.timeline),
        }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def load_trace_bundle(
    directory: Path | str,
    *,
    normalized_name: str = "trace.jsonl",
    raw_name: str = "raw_events.jsonl",
) -> dict[str, Any]:
    """Load normalized + raw JSONL from a trace directory."""
    root = Path(directory)
    normalized = _read_jsonl(root / normalized_name)
    raw = _read_jsonl(root / raw_name)
    return {
        "directory": str(root),
        "normalized": normalized,
        "raw": raw,
    }


def merge_timeline(
    normalized: list[dict[str, Any]],
    raw: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge raw + normalized records by seq (stable, exact order)."""
    combined = [dict(r, _channel=r.get("channel", "normalized")) for r in normalized]
    combined.extend(dict(r, _channel=r.get("channel", "raw")) for r in raw)
    combined.sort(key=lambda r: (int(r.get("seq") or 0), 0 if r.get("_channel") == "raw" else 1))
    return combined


def reconstruct_conversation(
    directory: Path | str | None = None,
    *,
    bundle: dict[str, Any] | None = None,
) -> ConversationReplay:
    """
    Rebuild a conversation timeline from Phase 5 traces.

    Prefer `directory` (trace folder containing trace.jsonl + raw_events.jsonl).
    """
    if bundle is None:
        if directory is None:
            raise ValueError("directory or bundle is required")
        bundle = load_trace_bundle(directory)

    normalized = list(bundle.get("normalized") or [])
    raw = list(bundle.get("raw") or [])
    timeline = merge_timeline(normalized, raw)

    run_id = None
    for record in normalized + raw:
        if record.get("run_id"):
            run_id = record["run_id"]
            break

    turns: list[ReplayTurn] = []
    current: ReplayTurn | None = None
    completion_markers: list[dict[str, Any]] = []
    assistant_messages: list[str] = []
    open_tools: dict[str, dict[str, Any]] = {}
    tool_pairs: list[dict[str, Any]] = []

    def ensure_turn(turn_id: str | None = None) -> ReplayTurn:
        nonlocal current
        if current is None:
            current = ReplayTurn(turn_id=turn_id)
            turns.append(current)
        elif turn_id and current.turn_id is None:
            current.turn_id = turn_id
        return current

    for record in normalized:
        rtype = record.get("type")
        turn_id = record.get("turn_id")

        if rtype == "backend_turn_start":
            current = ReplayTurn(
                turn_id=turn_id,
                user_message=str(record.get("message") or ""),
            )
            turns.append(current)
            continue

        if rtype == "assistant_text_delta":
            turn = ensure_turn(turn_id)
            turn.assistant_text += str(record.get("text") or "")
            continue

        if rtype == "assistant_message":
            turn = ensure_turn(turn_id)
            text = str(record.get("text") or "")
            turn.assistant_text = text or turn.assistant_text
            if text:
                assistant_messages.append(text)
            continue

        if rtype in ("tool_request", "agent_spawn"):
            turn = ensure_turn(turn_id)
            entry = {
                "tool_name": record.get("tool_name"),
                "arguments": record.get("arguments") or {},
                "invocation_id": record.get("invocation_id"),
                "normalized_type": rtype,
            }
            if rtype == "agent_spawn":
                turn.agent_events.append(entry)
            else:
                turn.tool_requests.append(entry)
            inv = str(record.get("invocation_id") or "")
            if inv:
                open_tools[inv] = entry
            continue

        if rtype in ("tool_response", "agent_completed"):
            turn = ensure_turn(turn_id)
            entry = {
                "tool_name": record.get("tool_name"),
                "output": record.get("output"),
                "is_error": record.get("is_error"),
                "invocation_id": record.get("invocation_id"),
                "normalized_type": rtype,
            }
            if rtype == "agent_completed":
                turn.agent_events.append(entry)
            else:
                turn.tool_responses.append(entry)
            inv = str(record.get("invocation_id") or "")
            request = open_tools.pop(inv, None)
            tool_pairs.append({"request": request, "response": entry})
            continue

        if rtype == "verification_result":
            turn = ensure_turn(turn_id)
            turn.verification_results.append(
                {
                    "verdict": record.get("verdict"),
                    "source_tool": record.get("source_tool"),
                    "invocation_id": record.get("invocation_id"),
                }
            )
            continue

        if rtype == "completion_marker":
            marker = {
                "source": record.get("source"),
                "mode": record.get("mode"),
                "excerpt": record.get("excerpt"),
                "turn_id": turn_id,
            }
            completion_markers.append(marker)
            ensure_turn(turn_id).completion_markers.append(marker)
            continue

        if rtype == "error":
            ensure_turn(turn_id).errors.append(
                {"message": record.get("message"), "code": record.get("code")}
            )
            continue

    return ConversationReplay(
        run_id=run_id,
        timeline=timeline,
        turns=turns,
        completion_markers=completion_markers,
        assistant_messages=assistant_messages,
        tool_pairs=tool_pairs,
        raw_event_count=len(raw),
        normalized_event_count=len(normalized),
    )
