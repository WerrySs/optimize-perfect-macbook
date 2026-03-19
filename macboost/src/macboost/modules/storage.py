"""Módulo Limpieza de Almacenamiento — Eliminación segura de cachés y datos huérfanos."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from macboost.core.undo import UndoEntry
from macboost.modules.base import BaseModule, FixResult, ScanResult

HOME = Path.home()

CACHE_TARGETS = [
    ("Cachés de usuario", HOME / "Library" / "Caches"),
    ("Logs de usuario", HOME / "Library" / "Logs"),
]

DEV_TARGETS = {
    "xcode_derived": ("Xcode DerivedData", HOME / "Library" / "Developer" / "Xcode" / "DerivedData"),
}

COMMAND_TARGETS = {
    "homebrew": ("Homebrew cache", "brew cleanup --prune=all"),
    "npm": ("npm cache", "npm cache clean --force"),
    "docker": ("Docker system", "docker system prune -af"),
}


class StorageModule(BaseModule):
    name = "storage"
    description = "Limpieza de Almacenamiento"
    priority = "crítico"

    def scan(self) -> ScanResult:
        issues = []
        total_recoverable = 0

        # Cachés de usuario
        for label, path in CACHE_TARGETS:
            size = self._dir_size(path)
            if size > 100 * 1024 * 1024:  # > 100 MB
                issues.append({
                    "type": "cache",
                    "description": f"{label}: {self._bytes_to_human(size)}",
                    "path": str(path),
                    "size_bytes": size,
                    "fixable": True,
                })
                total_recoverable += size

        # Xcode DerivedData
        if self.config.get("xcode_derived", True):
            label, path = DEV_TARGETS["xcode_derived"]
            size = self._dir_size(path)
            if size > 50 * 1024 * 1024:
                issues.append({
                    "type": "dev_cache",
                    "description": f"{label}: {self._bytes_to_human(size)}",
                    "path": str(path),
                    "size_bytes": size,
                    "fixable": True,
                })
                total_recoverable += size

        # Logs del sistema
        sys_logs = Path("/var/log")
        if sys_logs.exists():
            size = self._dir_size(sys_logs)
            if size > 200 * 1024 * 1024:
                issues.append({
                    "type": "system_logs",
                    "description": f"Logs del sistema: {self._bytes_to_human(size)}",
                    "path": str(sys_logs),
                    "size_bytes": size,
                    "fixable": True,
                })
                total_recoverable += size

        # .DS_Store files
        try:
            result = subprocess.run(
                ["find", str(HOME), "-name", ".DS_Store", "-maxdepth", "5"],
                capture_output=True, text=True, timeout=15,
            )
            ds_count = len(result.stdout.strip().splitlines()) if result.stdout.strip() else 0
            if ds_count > 50:
                issues.append({
                    "type": "ds_store",
                    "description": f"{ds_count} archivos .DS_Store encontrados",
                    "fixable": True,
                })
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass

        # pip cache
        try:
            result = subprocess.run(
                ["pip", "cache", "info"], capture_output=True, text=True, timeout=10,
            )
            if "size" in result.stdout.lower():
                issues.append({
                    "type": "pip_cache",
                    "description": "pip cache presente",
                    "fixable": True,
                })
        except Exception:
            pass

        return ScanResult(
            module=self.name,
            issues=issues,
            status="warning" if issues else "ok",
            summary=f"Espacio recuperable: ~{self._bytes_to_human(total_recoverable)}",
            space_recoverable_bytes=total_recoverable,
        )

    def fix(self, preview: bool = False) -> FixResult:
        actions = []
        freed = 0

        # Limpiar cachés de usuario
        for label, path in CACHE_TARGETS:
            size = self._dir_size(path)
            if size > 100 * 1024 * 1024:
                if not preview:
                    self._clean_directory(path)
                    freed += size
                actions.append({
                    "action": "clean_cache",
                    "detail": f"{'Limpiaría' if preview else 'Limpiado'} {label}: {self._bytes_to_human(size)}",
                    "preview": preview,
                })

        # Xcode DerivedData
        if self.config.get("xcode_derived", True):
            label, path = DEV_TARGETS["xcode_derived"]
            size = self._dir_size(path)
            if size > 50 * 1024 * 1024:
                if not preview:
                    self._clean_directory(path)
                    freed += size
                actions.append({
                    "action": "clean_xcode",
                    "detail": f"{'Limpiaría' if preview else 'Limpiado'} {label}: {self._bytes_to_human(size)}",
                    "preview": preview,
                })

        # Homebrew
        if self.config.get("homebrew", True):
            label, cmd = COMMAND_TARGETS["homebrew"]
            if not preview:
                try:
                    subprocess.run(cmd, shell=True, capture_output=True, timeout=120)
                    actions.append({"action": "clean_homebrew", "detail": f"Limpiado {label}"})
                except Exception:
                    actions.append({"action": "clean_homebrew", "detail": "Homebrew no disponible", "skipped": True})
            else:
                actions.append({"action": "clean_homebrew", "detail": f"Se limpiaría {label}", "preview": True})

        # npm
        if self.config.get("npm", True):
            label, cmd = COMMAND_TARGETS["npm"]
            if not preview:
                try:
                    subprocess.run(cmd, shell=True, capture_output=True, timeout=60)
                    actions.append({"action": "clean_npm", "detail": f"Limpiado {label}"})
                except Exception:
                    actions.append({"action": "clean_npm", "detail": "npm no disponible", "skipped": True})
            else:
                actions.append({"action": "clean_npm", "detail": f"Se limpiaría {label}", "preview": True})

        # .DS_Store
        if not preview:
            try:
                subprocess.run(
                    ["find", str(HOME), "-name", ".DS_Store", "-maxdepth", "5", "-delete"],
                    capture_output=True, timeout=30,
                )
                actions.append({"action": "clean_ds_store", "detail": "Archivos .DS_Store eliminados"})
            except Exception:
                pass
        else:
            actions.append({"action": "clean_ds_store", "detail": "Se eliminarían archivos .DS_Store", "preview": True})

        if actions and not preview:
            self.undo.save(UndoEntry(
                module=self.name,
                action="clean",
                description=f"Limpieza de almacenamiento: {self._bytes_to_human(freed)} liberados",
                undo_commands=[],  # Los cachés se regeneran solos
            ))

        return FixResult(
            module=self.name,
            actions=actions,
            status="ok",
            summary=f"{'Preview: ' if preview else ''}{self._bytes_to_human(freed)} {'recuperables' if preview else 'liberados'}",
            space_freed_bytes=freed,
            preview_only=preview,
        )

    def quick_fix(self) -> FixResult:
        """Solo limpia /tmp y cachés menores."""
        actions = []
        tmp_path = Path("/tmp")
        try:
            for item in tmp_path.iterdir():
                if item.name.startswith("."):
                    continue
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                except PermissionError:
                    pass
            actions.append({"action": "clean_tmp", "detail": "Limpiado /tmp"})
        except PermissionError:
            actions.append({"action": "clean_tmp", "detail": "Sin permisos para /tmp", "skipped": True})

        return FixResult(module=self.name, actions=actions, status="ok", summary="Quick fix almacenamiento")

    def _dir_size(self, path: Path) -> int:
        if not path.exists():
            return 0
        total = 0
        try:
            for f in path.rglob("*"):
                try:
                    if f.is_file():
                        total += f.stat().st_size
                except (PermissionError, OSError):
                    pass
        except PermissionError:
            pass
        return total

    def _clean_directory(self, path: Path):
        if not path.exists():
            return
        for item in path.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
            except (PermissionError, OSError):
                pass
