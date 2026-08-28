"""Deterministic fast-path for harness intervention approvals (Phase 8)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from controller.workflow_common import validate_agent_spawn

# Tools auto-approved when confined to the repository.
_AUTO_APPROVE_TOOLS = frozenset(
    {
        "Read",
        "Glob",
        "Grep",
        "Write",
        "Edit",
        "MultiEdit",
        "LS",
        "Find",
        "Tree",
        "Ripgrep",
        "TodoWrite",
        "TodoRead",
        "Task",
        "WriteFile",
        "Create",
        "FileWrite",
    }
)

_DESTRUCTIVE_BASH_PATTERNS = (
    re.compile(r"\bsudo\b", re.I),
    re.compile(r"rm\s+-rf\s+[/~]"),
    re.compile(r"rm\s+-rf\s+\S*\s+[/~]"),
    re.compile(r">\s*/dev/(?!null|stdout|stderr|zero)"),
    re.compile(r"\.ssh"),
    re.compile(r"\.aws/credentials"),
)

_AMBIGUOUS_BASH_PATTERNS = (
    re.compile(r"\bcurl\b", re.I),
    re.compile(r"\bwget\b", re.I),
    re.compile(r"\bdocker\b", re.I),
    re.compile(r"\bgit\s+push\b", re.I),
    re.compile(r"\bnc\s", re.I),
    re.compile(r"\bssh\b", re.I),
)

_SAFE_BASH_PREFIXES = (
    "ls",
    "find",
    "tree",
    "cat",
    "head",
    "tail",
    "pwd",
    "mkdir",
    "touch",
    "cp",
    "mv",
    "chmod",
    "pip install",
    "pip3 install",
    "python ",
    "python3 ",
    "pytest",
    "flask ",
    "npm install",
    "npm run",
    "node ",
    "grep ",
    "rg ",
    "sed -i",
    "source ",
    ". ",
    "test ",
    "[ ",
    "wc ",
    "sort ",
    "uniq ",
    "diff ",
    "which ",
    "env ",
    "export ",
    "cd ",
    "echo ",
    "echo",
)


@dataclass(frozen=True)
class InterventionGuardResult:
    """Resolved intervention without LLM."""

    response: str
    reasoning: str
    is_echo_bash: bool = False


@dataclass
class StallTracker:
    """Per-turn counters for intervention stall detection."""

    echo_bash_denials: int = 0
    intervention_count: int = 0
    saw_write_or_edit: bool = False

    echo_denial_threshold: int = 3
    intervention_without_write_threshold: int = 50

    def reset(self) -> None:
        self.echo_bash_denials = 0
        self.intervention_count = 0
        self.saw_write_or_edit = False

    def record(
        self,
        *,
        tool_name: str,
        response: str,
        is_echo_bash: bool,
    ) -> None:
        self.intervention_count += 1
        if tool_name in ("Write", "Edit", "MultiEdit", "TodoWrite", "WriteFile", "Create", "FileWrite"):
            self.saw_write_or_edit = True
        if response.lower().startswith("no") and is_echo_bash:
            self.echo_bash_denials += 1

    def should_cancel_turn(self) -> bool:
        if self.echo_bash_denials >= self.echo_denial_threshold:
            return True
        if (
            self.intervention_count >= self.intervention_without_write_threshold
            and not self.saw_write_or_edit
        ):
            return True
        return False


def extract_pending_tool(recent_events: list[dict[str, Any]]) -> tuple[str, dict[str, Any]] | None:
    """Return the tool_started event that triggered the current intervention."""
    for event in reversed(recent_events):
        event_type = event.get("event_type")
        if event_type == "intervention_required":
            continue
        if event_type == "tool_started":
            payload = event.get("payload") or {}
            return str(payload.get("tool_name") or ""), dict(payload.get("arguments") or {})
        break
    return None


def normalize_bash_command(command: str) -> str:
    return " ".join(command.strip().split())


def is_echo_only_bash(command: str) -> bool:
    """True when Bash only prints messages (no file/test side effects)."""
    normalized = command.strip()
    if not normalized:
        return False

    remainder = normalized
    while True:
        match = re.match(r"^cd\s+[^\s;&|]+(?:\s*&&\s*)", remainder, re.I)
        if not match:
            break
        remainder = remainder[match.end() :].strip()

    if not re.match(r"^(echo|printf)\b", remainder, re.I):
        return False

    # Disallow pipes or chained commands beyond echo/printf.
    if re.search(r"[|;&](?!\s*$)", remainder):
        return False
    return True


def _repo_root(context: dict[str, Any]) -> Path | None:
    working_directory = context.get("working_directory")
    if not working_directory:
        return None
    return Path(working_directory).resolve()


_ALLOWED_SYSTEM_PATHS = {
    Path("/dev/null"),
    Path("/dev/stdout"),
    Path("/dev/stderr"),
    Path("/dev/zero"),
}


def _path_within_repo(path_str: str, repo: Path) -> bool:
    if not path_str:
        return True
    try:
        candidate = Path(path_str).expanduser()
        if candidate in _ALLOWED_SYSTEM_PATHS:
            return True
        cand_str = str(candidate)
        if cand_str.startswith(("/usr/", "/bin/", "/lib", "/opt/", "/etc/")):
            return True

        if not candidate.is_absolute():
            cand_abs = (repo / candidate).absolute()
        else:
            cand_abs = candidate.absolute()

        repo_abs = repo.absolute()
        repo_res = repo.resolve()

        if cand_abs == repo_abs or repo_abs in cand_abs.parents or cand_abs == repo_res or repo_res in cand_abs.parents:
            return True

        try:
            resolved = cand_abs.resolve()
            if str(resolved).startswith(("/usr/", "/bin/", "/lib", "/opt/", "/etc/")):
                return True
            if resolved == repo_res or repo_res in resolved.parents or resolved == repo_abs or repo_abs in resolved.parents:
                return True
        except Exception:
            pass

        return False
    except (OSError, ValueError):
        return False


def _extract_paths_from_bash(command: str) -> list[str]:
    paths: list[str] = []
    for token in re.findall(r"(?<![\w\.\-/])/[^\s'\";|&<>]+", command):
        paths.append(token.rstrip("'\""))
    for token in re.findall(r"(~[^\s'\";|&]*)", command):
        paths.append(token)
    return paths


def _bash_confined_to_repo(command: str, repo: Path) -> bool:
    for pattern in _DESTRUCTIVE_BASH_PATTERNS:
        if pattern.search(command):
            return False

    # Relative parent escapes (cd .., ../paths)
    if re.search(r"\bcd\s+\.\.(\s|$|/|;|&)", command, re.I):
        return False
    if "../" in command or "/.." in command:
        return False

    home = Path.home()
    for path_str in _extract_paths_from_bash(command):
        if path_str.startswith("~") and not path_str.startswith(str(home)):
            return False
        if path_str.startswith("/") and not _path_within_repo(path_str, repo):
            return False

    if re.search(r"\bcd\s+([^\s;&|]+)", command, re.I):
        for match in re.finditer(r"\bcd\s+([^\s;&|]+)", command, re.I):
            target = match.group(1).strip("'\"")
            if target in {".", "./"}:
                continue
            if target.startswith("..") or "/../" in target or target.endswith("/.."):
                return False
            if target.startswith("~") and target != "~":
                expanded = os.path.expanduser(target)
                if not _path_within_repo(expanded, repo):
                    return False
            elif target.startswith("/") and not _path_within_repo(target, repo):
                return False
            elif not target.startswith("/") and not target.startswith("~"):
                # Relative cd target — resolve against repo
                if not _path_within_repo(target, repo):
                    return False
    return True


def _split_bash_command(cmd: str) -> list[str]:
    subcmds = []
    current = []
    in_single = False
    in_double = False
    i = 0
    while i < len(cmd):
        c = cmd[i]
        if c == "'" and not in_double:
            in_single = not in_single
            current.append(c)
            i += 1
        elif c == '"' and not in_single:
            in_double = not in_double
            current.append(c)
            i += 1
        elif c == '\\':
            current.append(c)
            if i + 1 < len(cmd):
                current.append(cmd[i+1])
                i += 1
            i += 1
        elif not in_single and not in_double:
            if c == ';':
                subcmds.append(''.join(current))
                current = []
                i += 1
            elif cmd[i:i+2] in ('&&', '||'):
                subcmds.append(''.join(current))
                current = []
                i += 2
            else:
                current.append(c)
                i += 1
        else:
            current.append(c)
            i += 1
    if current:
        subcmds.append(''.join(current))
    return subcmds


def _is_safe_bash(command: str, repo: Path) -> bool:
    if not _bash_confined_to_repo(command, repo):
        return False

    for pattern in _AMBIGUOUS_BASH_PATTERNS:
        if pattern.search(command):
            return False

    normalized = normalize_bash_command(command)
    stripped = normalized.lstrip()

    if is_echo_only_bash(command):
        return False

    # Split compound commands by ; or && or || (quote aware)
    subcmds = _split_bash_command(stripped)

    safe_executables = {
        "python", "python3", "pip", "pip3", "pytest", "node", "npm", "bun",
        "ls", "find", "tree", "cat", "head", "tail", "wc", "sort", "uniq", "diff",
        "sed", "grep", "rg", "touch", "mkdir", "cp", "mv", "rm", "git",
        "test", "pwd", "cd", "source", ".", "which", "env", "export", "[", "echo"
    }

    for sub in subcmds:
        sub_clean = sub.strip()
        if not sub_clean:
            continue

        # Strip environment variable assignments at start: e.g. V=... FOO=bar python ...
        sub_clean = re.sub(r'^(?:[A-Za-z_][A-Za-z0-9_]*=\S+;?\s*)+', '', sub_clean).strip()
        # Strip quotes from executable path if present: e.g. "$V/bin/python" -> $V/bin/python
        sub_clean = sub_clean.strip('"\'')

        words = sub_clean.split()
        if not words:
            continue

        first_word = words[0].strip('"\'')
        exec_name = os.path.basename(first_word).lower()

        is_safe_exec = (
            exec_name in safe_executables or
            "python" in exec_name or
            "pip" in exec_name
        )

        if not is_safe_exec:
            matched_prefix = any(sub_clean.lower().startswith(prefix) for prefix in _SAFE_BASH_PREFIXES)
            if not matched_prefix:
                if not ("<<" in sub or re.search(r">\s*\S+", sub)):
                    return False

    return True


def _count_matching_bash(tool_events: list[dict[str, Any]], command: str) -> int:
    target = normalize_bash_command(command)
    count = 0
    for event in tool_events:
        if event.get("event_type") != "tool_started":
            continue
        payload = event.get("payload") or {}
        if payload.get("tool_name") != "Bash":
            continue
        args = payload.get("arguments") or {}
        if normalize_bash_command(str(args.get("command") or "")) == target:
            count += 1
    return count


def _tool_paths_within_repo(tool_name: str, arguments: dict[str, Any], repo: Path) -> bool:
    if tool_name == "Read":
        return _path_within_repo(str(arguments.get("file_path") or ""), repo)
    if tool_name in ("Write", "Edit", "MultiEdit"):
        for key in ("file_path", "path", "target_file"):
            if key in arguments and not _path_within_repo(str(arguments[key]), repo):
                return False
        return True
    if tool_name == "Glob":
        target = str(arguments.get("target_directory") or arguments.get("path") or "")
        return not target or _path_within_repo(target, repo)
    if tool_name == "Grep":
        target = str(arguments.get("path") or "")
        return not target or _path_within_repo(target, repo)
    return True


def evaluate_intervention_guard(context: dict[str, Any]) -> InterventionGuardResult | None:
    """
    Return a deterministic intervention decision, or None to defer to the LLM.

    Auto-approves in-repo engineering tools; auto-denies noop echo bash and repeats.
    """
    pending = extract_pending_tool(context.get("recent_events") or [])
    if pending is None:
        return None

    tool_name, arguments = pending
    repo = _repo_root(context)
    if repo is None:
        return None

    if tool_name in _AUTO_APPROVE_TOOLS:
        if _tool_paths_within_repo(tool_name, arguments, repo):
            return InterventionGuardResult(
                response="yes",
                reasoning=f"auto-approve in-repo {tool_name}",
            )
        return InterventionGuardResult(
            response="no",
            reasoning=f"deny {tool_name} outside repository boundary",
        )

    if tool_name == "Agent":
        ok, reason = validate_agent_spawn(arguments, repo_path=repo)
        if ok:
            return InterventionGuardResult(
                response="yes",
                reasoning=f"auto-approve {reason}",
            )
        return InterventionGuardResult(
            response="no",
            reasoning=reason,
        )

    if tool_name == "Bash":
        command = str(arguments.get("command") or "")
        if not command.strip():
            return InterventionGuardResult(
                response="no",
                reasoning="deny empty Bash command",
            )

        if is_echo_only_bash(command):
            return InterventionGuardResult(
                response="no",
                reasoning="deny echo-only Bash (completion must be assistant text, not shell output)",
                is_echo_bash=True,
            )

        repeats = _count_matching_bash(context.get("tool_events") or [], command)
        if repeats >= 5:
            return InterventionGuardResult(
                response="no",
                reasoning="deny repeated identical Bash command in this turn",
            )

        if not _bash_confined_to_repo(command, repo):
            return InterventionGuardResult(
                response="no",
                reasoning="deny Bash outside repository or destructive pattern",
            )

        if _is_safe_bash(command, repo):
            return InterventionGuardResult(
                response="yes",
                reasoning="auto-approve safe in-repo Bash",
            )

        return None

    return None
