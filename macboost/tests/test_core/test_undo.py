"""Tests para UndoEngine."""

from unittest.mock import patch

import pytest

from macboost.core.undo import UndoEngine, UndoEntry


@pytest.fixture
def undo_engine(tmp_path):
    """UndoEngine con directorio temporal."""
    snapshots_dir = tmp_path / "snapshots"
    snapshots_dir.mkdir()
    with patch("macboost.core.undo.SNAPSHOTS_DIR", snapshots_dir):
        engine = UndoEngine()
    engine._snapshots_dir = snapshots_dir
    # Patch SNAPSHOTS_DIR for all operations
    with patch("macboost.core.undo.SNAPSHOTS_DIR", snapshots_dir):
        yield engine


@pytest.fixture
def sample_entry():
    return UndoEntry(
        module="test",
        action="test_action",
        description="Test operation",
        undo_commands=[{"type": "shell", "command": "echo test"}],
    )


def test_save_entry(undo_engine, sample_entry, tmp_path):
    snapshots_dir = tmp_path / "snapshots"
    with patch("macboost.core.undo.SNAPSHOTS_DIR", snapshots_dir):
        entry_id = undo_engine.save(sample_entry)
    assert entry_id == sample_entry.id
    assert (snapshots_dir / f"{entry_id}.json").exists()


def test_get_entry(undo_engine, sample_entry, tmp_path):
    snapshots_dir = tmp_path / "snapshots"
    with patch("macboost.core.undo.SNAPSHOTS_DIR", snapshots_dir):
        undo_engine.save(sample_entry)
        entry = undo_engine.get_entry(sample_entry.id)
    assert entry is not None
    assert entry.module == "test"
    assert entry.description == "Test operation"


def test_get_nonexistent(undo_engine, tmp_path):
    snapshots_dir = tmp_path / "snapshots"
    with patch("macboost.core.undo.SNAPSHOTS_DIR", snapshots_dir):
        entry = undo_engine.get_entry("nonexistent")
    assert entry is None


def test_list_entries(undo_engine, tmp_path):
    snapshots_dir = tmp_path / "snapshots"
    with patch("macboost.core.undo.SNAPSHOTS_DIR", snapshots_dir):
        for i in range(5):
            e = UndoEntry(module="test", action=f"action_{i}", description=f"Op {i}", undo_commands=[])
            undo_engine.save(e)
        entries = undo_engine.list_entries()
    assert len(entries) == 5


def test_get_latest(undo_engine, tmp_path):
    snapshots_dir = tmp_path / "snapshots"
    with patch("macboost.core.undo.SNAPSHOTS_DIR", snapshots_dir):
        for i in range(3):
            e = UndoEntry(module="test", action=f"action_{i}", description=f"Op {i}", undo_commands=[])
            undo_engine.save(e)
        latest = undo_engine.get_latest()
    assert latest is not None


def test_clear_history(undo_engine, sample_entry, tmp_path):
    snapshots_dir = tmp_path / "snapshots"
    with patch("macboost.core.undo.SNAPSHOTS_DIR", snapshots_dir):
        undo_engine.save(sample_entry)
        undo_engine.clear_history()
        entries = undo_engine.list_entries()
    assert len(entries) == 0


def test_entry_serialization():
    entry = UndoEntry(
        module="ram",
        action="purge",
        description="Purge RAM",
        undo_commands=[{"type": "shell", "command": "echo undo"}],
    )
    d = entry.to_dict()
    restored = UndoEntry.from_dict(d)
    assert restored.module == entry.module
    assert restored.action == entry.action
    assert restored.id == entry.id
