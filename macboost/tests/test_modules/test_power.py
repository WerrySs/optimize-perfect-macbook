"""Tests para el módulo Power."""

from unittest.mock import MagicMock, patch

import pytest

from macboost.core.undo import UndoEngine


@pytest.fixture
def power_module(tmp_path):
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    with patch("macboost.core.undo.SNAPSHOTS_DIR", snapshots):
        from macboost.modules.power import PowerModule
        undo = UndoEngine()
        config = {
            "enabled": True,
            "default_profile": "balanced",
        }
        return PowerModule(config=config, undo_engine=undo)


def test_scan_returns_result(power_module):
    result = power_module.scan()
    assert result.module == "power"
    assert isinstance(result.issues, list)


def test_set_profile_preview(power_module):
    result = power_module.set_profile("performance", preview=True)
    assert result.preview_only is True
    assert result.module == "power"


def test_set_invalid_profile(power_module):
    result = power_module.set_profile("turbo_extreme")
    assert result.status == "error"


def test_profiles_defined():
    from macboost.modules.power import PROFILES
    assert "lowpower" in PROFILES
    assert "balanced" in PROFILES
    assert "performance" in PROFILES
    for name, profile in PROFILES.items():
        assert "label" in profile
        assert "spotlight" in profile
        assert "timemachine" in profile


def test_get_current_status(power_module):
    status = power_module.get_current_status()
    assert "profile" in status
    assert "profiles_available" in status
    assert set(status["profiles_available"]) == {"lowpower", "balanced", "performance"}
