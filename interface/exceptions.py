"""Harness contract exceptions."""


class HarnessError(Exception):
    """Base exception for harness contract errors."""


class HarnessConnectionError(HarnessError):
    """Raised when connection to a backend fails."""


class HarnessNotConnectedError(HarnessError):
    """Raised when an operation requires an active connection."""


class HarnessSessionError(HarnessError):
    """Raised for invalid or closed session operations."""


class HarnessTurnError(HarnessError):
    """Raised when a turn fails or is interrupted."""


class HarnessUnsupportedError(HarnessError):
    """Raised when the harness does not support a requested capability."""
