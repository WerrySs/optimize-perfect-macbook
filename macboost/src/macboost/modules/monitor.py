"""Módulo Health Monitor — Métricas del sistema y reportes."""

from __future__ import annotations

import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import psutil

from macboost.core.config import REPORTS_DIR
from macboost.modules.base import BaseModule, FixResult, ScanResult


class MonitorModule(BaseModule):
    name = "monitor"
    description = "Health Monitor"
    priority = "automatizado"

    def scan(self) -> ScanResult:
        metrics = self.collect_metrics()
        issues = []

        if metrics["ram"]["percent"] > self.config.get("alert_ram_percent", 90):
            issues.append({
                "type": "ram_critical",
                "description": f"RAM al {metrics['ram']['percent']}%",
                "severity": "high",
                "fixable": False,
            })

        ssd_used_pct = (1 - metrics["ssd"]["free"] / metrics["ssd"]["total"]) * 100
        if ssd_used_pct > self.config.get("alert_ssd_percent", 90):
            issues.append({
                "type": "ssd_critical",
                "description": f"SSD al {ssd_used_pct:.0f}% de uso",
                "severity": "high",
                "fixable": False,
            })

        return ScanResult(
            module=self.name,
            issues=issues,
            status="warning" if issues else "ok",
            summary=f"Monitor: CPU {metrics['cpu']['percent']}%, RAM {metrics['ram']['percent']}%",
        )

    def fix(self, preview: bool = False) -> FixResult:
        # Monitor no tiene "fix", solo genera reportes
        report_path = self.generate_report()
        return FixResult(
            module=self.name,
            actions=[{"action": "generate_report", "detail": f"Reporte generado: {report_path}"}],
            status="ok",
            summary=f"Reporte guardado en {report_path}",
        )

    def collect_metrics(self) -> dict:
        """Recopila todas las métricas del sistema."""
        cpu = self._get_cpu_metrics()
        ram = self._get_ram_metrics()
        ssd = self._get_ssd_metrics()
        battery = self._get_battery_metrics()
        network = self._get_network_metrics()

        return {
            "timestamp": time.time(),
            "cpu": cpu,
            "ram": ram,
            "ssd": ssd,
            "battery": battery,
            "network": network,
        }

    def generate_report(self) -> str:
        """Genera un reporte HTML de salud del sistema."""
        metrics = self.collect_metrics()
        now = datetime.now()
        filename = f"report_{now.strftime('%Y%m%d_%H%M%S')}.html"
        filepath = REPORTS_DIR / filename

        html = self._render_report_html(metrics, now)
        filepath.write_text(html)
        return str(filepath)

    def _get_cpu_metrics(self) -> dict:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        cpu_count = psutil.cpu_count()
        per_cpu = psutil.cpu_percent(percpu=True)
        freq = psutil.cpu_freq()

        return {
            "percent": cpu_percent,
            "cores": cpu_count,
            "per_core": per_cpu,
            "freq_current": freq.current if freq else 0,
            "freq_max": freq.max if freq else 0,
        }

    def _get_ram_metrics(self) -> dict:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "total": mem.total,
            "available": mem.available,
            "used": mem.used,
            "percent": mem.percent,
            "swap_total": swap.total,
            "swap_used": swap.used,
            "swap_percent": swap.percent,
        }

    def _get_ssd_metrics(self) -> dict:
        usage = shutil.disk_usage("/")
        return {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": round((usage.used / usage.total) * 100, 1),
        }

    def _get_battery_metrics(self) -> dict:
        battery = psutil.sensors_battery()
        if battery is None:
            return {"available": False}

        # Ciclos de carga desde ioreg
        cycles = self._get_battery_cycles()

        return {
            "available": True,
            "percent": battery.percent,
            "power_plugged": battery.power_plugged,
            "secs_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else -1,
            "cycles": cycles,
        }

    def _get_battery_cycles(self) -> int:
        try:
            result = subprocess.run(
                ["ioreg", "-r", "-c", "AppleSmartBattery"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.splitlines():
                if "CycleCount" in line:
                    return int(line.split("=")[-1].strip())
        except Exception:
            pass
        return 0

    def _get_network_metrics(self) -> dict:
        net_io = psutil.net_io_counters()
        return {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
        }

    def _render_report_html(self, metrics: dict, timestamp: datetime) -> str:
        ram = metrics["ram"]
        cpu = metrics["cpu"]
        ssd = metrics["ssd"]
        bat = metrics["battery"]

        ram_gb_used = ram["used"] / (1024**3)
        ram_gb_total = ram["total"] / (1024**3)
        ssd_gb_free = ssd["free"] / (1024**3)
        ssd_gb_total = ssd["total"] / (1024**3)

        battery_section = ""
        if bat.get("available"):
            battery_section = f"""
            <div class="metric">
                <h3>Batería</h3>
                <div class="bar"><div class="fill" style="width:{bat['percent']}%"></div></div>
                <p>{bat['percent']}% — {bat.get('cycles', 'N/A')} ciclos — {'Cargando' if bat.get('power_plugged') else 'Batería'}</p>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>MacBoost — Reporte de Salud</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'SF Pro', sans-serif; background: #1a1a2e; color: #eee; padding: 40px; }}
        h1 {{ color: #00d4ff; margin-bottom: 8px; }}
        h2 {{ color: #aaa; font-weight: 400; margin-bottom: 30px; font-size: 14px; }}
        h3 {{ color: #00d4ff; margin-bottom: 10px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        .metric {{ background: #16213e; border-radius: 12px; padding: 20px; }}
        .bar {{ background: #333; border-radius: 8px; height: 20px; overflow: hidden; margin: 10px 0; }}
        .fill {{ background: linear-gradient(90deg, #00d4ff, #0099ff); height: 100%; border-radius: 8px; transition: width 0.3s; }}
        .fill.warn {{ background: linear-gradient(90deg, #ffaa00, #ff6600); }}
        .fill.crit {{ background: linear-gradient(90deg, #ff4444, #cc0000); }}
        p {{ color: #aaa; font-size: 14px; }}
        .footer {{ margin-top: 40px; text-align: center; color: #555; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>⚡ MacBoost — Reporte de Salud</h1>
    <h2>{timestamp.strftime('%d/%m/%Y %H:%M:%S')}</h2>
    <div class="metrics">
        <div class="metric">
            <h3>CPU</h3>
            <div class="bar"><div class="fill{'  warn' if cpu['percent'] > 70 else ''}" style="width:{cpu['percent']}%"></div></div>
            <p>{cpu['percent']}% uso — {cpu['cores']} cores</p>
        </div>
        <div class="metric">
            <h3>RAM</h3>
            <div class="bar"><div class="fill{' warn' if ram['percent'] > 70 else ''}{' crit' if ram['percent'] > 90 else ''}" style="width:{ram['percent']}%"></div></div>
            <p>{ram['percent']}% — {ram_gb_used:.1f} GB / {ram_gb_total:.1f} GB</p>
        </div>
        <div class="metric">
            <h3>SSD</h3>
            <div class="bar"><div class="fill" style="width:{ssd['percent']}%"></div></div>
            <p>{ssd['percent']}% usado — {ssd_gb_free:.0f} GB libres de {ssd_gb_total:.0f} GB</p>
        </div>
        {battery_section}
    </div>
    <div class="footer">
        <p>Generado por MacBoost v1.0.0</p>
    </div>
</body>
</html>"""
