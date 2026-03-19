"""Menu Bar App — Icono persistente en la barra de menú de macOS."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
import time

import psutil
import rumps

from macboost.core.config import APP_DIR
from macboost.core.health import calculate_health_score
from macboost.core.orchestrator import Orchestrator

PID_FILE = APP_DIR / "menubar.pid"


# ─── Barras y formatos visuales ───────────────────────────────────────────

def _bar(percent: float, width: int = 12) -> str:
    """Barra de progreso con gradiente visual."""
    filled = int(percent / 100 * width)
    empty = width - filled
    return "▓" * filled + "░" * empty


def _status_dot(percent: float) -> str:
    """Indicador de color según nivel."""
    if percent < 60:
        return "🟢"
    if percent < 80:
        return "🟡"
    return "🔴"


def _score_icon(score: float) -> str:
    """Icono según health score."""
    if score >= 80:
        return "⚡"
    if score >= 60:
        return "⚡"
    return "⚠️"


def _bytes_human(b: int | float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _secs_to_human(secs: int) -> str:
    if secs < 0:
        return "∞"
    h, m = divmod(secs // 60, 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


# ─── Menu Bar App ─────────────────────────────────────────────────────────

class MacBoostMenuBar(rumps.App):

    def __init__(self):
        super().__init__(
            name="MacBoost",
            title="⚡",
            quit_button=None,
        )
        self.orch = Orchestrator()
        self._last_scan = None
        self._build_menu()
        self._start_monitor()

    # ── Construcción del menú ──

    def _build_menu(self):
        # Header
        self.header_item = rumps.MenuItem("⚡ MacBoost          Score: --")
        self.header_item.set_callback(None)

        self.version_item = rumps.MenuItem("    v1.1.0")
        self.version_item.set_callback(None)

        # Métricas
        self.cpu_item = rumps.MenuItem("🖥  CPU     ░░░░░░░░░░░░  --%")
        self.cpu_item.set_callback(None)
        self.ram_item = rumps.MenuItem("🧠  RAM     ░░░░░░░░░░░░  --%")
        self.ram_item.set_callback(None)
        self.ssd_item = rumps.MenuItem("💾  SSD      ░░░░░░░░░░░░  --%")
        self.ssd_item.set_callback(None)
        self.bat_item = rumps.MenuItem("🔋  BAT      ░░░░░░░░░░░░  --%")
        self.bat_item.set_callback(None)
        self.temp_item = rumps.MenuItem("🌡  Temp    --")
        self.temp_item.set_callback(None)
        self.net_item = rumps.MenuItem("🌐  Red      ↑ -- ↓ --")
        self.net_item.set_callback(None)

        # Acciones rápidas
        self.quick_item = rumps.MenuItem("⚡  Optimización Rápida", callback=self._on_quick)
        self.scan_item = rumps.MenuItem("🔍  Escanear Sistema", callback=self._on_scan)
        self.clean_item = rumps.MenuItem("🧹  Limpiar Almacenamiento", callback=self._on_clean)

        # Submenu: Módulos
        self.modules_menu = rumps.MenuItem("🔧  Módulos")
        self.modules_menu.add(rumps.MenuItem("🧠  RAM — Kill Zombies + Purge", callback=self._on_fix_ram))
        self.modules_menu.add(rumps.MenuItem("💾  Storage — Limpiar Cachés", callback=self._on_fix_storage))
        self.modules_menu.add(rumps.MenuItem("🚀  Boot — Gestionar Launch Agents", callback=self._on_fix_boot))
        self.modules_menu.add(rumps.MenuItem("🌐  Network — Optimizar DNS", callback=self._on_fix_network))
        self.modules_menu.add(rumps.MenuItem("🎨  UI — Tweaks Visuales", callback=self._on_fix_ui))

        # Submenu: Energía
        self.power_menu = rumps.MenuItem("🔋  Perfil de Energía")
        self.power_low = rumps.MenuItem("🪶  Low Power — Máxima batería", callback=self._on_power_low)
        self.power_balanced = rumps.MenuItem("⚖️  Balanced — Uso diario", callback=self._on_power_balanced)
        self.power_perf = rumps.MenuItem("🚀  Performance — Máximo rendimiento", callback=self._on_power_perf)
        self.power_menu.add(self.power_low)
        self.power_menu.add(self.power_balanced)
        self.power_menu.add(self.power_perf)
        self.power_balanced.state = True  # Default

        # Submenu: Top procesos
        self.top_menu = rumps.MenuItem("📊  Top Procesos RAM")

        # Info
        self.last_scan_item = rumps.MenuItem("📋  Último escaneo: nunca")
        self.last_scan_item.set_callback(None)

        self.undo_item = rumps.MenuItem("↩️  Deshacer último cambio", callback=self._on_undo)
        self.prefs_item = rumps.MenuItem("⚙️  Preferencias", callback=self._on_preferences)
        self.update_item = rumps.MenuItem("🔄  Buscar Actualizaciones", callback=self._on_check_update)

        self.menu = [
            self.header_item,
            self.version_item,
            None,
            self.cpu_item,
            self.ram_item,
            self.ssd_item,
            self.bat_item,
            self.temp_item,
            self.net_item,
            None,
            self.quick_item,
            self.scan_item,
            self.clean_item,
            None,
            self.modules_menu,
            self.power_menu,
            self.top_menu,
            None,
            self.last_scan_item,
            self.undo_item,
            None,
            self.prefs_item,
            self.update_item,
            None,
            rumps.MenuItem("❌  Salir de MacBoost", callback=self._on_quit),
        ]

    # ── Monitor en tiempo real ──

    def _start_monitor(self):
        self._net_sent_prev = 0
        self._net_recv_prev = 0
        t = threading.Thread(target=self._monitor_loop, daemon=True)
        t.start()

    def _monitor_loop(self):
        while True:
            try:
                self._update_metrics()
                self._update_top_processes()
            except Exception:
                pass
            time.sleep(4)

    def _update_metrics(self):
        # CPU
        cpu_pct = psutil.cpu_percent(interval=1)
        cores = psutil.cpu_count()
        self.cpu_item.title = f"{_status_dot(cpu_pct)}  CPU     {_bar(cpu_pct)}  {cpu_pct:5.1f}%   {cores} cores"

        # RAM
        mem = psutil.virtual_memory()
        ram_used = mem.used / (1024**3)
        ram_total = mem.total / (1024**3)
        self.ram_item.title = f"{_status_dot(mem.percent)}  RAM    {_bar(mem.percent)}  {mem.percent:5.1f}%   {ram_used:.1f}/{ram_total:.0f} GB"

        # SSD
        disk = shutil.disk_usage("/")
        ssd_pct = round((disk.used / disk.total) * 100, 1)
        ssd_free = disk.free / (1024**3)
        self.ssd_item.title = f"{_status_dot(ssd_pct)}  SSD     {_bar(ssd_pct)}  {ssd_pct:5.1f}%   {ssd_free:.0f} GB libres"

        # Battery
        bat = psutil.sensors_battery()
        if bat:
            plug = "⚡" if bat.power_plugged else "🔋"
            time_str = _secs_to_human(bat.secsleft) if not bat.power_plugged and bat.secsleft > 0 else ""
            extra = f"   {time_str}" if time_str else ""
            self.bat_item.title = f"{plug}  BAT     {_bar(bat.percent)}  {bat.percent:5.1f}%{extra}"
        else:
            self.bat_item.title = "🖥  BAT     N/A — Mac de escritorio"

        # Temperature (via powermetrics or ioreg)
        temp = self._get_cpu_temp()
        if temp:
            t_icon = "🟢" if temp < 60 else "🟡" if temp < 80 else "🔴"
            self.temp_item.title = f"🌡  Temp   {t_icon} {temp:.0f}°C"
        else:
            self.temp_item.title = "🌡  Temp    --"

        # Network throughput
        net = psutil.net_io_counters()
        sent_delta = (net.bytes_sent - self._net_sent_prev) if self._net_sent_prev else 0
        recv_delta = (net.bytes_recv - self._net_recv_prev) if self._net_recv_prev else 0
        self._net_sent_prev = net.bytes_sent
        self._net_recv_prev = net.bytes_recv
        # Per second (monitor updates ~every 5s)
        sent_s = sent_delta / 5
        recv_s = recv_delta / 5
        self.net_item.title = f"🌐  Red     ↑ {_bytes_human(sent_s)}/s   ↓ {_bytes_human(recv_s)}/s"

        # Health Score
        try:
            health = calculate_health_score()
            score = health["total"]
            icon = _score_icon(score)
            self.header_item.title = f"⚡ MacBoost          Score: {score:.0f}/100"
            self.title = f"{icon} {score:.0f}"
        except Exception:
            self.header_item.title = "⚡ MacBoost          Score: --"

        # Power profile indicator
        self._update_power_indicator()

    def _update_top_processes(self):
        """Actualiza submenu de top procesos."""
        ram_mod = self.orch.modules.get("ram")
        if not ram_mod:
            return
        procs = ram_mod.get_top_processes(8)
        # Limpiar submenu
        keys = list(self.top_menu.keys())
        for k in keys:
            del self.top_menu[k]
        # Añadir procesos
        for i, p in enumerate(procs):
            icon = "🔴" if p["rss_mb"] > 1000 else "🟡" if p["rss_mb"] > 500 else "⚪"
            label = f"{icon}  {p['name'][:20]:<20}  {p['rss_mb']:>7.0f} MB"
            item = rumps.MenuItem(label)
            item.set_callback(None)
            self.top_menu.add(item)

    def _update_power_indicator(self):
        """Marca el perfil de energía activo."""
        power_mod = self.orch.modules.get("power")
        if not power_mod:
            return
        try:
            status = power_mod.get_current_status()
            profile = status["profile"]
            self.power_low.state = profile == "lowpower"
            self.power_balanced.state = profile == "balanced"
            self.power_perf.state = profile == "performance"
        except Exception:
            pass

    def _get_cpu_temp(self) -> float | None:
        """Intenta obtener temperatura del CPU."""
        try:
            result = subprocess.run(
                ["ioreg", "-r", "-n", "AppleAPMIController"],
                capture_output=True, text=True, timeout=3,
            )
            # Fallback: check SMC temps
            temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
            if temps:
                for name, entries in temps.items():
                    for entry in entries:
                        if entry.current > 0:
                            return entry.current
        except Exception:
            pass
        return None

    # ── Acciones ──

    def _on_quick(self, _):
        rumps.notification("MacBoost", "⚡ Optimización rápida", "Ejecutando purge RAM + flush DNS + limpiar tmp...")
        try:
            results = self.orch.quick_optimize()
            msgs = []
            for name, r in results.items():
                for a in r.actions:
                    if not a.get("skipped"):
                        msgs.append(a["detail"])
            rumps.notification("MacBoost", "✅ Completado", "\n".join(msgs) if msgs else "Optimización aplicada")
        except Exception as e:
            rumps.notification("MacBoost", "❌ Error", str(e))

    def _on_scan(self, _):
        rumps.notification("MacBoost", "🔍 Escaneando...", "Analizando todos los módulos del sistema")
        try:
            report = self.orch.scan_all()
            self._last_scan = report
            from datetime import datetime
            now = datetime.now().strftime("%H:%M")
            self.last_scan_item.title = f"📋  Último escaneo: {now} — {report.total_issues} problemas"

            details = []
            for name, r in report.results.items():
                icon = "✅" if r.status == "ok" else "⚠️" if r.status == "warning" else "ℹ️"
                details.append(f"{icon} {name}: {r.summary}")

            rumps.notification(
                "MacBoost",
                f"🔍 Escaneo completado ({report.duration_seconds:.1f}s)",
                f"{report.total_issues} problemas encontrados\n{report.total_fixable} corregibles",
            )
        except Exception as e:
            rumps.notification("MacBoost", "❌ Error", str(e))

    def _on_clean(self, _):
        storage_mod = self.orch.modules.get("storage")
        if not storage_mod:
            return
        scan = storage_mod.scan()
        if scan.space_recoverable_bytes > 0:
            human = _bytes_human(scan.space_recoverable_bytes)
            resp = rumps.alert(
                title="🧹 Limpiar Almacenamiento",
                message=f"Espacio recuperable: ~{human}\n\n"
                        f"{len(scan.issues)} categorías encontradas:\n" +
                        "\n".join(f"  • {i['description']}" for i in scan.issues[:6]),
                ok="🧹 Limpiar",
                cancel="Cancelar",
            )
            if resp == 1:
                result = storage_mod.fix()
                freed = _bytes_human(result.space_freed_bytes)
                rumps.notification("MacBoost", "✅ Limpieza completada", f"{freed} liberados")
        else:
            rumps.notification("MacBoost", "💾 Almacenamiento", "Todo limpio — nada que recuperar")

    # Módulos individuales
    def _on_fix_ram(self, _):
        self._run_module_fix("ram", "🧠 RAM")

    def _on_fix_storage(self, _):
        self._run_module_fix("storage", "💾 Storage")

    def _on_fix_boot(self, _):
        self._run_module_fix("boot", "🚀 Boot")

    def _on_fix_network(self, _):
        self._run_module_fix("network", "🌐 Network")

    def _on_fix_ui(self, _):
        self._run_module_fix("ui", "🎨 UI")

    def _run_module_fix(self, name: str, label: str):
        mod = self.orch.modules.get(name)
        if not mod:
            rumps.notification("MacBoost", label, "Módulo no disponible")
            return
        # Preview primero
        preview = mod.fix(preview=True)
        if not preview.actions:
            rumps.notification("MacBoost", label, "No hay acciones pendientes")
            return
        msg = "\n".join(f"  • {a['detail']}" for a in preview.actions[:8])
        resp = rumps.alert(
            title=f"{label} — Preview",
            message=f"Se ejecutarán {len(preview.actions)} acciones:\n\n{msg}",
            ok="✅ Aplicar",
            cancel="Cancelar",
        )
        if resp == 1:
            result = mod.fix(preview=False)
            rumps.notification("MacBoost", f"✅ {label}", result.summary)

    # Perfiles de energía
    def _on_power_low(self, _):
        self._set_power("lowpower", "🪶 Low Power")

    def _on_power_balanced(self, _):
        self._set_power("balanced", "⚖️ Balanced")

    def _on_power_perf(self, _):
        self._set_power("performance", "🚀 Performance")

    def _set_power(self, profile: str, label: str):
        power = self.orch.modules.get("power")
        if power:
            result = power.set_profile(profile)
            rumps.notification("MacBoost", f"🔋 Perfil: {label}", result.summary)
            self._update_power_indicator()

    # Undo
    def _on_undo(self, _):
        latest = self.orch.undo.get_latest()
        if not latest:
            rumps.notification("MacBoost", "↩️ Undo", "No hay cambios para deshacer")
            return
        resp = rumps.alert(
            title="↩️ Deshacer último cambio",
            message=f"Operación: {latest.description}\nMódulo: {latest.module}\nID: {latest.id}",
            ok="↩️ Deshacer",
            cancel="Cancelar",
        )
        if resp == 1:
            success, msg = self.orch.undo.execute_undo(latest.id)
            icon = "✅" if success else "❌"
            rumps.notification("MacBoost", f"{icon} Undo", msg)

    # Preferencias
    def _on_preferences(self, _):
        config_path = str(APP_DIR / "config.toml")
        rumps.alert(
            title="⚙️ Preferencias de MacBoost",
            message=f"Configuración:\n{config_path}\n\n"
                    "Puedes editarlo con cualquier editor de texto.\n\n"
                    "CLI: macboost --help para ver todos los comandos",
            ok="📂 Abrir en Finder",
            cancel="Cerrar",
        )
        subprocess.run(["open", str(APP_DIR)], capture_output=True)

    # Update check
    def _on_check_update(self, _):
        try:
            from macboost.core.updater import check_update
            info = check_update()
            if info["available"]:
                resp = rumps.alert(
                    title="🔄 Actualización disponible",
                    message=f"Nueva versión: v{info['latest']}\nVersión actual: v{info['current']}\n\n"
                            "Ejecuta en terminal:\nmacboost update",
                    ok="OK",
                )
            else:
                rumps.notification("MacBoost", "✅ Actualizado", info["message"])
        except Exception:
            rumps.notification("MacBoost", "🔄 Update", "No se pudo verificar")

    # Quit
    def _on_quit(self, _):
        # Limpiar PID file
        PID_FILE.unlink(missing_ok=True)
        rumps.quit_application()


# ─── Daemon / Launcher ────────────────────────────────────────────────────

def _write_pid():
    """Escribe el PID actual al archivo."""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def _is_running() -> bool:
    """Verifica si ya hay una instancia corriendo."""
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # Check if process exists
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        PID_FILE.unlink(missing_ok=True)
        return False


def start_daemon():
    """Lanza el menubar como proceso independiente que sobrevive al cierre de terminal."""
    if _is_running():
        pid = int(PID_FILE.read_text().strip())
        print(f"MacBoost ya está corriendo (PID: {pid})")
        return

    # Usar nohup para sobrevivir al cierre de terminal SIN perder
    # acceso al WindowServer de macOS (necesario para el icono de menú).
    # No usamos setsid/start_new_session porque crean una sesión nueva
    # desconectada del display server.
    python_exec = sys.executable
    log_file = APP_DIR / "menubar.log"
    APP_DIR.mkdir(parents=True, exist_ok=True)

    script = (
        "import signal; "
        "signal.signal(signal.SIGHUP, signal.SIG_IGN); "
        "from macboost.menubar.app import run_menubar; "
        "run_menubar()"
    )

    with open(log_file, "a") as log:
        proc = subprocess.Popen(
            [python_exec, "-c", script],
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
        )

    PID_FILE.write_text(str(proc.pid))

    print(f"⚡ MacBoost iniciado en segundo plano (PID: {proc.pid})")
    print("   Busca el icono ⚡ en tu barra de menú")
    print("   Para detener: macboost menubar stop")


def stop_daemon():
    """Detiene el daemon del menubar."""
    if not PID_FILE.exists():
        # Intentar buscar por nombre de proceso
        try:
            result = subprocess.run(
                ["pgrep", "-f", "macboost.menubar"],
                capture_output=True, text=True,
            )
            if result.stdout.strip():
                for pid in result.stdout.strip().splitlines():
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                print("⚡ MacBoost detenido")
                return
        except Exception:
            pass
        print("MacBoost no está corriendo")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink(missing_ok=True)
        print(f"⚡ MacBoost detenido (PID: {pid})")
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        print("MacBoost no estaba corriendo")
    except Exception as e:
        print(f"Error deteniendo MacBoost: {e}")


def daemon_status() -> dict:
    """Devuelve estado del daemon."""
    running = _is_running()
    pid = None
    if running and PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
    return {"running": running, "pid": pid}


def run_menubar():
    """Ejecuta la app directamente (usado por el daemon)."""
    _write_pid()
    signal.signal(signal.SIGHUP, signal.SIG_IGN)  # Ignorar SIGHUP
    MacBoostMenuBar().run()
