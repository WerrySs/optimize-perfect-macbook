"""Config Manager — Lee/escribe ~/.macboost/config.toml."""

from __future__ import annotations

import shutil
from pathlib import Path

import toml

APP_DIR = Path.home() / ".macboost"
CONFIG_FILE = APP_DIR / "config.toml"
SNAPSHOTS_DIR = APP_DIR / "snapshots"
REPORTS_DIR = APP_DIR / "reports"

DEFAULT_CONFIG: dict = {
    "general": {
        "auto_scan_interval": "6h",
        "notifications": True,
        "health_report": "weekly",
        "theme": "auto",
    },
    "modules": {
        "ram": {
            "enabled": True,
            "kill_threshold_mb": 500,
            "whitelist": ["Finder", "Dock", "WindowServer", "loginwindow", "SystemUIServer"],
        },
        "storage": {
            "enabled": True,
            "auto_clean_caches": False,
            "xcode_derived": True,
            "homebrew": True,
            "npm": True,
            "docker": True,
        },
        "boot": {
            "enabled": True,
            "blacklist": [
                "com.adobe.AdobeCreativeCloud",
                "com.spotify.client.startuphelper",
            ],
        },
        "network": {
            "enabled": True,
            "dns_provider": "cloudflare",
            "custom_dns": [],
            "disable_ipv6": False,
        },
        "ui": {
            "enabled": True,
            "instant_dock": True,
            "reduce_transparency": False,
            "reduce_motion": False,
        },
        "power": {
            "enabled": True,
            "default_profile": "balanced",
        },
        "health": {
            "enabled": True,
            "alert_ram_percent": 90,
            "alert_ssd_percent": 90,
            "alert_temp_celsius": 95,
        },
    },
}


class ConfigManager:
    """Gestiona la configuración de MacBoost."""

    def __init__(self):
        self._ensure_dirs()
        self._config: dict = self._load()

    def _ensure_dirs(self):
        for d in (APP_DIR, SNAPSHOTS_DIR, REPORTS_DIR):
            d.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                user_cfg = toml.load(f)
            return self._merge(DEFAULT_CONFIG, user_cfg)
        self._save(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    def _merge(self, base: dict, override: dict) -> dict:
        merged = base.copy()
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _save(self, config: dict):
        with open(CONFIG_FILE, "w") as f:
            toml.dump(config, f)

    @property
    def config(self) -> dict:
        return self._config

    def get(self, *keys: str, default=None):
        """Acceso con dot-path: config.get('modules', 'ram', 'enabled')."""
        current = self._config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def set(self, *keys_and_value):
        """Set con dot-path: config.set('modules', 'ram', 'enabled', True)."""
        *keys, value = keys_and_value
        current = self._config
        for key in keys[:-1]:
            current = current.setdefault(key, {})
        current[keys[-1]] = value
        self._save(self._config)

    def get_module_config(self, module_name: str) -> dict:
        return self.get("modules", module_name, default={})

    def is_module_enabled(self, module_name: str) -> bool:
        return self.get("modules", module_name, "enabled", default=True)

    def reset(self):
        """Restaura la configuración por defecto."""
        if CONFIG_FILE.exists():
            backup = CONFIG_FILE.with_suffix(".toml.bak")
            shutil.copy2(CONFIG_FILE, backup)
        self._config = DEFAULT_CONFIG.copy()
        self._save(self._config)
