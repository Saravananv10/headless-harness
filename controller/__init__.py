"""Autonomous controller — decision-making layer (Phase 6)."""

from controller.context_builder import ControllerContext, build_context, build_intervention_context
from controller.controller import Controller, ControllerConfig, ControllerRunResult
from controller.decision import (
    ActionType,
    ControllerAction,
    InterventionDecision,
    action_to_dict,
    parse_controller_action,
    parse_intervention_decision,
)
from controller.exceptions import (
    ControllerError,
    ControllerRunError,
    InvalidActionError,
    LLMClientError,
)
from controller.llm import (
    CallableLLMClient,
    DeterministicLLMClient,
    LLMClient,
    OpenAICompatibleClient,
)
from controller.trace import ConversationTrace, DEFAULT_LOG_ROOT, new_run_id
from controller.trace_replay import (
    ConversationReplay,
    reconstruct_conversation,
    load_trace_bundle,
)
from controller.policies import DecisionPolicy
from controller.verification_workflow import (
    VERIFICATION_PHASE_MARKER,
    build_verification_message,
)
from controller.supervisor_policy import SupervisorPolicy
from controller.completion import (
    CompletionDetector,
    CompletionHit,
    CompletionMode,
    TerminalEventKind,
    TerminalMarker,
    text_has_completion,
)
from controller.conversation_config import ConversationConfig
from controller.conversation_runner import ConversationRunner, ConversationRunResult
from controller.orchestration_state import OrchestrationState
from controller.tool_approver import StatelessAutoApprover, ToolApproval
from controller.session_health import (
    HealthStage,
    HealthVerdict,
    SessionHealthMonitor,
    SessionHealthTerminated,
)
from controller.workflow_common import PLAN_FILENAME, plan_exists, plan_path
from controller.prompt_builder import (
    INTERVENTION_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    available_actions,
    build_decision_messages,
    build_intervention_messages,
)

__all__ = [
    "ActionType",
    "CallableLLMClient",
    "Controller",
    "ControllerAction",
    "ControllerConfig",
    "ControllerContext",
    "ControllerError",
    "ControllerRunError",
    "ControllerRunResult",
    "ConversationTrace",
    "ConversationReplay",
    "DEFAULT_LOG_ROOT",
    "DecisionPolicy",
    "CompletionMode",
    "CompletionDetector",
    "CompletionHit",
    "TerminalEventKind",
    "TerminalMarker",
    "ConversationConfig",
    "ConversationRunner",
    "ConversationRunResult",
    "OrchestrationState",
    "StatelessAutoApprover",
    "ToolApproval",
    "reconstruct_conversation",
    "load_trace_bundle",
    "text_has_completion",
    "HealthStage",
    "HealthVerdict",
    "SessionHealthMonitor",
    "SessionHealthTerminated",
    "SupervisorPolicy",
    "PLAN_FILENAME",
    "VERIFICATION_PHASE_MARKER",
    "DeterministicLLMClient",
    "INTERVENTION_SYSTEM_PROMPT",
    "InvalidActionError",
    "InterventionDecision",
    "LLMClient",
    "LLMClientError",
    "OpenAICompatibleClient",
    "SYSTEM_PROMPT",
    "action_to_dict",
    "available_actions",
    "build_context",
    "build_decision_messages",
    "build_intervention_context",
    "build_intervention_messages",
    "build_verification_message",
    "parse_controller_action",
    "parse_intervention_decision",
    "plan_exists",
    "plan_path",
    "new_run_id",
]
