"""Tests for datagen.dataset_manifest (append-only ledger + content-addressed snapshots)."""

from __future__ import annotations

from pathlib import Path

from datagen import dataset_manifest


def _entry(task_id: str, status: str = "PASSED") -> dataset_manifest.ManifestEntry:
    return dataset_manifest.ManifestEntry(
        task_id=task_id,
        category="finance_ca_practice",
        origin="datagen_task_bank",
        run_id=f"run_{task_id}",
        status=status,
        verdict="PASS" if status == "PASSED" else "FAIL",
        authoritative_pass=status == "PASSED",
        turn_count=4,
        tool_executions=10,
        template_hash="abc123",
    )


def test_append_and_load_round_trip(tmp_path: Path):
    path = tmp_path / "entries.jsonl"
    dataset_manifest.append_entry(_entry("t1"), path=path)
    dataset_manifest.append_entry(_entry("t2", status="FAILED"), path=path)

    entries = dataset_manifest.load_entries(path=path)
    assert len(entries) == 2
    assert entries[0]["task_id"] == "t1"
    assert entries[1]["status"] == "FAILED"


def test_load_entries_missing_file_returns_empty(tmp_path: Path):
    assert dataset_manifest.load_entries(path=tmp_path / "nope.jsonl") == []


def test_freeze_dataset_is_deterministic(tmp_path: Path):
    entries_path = tmp_path / "entries.jsonl"
    dataset_manifest.append_entry(_entry("t1"), path=entries_path)
    dataset_manifest.append_entry(_entry("t2", status="FAILED"), path=entries_path)

    snap_dir_a = tmp_path / "snaps_a"
    snap_dir_b = tmp_path / "snaps_b"
    snap_a = dataset_manifest.freeze_dataset(entries_path=entries_path, snapshots_dir=snap_dir_a)
    snap_b = dataset_manifest.freeze_dataset(entries_path=entries_path, snapshots_dir=snap_dir_b)

    assert snap_a["dataset_id"] == snap_b["dataset_id"]
    assert snap_a["entry_count"] == 2
    assert snap_a["passed_count"] == 1
    assert (snap_dir_a / f"{snap_a['dataset_id']}.json").is_file()


def test_freeze_dataset_changes_when_entries_change(tmp_path: Path):
    entries_path = tmp_path / "entries.jsonl"
    dataset_manifest.append_entry(_entry("t1"), path=entries_path)
    snap1 = dataset_manifest.freeze_dataset(entries_path=entries_path, snapshots_dir=tmp_path / "s1")

    dataset_manifest.append_entry(_entry("t2"), path=entries_path)
    snap2 = dataset_manifest.freeze_dataset(entries_path=entries_path, snapshots_dir=tmp_path / "s2")

    assert snap1["dataset_id"] != snap2["dataset_id"]


def test_freeze_dataset_filters_by_run_id(tmp_path: Path):
    entries_path = tmp_path / "entries.jsonl"
    dataset_manifest.append_entry(_entry("t1"), path=entries_path)
    dataset_manifest.append_entry(_entry("t2"), path=entries_path)

    snap = dataset_manifest.freeze_dataset(
        filter_run_ids={"run_t1"}, entries_path=entries_path, snapshots_dir=tmp_path / "s"
    )
    assert snap["entry_count"] == 1


def test_compute_template_hash_changes_with_content(tmp_path: Path):
    f = tmp_path / "template.py"
    f.write_text("version 1", encoding="utf-8")
    hash1 = dataset_manifest.compute_template_hash([f])

    f.write_text("version 2", encoding="utf-8")
    hash2 = dataset_manifest.compute_template_hash([f])

    assert hash1 != hash2
    assert dataset_manifest.compute_template_hash([f]) == hash2  # stable for same content


def test_compute_objective_hash_is_stable():
    assert dataset_manifest.compute_objective_hash("hello") == dataset_manifest.compute_objective_hash("hello")
    assert dataset_manifest.compute_objective_hash("hello") != dataset_manifest.compute_objective_hash("world")
