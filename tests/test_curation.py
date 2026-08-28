"""Tests for datagen.curation (durable manual "known-good, don't regenerate" list)."""

from __future__ import annotations

from pathlib import Path

from datagen import curation


def test_unmarked_task_is_not_good(tmp_path: Path):
    clist = curation.CurationList(path=tmp_path / "curation.json")
    assert clist.is_marked_good("t1") is False


def test_mark_good_persists_and_reloads(tmp_path: Path):
    path = tmp_path / "curation.json"
    clist = curation.CurationList(path=path)
    clist.mark_good("t1", reason="strong demo, keep as-is")

    reloaded = curation.CurationList(path=path)
    assert reloaded.is_marked_good("t1") is True
    assert reloaded.reason_for("t1") == "strong demo, keep as-is"


def test_unmark_removes_entry(tmp_path: Path):
    path = tmp_path / "curation.json"
    clist = curation.CurationList(path=path)
    clist.mark_good("t1")
    assert clist.unmark("t1") is True
    assert clist.is_marked_good("t1") is False
    assert clist.unmark("t1") is False  # already gone


def test_all_marked_lists_everything_sorted(tmp_path: Path):
    clist = curation.CurationList(path=tmp_path / "curation.json")
    clist.mark_good("zeta")
    clist.mark_good("alpha")
    assert clist.all_marked() == ["alpha", "zeta"]
