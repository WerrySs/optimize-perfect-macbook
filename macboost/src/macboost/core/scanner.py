"""Scanner — Runner genérico de escaneos del sistema."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from macboost.modules.base import BaseModule, ScanResult


@dataclass
class FullScanReport:
    """Reporte completo de un escaneo de todos los módulos."""

    timestamp: float = field(default_factory=time.time)
    duration_seconds: float = 0.0
    results: dict[str, ScanResult] = field(default_factory=dict)
    total_issues: int = 0
    total_fixable: int = 0

    def summary(self) -> str:
        lines = [f"Escaneo completado en {self.duration_seconds:.1f}s"]
        lines.append(f"Problemas encontrados: {self.total_issues}")
        lines.append(f"Problemas corregibles: {self.total_fixable}")
        for name, result in self.results.items():
            status = "✓" if not result.issues else f"⚠ {len(result.issues)} problemas"
            lines.append(f"  {name}: {status}")
        return "\n".join(lines)


class SystemScanner:
    """Ejecuta escaneos sobre una lista de módulos."""

    def __init__(self, modules: dict[str, BaseModule]):
        self.modules = modules

    def scan_all(self) -> FullScanReport:
        report = FullScanReport()
        start = time.time()
        for name, module in self.modules.items():
            result = module.scan()
            report.results[name] = result
            report.total_issues += len(result.issues)
            report.total_fixable += sum(1 for i in result.issues if i.get("fixable", False))
        report.duration_seconds = time.time() - start
        return report

    def scan_module(self, module_name: str) -> ScanResult:
        module = self.modules.get(module_name)
        if not module:
            return ScanResult(module=module_name, issues=[], status="error")
        return module.scan()
