"""Tests para el módulo UI."""

from unittest.mock import MagicMock, patch

import pytest

from macboost.core.undo import UndoEngine


@pytest.fixture
def ui_module(tmp_path):
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    with patch("macboost.core.undo.SNAPSHOTS_DIR", snapshots):
        from macboost.modules.ui import UIModule
        undo = UndoEngine()
        config = {
            "enabled": True,
            "instant_dock": True,
            "reduce_transparency": False,
            "reduce_motion": False,
        }
        return UIModule(config=config, undo_engine=undo)


def test_scan_returns_result(ui_module):
    result = ui_module.scan()
    assert result.module == "ui"
    assert isinstance(result.issues, list)


def test_fix_preview_mode(ui_module):
    with patch("macboost.modules.ui.subprocess") as mock_sub:
        mock_run = MagicMock()
        mock_run.returncode = 1
        mock_run.stdout = ""
        mock_sub.run.return_value = mock_run
        mock_sub.CalledProcessError = Exception
        result = ui_module.fix(preview=True)
    assert result.preview_only is True


def test_ui_tweaks_defined():
    from macboost.modules.ui import UI_TWEAKS
    assert len(UI_TWEAKS) > 0
    for tweak in UI_TWEAKS:
        assert "id" in tweak
        assert "label" in tweak
        assert "commands" in tweak
        assert "undo" in tweak
