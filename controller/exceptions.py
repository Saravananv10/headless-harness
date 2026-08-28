"""Controller exceptions."""


class ControllerError(Exception):
    """Base exception for controller errors."""


class InvalidActionError(ControllerError):
    """Raised when a controller response cannot be parsed or validated."""


class ControllerRunError(ControllerError):
    """Raised when an autonomous run cannot continue."""


class LLMClientError(ControllerError):
    """Raised when the controller LLM request fails."""


class TurnStallDetected(ControllerError):
    """Raised when a turn is cancelled due to intervention stall."""
