"""Tests for workspace confusion detection."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.intervention_guard import _bash_confined_to_repo
from controller.workspace_confusion import (
    WorkspaceConfusionTracker,
    classify_bash_parent_escape,
)


def test_three_out_of_repo_denials_trigger_confused() -> None:
    ws = WorkspaceConfusionTracker(threshold=3, repo_path="/tmp/repo")
    for i in range(3):
        ws.record_denial(
            tool_name="Read",
            reason="deny Read outside repository boundary",
            target=f"/other/path{i}",
        )
    assert ws.is_confused
    assert ws.confusion_count == 3


def test_harness_path_counts() -> None:
    ws = WorkspaceConfusionTracker(threshold=2, repo_path="/tmp/repo")
    ws.record_denial(
        tool_name="Read",
        reason="deny Read outside repository boundary",
        target="/Users/x/headless_harness_datagen/controller/foo.py",
    )
    ws.record_denial(
        tool_name="Read",
        reason="deny",
        target="/tmp/headless_harness/x",
    )
    assert ws.is_confused


def test_bash_parent_escape_classified() -> None:
    assert classify_bash_parent_escape("cd .. && ls") is True
    assert classify_bash_parent_escape("ls ../foo") is True
    assert classify_bash_parent_escape("ls -la") is False


def test_bash_confined_rejects_parent_cd() -> None:
    repo = Path("/tmp/repo")
    assert _bash_confined_to_repo("cd ..", repo) is False
    assert _bash_confined_to_repo("ls ../outside", repo) is False


def main() -> int:
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
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
