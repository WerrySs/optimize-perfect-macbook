"""Orchestrator — Coordina la ejecución de módulos."""

from __future__ import annotations

from macboost.core.config import ConfigManager
from macboost.core.health import calculate_health_score
from macboost.core.scanner import FullScanReport, SystemScanner
from macboost.core.undo import UndoEngine
from macboost.modules.base import BaseModule, FixResult, ScanResult
from macboost.modules.boot import BootModule
from macboost.modules.monitor import MonitorModule
from macboost.modules.network import NetworkModule
from macboost.modules.power import PowerModule
from macboost.modules.ram import RAMModule
from macboost.modules.storage import StorageModule
from macboost.modules.ui import UIModule

MODULE_REGISTRY: dict[str, type[BaseModule]] = {
    "ram": RAMModule,
    "storage": StorageModule,
    "boot": BootModule,
    "network": NetworkModule,
    "ui": UIModule,
    "power": PowerModule,
    "monitor": MonitorModule,
}


class Orchestrator:
    """Motor principal que coordina todos los componentes."""

    def __init__(self):
        self.config = ConfigManager()
        self.undo = UndoEngine()
        self._modules: dict[str, BaseModule] = {}
        self._load_modules()
        self.scanner = SystemScanner(self._modules)

    def _load_modules(self):
        for name, cls in MODULE_REGISTRY.items():
            if self.config.is_module_enabled(name):
                module_config = self.config.get_module_config(name)
                self._modules[name] = cls(config=module_config, undo_engine=self.undo)

    @property
    def modules(self) -> dict[str, BaseModule]:
        return self._modules

    def scan_all(self) -> FullScanReport:
        return self.scanner.scan_all()

    def scan_module(self, name: str) -> ScanResult:
        return self.scanner.scan_module(name)

    def fix_all(self, preview: bool = False) -> dict[str, FixResult]:
        results = {}
        for name, module in self._modules.items():
            if name == "monitor":
                continue
            results[name] = module.fix(preview=preview)
        return results

    def fix_module(self, name: str, preview: bool = False) -> FixResult:
        module = self._modules.get(name)
        if not module:
            return FixResult(module=name, actions=[], status="error")
        return module.fix(preview=preview)

    def quick_optimize(self) -> dict[str, FixResult]:
        """Optimización rápida: purge RAM + flush DNS + limpiar /tmp."""
        results = {}
        if "ram" in self._modules:
            results["ram"] = self._modules["ram"].quick_fix()
        if "network" in self._modules:
            results["network"] = self._modules["network"].quick_fix()
        if "storage" in self._modules:
            results["storage"] = self._modules["storage"].quick_fix()
        return results

    def get_status(self) -> dict:
        """Estado completo del sistema."""
        health = calculate_health_score()
        return {
            "health_score": health["total"],
            "scores": health["scores"],
            "modules_enabled": list(self._modules.keys()),
            "last_undo": self.undo.get_latest(),
        }
