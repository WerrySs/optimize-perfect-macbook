"""Módulo RAM & Procesos — Monitoreo y optimización de memoria."""

from __future__ import annotations

import subprocess

import psutil

from macboost.core.undo import UndoEntry
from macboost.modules.base import BaseModule, FixResult, ScanResult

SYSTEM_WHITELIST = {
    "kernel_task", "launchd", "WindowServer", "Finder", "Dock",
    "loginwindow", "SystemUIServer", "mds", "mds_stores", "coreaudiod",
    "bluetoothd", "configd", "distnoted", "logd", "notifyd",
    "opendirectoryd", "securityd", "syslogd", "UserEventAgent",
}


class RAMModule(BaseModule):
    name = "ram"
    description = "RAM & Procesos"
    priority = "crítico"

    def scan(self) -> ScanResult:
        mem = psutil.virtual_memory()
        issues = []

        # RAM alta
        if mem.percent > 80:
            issues.append({
                "type": "high_ram",
                "description": f"Uso de RAM al {mem.percent}% ({self._bytes_to_human(mem.used)} / {self._bytes_to_human(mem.total)})",
                "severity": "high" if mem.percent > 90 else "medium",
                "fixable": True,
            })

        # Procesos zombie
        zombies = [p for p in psutil.process_iter(["pid", "name", "status"]) if p.info["status"] == psutil.STATUS_ZOMBIE]
        if zombies:
            issues.append({
                "type": "zombie_processes",
                "description": f"{len(zombies)} procesos zombie detectados",
                "severity": "medium",
                "fixable": True,
                "details": [{"pid": z.info["pid"], "name": z.info["name"]} for z in zombies],
            })

        # Top procesos por RAM
        top_procs = self._get_top_processes(20)
        hogs = [p for p in top_procs if p["rss_mb"] > self.config.get("kill_threshold_mb", 500)]
        whitelist = set(self.config.get("whitelist", [])) | SYSTEM_WHITELIST
        killable = [p for p in hogs if p["name"] not in whitelist]

        if killable:
            issues.append({
                "type": "memory_hogs",
                "description": f"{len(killable)} procesos consumiendo > {self.config.get('kill_threshold_mb', 500)} MB",
                "severity": "medium",
                "fixable": True,
                "details": killable,
            })

        return ScanResult(
            module=self.name,
            issues=issues,
            status="warning" if issues else "ok",
            summary=f"RAM: {mem.percent}% usado, {len(issues)} problemas",
        )

    def fix(self, preview: bool = False) -> FixResult:
        actions = []

        # Kill zombies
        zombies = [p for p in psutil.process_iter(["pid", "name", "status"]) if p.info["status"] == psutil.STATUS_ZOMBIE]
        if zombies:
            if not preview:
                killed = 0
                for z in zombies:
                    try:
                        psutil.Process(z.info["pid"]).kill()
                        killed += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                actions.append({"action": "kill_zombies", "detail": f"Eliminados {killed} procesos zombie"})
            else:
                actions.append({"action": "kill_zombies", "detail": f"Se eliminarían {len(zombies)} procesos zombie", "preview": True})

        # Purge RAM
        if not preview:
            try:
                subprocess.run(["sudo", "-n", "purge"], capture_output=True, timeout=30)
                actions.append({"action": "purge_ram", "detail": "Purge de RAM completado"})
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                actions.append({"action": "purge_ram", "detail": "Purge requiere sudo", "skipped": True})
        else:
            actions.append({"action": "purge_ram", "detail": "Se haría purge de RAM comprimida", "preview": True})

        if actions and not preview:
            self.undo.save(UndoEntry(
                module=self.name,
                action="fix",
                description="Optimización de RAM (purge + kill zombies)",
                undo_commands=[],  # RAM purge no necesita undo real
            ))

        return FixResult(
            module=self.name,
            actions=actions,
            status="ok",
            summary=f"{len(actions)} acciones {'previstas' if preview else 'ejecutadas'}",
            preview_only=preview,
        )

    def quick_fix(self) -> FixResult:
        """Solo purge RAM sin matar procesos."""
        actions = []
        try:
            subprocess.run(["sudo", "-n", "purge"], capture_output=True, timeout=30)
            actions.append({"action": "purge_ram", "detail": "Purge de RAM completado"})
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            actions.append({"action": "purge_ram", "detail": "Purge requiere sudo", "skipped": True})

        return FixResult(module=self.name, actions=actions, status="ok", summary="Quick fix RAM")

    def _get_top_processes(self, limit: int = 20) -> list[dict]:
        procs = []
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                info = p.info
                rss = info["memory_info"].rss if info["memory_info"] else 0
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "rss_mb": round(rss / 1024 / 1024, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(key=lambda x: x["rss_mb"], reverse=True)
        return procs[:limit]

    def get_top_processes(self, limit: int = 20) -> list[dict]:
        return self._get_top_processes(limit)
