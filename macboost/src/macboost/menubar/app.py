"""Menu Bar App — Icono persistente en la barra de menú de macOS."""

from __future__ import annotations

import threading
import time
import webbrowser

import psutil
import rumps

from macboost.core.health import calculate_health_score
from macboost.core.orchestrator import Orchestrator


class MacBoostMenuBar(rumps.App):
    """App de barra de menú para MacBoost."""

    def __init__(self):
        super().__init__(
            name="MacBoost",
            title="⚡",
            quit_button=None,
        )
        self.orch = Orchestrator()
        self._build_menu()
        self._start_monitor()

    def _build_menu(self):
        self.score_item = rumps.MenuItem("Score: --", callback=None)
        self.score_item.set_callback(None)

        self.cpu_item = rumps.MenuItem("CPU: --")
        self.cpu_item.set_callback(None)
        self.ram_item = rumps.MenuItem("RAM: --")
        self.ram_item.set_callback(None)
        self.ssd_item = rumps.MenuItem("SSD: --")
        self.ssd_item.set_callback(None)
        self.bat_item = rumps.MenuItem("BAT: --")
        self.bat_item.set_callback(None)

        self.menu = [
            self.score_item,
            None,  # separator
            self.cpu_item,
            self.ram_item,
            self.ssd_item,
            self.bat_item,
            None,
            rumps.MenuItem("Optimización Rápida", callback=self.on_quick_optimize),
            rumps.MenuItem("Escanear Sistema", callback=self.on_scan),
            rumps.MenuItem("Limpiar Almacenamiento", callback=self.on_clean_storage),
            None,
            rumps.MenuItem("Dashboard Web", callback=self.on_open_dashboard),
            rumps.MenuItem("Preferencias", callback=self.on_preferences),
            None,
            rumps.MenuItem("Salir", callback=self.on_quit),
        ]

    def _start_monitor(self):
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _monitor_loop(self):
        while True:
            try:
                self._update_metrics()
            except Exception:
                pass
            time.sleep(5)

    def _update_metrics(self):
        # CPU
        cpu_pct = psutil.cpu_percent(interval=1)
        self.cpu_item.title = f"CPU  {self._bar(cpu_pct)}  {cpu_pct}%"

        # RAM
        mem = psutil.virtual_memory()
        ram_gb = mem.used / (1024**3)
        self.ram_item.title = f"RAM  {self._bar(mem.percent)}  {mem.percent}%  {ram_gb:.1f} GB"

        # SSD
        import shutil
        disk = shutil.disk_usage("/")
        ssd_pct = round((disk.used / disk.total) * 100, 1)
        ssd_free_gb = disk.free / (1024**3)
        self.ssd_item.title = f"SSD  {self._bar(ssd_pct)}  {ssd_pct}%  {ssd_free_gb:.0f} GB libres"

        # Battery
        bat = psutil.sensors_battery()
        if bat:
            self.bat_item.title = f"BAT  {self._bar(bat.percent)}  {bat.percent}%"
        else:
            self.bat_item.title = "BAT  N/A (Desktop)"

        # Health Score
        try:
            health = calculate_health_score()
            score = health["total"]
            self.score_item.title = f"⚡ MacBoost    Score: {score:.0f}"

            # Actualizar icono según estado
            if score >= 80:
                self.title = "⚡"
            elif score >= 60:
                self.title = "⚡"  # En una app real, cambiaríamos el color del icono
            else:
                self.title = "⚠️"
        except Exception:
            self.score_item.title = "⚡ MacBoost    Score: --"

    def _bar(self, percent: float, width: int = 10) -> str:
        filled = int(percent / 100 * width)
        return "█" * filled + "░" * (width - filled)

    @rumps.clicked("Optimización Rápida")
    def on_quick_optimize(self, _):
        rumps.notification(
            title="MacBoost",
            subtitle="Optimización rápida",
            message="Ejecutando...",
        )
        try:
            results = self.orch.quick_optimize()
            summaries = [r.summary for r in results.values()]
            rumps.notification(
                title="MacBoost",
                subtitle="✓ Optimización completada",
                message="; ".join(summaries),
            )
        except Exception as e:
            rumps.notification("MacBoost", "Error", str(e))

    @rumps.clicked("Escanear Sistema")
    def on_scan(self, _):
        rumps.notification("MacBoost", "Escaneo", "Escaneando sistema...")
        try:
            report = self.orch.scan_all()
            rumps.notification(
                title="MacBoost",
                subtitle=f"Escaneo completado ({report.duration_seconds:.1f}s)",
                message=f"{report.total_issues} problemas, {report.total_fixable} corregibles",
            )
        except Exception as e:
            rumps.notification("MacBoost", "Error", str(e))

    @rumps.clicked("Limpiar Almacenamiento")
    def on_clean_storage(self, _):
        storage_mod = self.orch.modules.get("storage")
        if storage_mod:
            scan = storage_mod.scan()
            if scan.space_recoverable_bytes > 0:
                human_size = storage_mod._bytes_to_human(scan.space_recoverable_bytes)
                response = rumps.alert(
                    title="Limpiar Almacenamiento",
                    message=f"Se pueden recuperar ~{human_size}. ¿Continuar?",
                    ok="Limpiar",
                    cancel="Cancelar",
                )
                if response == 1:  # OK
                    result = storage_mod.fix()
                    rumps.notification("MacBoost", "✓ Limpieza completada", result.summary)
            else:
                rumps.notification("MacBoost", "Almacenamiento", "No se encontraron archivos para limpiar")

    @rumps.clicked("Dashboard Web")
    def on_open_dashboard(self, _):
        webbrowser.open("http://localhost:7777")
        # Iniciar servidor en background si no está corriendo
        threading.Thread(target=self._start_dashboard, daemon=True).start()

    @rumps.clicked("Preferencias")
    def on_preferences(self, _):
        rumps.alert(
            title="MacBoost — Preferencias",
            message="Edita la configuración en:\n~/.macboost/config.toml\n\nO usa la CLI:\nmacboost config",
        )

    @rumps.clicked("Salir")
    def on_quit(self, _):
        rumps.quit_application()

    def _start_dashboard(self):
        try:
            from macboost.dashboard.server import start_server
            start_server()
        except Exception:
            pass


def run_menubar():
    MacBoostMenuBar().run()
