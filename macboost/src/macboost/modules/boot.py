"""Módulo Arranque & Launch Agents — Auditoría y gestión de servicios de inicio."""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

from macboost.core.undo import UndoEntry
from macboost.modules.base import BaseModule, FixResult, ScanResult

HOME = Path.home()

SCAN_DIRS = {
    "user_agents": HOME / "Library" / "LaunchAgents",
    "system_agents": Path("/Library/LaunchAgents"),
    "system_daemons": Path("/Library/LaunchDaemons"),
}

READ_ONLY_DIRS = {
    "apple_agents": Path("/System/Library/LaunchAgents"),
    "apple_daemons": Path("/System/Library/LaunchDaemons"),
}

KNOWN_SAFE = {
    "com.apple.", "com.google.keystone", "com.microsoft.update",
}

KNOWN_BLOAT = {
    "com.adobe.AdobeCreativeCloud",
    "com.adobe.ARMDCHelper",
    "com.spotify.client.startuphelper",
    "com.cisco.anyconnect.vpnagentd",
    "com.oracle.java.Java-Updater",
    "com.adobe.ARMDC.Communicator",
    "com.adobe.ARMDC.SMJobBlessHelper",
}


class BootModule(BaseModule):
    name = "boot"
    description = "Arranque & Launch Agents"
    priority = "alto"

    def scan(self) -> ScanResult:
        issues = []
        all_agents = self._get_all_agents()

        blacklist = set(self.config.get("blacklist", []))

        for agent in all_agents:
            label = agent.get("label", "")
            # Es bloat conocido o está en blacklist
            if label in KNOWN_BLOAT or label in blacklist:
                if agent.get("enabled", True):
                    issues.append({
                        "type": "unnecessary_agent",
                        "description": f"Agent innecesario activo: {label}",
                        "label": label,
                        "path": agent.get("path", ""),
                        "fixable": agent.get("manageable", False),
                        "severity": "medium",
                    })
            # No es de Apple y no es conocido
            elif not any(label.startswith(safe) for safe in KNOWN_SAFE):
                if agent.get("location") == "user_agents":
                    issues.append({
                        "type": "unknown_agent",
                        "description": f"Agent desconocido: {label}",
                        "label": label,
                        "path": agent.get("path", ""),
                        "fixable": True,
                        "severity": "low",
                    })

        total_agents = len(all_agents)
        return ScanResult(
            module=self.name,
            issues=issues,
            status="warning" if issues else "ok",
            summary=f"{total_agents} agents/daemons cargados, {len(issues)} revisables",
        )

    def fix(self, preview: bool = False) -> FixResult:
        actions = []
        blacklist = set(self.config.get("blacklist", []))
        undo_commands = []

        all_agents = self._get_all_agents()

        for agent in all_agents:
            label = agent.get("label", "")
            if (label in KNOWN_BLOAT or label in blacklist) and agent.get("enabled", True) and agent.get("manageable", False):
                plist_path = agent.get("path", "")
                if not preview and plist_path:
                    try:
                        subprocess.run(
                            ["launchctl", "unload", "-w", plist_path],
                            capture_output=True, timeout=10,
                        )
                        actions.append({"action": "disable_agent", "detail": f"Desactivado: {label}"})
                        undo_commands.append({"type": "launchctl_load", "plist": plist_path})
                    except Exception:
                        actions.append({"action": "disable_agent", "detail": f"No se pudo desactivar: {label}", "skipped": True})
                else:
                    actions.append({"action": "disable_agent", "detail": f"Se desactivaría: {label}", "preview": True})

        if actions and not preview:
            self.undo.save(UndoEntry(
                module=self.name,
                action="disable_agents",
                description=f"Desactivados {len(actions)} Launch Agents",
                undo_commands=undo_commands,
            ))

        return FixResult(
            module=self.name,
            actions=actions,
            status="ok",
            summary=f"{len(actions)} agents {'a desactivar' if preview else 'desactivados'}",
            preview_only=preview,
        )

    def get_all_agents(self) -> list[dict]:
        return self._get_all_agents()

    def toggle_agent(self, plist_path: str, enable: bool) -> tuple[bool, str]:
        """Habilita o deshabilita un Launch Agent específico."""
        action = "load" if enable else "unload"
        try:
            subprocess.run(
                ["launchctl", action, "-w", plist_path],
                capture_output=True, check=True, timeout=10,
            )

            undo_action = "unload" if enable else "load"
            self.undo.save(UndoEntry(
                module=self.name,
                action=f"toggle_{action}",
                description=f"{'Activado' if enable else 'Desactivado'}: {plist_path}",
                undo_commands=[{"type": f"launchctl_{undo_action}", "plist": plist_path}],
            ))
            return True, f"Agent {'activado' if enable else 'desactivado'}"
        except subprocess.CalledProcessError as e:
            return False, f"Error: {e.stderr or e}"

    def _get_all_agents(self) -> list[dict]:
        agents = []
        for location, directory in SCAN_DIRS.items():
            if not directory.exists():
                continue
            for plist_file in directory.glob("*.plist"):
                agent_info = self._parse_plist(plist_file, location, manageable=True)
                if agent_info:
                    agents.append(agent_info)

        for location, directory in READ_ONLY_DIRS.items():
            if not directory.exists():
                continue
            for plist_file in directory.glob("*.plist"):
                agent_info = self._parse_plist(plist_file, location, manageable=False)
                if agent_info:
                    agents.append(agent_info)

        return agents

    def _parse_plist(self, path: Path, location: str, manageable: bool) -> dict | None:
        try:
            with open(path, "rb") as f:
                data = plistlib.load(f)
            label = data.get("Label", path.stem)
            return {
                "label": label,
                "path": str(path),
                "location": location,
                "program": data.get("Program", data.get("ProgramArguments", [""])[0] if data.get("ProgramArguments") else ""),
                "run_at_load": data.get("RunAtLoad", False),
                "keep_alive": data.get("KeepAlive", False),
                "enabled": not data.get("Disabled", False),
                "manageable": manageable,
                "is_apple": label.startswith("com.apple."),
            }
        except Exception:
            return None
