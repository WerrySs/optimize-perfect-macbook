"""Updater — Sistema de versiones y auto-actualización."""

from __future__ import annotations

import subprocess
import urllib.request
import json
from packaging.version import Version

from macboost import __version__

REPO_OWNER = "WerrySs"
REPO_NAME = "optimize-perfect-macbook"
VERSION_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/macboost/VERSION"
RELEASES_API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git"


def get_current_version() -> str:
    return __version__


def get_remote_version() -> str | None:
    """Consulta la última versión publicada en el repo."""
    try:
        req = urllib.request.Request(VERSION_URL, headers={"User-Agent": "MacBoost"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read().decode().strip()
    except Exception:
        pass

    # Fallback: GitHub Releases API
    try:
        req = urllib.request.Request(RELEASES_API, headers={"User-Agent": "MacBoost"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "")
            return tag.lstrip("v")
    except Exception:
        return None


def check_update() -> dict:
    """Verifica si hay una actualización disponible.

    Returns:
        dict con keys: available (bool), current, latest, message
    """
    current = get_current_version()
    latest = get_remote_version()

    if latest is None:
        return {
            "available": False,
            "current": current,
            "latest": None,
            "message": "No se pudo verificar actualizaciones (sin conexión o repo no accesible)",
        }

    try:
        is_newer = Version(latest) > Version(current)
    except Exception:
        is_newer = latest != current

    if is_newer:
        return {
            "available": True,
            "current": current,
            "latest": latest,
            "message": f"Nueva versión disponible: {latest} (actual: {current}). Ejecuta: macboost update",
        }

    return {
        "available": False,
        "current": current,
        "latest": latest,
        "message": f"MacBoost está actualizado (v{current})",
    }


def perform_update(force: bool = False) -> tuple[bool, str]:
    """Ejecuta la actualización de MacBoost.

    Intenta con pipx primero, luego pip.
    Returns: (éxito, mensaje)
    """
    update_info = check_update()
    if not update_info["available"] and not force:
        return True, update_info["message"]

    latest = update_info["latest"] or "latest"

    # Intentar con pipx
    if _has_command("pipx"):
        return _update_pipx()

    # Fallback: pip
    if _has_command("pip3"):
        return _update_pip()

    return False, "No se encontró pipx ni pip3. Instala pipx con: brew install pipx"


def _update_pipx() -> tuple[bool, str]:
    """Actualiza via pipx reinstall desde el repo."""
    try:
        # pipx no tiene "upgrade from git", así que reinstalamos
        result = subprocess.run(
            ["pipx", "install", "--force",
             f"git+{REPO_URL}#subdirectory=macboost"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            # Leer nueva versión
            new_ver = _get_installed_version()
            return True, f"MacBoost actualizado a v{new_ver}"
        return False, f"Error actualizando: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "Timeout durante la actualización"
    except Exception as e:
        return False, f"Error: {e}"


def _update_pip() -> tuple[bool, str]:
    """Actualiza via pip install --upgrade desde el repo."""
    try:
        install_url = f"git+{REPO_URL}#subdirectory=macboost"
        # Probar distintas variantes de pip install
        for cmd in [
            ["pip3", "install", "--user", "--break-system-packages", "--upgrade", install_url],
            ["pip3", "install", "--user", "--upgrade", install_url],
            ["pip3", "install", "--upgrade", install_url],
        ]:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                new_ver = _get_installed_version()
                return True, f"MacBoost actualizado a v{new_ver}"
        return False, f"Error actualizando con pip: {result.stderr.strip()}"
    except Exception as e:
        return False, f"Error: {e}"


def _has_command(cmd: str) -> bool:
    try:
        subprocess.run(["which", cmd], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _get_installed_version() -> str:
    """Lee la versión instalada tras actualizar."""
    try:
        result = subprocess.run(
            ["macboost", "version", "--short"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or "desconocida"
    except Exception:
        return "desconocida"
