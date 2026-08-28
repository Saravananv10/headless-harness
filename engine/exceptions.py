"""Conversation engine exceptions."""


class ExecutionEngineError(Exception):
    """Base exception for execution engine errors."""


class ConversationNotFoundError(ExecutionEngineError):
    """Raised when a conversation id is unknown."""


class ConversationStateError(ExecutionEngineError):
    """Raised when a conversation is in an invalid state for the requested operation."""


class InterventionRequiredError(ExecutionEngineError):
    """Raised when an intervention handler is required but not provided."""

    def __init__(self, intervention_id: str, prompt: str) -> None:
        super().__init__(f"Intervention required: {prompt}")
        self.intervention_id = intervention_id
        self.prompt = prompt
