"""Health Score — Cálculo de la puntuación de salud del sistema (0-100)."""

from __future__ import annotations

import shutil
import subprocess

import psutil


def get_cpu_score() -> float:
    """Score basado en uso de CPU (100 = idle, 0 = 100% uso)."""
    usage = psutil.cpu_percent(interval=1)
    return max(0.0, 100.0 - usage)


def get_ram_score() -> float:
    """Score basado en presión de memoria."""
    mem = psutil.virtual_memory()
    used_percent = mem.percent
    if used_percent < 60:
        return 100.0
    if used_percent < 80:
        return 100.0 - ((used_percent - 60) * 2.5)
    return max(0.0, 100.0 - ((used_percent - 60) * 2.5))


def get_ssd_score() -> float:
    """Score basado en espacio libre en disco."""
    usage = shutil.disk_usage("/")
    free_percent = (usage.free / usage.total) * 100
    if free_percent > 30:
        return 100.0
    if free_percent > 10:
        return 50.0 + (free_percent - 10) * 2.5
    return max(0.0, free_percent * 5.0)


def get_boot_score() -> float:
    """Score basado en cantidad de Launch Agents activos."""
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=10,
        )
        agent_count = len(result.stdout.strip().splitlines()) - 1
        if agent_count < 80:
            return 100.0
        if agent_count < 150:
            return 100.0 - ((agent_count - 80) * 0.7)
        return max(0.0, 100.0 - ((agent_count - 80) * 0.7))
    except Exception:
        return 70.0


def get_network_score() -> float:
    """Score basado en latencia DNS."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-t", "3", "1.1.1.1"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if "time=" in line:
                time_ms = float(line.split("time=")[1].split()[0])
                if time_ms < 20:
                    return 100.0
                if time_ms < 50:
                    return 90.0
                if time_ms < 100:
                    return 70.0
                return max(0.0, 100.0 - time_ms)
        return 50.0
    except Exception:
        return 50.0


def get_battery_score() -> float:
    """Score basado en salud de batería."""
    battery = psutil.sensors_battery()
    if battery is None:
        return 100.0  # Desktop Mac, no aplica
    percent = battery.percent
    if percent > 50:
        return 100.0
    return percent * 2.0


def calculate_health_score() -> dict:
    """Calcula el Health Score ponderado (0-100).

    Score = (RAM × 0.25) + (CPU × 0.20) + (SSD × 0.20)
          + (Boot × 0.15) + (Network × 0.10) + (Battery × 0.10)
    """
    scores = {
        "cpu": get_cpu_score(),
        "ram": get_ram_score(),
        "ssd": get_ssd_score(),
        "boot": get_boot_score(),
        "network": get_network_score(),
        "battery": get_battery_score(),
    }

    weights = {
        "ram": 0.25,
        "cpu": 0.20,
        "ssd": 0.20,
        "boot": 0.15,
        "network": 0.10,
        "battery": 0.10,
    }

    total = sum(scores[k] * weights[k] for k in weights)

    return {
        "total": round(total, 1),
        "scores": {k: round(v, 1) for k, v in scores.items()},
        "weights": weights,
    }
