"""Undo Engine — Snapshots JSON para revertir cualquier cambio."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from macboost.core.config import SNAPSHOTS_DIR


class UndoEntry:
    """Representa una operación reversible."""

    def __init__(
        self,
        module: str,
        action: str,
        description: str,
        undo_commands: list[dict],
        entry_id: str | None = None,
        timestamp: float | None = None,
    ):
        self.id = entry_id or uuid.uuid4().hex[:8]
        self.module = module
        self.action = action
        self.description = description
        self.undo_commands = undo_commands
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "module": self.module,
            "action": self.action,
            "description": self.description,
            "undo_commands": self.undo_commands,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> UndoEntry:
        return cls(
            entry_id=data["id"],
            module=data["module"],
            action=data["action"],
            description=data["description"],
            undo_commands=data["undo_commands"],
            timestamp=data["timestamp"],
        )


class UndoEngine:
    """Gestiona el historial de operaciones reversibles."""

    def __init__(self):
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    def save(self, entry: UndoEntry) -> str:
        filepath = SNAPSHOTS_DIR / f"{entry.id}.json"
        with open(filepath, "w") as f:
            json.dump(entry.to_dict(), f, indent=2)
        return entry.id

    def list_entries(self, limit: int = 20) -> list[UndoEntry]:
        entries = []
        for filepath in sorted(SNAPSHOTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            with open(filepath) as f:
                data = json.load(f)
            entries.append(UndoEntry.from_dict(data))
            if len(entries) >= limit:
                break
        return entries

    def get_entry(self, entry_id: str) -> UndoEntry | None:
        filepath = SNAPSHOTS_DIR / f"{entry_id}.json"
        if not filepath.exists():
            return None
        with open(filepath) as f:
            data = json.load(f)
        return UndoEntry.from_dict(data)

    def get_latest(self) -> UndoEntry | None:
        entries = self.list_entries(limit=1)
        return entries[0] if entries else None

    def execute_undo(self, entry_id: str) -> tuple[bool, str]:
        """Ejecuta el undo de una operación. Retorna (éxito, mensaje)."""
        import subprocess

        entry = self.get_entry(entry_id)
        if not entry:
            return False, f"No se encontró la entrada con ID: {entry_id}"

        errors = []
        for cmd_info in entry.undo_commands:
            cmd_type = cmd_info.get("type", "shell")
            try:
                if cmd_type == "shell":
                    subprocess.run(
                        cmd_info["command"],
                        shell=True,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                elif cmd_type == "defaults_write":
                    domain = cmd_info["domain"]
                    key = cmd_info["key"]
                    value = cmd_info["value"]
                    value_type = cmd_info.get("value_type", "-string")
                    subprocess.run(
                        ["defaults", "write", domain, key, value_type, str(value)],
                        check=True,
                        capture_output=True,
                    )
                elif cmd_type == "defaults_delete":
                    domain = cmd_info["domain"]
                    key = cmd_info["key"]
                    subprocess.run(
                        ["defaults", "delete", domain, key],
                        check=True,
                        capture_output=True,
                    )
                elif cmd_type == "launchctl_load":
                    subprocess.run(
                        ["launchctl", "load", "-w", cmd_info["plist"]],
                        check=True,
                        capture_output=True,
                    )
                elif cmd_type == "launchctl_unload":
                    subprocess.run(
                        ["launchctl", "unload", "-w", cmd_info["plist"]],
                        check=True,
                        capture_output=True,
                    )
            except subprocess.CalledProcessError as e:
                errors.append(f"Error en '{cmd_info}': {e.stderr or e}")

        # Eliminar snapshot tras undo exitoso
        filepath = SNAPSHOTS_DIR / f"{entry_id}.json"
        if not errors:
            filepath.unlink(missing_ok=True)
            return True, f"Undo completado: {entry.description}"
        return False, f"Undo parcial con errores: {'; '.join(errors)}"

    def clear_history(self):
        for filepath in SNAPSHOTS_DIR.glob("*.json"):
            filepath.unlink()
