"""WebSocket para métricas en tiempo real."""

from __future__ import annotations

import asyncio
import json
import shutil
import time

import psutil
from fastapi import WebSocket, WebSocketDisconnect

from macboost.core.health import calculate_health_score


class MetricsManager:
    """Gestiona las conexiones WebSocket para métricas en tiempo real."""

    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.connections.remove(websocket)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.connections.remove(ws)

    def collect_metrics(self) -> dict:
        cpu_pct = psutil.cpu_percent(interval=0)
        mem = psutil.virtual_memory()
        disk = shutil.disk_usage("/")
        battery = psutil.sensors_battery()
        net = psutil.net_io_counters()

        try:
            health = calculate_health_score()
            score = health["total"]
        except Exception:
            score = 0

        return {
            "timestamp": time.time(),
            "score": score,
            "cpu": {
                "percent": cpu_pct,
                "per_core": psutil.cpu_percent(percpu=True),
            },
            "ram": {
                "percent": mem.percent,
                "used_gb": round(mem.used / (1024**3), 2),
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
            },
            "ssd": {
                "percent": round((disk.used / disk.total) * 100, 1),
                "free_gb": round(disk.free / (1024**3), 1),
                "total_gb": round(disk.total / (1024**3), 1),
            },
            "battery": {
                "percent": battery.percent if battery else None,
                "plugged": battery.power_plugged if battery else None,
            },
            "network": {
                "sent_mb": round(net.bytes_sent / (1024**2), 1),
                "recv_mb": round(net.bytes_recv / (1024**2), 1),
            },
        }


metrics_manager = MetricsManager()


async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket que envía métricas cada 2 segundos."""
    await metrics_manager.connect(websocket)
    try:
        while True:
            data = metrics_manager.collect_metrics()
            await websocket.send_json(data)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        metrics_manager.disconnect(websocket)
    except Exception:
        metrics_manager.disconnect(websocket)
