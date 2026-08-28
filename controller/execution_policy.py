"""Session execution policy mutated by recovery (deny subagents, lock workspace)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from controller.lifecycle import normalize_subagent_type


@dataclass
class ExecutionPolicy:
    """Mutable session policy applied during tool approval after safety checks."""

    deny_subagent_types: set[str] = field(default_factory=set)
    lock_workspace: bool = False
    # Cleared after one successful in-repo tool while locked (optional soft unlock).
    require_in_repo_until_success: bool = False

    def deny_subagents(self, *types: str) -> None:
        for t in types:
            sub = normalize_subagent_type(t)
            if sub:
                self.deny_subagent_types.add(sub)

    def clear_subagent_denials(self, *types: str) -> None:
        for t in types:
            sub = normalize_subagent_type(t)
            self.deny_subagent_types.discard(sub)

    def apply_lock_workspace(self) -> None:
        self.lock_workspace = True
        self.require_in_repo_until_success = True

    def note_successful_in_repo_tool(self) -> None:
        if self.require_in_repo_until_success:
            self.require_in_repo_until_success = False

    def is_subagent_denied(self, subagent_type: str | None) -> bool:
        return normalize_subagent_type(subagent_type) in self.deny_subagent_types

    def apply_recovery_effects(self, effects: Any) -> None:
        """Apply RecoveryEffects from select_recovery."""
        if effects is None:
            return
        for sub in getattr(effects, "deny_subagent_types", ()) or ():
            self.deny_subagents(sub)
        if getattr(effects, "lock_workspace", False):
            self.apply_lock_workspace()

    def snapshot(self) -> dict[str, Any]:
        return {
            "deny_subagent_types": sorted(self.deny_subagent_types),
            "lock_workspace": self.lock_workspace,
            "require_in_repo_until_success": self.require_in_repo_until_success,
        }


@dataclass(frozen=True)
class PolicyGateResult:
    deny: bool
    response: str
    reasoning: str


def evaluate_execution_policy(
    *,
    tool_name: str,
    arguments: dict[str, Any] | None,
    policy: ExecutionPolicy | None,
) -> PolicyGateResult | None:
    """Deny Agent spawns blocked by recovery ExecutionPolicy."""
    if policy is None:
        return None
    if (tool_name or "").strip() != "Agent":
        return None
    args = dict(arguments or {})
    sub = normalize_subagent_type(
        str(
            args.get("subagent_type")
            or args.get("agentType")
            or args.get("agent_type")
            or ""
        )
    )
    if not sub or not policy.is_subagent_denied(sub):
        return None
    return PolicyGateResult(
        deny=True,
        response="no",
        reasoning=(
            f"deny Agent {sub}: blocked by recovery execution policy — "
            "advance Plan/implement instead"
        ),
    )
