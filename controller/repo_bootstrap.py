"""Ensure each experiment project directory is its own git repository."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_GIT_USER_EMAIL = "harness@local"
_GIT_USER_NAME = "Headless Harness"
_INITIAL_COMMIT_MESSAGE = "Initial commit"


@dataclass(frozen=True)
class GitBootstrapResult:
    """Outcome of ensuring a project directory is a git repo with HEAD."""

    initialized: bool
    already_ready: bool
    repo_path: str
    error: str | None = None


def _run_git(repo_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
        text=True,
    )


def _has_head(repo_path: Path) -> bool:
    try:
        _run_git(repo_path, "rev-parse", "HEAD")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return False


def _ensure_local_identity(repo_path: Path) -> None:
    """Set local committer identity when missing so empty commit can succeed."""
    try:
        email = _run_git(repo_path, "config", "--get", "user.email").stdout.strip()
    except subprocess.CalledProcessError:
        email = ""
    if not email:
        _run_git(repo_path, "config", "user.email", _GIT_USER_EMAIL)

    try:
        name = _run_git(repo_path, "config", "--get", "user.name").stdout.strip()
    except subprocess.CalledProcessError:
        name = ""
    if not name:
        _run_git(repo_path, "config", "user.name", _GIT_USER_NAME)


def ensure_project_git_repo(repo_path: Path | str) -> GitBootstrapResult:
    """
    Idempotently initialize ``repo_path`` as a git repository with HEAD.

    Runs ``git init`` and ``git commit --allow-empty -m "Initial commit"``
    when needed so Chakra worktree isolation anchors to the project, not a
    parent monorepo.
    """
    path = Path(repo_path).resolve()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return GitBootstrapResult(
            initialized=False,
            already_ready=False,
            repo_path=str(path),
            error=f"Failed to create repository directory: {exc}",
        )

    git_dir = path / ".git"
    if git_dir.exists() and _has_head(path):
        return GitBootstrapResult(
            initialized=False,
            already_ready=True,
            repo_path=str(path),
        )

    try:
        if not git_dir.exists():
            _run_git(path, "init")
        _ensure_local_identity(path)
        if not _has_head(path):
            _run_git(path, "commit", "--allow-empty", "-m", _INITIAL_COMMIT_MESSAGE)
    except FileNotFoundError:
        return GitBootstrapResult(
            initialized=False,
            already_ready=False,
            repo_path=str(path),
            error="git is not installed or not on PATH",
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        return GitBootstrapResult(
            initialized=False,
            already_ready=False,
            repo_path=str(path),
            error=f"git bootstrap failed: {detail}",
        )
    except OSError as exc:
        return GitBootstrapResult(
            initialized=False,
            already_ready=False,
            repo_path=str(path),
            error=f"git bootstrap failed: {exc}",
        )

    if not _has_head(path):
        return GitBootstrapResult(
            initialized=False,
            already_ready=False,
            repo_path=str(path),
            error="git bootstrap completed but HEAD is missing",
        )

    logger.info("Initialized git repository at %s", path)
    return GitBootstrapResult(
        initialized=True,
        already_ready=False,
        repo_path=str(path),
    )
