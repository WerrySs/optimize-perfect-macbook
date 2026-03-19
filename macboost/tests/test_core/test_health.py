"""Tests para Health Score."""

from unittest.mock import MagicMock, patch

import pytest


def test_calculate_health_score():
    """Verifica que el health score se calcula correctamente."""
    with patch("macboost.core.health.get_cpu_score", return_value=80.0), \
         patch("macboost.core.health.get_ram_score", return_value=70.0), \
         patch("macboost.core.health.get_ssd_score", return_value=90.0), \
         patch("macboost.core.health.get_boot_score", return_value=85.0), \
         patch("macboost.core.health.get_network_score", return_value=75.0), \
         patch("macboost.core.health.get_battery_score", return_value=100.0):
        from macboost.core.health import calculate_health_score
        result = calculate_health_score()

    assert "total" in result
    assert "scores" in result
    assert "weights" in result
    assert 0 <= result["total"] <= 100

    # Verificar cálculo: RAM(70*0.25) + CPU(80*0.20) + SSD(90*0.20) + Boot(85*0.15) + Net(75*0.10) + Bat(100*0.10)
    # = 17.5 + 16 + 18 + 12.75 + 7.5 + 10 = 81.75
    assert result["total"] == 81.8  # rounded


def test_ram_score_low_usage():
    """RAM con uso bajo debería dar score alto."""
    mock_mem = MagicMock()
    mock_mem.percent = 40
    with patch("macboost.core.health.psutil") as mock_psutil:
        mock_psutil.virtual_memory.return_value = mock_mem
        from macboost.core.health import get_ram_score
        score = get_ram_score()
    assert score == 100.0


def test_ram_score_high_usage():
    """RAM con uso alto debería dar score bajo."""
    mock_mem = MagicMock()
    mock_mem.percent = 95
    with patch("macboost.core.health.psutil") as mock_psutil:
        mock_psutil.virtual_memory.return_value = mock_mem
        from macboost.core.health import get_ram_score
        score = get_ram_score()
    assert score < 20


def test_ssd_score_plenty_free():
    """SSD con mucho espacio libre debería dar score alto."""
    with patch("macboost.core.health.shutil") as mock_shutil:
        mock_shutil.disk_usage.return_value = MagicMock(total=500e9, free=200e9)
        from macboost.core.health import get_ssd_score
        score = get_ssd_score()
    assert score == 100.0


def test_battery_no_battery():
    """Mac de escritorio sin batería debería dar 100."""
    with patch("macboost.core.health.psutil") as mock_psutil:
        mock_psutil.sensors_battery.return_value = None
        from macboost.core.health import get_battery_score
        score = get_battery_score()
    assert score == 100.0


def test_health_score_has_all_components():
    """Verifica que el resultado tiene todos los componentes."""
    with patch("macboost.core.health.get_cpu_score", return_value=50.0), \
         patch("macboost.core.health.get_ram_score", return_value=50.0), \
         patch("macboost.core.health.get_ssd_score", return_value=50.0), \
         patch("macboost.core.health.get_boot_score", return_value=50.0), \
         patch("macboost.core.health.get_network_score", return_value=50.0), \
         patch("macboost.core.health.get_battery_score", return_value=50.0):
        from macboost.core.health import calculate_health_score
        result = calculate_health_score()

    expected_keys = {"cpu", "ram", "ssd", "boot", "network", "battery"}
    assert set(result["scores"].keys()) == expected_keys
    assert result["total"] == 50.0
