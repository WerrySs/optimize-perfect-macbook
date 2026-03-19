"""Tests para ConfigManager."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import toml


@pytest.fixture
def temp_config_dir(tmp_path):
    """Crea un directorio temporal para la configuración."""
    config_dir = tmp_path / ".macboost"
    config_dir.mkdir()
    (config_dir / "snapshots").mkdir()
    (config_dir / "reports").mkdir()
    return config_dir


@pytest.fixture
def config_manager(temp_config_dir):
    """ConfigManager con directorio temporal."""
    with patch("macboost.core.config.APP_DIR", temp_config_dir), \
         patch("macboost.core.config.CONFIG_FILE", temp_config_dir / "config.toml"), \
         patch("macboost.core.config.SNAPSHOTS_DIR", temp_config_dir / "snapshots"), \
         patch("macboost.core.config.REPORTS_DIR", temp_config_dir / "reports"):
        from macboost.core.config import ConfigManager
        return ConfigManager()


def test_default_config_created(config_manager, temp_config_dir):
    """Verifica que se crea el config.toml por defecto."""
    config_file = temp_config_dir / "config.toml"
    assert config_file.exists()


def test_get_value(config_manager):
    """Verifica acceso a valores de configuración."""
    assert config_manager.get("general", "notifications") is True
    assert config_manager.get("modules", "ram", "enabled") is True


def test_get_default(config_manager):
    """Verifica que retorna default para claves inexistentes."""
    assert config_manager.get("nonexistent", default="fallback") == "fallback"


def test_set_value(config_manager):
    """Verifica escritura de valores."""
    config_manager.set("general", "theme", "dark")
    assert config_manager.get("general", "theme") == "dark"


def test_module_config(config_manager):
    """Verifica configuración de módulos."""
    ram_config = config_manager.get_module_config("ram")
    assert ram_config["enabled"] is True
    assert "whitelist" in ram_config


def test_is_module_enabled(config_manager):
    """Verifica estado de módulos."""
    assert config_manager.is_module_enabled("ram") is True
    assert config_manager.is_module_enabled("nonexistent") is True  # default True


def test_reset(config_manager, temp_config_dir):
    """Verifica reset a valores por defecto."""
    config_manager.set("general", "theme", "dark")
    config_manager.reset()
    assert config_manager.get("general", "theme") == "auto"
    # Verifica que se creó backup
    backup = temp_config_dir / "config.toml.bak"
    assert backup.exists()
