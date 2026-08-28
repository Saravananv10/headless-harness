"""Capability advertisement for harness implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class HarnessCapability(str, Enum):
    """Operations or features a harness may expose."""

    CONNECT = "connect"
    DISCONNECT = "disconnect"
    STREAMING = "streaming"
    SESSIONS = "sessions"
    SESSION_RESUME = "session_resume"
    TOOL_EXECUTION = "tool_execution"
    INTERACTIVE_APPROVAL = "interactive_approval"
    CANCELLATION = "cancellation"
    MODEL_OVERRIDE = "model_override"
    WORKING_DIRECTORY = "working_directory"


@dataclass(frozen=True)
class HarnessCapabilities:
    """Declared capabilities of a harness implementation."""

    supported: frozenset[HarnessCapability] = field(default_factory=frozenset)

    def supports(self, capability: HarnessCapability) -> bool:
        return capability in self.supported

    def require(self, capability: HarnessCapability) -> None:
        if not self.supports(capability):
            raise ValueError(f"Harness does not support capability: {capability.value}")
