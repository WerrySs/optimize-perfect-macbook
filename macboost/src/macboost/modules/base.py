"""Clase base abstracta para todos los módulos de optimización."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from macboost.core.undo import UndoEngine


@dataclass
class ScanResult:
    """Resultado de un escaneo de módulo."""

    module: str
    issues: list[dict] = field(default_factory=list)
    status: str = "ok"
    summary: str = ""
    space_recoverable_bytes: int = 0


@dataclass
class FixResult:
    """Resultado de aplicar fixes de un módulo."""

    module: str
    actions: list[dict] = field(default_factory=list)
    status: str = "ok"
    summary: str = ""
    space_freed_bytes: int = 0
    preview_only: bool = False


class BaseModule(ABC):
    """Interfaz estándar para todos los módulos de MacBoost."""

    name: str = "base"
    description: str = ""
    priority: str = "medio"

    def __init__(self, config: dict, undo_engine: UndoEngine):
        self.config = config
        self.undo = undo_engine

    @abstractmethod
    def scan(self) -> ScanResult:
        """Escanea el sistema y detecta problemas/oportunidades."""
        ...

    @abstractmethod
    def fix(self, preview: bool = False) -> FixResult:
        """Aplica optimizaciones. Si preview=True, solo reporta sin ejecutar."""
        ...

    def quick_fix(self) -> FixResult:
        """Optimización rápida (subset de fix)."""
        return self.fix()

    def _bytes_to_human(self, size_bytes: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
