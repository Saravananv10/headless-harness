"""Deterministic completion detection from explicit conversation markers (Phase 6).

Rules:
- Completion is never guessed from inactivity, silence, or missing tool calls.
- Only explicit terminal markers count.
- Markers are only accepted from terminal conversation events
  (``tool_completed``, ``turn_completed``), never from mid-stream text deltas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from verification.parser import Verdict, parse_verdict

IMPLEMENTATION_COMPLETE_MARKER = "IMPLEMENTATION_STATUS: COMPLETE"
REPAIR_COMPLETE_MARKER = "REPAIR_STATUS: COMPLETE"
VERDICT_PASS_MARKER = "VERDICT: PASS"

_IMPLEMENTATION_COMPLETE_RE = re.compile(
    r"IMPLEMENTATION_STATUS:\s*COMPLETE",
    re.IGNORECASE,
)
_REPAIR_COMPLETE_RE = re.compile(
    r"REPAIR_STATUS:\s*COMPLETE",
    re.IGNORECASE,
)


class TerminalMarker(str, Enum):
    """Explicit terminal markers defined by the orchestration contract."""

    IMPLEMENTATION_COMPLETE = "implementation_status_complete"
    VERDICT_PASS = "verdict_pass"
    REPAIR_COMPLETE = "repair_status_complete"


class TerminalEventKind(str, Enum):
    """Event kinds that may carry a terminal completion marker."""

    TOOL_COMPLETED = "tool_completed"
    TURN_COMPLETED = "turn_completed"


# Mid-stream text_delta is intentionally excluded — not a terminal event.
_ALLOWED_EVENT_KINDS = frozenset(TerminalEventKind)


class CompletionMode(str, Enum):
    """Which explicit marker ends the conversation for this run."""

    VERDICT_PASS = "verdict_pass"
    IMPLEMENTATION_COMPLETE = "implementation_complete"
    REPAIR_COMPLETE = "repair_complete"


_MODE_REQUIRED_MARKER: dict[CompletionMode, TerminalMarker] = {
    CompletionMode.VERDICT_PASS: TerminalMarker.VERDICT_PASS,
    CompletionMode.IMPLEMENTATION_COMPLETE: TerminalMarker.IMPLEMENTATION_COMPLETE,
    CompletionMode.REPAIR_COMPLETE: TerminalMarker.REPAIR_COMPLETE,
}


def find_markers(text: str) -> list[TerminalMarker]:
    """Return every explicit terminal marker present in text (deterministic scan)."""
    if not text or not text.strip():
        return []
    found: list[TerminalMarker] = []
    if parse_verdict(text) == Verdict.PASS:
        found.append(TerminalMarker.VERDICT_PASS)
    if _IMPLEMENTATION_COMPLETE_RE.search(text):
        found.append(TerminalMarker.IMPLEMENTATION_COMPLETE)
    if _REPAIR_COMPLETE_RE.search(text):
        found.append(TerminalMarker.REPAIR_COMPLETE)
    return found


def text_has_completion(text: str, mode: CompletionMode) -> bool:
    """True when the mode's required explicit marker is present in text."""
    required = _MODE_REQUIRED_MARKER[mode]
    return required in find_markers(text)


@dataclass(frozen=True)
class CompletionHit:
    """A confirmed terminal completion from an explicit marker + terminal event."""

    marker: TerminalMarker
    mode: CompletionMode
    event_kind: TerminalEventKind
    source: str
    excerpt: str

    def to_dict(self) -> dict[str, str]:
        return {
            "marker": self.marker.value,
            "mode": self.mode.value,
            "event_kind": self.event_kind.value,
            "source": self.source,
            "excerpt": self.excerpt,
        }


class CompletionDetector:
    """
    Stateless detector: explicit marker ∩ allowed terminal event ⇒ complete.

    Does not consult inactivity, tool counts, turn counts, or stage heuristics.
    """

    def __init__(self, mode: CompletionMode = CompletionMode.VERDICT_PASS) -> None:
        self.mode = mode
        self.required_marker = _MODE_REQUIRED_MARKER[mode]

    def inspect(
        self,
        text: str,
        *,
        event_kind: TerminalEventKind | str,
        source: str,
    ) -> CompletionHit | None:
        """
        Inspect text from a conversation event.

        Returns a CompletionHit only when:
        1. ``event_kind`` is a terminal event kind, and
        2. the mode's required explicit marker is present in ``text``.
        """
        kind: TerminalEventKind
        if isinstance(event_kind, TerminalEventKind):
            kind = event_kind
        else:
            try:
                kind = TerminalEventKind(str(event_kind))
            except ValueError:
                # Non-terminal / unknown event kinds never complete (Phase 6).
                return None
        if kind not in _ALLOWED_EVENT_KINDS:
            return None
        if not text or not text.strip():
            return None
        markers = find_markers(text)
        if self.required_marker not in markers:
            return None
        return CompletionHit(
            marker=self.required_marker,
            mode=self.mode,
            event_kind=kind,
            source=source,
            excerpt=text.strip()[-500:],
        )

    def is_terminal_event_kind(self, event_kind: str) -> bool:
        try:
            return TerminalEventKind(event_kind) in _ALLOWED_EVENT_KINDS
        except ValueError:
            return False
