"""Módulo UI & Animaciones — Reducción de overhead visual de macOS."""

from __future__ import annotations

import subprocess

from macboost.core.undo import UndoEntry
from macboost.modules.base import BaseModule, FixResult, ScanResult

UI_TWEAKS = [
    {
        "id": "instant_dock_hide",
        "label": "Dock: autohide instantáneo",
        "config_key": "instant_dock",
        "commands": [
            {"domain": "com.apple.dock", "key": "autohide-delay", "type": "-float", "value": "0"},
            {"domain": "com.apple.dock", "key": "autohide-time-modifier", "type": "-float", "value": "0.3"},
        ],
        "undo": [
            {"type": "defaults_delete", "domain": "com.apple.dock", "key": "autohide-delay"},
            {"type": "defaults_delete", "domain": "com.apple.dock", "key": "autohide-time-modifier"},
        ],
    },
    {
        "id": "no_bounce",
        "label": "Dock: sin animación de bounce",
        "config_key": "instant_dock",
        "commands": [
            {"domain": "com.apple.dock", "key": "launchanim", "type": "-bool", "value": "false"},
        ],
        "undo": [
            {"type": "defaults_delete", "domain": "com.apple.dock", "key": "launchanim"},
        ],
    },
    {
        "id": "no_finder_animations",
        "label": "Finder: sin animaciones",
        "config_key": "instant_dock",
        "commands": [
            {"domain": "com.apple.finder", "key": "DisableAllAnimations", "type": "-bool", "value": "true"},
        ],
        "undo": [
            {"type": "defaults_delete", "domain": "com.apple.finder", "key": "DisableAllAnimations"},
        ],
    },
    {
        "id": "reduce_transparency",
        "label": "Reducir transparencias",
        "config_key": "reduce_transparency",
        "commands": [
            {"domain": "com.apple.universalaccess", "key": "reduceTransparency", "type": "-bool", "value": "true"},
        ],
        "undo": [
            {"type": "defaults_write", "domain": "com.apple.universalaccess", "key": "reduceTransparency", "value_type": "-bool", "value": "false"},
        ],
    },
    {
        "id": "reduce_motion",
        "label": "Reducir animaciones del sistema",
        "config_key": "reduce_motion",
        "commands": [
            {"domain": "com.apple.universalaccess", "key": "reduceMotion", "type": "-bool", "value": "true"},
        ],
        "undo": [
            {"type": "defaults_write", "domain": "com.apple.universalaccess", "key": "reduceMotion", "value_type": "-bool", "value": "false"},
        ],
    },
    {
        "id": "expanded_save_dialog",
        "label": "Diálogos guardar expandidos por defecto",
        "config_key": "instant_dock",
        "commands": [
            {"domain": "NSGlobalDomain", "key": "NSNavPanelExpandedStateForSaveMode", "type": "-bool", "value": "true"},
            {"domain": "NSGlobalDomain", "key": "NSNavPanelExpandedStateForSaveMode2", "type": "-bool", "value": "true"},
        ],
        "undo": [
            {"type": "defaults_delete", "domain": "NSGlobalDomain", "key": "NSNavPanelExpandedStateForSaveMode"},
            {"type": "defaults_delete", "domain": "NSGlobalDomain", "key": "NSNavPanelExpandedStateForSaveMode2"},
        ],
    },
    {
        "id": "show_extensions",
        "label": "Mostrar extensiones de archivo",
        "config_key": "instant_dock",
        "commands": [
            {"domain": "NSGlobalDomain", "key": "AppleShowAllExtensions", "type": "-bool", "value": "true"},
        ],
        "undo": [
            {"type": "defaults_delete", "domain": "NSGlobalDomain", "key": "AppleShowAllExtensions"},
        ],
    },
    {
        "id": "heic_screenshots",
        "label": "Screenshots en HEIC (más ligeros)",
        "config_key": "instant_dock",
        "commands": [
            {"domain": "com.apple.screencapture", "key": "type", "type": "-string", "value": "heic"},
        ],
        "undo": [
            {"type": "defaults_write", "domain": "com.apple.screencapture", "key": "type", "value_type": "-string", "value": "png"},
        ],
    },
]


class UIModule(BaseModule):
    name = "ui"
    description = "UI & Animaciones"
    priority = "medio"

    def scan(self) -> ScanResult:
        issues = []

        for tweak in UI_TWEAKS:
            config_key = tweak["config_key"]
            if not self.config.get(config_key, False) and config_key != "instant_dock":
                continue

            # Verificar si el tweak ya está aplicado
            applied = self._is_tweak_applied(tweak)
            if not applied:
                issues.append({
                    "type": "ui_tweak",
                    "description": f"No aplicado: {tweak['label']}",
                    "tweak_id": tweak["id"],
                    "fixable": True,
                    "severity": "low",
                })

        return ScanResult(
            module=self.name,
            issues=issues,
            status="info" if issues else "ok",
            summary=f"{len(issues)} tweaks de UI disponibles",
        )

    def fix(self, preview: bool = False) -> FixResult:
        actions = []
        all_undo = []
        needs_dock_restart = False

        for tweak in UI_TWEAKS:
            config_key = tweak["config_key"]
            if not self.config.get(config_key, False) and config_key != "instant_dock":
                continue

            if self._is_tweak_applied(tweak):
                continue

            if not preview:
                for cmd in tweak["commands"]:
                    try:
                        subprocess.run(
                            ["defaults", "write", cmd["domain"], cmd["key"], cmd["type"], cmd["value"]],
                            capture_output=True, check=True, timeout=5,
                        )
                    except subprocess.CalledProcessError:
                        pass

                all_undo.extend(tweak["undo"])
                if "com.apple.dock" in str(tweak["commands"]):
                    needs_dock_restart = True

            actions.append({
                "action": "apply_tweak",
                "detail": f"{'Se aplicaría' if preview else 'Aplicado'}: {tweak['label']}",
                "preview": preview,
            })

        # Reiniciar Dock si hubo cambios
        if needs_dock_restart and not preview:
            subprocess.run(["killall", "Dock"], capture_output=True)

        if actions and not preview and all_undo:
            self.undo.save(UndoEntry(
                module=self.name,
                action="apply_ui_tweaks",
                description=f"Aplicados {len(actions)} tweaks de UI",
                undo_commands=all_undo,
            ))

        return FixResult(
            module=self.name,
            actions=actions,
            status="ok",
            summary=f"{len(actions)} tweaks {'previstos' if preview else 'aplicados'}",
            preview_only=preview,
        )

    def _is_tweak_applied(self, tweak: dict) -> bool:
        for cmd in tweak["commands"]:
            try:
                result = subprocess.run(
                    ["defaults", "read", cmd["domain"], cmd["key"]],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode != 0:
                    return False
                current = result.stdout.strip()
                expected = cmd["value"]
                if cmd["type"] == "-bool":
                    current = current.lower() in ("1", "true", "yes")
                    expected = expected.lower() in ("1", "true", "yes")
                if str(current) != str(expected):
                    return False
            except Exception:
                return False
        return True
