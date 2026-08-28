"""Thin supervisor policy — completion mode holder for ConversationRunner.

Phase 4: tool approval is handled by StatelessAutoApprover, not this policy.
decide() remains for legacy Controller callers and unit tests.
"""

from __future__ import annotations

from controller.completion import (
    IMPLEMENTATION_COMPLETE_MARKER,
    CompletionMode,
    text_has_completion,
)
from controller.context_builder import ControllerContext
from controller.decision import ActionType, ControllerAction
from controller.llm import LLMClient
from controller.policies import DecisionPolicy
from controller.trace import ConversationTrace
from controller.workflow_common import summarize_preserving_markers

CONTINUE_MESSAGE = (
    "Continue the repository generation workflow in this same conversation. "
    "Do not restart from scratch. Proceed with whatever remains "
    "(implementation, verification, repair, or re-verification) until the "
    "terminal completion marker is reached."
)

# Re-export for existing imports
__all__ = [
    "CONTINUE_MESSAGE",
    "CompletionMode",
    "IMPLEMENTATION_COMPLETE_MARKER",
    "SupervisorPolicy",
    "text_has_completion",
]


def _assistant_text(context: ControllerContext) -> str:
    return (context.last_assistant_message or "").strip()


def _history_has_user_message(context: ControllerContext) -> bool:
    return any(entry.get("role") == "user" for entry in context.history)


class SupervisorPolicy(DecisionPolicy):
    """
    Non-steering supervisor helpers for a single persistent Chakra conversation.

    ConversationRunner uses completion_mode + decide_intervention only.
    """

    def __init__(
        self,
        llm: LLMClient,
        *,
        bootstrap_message: str,
        completion_mode: CompletionMode = CompletionMode.VERDICT_PASS,
        max_retries: int = 2,
        temperature: float = 0.2,
        trace: ConversationTrace | None = None,
    ) -> None:
        super().__init__(llm, max_retries=max_retries, temperature=temperature, trace=trace)
        self.bootstrap_message = bootstrap_message.strip()
        self.completion_mode = completion_mode
        if not self.bootstrap_message:
            raise ValueError("bootstrap_message must be non-empty")

    def decide(self, context: ControllerContext) -> ControllerAction:
        if context.metadata.get("turn_limit_reached"):
            return self._complete_at_turn_limit(context)

        if not _history_has_user_message(context):
            return ControllerAction(
                action=ActionType.SEND_MESSAGE,
                reasoning="Start single persistent Chakra conversation with bootstrap objective.",
                message=self.bootstrap_message,
            )

        text = _assistant_text(context)
        if text_has_completion(text, self.completion_mode):
            marker = (
                "VERDICT: PASS"
                if self.completion_mode == CompletionMode.VERDICT_PASS
                else IMPLEMENTATION_COMPLETE_MARKER
            )
            return ControllerAction(
                action=ActionType.COMPLETE,
                reasoning=f"Terminal marker reached ({marker}).",
                summary=summarize_preserving_markers(text),
            )

        return ControllerAction(
            action=ActionType.SEND_MESSAGE,
            reasoning="Conversation ongoing; continue without stage steering.",
            message=CONTINUE_MESSAGE,
        )

    def _complete_at_turn_limit(self, context: ControllerContext) -> ControllerAction:
        text = _assistant_text(context)
        if text_has_completion(text, self.completion_mode):
            return ControllerAction(
                action=ActionType.COMPLETE,
                reasoning="Terminal marker present at turn limit.",
                summary=summarize_preserving_markers(text),
            )
        return ControllerAction(
            action=ActionType.COMPLETE,
            reasoning=f"Turn limit reached ({context.turn_count} turns) without terminal marker.",
            summary=summarize_preserving_markers(text)
            or f"Stopped at turn limit ({context.turn_count} turns) without terminal completion.",
        )
