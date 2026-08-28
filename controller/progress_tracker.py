"""Live forward-progress tracker — workflow milestones only reset stalls.

Activity (Reads, Edits, Bash, agent churn) is counted for metrics/budgets but
does NOT reset the stall counter. Only phase transitions and completed
milestones count as workflow progress.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_STALL_CYCLES = 5

# Chakra's literal message when a subagent spawn completes without doing
# anything (0 tokens, 0 tool_uses) — a backend glitch, not real work.
_EMPTY_AGENT_RESULT_MARKER = "returned no output"

# Workflow progress kinds that reset the stall counter.
WORKFLOW_PROGRESS_KINDS = frozenset(
    {
        "phase_transition",
        "milestone_plan",
        "milestone_implementation",
        "milestone_env",
        "milestone_repair",
        "milestone_verify",
    }
)


def _norm_subagent(raw: Any) -> str:
    return str(raw or "").strip().lower().replace("_", "-")


@dataclass
class ProgressTracker:
    """Session-scoped tracker for controller resume decisions."""

    stall_cycles: int = DEFAULT_STALL_CYCLES
    seen_reads: set[str] = field(default_factory=set)
    seen_subagents: set[str] = field(default_factory=set)
    progress_event_count: int = 0
    last_progress_kind: str | None = None
    pending_progress_since_resume: bool = False
    consecutive_resumes_without_progress: int = 0
    max_consecutive_without_progress: int = 0
    useful_tool_calls: int = 0
    activity_event_count: int = 0
    # Explore / activity helpers
    explore_agent_completed: bool = False
    unique_in_repo_reads: int = 0
    # Backend-glitch detection: Chakra sometimes completes an Agent spawn
    # with zero output/tool_uses (nothing actually ran). Blindly re-spawning
    # into the same void wastes cycles — track it so recovery can react
    # specifically instead of falling through to the generic stall path.
    consecutive_empty_agent_results: int = 0
    max_consecutive_empty_agent_results: int = 0
    # Set True after workflow progress this cycle (between resumes)
    _cycle_had_progress: bool = False
    _last_phase: str | None = None
    _seen_milestones: set[str] = field(default_factory=set)

    def _record_workflow(self, kind: str, *, detail: str = "") -> None:
        if kind not in WORKFLOW_PROGRESS_KINDS:
            return
        self.progress_event_count += 1
        self.last_progress_kind = kind
        self.pending_progress_since_resume = True
        self._cycle_had_progress = True
        del detail

    def _record_activity(self, kind: str) -> None:
        self.activity_event_count += 1
        del kind

    def note_workflow(self, kind: str, *, detail: str = "") -> None:
        """Record a workflow milestone / phase transition (resets stall)."""
        self._record_workflow(kind, detail=detail)

    def note_phase(self, phase: str | None) -> None:
        """Record phase_transition when inferred phase changes."""
        p = (phase or "").strip()
        if not p:
            return
        if self._last_phase is None:
            self._last_phase = p
            return
        if p != self._last_phase:
            prev = self._last_phase
            self._last_phase = p
            self._record_workflow("phase_transition", detail=f"{prev}->{p}")

    def note_milestone(self, name: str) -> None:
        """Record a one-shot milestone the first time it is observed."""
        key = (name or "").strip()
        if not key or key in self._seen_milestones:
            return
        self._seen_milestones.add(key)
        kind_map = {
            "plan": "milestone_plan",
            "implementation": "milestone_implementation",
            "env": "milestone_env",
            "repair": "milestone_repair",
            "verify": "milestone_verify",
        }
        kind = kind_map.get(key)
        if kind:
            self._record_workflow(kind, detail=key)

    def sync_lifecycle_milestones(
        self,
        *,
        plan_done: bool = False,
        plan_agent_seen: bool = False,
        implementation_complete: bool = False,
        env_ready: bool = False,
        repair_complete_count: int = 0,
        authoritative_pass: bool = False,
        last_verdict: str | None = None,
        verification_agent_verdict_count: int = 0,
    ) -> None:
        """Derive workflow milestones from lifecycle flags (idempotent)."""
        if plan_done or plan_agent_seen:
            self.note_milestone("plan")
        if env_ready:
            self.note_milestone("env")
        if implementation_complete:
            self.note_milestone("implementation")
        if repair_complete_count > 0:
            self.note_milestone("repair")
        if authoritative_pass:
            self.note_milestone("verify")
        elif (
            verification_agent_verdict_count > 0
            and last_verdict
            and last_verdict.upper() in {"FAIL", "PARTIAL"}
        ):
            # Accepted verify failure that drives repair counts as workflow progress.
            self.note_milestone("verify")

    def note_agent_spawn(self, subagent_type: str | None) -> None:
        """Activity: track spawn types; does not reset stall."""
        sub = _norm_subagent(subagent_type)
        if not sub:
            return
        if sub not in self.seen_subagents:
            self.seen_subagents.add(sub)
            self._record_activity("new_agent_type")

    def note_agent_completed(self, *, subagent_type: str | None = None) -> None:
        """Activity: agent finished. Tracks Explore completion for exit criteria."""
        self._record_activity("agent_completed")
        sub = _norm_subagent(subagent_type)
        if sub == "explore":
            self.explore_agent_completed = True

    def note_read(self, path: str | None, *, in_repo: bool = True) -> None:
        """Activity: Read tool. Unique in-repo paths feed Explore exit criteria."""
        p = (path or "").strip()
        if not p:
            return
        self.useful_tool_calls += 1
        self._record_activity("file_read")
        if p not in self.seen_reads:
            self.seen_reads.add(p)
            if in_repo:
                self.unique_in_repo_reads += 1

    def note_edit(self, path: str | None = None) -> None:
        """Activity: Edit/Write — does not reset stall."""
        self.useful_tool_calls += 1
        self._record_activity("file_edit")
        del path

    def note_useful_tool(self, tool_name: str) -> None:
        name = (tool_name or "").strip()
        if name and name not in {"", "unknown"}:
            self.useful_tool_calls += 1
            self._record_activity("tool")

    def observe_tool_started(
        self, tool_name: str, arguments: dict[str, Any] | None
    ) -> None:
        args = arguments or {}
        name = tool_name or ""
        if name == "Agent":
            sub = (
                args.get("subagent_type")
                or args.get("agentType")
                or args.get("agent_type")
            )
            self.note_agent_spawn(str(sub) if sub else None)
            return
        if name == "Read":
            self.note_read(str(args.get("file_path") or args.get("path") or ""))
            return
        if name in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
            self.note_edit(str(args.get("file_path") or args.get("path") or ""))
            return
        if name:
            self.note_useful_tool(name)

    def observe_tool_completed(
        self,
        tool_name: str,
        *,
        is_error: bool = False,
        output: str = "",
        subagent_type: str | None = None,
    ) -> None:
        if tool_name == "Agent":
            self.note_agent_completed(subagent_type=subagent_type)
            if _EMPTY_AGENT_RESULT_MARKER in (output or "").lower():
                self.consecutive_empty_agent_results += 1
                self.max_consecutive_empty_agent_results = max(
                    self.max_consecutive_empty_agent_results,
                    self.consecutive_empty_agent_results,
                )
            else:
                self.consecutive_empty_agent_results = 0
            return
        del is_error, output

    def on_resume_cycle(self) -> int:
        """
        Call once per controller resume decision.

        Returns consecutive resumes without workflow progress *after* this cycle.
        """
        if self.pending_progress_since_resume or self._cycle_had_progress:
            self.consecutive_resumes_without_progress = 0
            self.pending_progress_since_resume = False
            self._cycle_had_progress = False
        else:
            self.consecutive_resumes_without_progress += 1
            self.max_consecutive_without_progress = max(
                self.max_consecutive_without_progress,
                self.consecutive_resumes_without_progress,
            )
        return self.consecutive_resumes_without_progress

    @property
    def is_stalled(self) -> bool:
        return self.consecutive_resumes_without_progress >= max(1, self.stall_cycles)

    def snapshot(self) -> dict[str, Any]:
        return {
            "stall_cycles": self.stall_cycles,
            "progress_event_count": self.progress_event_count,
            "activity_event_count": self.activity_event_count,
            "last_progress_kind": self.last_progress_kind,
            "consecutive_resumes_without_progress": self.consecutive_resumes_without_progress,
            "max_consecutive_without_progress": self.max_consecutive_without_progress,
            "useful_tool_calls": self.useful_tool_calls,
            "unique_in_repo_reads": self.unique_in_repo_reads,
            "explore_agent_completed": self.explore_agent_completed,
            "seen_subagents": sorted(self.seen_subagents),
            "is_stalled": self.is_stalled,
            "consecutive_empty_agent_results": self.consecutive_empty_agent_results,
            "max_consecutive_empty_agent_results": self.max_consecutive_empty_agent_results,
        }
