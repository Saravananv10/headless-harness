"""Unit tests for Agent spawn protocol helper."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.workflow_common import (
    AGENT_SPAWN_FORBIDDEN,
    agent_spawn_instructions,
    validate_agent_spawn,
)


def test_agent_spawn_instructions_allows_worktree_forbids_remote() -> None:
    text = agent_spawn_instructions(
        repo_path="/tmp/repo",
        subagent_type="verification",
        extra_prompt_bullets=["original objective", "plan.md path"],
    )
    assert 'subagent_type="verification"' in text
    assert 'cwd="/tmp/repo"' in text
    assert "run_in_background=false" in text
    assert 'isolation="worktree"' in text
    assert "Worktree isolation is allowed" in text
    assert 'isolation="remote"' in AGENT_SPAWN_FORBIDDEN
    assert "original objective" in text
    assert "plan.md path" in text


def test_agent_spawn_instructions_without_bullets() -> None:
    text = agent_spawn_instructions(repo_path="/proj", subagent_type="Plan")
    assert 'cwd="/proj"' in text
    assert 'subagent_type="Plan"' in text
    assert "prompt must include" not in text


def test_validate_agent_spawn_ok() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = str(Path(tmp).resolve())
        ok, reason = validate_agent_spawn(
            {
                "subagent_type": "verification",
                "cwd": repo,
                "prompt": "verify",
            },
            repo_path=repo,
        )
        assert ok
        assert "ok" in reason.lower()


def test_validate_agent_spawn_allows_missing_cwd() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = str(Path(tmp).resolve())
        ok, reason = validate_agent_spawn(
            {"subagent_type": "Plan", "prompt": "plan"},
            repo_path=repo,
        )
        assert ok
        assert "cwd omitted" in reason.lower()


def test_validate_agent_spawn_allows_worktree() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = str(Path(tmp).resolve())
        ok, reason = validate_agent_spawn(
            {
                "subagent_type": "general-purpose",
                "cwd": repo,
                "isolation": "worktree",
            },
            repo_path=repo,
        )
        assert ok
        assert "ok" in reason.lower()


def test_validate_agent_spawn_denies_remote() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = str(Path(tmp).resolve())
        ok, reason = validate_agent_spawn(
            {
                "subagent_type": "verification",
                "cwd": repo,
                "isolation": "remote",
            },
            repo_path=repo,
        )
        assert not ok
        assert "remote" in reason.lower()


def test_validate_agent_spawn_denies_empty_type() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = str(Path(tmp).resolve())
        ok, reason = validate_agent_spawn(
            {"cwd": repo},
            repo_path=repo,
        )
        assert not ok
        assert "subagent_type" in reason.lower()


def main() -> int:
    tests = [
        test_agent_spawn_instructions_allows_worktree_forbids_remote,
        test_agent_spawn_instructions_without_bullets,
        test_validate_agent_spawn_ok,
        test_validate_agent_spawn_allows_missing_cwd,
        test_validate_agent_spawn_allows_worktree,
        test_validate_agent_spawn_denies_remote,
        test_validate_agent_spawn_denies_empty_type,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    if failed:
        print(f"\n{failed} test(s) failed")
        return 1
    print(f"\nAll {len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
