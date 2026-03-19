"""Tests para el módulo Storage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from macboost.core.undo import UndoEngine


@pytest.fixture
def storage_module(tmp_path):
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    with patch("macboost.core.undo.SNAPSHOTS_DIR", snapshots):
        from macboost.modules.storage import StorageModule
        undo = UndoEngine()
        config = {
            "enabled": True,
            "auto_clean_caches": False,
            "xcode_derived": True,
            "homebrew": True,
            "npm": True,
            "docker": False,
        }
        return StorageModule(config=config, undo_engine=undo)


def test_scan_returns_result(storage_module):
    result = storage_module.scan()
    assert result.module == "storage"
    assert isinstance(result.issues, list)


def test_fix_preview_mode(storage_module):
    result = storage_module.fix(preview=True)
    assert result.preview_only is True


def test_quick_fix_returns_result(storage_module):
    result = storage_module.quick_fix()
    assert result.module == "storage"


def test_dir_size_nonexistent(storage_module):
    size = storage_module._dir_size(Path("/nonexistent/path"))
    assert size == 0


def test_bytes_to_human(storage_module):
    assert "GB" in storage_module._bytes_to_human(2 * 1024**3)
    assert "MB" in storage_module._bytes_to_human(500 * 1024**2)
    assert "KB" in storage_module._bytes_to_human(100 * 1024)
    assert "B" in storage_module._bytes_to_human(500)
