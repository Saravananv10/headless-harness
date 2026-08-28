"""Controller decision policies — generation, validation, and retries."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from controller.decision import (
    ControllerAction,
    InterventionDecision,
    action_to_dict,
    parse_controller_action,
    parse_intervention_decision,
)
from controller.exceptions import InvalidActionError
from controller.intervention_guard import evaluate_intervention_guard
from controller.llm import LLMClient
from controller.prompt_builder import build_decision_messages, build_intervention_messages
from controller.trace import ConversationTrace

logger = logging.getLogger(__name__)


@dataclass
class DecisionPolicy:
    """Generate and validate controller actions with retry on invalid output."""

    llm: LLMClient
    max_retries: int = 2
    temperature: float = 0.2
    trace: ConversationTrace | None = None

    def decide(self, context) -> ControllerAction:
        messages = build_decision_messages(context)
        last_error: InvalidActionError | None = None
        for attempt in range(self.max_retries + 1):
            if self.trace:
                self.trace.log_controller_llm_request(
                    purpose="decision",
                    messages=messages,
                    temperature=self.temperature,
                    attempt=attempt + 1,
                )
            raw = self.llm.complete(messages, temperature=self.temperature)
            if self.trace:
                self.trace.log_controller_llm_response(
                    purpose="decision",
                    raw=raw,
                    attempt=attempt + 1,
                )
            try:
                action = parse_controller_action(raw)
                if self.trace:
                    self.trace.log_controller_action(action_to_dict(action), purpose="decision")
                return action
            except InvalidActionError as exc:
                last_error = exc
                logger.warning("Invalid controller action (attempt %d): %s", attempt + 1, exc)
                messages = messages + [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": (
                            f"Your response was invalid: {exc}. "
                            "Respond again with valid JSON matching the required action schema."
                        ),
                    },
                ]
        raise last_error or InvalidActionError("Failed to produce a valid controller action")

    def decide_intervention(self, context: dict) -> InterventionDecision:
        guard_result = evaluate_intervention_guard(context)
        if guard_result is not None:
            decision = InterventionDecision(
                response=guard_result.response,
                reasoning=guard_result.reasoning,
            )
            if self.trace:
                self.trace.log(
                    "intervention_guard",
                    response=guard_result.response,
                    reasoning=guard_result.reasoning,
                    is_echo_bash=guard_result.is_echo_bash,
                )
                self.trace.log_controller_action(
                    {
                        "response": decision.response,
                        "reasoning": decision.reasoning,
                        "source": "guard",
                    },
                    purpose="intervention",
                )
            logger.info(
                "Intervention guard: %s — %s",
                decision.response,
                decision.reasoning,
            )
            return decision

        messages = build_intervention_messages(context)
        last_error: InvalidActionError | None = None
        for attempt in range(self.max_retries + 1):
            if self.trace:
                self.trace.log_controller_llm_request(
                    purpose="intervention",
                    messages=messages,
                    temperature=0.0,
                    attempt=attempt + 1,
                )
            raw = self.llm.complete(messages, temperature=0.0)
            if self.trace:
                self.trace.log_controller_llm_response(
                    purpose="intervention",
                    raw=raw,
                    attempt=attempt + 1,
                )
            try:
                decision = parse_intervention_decision(raw)
                if self.trace:
                    self.trace.log_controller_action(
                        {
                            "response": decision.response,
                            "reasoning": decision.reasoning,
                            "source": "llm",
                        },
                        purpose="intervention",
                    )
                return decision
            except InvalidActionError as exc:
                last_error = exc
                logger.warning("Invalid intervention decision (attempt %d): %s", attempt + 1, exc)
                messages = messages + [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": (
                            f"Invalid intervention response: {exc}. "
                            'Return JSON with a non-empty "response" field.'
                        ),
                    },
                ]
        raise last_error or InvalidActionError("Failed to produce a valid intervention decision")
