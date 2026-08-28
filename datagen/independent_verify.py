"""independent_verify.py — re-check a claimed PASS instead of trusting it.

verification/prompts.py's unified objective requires the verification
subagent to "record **Command run** lines + exit codes." This module pulls
those lines back out of the trace and actually re-executes them itself, in a
subprocess it controls, inside the generated repo — the closest thing to an
oracle achievable without a container runtime.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPORTS_ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "verification_reports"

_COMMAND_RE = re.compile(
    r"\*{0,2}Command run\*{0,2}\s*:?\s*`?([^\n`]+?)`?\s*(?:\(exit[^)]*\))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_MAX_COMMANDS = 3


@dataclass
class IndependentVerifyResult:
    passed: bool
    mode: str  # "reproduced_claimed_commands" | "generic_fallback" | "no_commands_found"
    commands: list[str] = field(default_factory=list)
    exit_codes: list[int] = field(default_factory=list)
    output_excerpt: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "mode": self.mode,
            "commands": self.commands,
            "exit_codes": self.exit_codes,
            "output_excerpt": self.output_excerpt,
        }


def _iter_verification_texts(trace_path: Path):
    """Yield output text of trace records that look like the verification
    subagent's own report (contains its VERDICT line)."""
    if not trace_path.is_file():
        return
    with trace_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = record.get("output") or record.get("text") or ""
            if isinstance(text, str) and "VERDICT:" in text:
                yield text


def extract_commands_from_trace(trace_path: Path) -> list[str]:
    """Pull up to _MAX_COMMANDS "Command run" lines out of the verification
    subagent's own reported output in the trace."""
    commands: list[str] = []
    for text in _iter_verification_texts(trace_path):
        for match in _COMMAND_RE.finditer(text):
            cmd = match.group(1).strip()
            if cmd and cmd not in commands:
                commands.append(cmd)
            if len(commands) >= _MAX_COMMANDS:
                return commands
    return commands


def verify(
    repo_dir: Path, trace_path: Path, *, timeout_seconds: int = 120
) -> IndependentVerifyResult:
    """Re-run the commands the verification subagent claimed it ran, for
    real, in `repo_dir`. `passed` requires every re-run command to exit 0."""
    commands = extract_commands_from_trace(trace_path)
    if not commands:
        return IndependentVerifyResult(passed=False, mode="no_commands_found")

    exit_codes: list[int] = []
    outputs: list[str] = []
    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=repo_dir,
                timeout=timeout_seconds,
                capture_output=True,
                text=True,
            )
            exit_codes.append(proc.returncode)
            outputs.append(f"$ {cmd}\n{proc.stdout[-1000:]}\n{proc.stderr[-1000:]}")
        except subprocess.TimeoutExpired:
            exit_codes.append(-1)
            outputs.append(f"$ {cmd}\n[timed out after {timeout_seconds}s]")
        except OSError as exc:
            exit_codes.append(-1)
            outputs.append(f"$ {cmd}\n[failed to launch: {exc}]")

    return IndependentVerifyResult(
        passed=all(code == 0 for code in exit_codes),
        mode="reproduced_claimed_commands",
        commands=commands,
        exit_codes=exit_codes,
        output_excerpt="\n\n".join(outputs)[-4000:],
    )


def save_report(result: IndependentVerifyResult, *, run_id: str) -> Path:
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    path = REPORTS_ROOT / f"{run_id}.json"
    payload = result.to_dict()
    payload["run_id"] = run_id
    payload["recorded_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
