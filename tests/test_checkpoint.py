"""Tests for datagen.checkpoint (crash-safe per-task resume state)."""

from __future__ import annotations

from pathlib import Path

from datagen import checkpoint


def test_unknown_task_has_no_status(tmp_path: Path):
    store = checkpoint.CheckpointStore(path=tmp_path / "cp.json")
    assert store.status("nope") is None
    assert store.is_done("nope") is False


def test_mark_done_persists_and_reloads(tmp_path: Path):
    path = tmp_path / "cp.json"
    store = checkpoint.CheckpointStore(path=path)
    store.mark_running("t1")
    assert store.status("t1") == "running"
    store.mark_done("t1", run_id="run_1")

    reloaded = checkpoint.CheckpointStore(path=path)
    assert reloaded.is_done("t1") is True


def test_mark_failed_then_reset_failed(tmp_path: Path):
    store = checkpoint.CheckpointStore(path=tmp_path / "cp.json")
    store.mark_failed("t1", detail="boom")
    store.mark_done("t2")
    assert store.status("t1") == "failed"

    n = store.reset_failed()
    assert n == 1
    assert store.status("t1") is None
    assert store.status("t2") == "done"  # untouched


def test_reset_single_task(tmp_path: Path):
    store = checkpoint.CheckpointStore(path=tmp_path / "cp.json")
    store.mark_done("t1")
    store.reset("t1")
    assert store.status("t1") is None


def test_summary_counts_by_status(tmp_path: Path):
    store = checkpoint.CheckpointStore(path=tmp_path / "cp.json")
    store.mark_done("t1")
    store.mark_done("t2")
    store.mark_failed("t3")
    assert store.summary() == {"done": 2, "failed": 1}


def test_missing_file_starts_empty(tmp_path: Path):
    store = checkpoint.CheckpointStore(path=tmp_path / "does_not_exist.json")
    assert store.summary() == {}
