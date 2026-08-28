"""Observe Chakra-owned verify/repair lifecycle events (Phase 7).

Python does not run generation, verification, or repair loops. It records
authoritative VERDICT lines from the verification Agent only, tracks
Plan / ENV / IMPLEMENTATION / REPAIR markers for telemetry and PASS safety,
and enforces the configured repair limit. Chakra decides when to spawn agents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from controller.workflow_common import plan_exists, repair_plan_exists
from verification.parser import (
    Verdict,
    evaluation_rejects_pass,
    is_verification_failure,
    parse_verdict,
)

_REPAIR_COMPLETE_RE = re.compile(
    r"REPAIR_STATUS:\s*COMPLETE",
    re.IGNORECASE,
)
_IMPLEMENTATION_COMPLETE_RE = re.compile(
    r"IMPLEMENTATION_STATUS:\s*COMPLETE",
    re.IGNORECASE,
)
_ENV_READY_RE = re.compile(
    r"ENV_STATUS:\s*READY",
    re.IGNORECASE,
)

_VERIFICATION_TYPES = frozenset({"verification", "verify"})
_PLAN_TYPES = frozenset({"plan"})
_GP_TYPES = frozenset({"general-purpose", "generalpurpose"})
_MAX_PENDING_AGENTS = 256


def normalize_subagent_type(raw: str | None) -> str:
    return (raw or "").strip().lower()


def is_verification_subagent(subagent_type: str | None) -> bool:
    return normalize_subagent_type(subagent_type) in _VERIFICATION_TYPES


def is_plan_subagent(subagent_type: str | None) -> bool:
    return normalize_subagent_type(subagent_type) in _PLAN_TYPES


def is_general_purpose_subagent(subagent_type: str | None) -> bool:
    return normalize_subagent_type(subagent_type) in _GP_TYPES


@dataclass
class LifecycleObserver:
    """
    Track verification outcomes and markers. Chakra owns phase activation.

    Authoritative verdicts come only from Agent completions whose spawn used
    ``subagent_type="verification"``. Main-assistant self-reported VERDICT
    lines are ignored for gating and completion.

    IMPLEMENTATION_STATUS / REPAIR_STATUS from general-purpose Agent completions
    update telemetry/gates; informal main prose is telemetry-only.
    """

    max_repair_iterations: int = 15
    repo_path: str = ""
    verdict_fail_count: int = 0
    verdict_pass_seen: bool = False
    repair_complete_count: int = 0
    last_verdict: str | None = None
    last_raw_verdict: str | None = None
    last_verifier_report: str = ""
    implementation_complete_seen: bool = False
    verification_agent_verdict_count: int = 0
    plan_agent_seen: bool = False
    env_ready_seen: bool = False
    implementation_gp_seen: bool = False
    repair_gp_seen_since_last_fail: bool = False
    repair_plan_seen_since_last_fail: bool = False
    last_pass_rejection: str | None = None
    rejected_pass_count: int = 0
    main_agent_write_count: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    # invocation_id → normalized subagent_type
    _agent_types: dict[str, str] = field(default_factory=dict)

    def register_agent_start(
        self, invocation_id: str, subagent_type: str | None
    ) -> None:
        inv = (invocation_id or "").strip()
        if not inv:
            return
        self._agent_types[inv] = normalize_subagent_type(subagent_type)
        if len(self._agent_types) > _MAX_PENDING_AGENTS:
            oldest = next(iter(self._agent_types))
            self._agent_types.pop(oldest, None)

    def agent_type(self, invocation_id: str) -> str | None:
        inv = (invocation_id or "").strip()
        if not inv:
            return None
        return self._agent_types.get(inv)

    def is_verification_invocation(self, invocation_id: str) -> bool:
        return is_verification_subagent(self.agent_type(invocation_id))

    def is_plan_invocation(self, invocation_id: str) -> bool:
        return is_plan_subagent(self.agent_type(invocation_id))

    def is_general_purpose_invocation(self, invocation_id: str) -> bool:
        return is_general_purpose_subagent(self.agent_type(invocation_id))

    @property
    def plan_done(self) -> bool:
        """True when plan.md exists (informational; does not drive resumes)."""
        repo = (self.repo_path or "").strip()
        if repo:
            return plan_exists(repo)
        return self.plan_agent_seen

    @property
    def repair_plan_done(self) -> bool:
        """True when repair_plan.md exists on disk or Plan mentioned it since last fail."""
        if self.repair_plan_seen_since_last_fail:
            return True
        repo = (self.repo_path or "").strip()
        if repo:
            return repair_plan_exists(repo)
        return False

    def _mark_plan_agent(self, source: str) -> None:
        if not self.plan_agent_seen:
            self.plan_agent_seen = True
            self.events.append({"kind": "plan_agent_complete", "source": source})

    def note_main_agent_write(self) -> None:
        """Telemetry: main session Write/Edit (does not set COMPLETE)."""
        self.main_agent_write_count += 1
        self.events.append(
            {
                "kind": "main_agent_write",
                "count": self.main_agent_write_count,
            }
        )

    def _record_pass_rejection(self, *, source: str, reason: str) -> None:
        self.verdict_fail_count += 1
        self.verdict_pass_seen = False
        self.last_verdict = Verdict.FAIL.value
        self.repair_gp_seen_since_last_fail = False
        self.repair_plan_seen_since_last_fail = False
        self.last_pass_rejection = reason
        self.rejected_pass_count += 1
        self.events.append(
            {
                "kind": "verdict_pass_rejected",
                "source": source,
                "reason": reason,
                "fail_count": self.verdict_fail_count,
                "rejected_pass_count": self.rejected_pass_count,
            }
        )

    def observe_text(
        self,
        text: str,
        *,
        source: str,
        authoritative: bool = False,
        invocation_id: str | None = None,
    ) -> Verdict | None:
        """
        Observe markers in streamed text.

        Plan agent completions (even empty) set plan_agent_seen for telemetry.
        """
        agent_kind = self.agent_type(invocation_id) if invocation_id else None
        from_gp = is_general_purpose_subagent(agent_kind)
        from_plan = is_plan_subagent(agent_kind)

        if from_plan:
            self._mark_plan_agent(source)

        if not text or not text.strip():
            return None

        if _ENV_READY_RE.search(text):
            if not self.env_ready_seen:
                self.env_ready_seen = True
                self.events.append({"kind": "env_ready", "source": source})

        if from_gp:
            if _IMPLEMENTATION_COMPLETE_RE.search(text):
                if not self.implementation_complete_seen:
                    self.implementation_complete_seen = True
                    self.implementation_gp_seen = True
                    self.events.append(
                        {"kind": "implementation_complete", "source": source}
                    )
                else:
                    self.implementation_gp_seen = True

            if _REPAIR_COMPLETE_RE.search(text):
                self.repair_complete_count += 1
                self.repair_gp_seen_since_last_fail = True
                self.events.append(
                    {
                        "kind": "repair_complete",
                        "source": source,
                        "repair_complete_count": self.repair_complete_count,
                    }
                )
        elif _IMPLEMENTATION_COMPLETE_RE.search(text) or _REPAIR_COMPLETE_RE.search(
            text
        ):
            if _IMPLEMENTATION_COMPLETE_RE.search(text):
                if not self.implementation_complete_seen:
                    self.implementation_complete_seen = True
                    self.events.append(
                        {"kind": "implementation_complete", "source": source}
                    )
            self.events.append(
                {
                    "kind": "informal_status_marker",
                    "source": source,
                    "has_implementation": bool(
                        _IMPLEMENTATION_COMPLETE_RE.search(text)
                    ),
                    "has_repair": bool(_REPAIR_COMPLETE_RE.search(text)),
                }
            )

        # Soft repair-plan telemetry: mention of repair_plan.md in Plan output.
        if from_plan and "repair_plan.md" in text.lower():
            self.repair_plan_seen_since_last_fail = True
            self.events.append({"kind": "repair_plan_mentioned", "source": source})

        if not authoritative:
            return None

        verdict = parse_verdict(text)
        if verdict is None:
            return None

        self.verification_agent_verdict_count += 1
        self.last_raw_verdict = verdict.value
        self.last_verifier_report = text.strip()

        # Soft readiness check: reject PASS only when repo looks empty of plan
        # and implementation markers — FAIL/PARTIAL always count.
        if (
            verdict == Verdict.PASS
            and not self.implementation_complete_seen
            and not self.plan_done
        ):
            self.events.append(
                {
                    "kind": "premature_verification_verdict",
                    "source": source,
                    "verdict": verdict.value,
                }
            )
            self._record_pass_rejection(
                source=source,
                reason="PASS before plan.md or IMPLEMENTATION_STATUS: COMPLETE",
            )
            return Verdict.FAIL

        if is_verification_failure(verdict):
            self.verdict_fail_count += 1
            self.verdict_pass_seen = False
            self.last_verdict = verdict.value
            self.repair_gp_seen_since_last_fail = False
            self.repair_plan_seen_since_last_fail = False
            self.last_pass_rejection = None
            self.events.append(
                {
                    "kind": "verdict_fail"
                    if verdict == Verdict.FAIL
                    else "verdict_partial",
                    "source": source,
                    "fail_count": self.verdict_fail_count,
                    "verdict": verdict.value,
                }
            )
        elif verdict == Verdict.PASS:
            reject_reason = evaluation_rejects_pass(text)
            if reject_reason:
                self._record_pass_rejection(source=source, reason=reject_reason)
                return Verdict.FAIL
            self.verdict_pass_seen = True
            self.last_verdict = Verdict.PASS.value
            self.last_pass_rejection = None
            self.events.append({"kind": "verdict_pass", "source": source})
        return verdict

    @property
    def phases_ready_for_verification(self) -> bool:
        """Telemetry: preferred readiness before verification (not a hard resume gate)."""
        return self.plan_done or (
            self.env_ready_seen
            and self.implementation_gp_seen
            and self.implementation_complete_seen
        )

    @property
    def authoritative_pass(self) -> bool:
        return self.last_verdict == Verdict.PASS.value and self.verdict_pass_seen

    @property
    def needs_plan_spawn(self) -> bool:
        """Telemetry only — Chakra decides when to spawn Plan."""
        return not self.plan_done

    @property
    def needs_env_or_implement_spawn(self) -> bool:
        """Telemetry only."""
        if not self.plan_done:
            return False
        return not (
            self.env_ready_seen
            and self.implementation_gp_seen
            and self.implementation_complete_seen
        )

    @property
    def needs_repair_and_reverify(self) -> bool:
        """Telemetry: last verdict needs repair work (Chakra-owned)."""
        if self.last_verdict is None:
            return False
        if self.authoritative_pass:
            return False
        try:
            failed = is_verification_failure(Verdict(self.last_verdict))
        except ValueError:
            failed = self.last_verdict == Verdict.FAIL.value
        if not failed and self.last_pass_rejection:
            failed = True
        if not failed:
            return False
        return not self.repair_gp_seen_since_last_fail

    @property
    def needs_verification_spawn(self) -> bool:
        """Telemetry only."""
        if self.authoritative_pass:
            return False
        if self.needs_repair_and_reverify:
            return False
        if (
            self.implementation_complete_seen
            and self.verification_agent_verdict_count == 0
        ):
            return True
        if (
            self.last_verdict is not None
            and self.last_verdict != Verdict.PASS.value
            and self.repair_gp_seen_since_last_fail
        ):
            return True
        return False

    @property
    def repair_iterations_exhausted(self) -> bool:
        limit = max(0, int(self.max_repair_iterations))
        if limit == 0:
            return False
        return self.verdict_fail_count >= limit and not self.authoritative_pass

    def snapshot(self) -> dict[str, Any]:
        return {
            "max_repair_iterations": self.max_repair_iterations,
            "repo_path": self.repo_path,
            "verdict_fail_count": self.verdict_fail_count,
            "verdict_pass_seen": self.verdict_pass_seen,
            "repair_complete_count": self.repair_complete_count,
            "last_verdict": self.last_verdict,
            "last_raw_verdict": self.last_raw_verdict,
            "implementation_complete_seen": self.implementation_complete_seen,
            "verification_agent_verdict_count": self.verification_agent_verdict_count,
            "plan_agent_seen": self.plan_agent_seen,
            "env_ready_seen": self.env_ready_seen,
            "implementation_gp_seen": self.implementation_gp_seen,
            "repair_gp_seen_since_last_fail": self.repair_gp_seen_since_last_fail,
            "repair_plan_seen_since_last_fail": self.repair_plan_seen_since_last_fail,
            "repair_plan_done": self.repair_plan_done,
            "plan_done": self.plan_done,
            "phases_ready_for_verification": self.phases_ready_for_verification,
            "last_pass_rejection": self.last_pass_rejection,
            "rejected_pass_count": self.rejected_pass_count,
            "main_agent_write_count": self.main_agent_write_count,
            "authoritative_pass": self.authoritative_pass,
            "needs_plan_spawn": self.needs_plan_spawn,
            "needs_env_or_implement_spawn": self.needs_env_or_implement_spawn,
            "needs_verification_spawn": self.needs_verification_spawn,
            "needs_repair_and_reverify": self.needs_repair_and_reverify,
            "repair_iterations_exhausted": self.repair_iterations_exhausted,
        }
