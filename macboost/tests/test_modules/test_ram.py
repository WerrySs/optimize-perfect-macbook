"""Tests para el módulo RAM."""

from unittest.mock import MagicMock, patch

import pytest

from macboost.core.undo import UndoEngine


@pytest.fixture
def ram_module(tmp_path):
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    with patch("macboost.core.undo.SNAPSHOTS_DIR", snapshots):
        from macboost.modules.ram import RAMModule
        undo = UndoEngine()
        config = {
            "enabled": True,
            "kill_threshold_mb": 500,
            "whitelist": ["Finder", "Dock"],
        }
        return RAMModule(config=config, undo_engine=undo)


def test_scan_returns_result(ram_module):
    result = ram_module.scan()
    assert result.module == "ram"
    assert result.status in ("ok", "warning")
    assert isinstance(result.issues, list)


def test_scan_detects_high_ram(ram_module):
    mock_mem = MagicMock()
    mock_mem.percent = 95
    mock_mem.used = 15 * 1024**3
    mock_mem.total = 16 * 1024**3
    with patch("macboost.modules.ram.psutil") as mock_psutil:
        mock_psutil.virtual_memory.return_value = mock_mem
        mock_psutil.process_iter.return_value = []
        mock_psutil.STATUS_ZOMBIE = "zombie"
        result = ram_module.scan()
    assert any(i["type"] == "high_ram" for i in result.issues)


def test_fix_preview_mode(ram_module):
    with patch("macboost.modules.ram.psutil") as mock_psutil:
        mock_psutil.process_iter.return_value = []
        mock_psutil.STATUS_ZOMBIE = "zombie"
        result = ram_module.fix(preview=True)
    assert result.preview_only is True
    for action in result.actions:
        assert action.get("preview") is True


def test_get_top_processes(ram_module):
    procs = ram_module.get_top_processes(5)
    assert isinstance(procs, list)
    # Verificar que están ordenados por RAM
    if len(procs) > 1:
        assert procs[0]["rss_mb"] >= procs[1]["rss_mb"]


def test_quick_fix_returns_result(ram_module):
    with patch("macboost.modules.ram.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0)
        mock_sub.CalledProcessError = Exception
        mock_sub.TimeoutExpired = Exception
        result = ram_module.quick_fix()
    assert result.module == "ram"
