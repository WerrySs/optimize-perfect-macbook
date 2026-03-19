"""Módulo Energía & Thermal — Perfiles de rendimiento y control de consumo."""

from __future__ import annotations

import subprocess

from macboost.core.undo import UndoEntry
from macboost.modules.base import BaseModule, FixResult, ScanResult

PROFILES = {
    "lowpower": {
        "label": "Low Power",
        "description": "Máxima duración de batería",
        "spotlight": False,
        "timemachine": False,
        "powernap": False,
        "lowpowermode": True,
    },
    "balanced": {
        "label": "Balanced",
        "description": "Uso diario equilibrado",
        "spotlight": True,
        "timemachine": True,
        "powernap": True,
        "lowpowermode": False,
    },
    "performance": {
        "label": "Performance",
        "description": "Máximo rendimiento para tareas pesadas",
        "spotlight": True,
        "timemachine": False,
        "powernap": False,
        "lowpowermode": False,
    },
}


class PowerModule(BaseModule):
    name = "power"
    description = "Energía & Thermal"
    priority = "medio"

    def scan(self) -> ScanResult:
        issues = []
        current_profile = self._detect_current_profile()
        target = self.config.get("default_profile", "balanced")

        if current_profile != target:
            issues.append({
                "type": "profile_mismatch",
                "description": f"Perfil actual: {current_profile}, recomendado: {target}",
                "fixable": True,
                "severity": "low",
            })

        # Verificar si Spotlight está indexando activamente
        if self._is_spotlight_indexing():
            issues.append({
                "type": "spotlight_indexing",
                "description": "Spotlight está indexando activamente (consume CPU/batería)",
                "fixable": True,
                "severity": "medium",
            })

        return ScanResult(
            module=self.name,
            issues=issues,
            status="info" if issues else "ok",
            summary=f"Perfil: {current_profile}, {len(issues)} sugerencias",
        )

    def fix(self, preview: bool = False) -> FixResult:
        target = self.config.get("default_profile", "balanced")
        return self.set_profile(target, preview=preview)

    def set_profile(self, profile_name: str, preview: bool = False) -> FixResult:
        """Aplica un perfil de energía."""
        profile = PROFILES.get(profile_name)
        if not profile:
            return FixResult(
                module=self.name,
                actions=[{"action": "error", "detail": f"Perfil no válido: {profile_name}"}],
                status="error",
            )

        actions = []
        undo_commands = []

        # Spotlight
        if not preview:
            if not profile["spotlight"]:
                try:
                    subprocess.run(
                        ["sudo", "-n", "mdutil", "-i", "off", "/"],
                        capture_output=True, timeout=10,
                    )
                    undo_commands.append({"type": "shell", "command": "sudo mdutil -i on /"})
                    actions.append({"action": "spotlight", "detail": "Spotlight indexing desactivado"})
                except Exception:
                    actions.append({"action": "spotlight", "detail": "Requiere sudo para Spotlight", "skipped": True})
            else:
                try:
                    subprocess.run(
                        ["sudo", "-n", "mdutil", "-i", "on", "/"],
                        capture_output=True, timeout=10,
                    )
                    actions.append({"action": "spotlight", "detail": "Spotlight indexing activado"})
                except Exception:
                    pass
        else:
            state = "desactivado" if not profile["spotlight"] else "activado"
            actions.append({"action": "spotlight", "detail": f"Se pondría Spotlight: {state}", "preview": True})

        # Time Machine
        if not preview:
            tm_action = "enable" if profile["timemachine"] else "disable"
            try:
                subprocess.run(
                    ["sudo", "-n", "tmutil", tm_action],
                    capture_output=True, timeout=10,
                )
                undo_cmd = "sudo tmutil enable" if not profile["timemachine"] else "sudo tmutil disable"
                undo_commands.append({"type": "shell", "command": undo_cmd})
                actions.append({"action": "timemachine", "detail": f"Time Machine: {tm_action}"})
            except Exception:
                actions.append({"action": "timemachine", "detail": "Requiere sudo para Time Machine", "skipped": True})
        else:
            state = "activado" if profile["timemachine"] else "pausado"
            actions.append({"action": "timemachine", "detail": f"Se pondría Time Machine: {state}", "preview": True})

        # Low Power Mode
        if not preview:
            lpm = "1" if profile["lowpowermode"] else "0"
            try:
                subprocess.run(
                    ["sudo", "-n", "pmset", "-a", "lowpowermode", lpm],
                    capture_output=True, timeout=10,
                )
                undo_val = "0" if profile["lowpowermode"] else "1"
                undo_commands.append({"type": "shell", "command": f"sudo pmset -a lowpowermode {undo_val}"})
                actions.append({"action": "lowpower", "detail": f"Low Power Mode: {'ON' if profile['lowpowermode'] else 'OFF'}"})
            except Exception:
                actions.append({"action": "lowpower", "detail": "Requiere sudo para pmset", "skipped": True})
        else:
            state = "ON" if profile["lowpowermode"] else "OFF"
            actions.append({"action": "lowpower", "detail": f"Se pondría Low Power Mode: {state}", "preview": True})

        if actions and not preview and undo_commands:
            self.undo.save(UndoEntry(
                module=self.name,
                action=f"set_profile_{profile_name}",
                description=f"Perfil cambiado a: {profile['label']}",
                undo_commands=undo_commands,
            ))

        return FixResult(
            module=self.name,
            actions=actions,
            status="ok",
            summary=f"Perfil {profile['label']} {'previsto' if preview else 'aplicado'}",
            preview_only=preview,
        )

    def get_current_status(self) -> dict:
        """Devuelve el estado actual de energía."""
        return {
            "profile": self._detect_current_profile(),
            "spotlight_indexing": self._is_spotlight_indexing(),
            "profiles_available": list(PROFILES.keys()),
        }

    def _detect_current_profile(self) -> str:
        try:
            result = subprocess.run(
                ["pmset", "-g", "custom"],
                capture_output=True, text=True, timeout=10,
            )
            output = result.stdout.lower()
            if "lowpowermode 1" in output:
                return "lowpower"
            if "powernap 0" in output:
                return "performance"
            return "balanced"
        except Exception:
            return "balanced"

    def _is_spotlight_indexing(self) -> bool:
        try:
            result = subprocess.run(
                ["mdutil", "-s", "/"],
                capture_output=True, text=True, timeout=10,
            )
            return "enabled" in result.stdout.lower() and "indexing" in result.stdout.lower()
        except Exception:
            return False
