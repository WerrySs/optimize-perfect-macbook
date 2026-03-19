"""Tests para la CLI de MacBoost."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from macboost.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_orchestrator():
    """Mock del Orchestrator para todos los tests de CLI."""
    mock_orch = MagicMock()
    mock_orch.scan_all.return_value = MagicMock(
        duration_seconds=1.5,
        total_issues=3,
        total_fixable=2,
        results={},
    )
    mock_orch.get_status.return_value = {
        "health_score": 85,
        "scores": {"cpu": 90, "ram": 80, "ssd": 85, "boot": 90, "network": 75, "battery": 100},
        "modules_enabled": ["ram", "storage", "boot", "network", "ui", "power", "monitor"],
        "last_undo": None,
    }
    mock_orch.fix_all.return_value = {}
    mock_orch.quick_optimize.return_value = {}
    mock_orch.modules = {}
    mock_orch.undo = MagicMock()
    mock_orch.undo.list_entries.return_value = []
    mock_orch.undo.get_latest.return_value = None

    with patch("macboost.cli.app._get_orchestrator", return_value=mock_orch):
        yield mock_orch


def test_scan_all():
    result = runner.invoke(app, ["scan", "--all"])
    assert result.exit_code == 0


def test_status():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "85" in result.output


def test_quick():
    result = runner.invoke(app, ["quick"])
    assert result.exit_code == 0
    assert "rápida" in result.output.lower() or "completada" in result.output.lower()


def test_health():
    with patch("macboost.cli.app.calculate_health_score") as mock_health:
        mock_health.return_value = {
            "total": 85.0,
            "scores": {"cpu": 90, "ram": 80, "ssd": 85, "boot": 90, "network": 75, "battery": 100},
            "weights": {"cpu": 0.20, "ram": 0.25, "ssd": 0.20, "boot": 0.15, "network": 0.10, "battery": 0.10},
        }
        result = runner.invoke(app, ["health"])
    assert result.exit_code == 0


def test_undo_list():
    result = runner.invoke(app, ["undo", "--list"])
    assert result.exit_code == 0


def test_no_args_shows_help():
    result = runner.invoke(app)
    assert result.exit_code == 0
    assert "MacBoost" in result.output or "macboost" in result.output
