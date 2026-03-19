"""Menu Bar App — Panel visual estilo Healthy con PyObjC + NSPopover + WKWebView."""

from __future__ import annotations

import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time

import objc
import psutil
from AppKit import (
    NSApplication,
    NSAppearance,
    NSPopover,
    NSStatusBar,
    NSVariableStatusItemLength,
    NSViewController,
)
from Foundation import NSMakeRect, NSMakeSize, NSObject, NSTimer
from WebKit import WKWebView, WKWebViewConfiguration, WKUserContentController

from macboost.core.config import APP_DIR
from macboost.core.health import calculate_health_score
from macboost.core.orchestrator import Orchestrator

PID_FILE = APP_DIR / "menubar.pid"


# ── Helpers ──────────────────────────────────────────────────────────────

def _bytes_human(b: int | float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _get_mac_name() -> str:
    try:
        r = subprocess.run(["scutil", "--get", "ComputerName"],
                           capture_output=True, text=True, timeout=3)
        name = r.stdout.strip()
        if name:
            return name
    except Exception:
        pass
    return platform.node() or "Mac"


def _get_cpu_temp() -> float | None:
    try:
        temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        for entries in temps.values():
            for entry in entries:
                if entry.current > 0:
                    return entry.current
    except Exception:
        pass
    return None


def _get_battery_details() -> tuple[int | None, str]:
    try:
        r = subprocess.run(
            ["ioreg", "-l", "-w0", "-r", "-c", "AppleSmartBattery"],
            capture_output=True, text=True, timeout=3,
        )
        cycles = None
        for line in r.stdout.splitlines():
            if '"CycleCount"' in line:
                cycles = int(line.split("=")[1].strip())
                break
        return cycles, "Normal"
    except Exception:
        return None, "Unknown"


def _notify(title: str, message: str):
    safe_msg = message.replace('"', '\\"').replace("'", "\\'")
    subprocess.Popen([
        "osascript", "-e",
        f'display notification "{safe_msg}" with title "{title}"',
    ])


# ── HTML Panel ───────────────────────────────────────────────────────────

def _build_html(mac_name: str, version: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Helvetica Neue', sans-serif;
    font-size: 13px; color: #f5f5f7; background: transparent;
    padding: 16px 18px; user-select: none; -webkit-user-select: none;
    -webkit-font-smoothing: antialiased;
}}

/* Header */
.hdr {{ display:flex; justify-content:space-between; align-items:center; }}
.mac {{ font-size:15px; font-weight:600; }}
.badge {{
    font-size:11px; font-weight:600; padding:3px 10px; border-radius:12px;
    display:inline-flex; align-items:center; gap:4px;
}}
.badge.g {{ background:#30d158; color:#fff; }}
.badge.y {{ background:#ffd60a; color:#1c1c1e; }}
.badge.r {{ background:#ff453a; color:#fff; }}
.sub {{ font-size:11px; color:#86868b; margin:3px 0 0; }}
.ver {{ font-size:10px; color:#6e6e73; margin-top:1px; }}

.sep {{ height:1px; background:rgba(255,255,255,0.08); margin:12px 0; }}

/* Metric rows */
.mr {{ display:flex; align-items:center; padding:5px 0; }}
.mr .ic {{ width:22px; font-size:13px; flex-shrink:0; }}
.mr .lb {{ flex:1; color:#d1d1d6; font-size:13px; }}
.mr .vl {{ color:#f5f5f7; font-weight:500; font-variant-numeric:tabular-nums; font-size:13px; }}
.mr .vl.g {{ color:#30d158; }}
.mr .vl.y {{ color:#ffd60a; }}
.mr .vl.r {{ color:#ff453a; }}

/* Progress bar metrics */
.mb {{ padding:6px 0 2px; }}
.mb .info {{ display:flex; align-items:center; margin-bottom:5px; }}
.mb .ic {{ width:22px; font-size:13px; flex-shrink:0; }}
.mb .lb {{ flex:1; color:#d1d1d6; }}
.mb .vl {{ color:#98989d; font-size:11px; font-variant-numeric:tabular-nums; }}
.trk {{
    height:6px; background:rgba(255,255,255,0.08); border-radius:3px;
    overflow:hidden;
}}
.fill {{
    height:100%; border-radius:3px;
    transition: width 0.6s ease, background 0.3s ease;
}}
.fill.g {{ background: linear-gradient(90deg, #30d158, #34c759); }}
.fill.y {{ background: linear-gradient(90deg, #ffd60a, #ff9f0a); }}
.fill.r {{ background: linear-gradient(90deg, #ff6961, #ff453a); }}

/* Battery section */
.stitle {{ font-size:12px; font-weight:600; color:#86868b; margin-bottom:6px; display:flex; align-items:center; gap:5px; }}
.br {{ display:flex; justify-content:space-between; padding:2px 0; font-size:12px; }}
.br .lb {{ color:#86868b; }}
.br .vl {{ color:#f5f5f7; font-weight:500; }}

/* Actions */
.acts {{ display:flex; flex-direction:column; gap:5px; }}
.abtn {{
    display:flex; align-items:center; padding:8px 11px;
    background:rgba(255,255,255,0.06); border:none; border-radius:8px;
    color:#e5e5ea; font-size:13px; cursor:pointer;
    transition: background 0.15s; font-family:inherit;
}}
.abtn:hover {{ background:rgba(255,255,255,0.12); }}
.abtn:active {{ background:rgba(255,255,255,0.16); }}
.abtn .txt {{ flex:1; text-align:left; }}
.abtn .arr {{ color:#48484a; font-size:14px; font-weight:300; }}
.abtn.running {{ opacity:0.6; pointer-events:none; }}

/* Footer */
.ft {{ display:flex; justify-content:space-between; margin-top:1px; }}
.ft a {{ color:#0a84ff; font-size:12px; cursor:pointer; text-decoration:none; }}
.ft a:hover {{ text-decoration:underline; }}

/* Network mini */
.net {{ display:flex; gap:14px; font-size:11px; color:#86868b; padding:2px 0; }}
.net span {{ font-variant-numeric:tabular-nums; }}
.net .up {{ color:#30d158; }}
.net .dn {{ color:#0a84ff; }}
</style></head><body>

<div class="hdr">
    <span class="mac">{mac_name}</span>
    <span class="badge g" id="badge">● Healthy</span>
</div>
<div class="sub" id="sub">All key metrics normal</div>
<div class="ver">MacBoost v{version}</div>

<div class="sep"></div>

<div class="mr">
    <span class="ic">⏱</span><span class="lb">Uptime</span>
    <span class="vl" id="uptime">--</span>
</div>
<div class="mr">
    <span class="ic">🌡</span><span class="lb">Thermals</span>
    <span class="vl g" id="therm">Nominal</span>
</div>

<div class="sep"></div>

<div class="mb">
    <div class="info"><span class="ic">🖥</span><span class="lb">CPU</span><span class="vl" id="cpuV">--%</span></div>
    <div class="trk"><div class="fill g" id="cpuB" style="width:0%"></div></div>
</div>
<div class="mb">
    <div class="info"><span class="ic">💾</span><span class="lb">Memory</span><span class="vl" id="ramV">--</span></div>
    <div class="trk"><div class="fill g" id="ramB" style="width:0%"></div></div>
</div>
<div class="mb">
    <div class="info"><span class="ic">💿</span><span class="lb">Storage</span><span class="vl" id="ssdV">--</span></div>
    <div class="trk"><div class="fill g" id="ssdB" style="width:0%"></div></div>
</div>

<div class="sep"></div>

<div id="batSec">
    <div class="stitle">🔋 Battery Health</div>
    <div class="br"><span class="lb">Charge</span><span class="vl" id="batC">--%</span></div>
    <div class="br"><span class="lb">Cycles</span><span class="vl" id="batCy">--</span></div>
    <div class="br"><span class="lb">Condition</span><span class="vl" id="batCo">--</span></div>
    <div class="sep"></div>
</div>

<div class="net">
    <span>Network</span>
    <span>↑ <span class="up" id="netU">0 B/s</span></span>
    <span>↓ <span class="dn" id="netD">0 B/s</span></span>
</div>

<div class="sep"></div>

<div class="acts">
    <button class="abtn" data-a="quick" onclick="doA(this)">
        <span class="txt">⚡  Quick Optimize</span><span class="arr">›</span>
    </button>
    <button class="abtn" data-a="scan" onclick="doA(this)">
        <span class="txt">🔍  Scan System</span><span class="arr">›</span>
    </button>
    <button class="abtn" data-a="clean" onclick="doA(this)">
        <span class="txt">🧹  Clean Storage</span><span class="arr">›</span>
    </button>
</div>

<div class="sep"></div>

<div class="ft">
    <a onclick="doS('prefs')">Preferences</a>
    <a onclick="doS('quit')" style="color:#ff453a">Quit MacBoost</a>
</div>

<script>
function doA(el) {{
    var a = el.getAttribute('data-a');
    el.classList.add('running');
    el.querySelector('.arr').textContent = '⏳';
    window.webkit.messageHandlers.macboost.postMessage({{action:a}});
}}
function doS(a) {{ window.webkit.messageHandlers.macboost.postMessage({{action:a}}); }}
function bc(p) {{ return p < 60 ? 'g' : p < 80 ? 'y' : 'r'; }}

function actionDone(name, ok) {{
    var el = document.querySelector('[data-a="'+name+'"]');
    if (!el) return;
    el.classList.remove('running');
    el.querySelector('.arr').textContent = ok ? '✓' : '✗';
    setTimeout(function(){{ el.querySelector('.arr').textContent = '›'; }}, 2500);
}}

function updateMetrics(d) {{
    // CPU
    document.getElementById('cpuV').textContent = d.cpu.toFixed(1) + '%';
    var cb = document.getElementById('cpuB');
    cb.style.width = d.cpu + '%'; cb.className = 'fill ' + bc(d.cpu);

    // RAM
    document.getElementById('ramV').textContent =
        d.ram_used.toFixed(1) + ' GB / ' + d.ram_total.toFixed(0) + ' GB (' + d.ram_pct.toFixed(0) + '%)';
    var rb = document.getElementById('ramB');
    rb.style.width = d.ram_pct + '%'; rb.className = 'fill ' + bc(d.ram_pct);

    // SSD
    document.getElementById('ssdV').textContent =
        d.ssd_free.toFixed(0) + ' GB free / ' + d.ssd_total.toFixed(0) + ' GB';
    var sb = document.getElementById('ssdB');
    sb.style.width = d.ssd_pct + '%'; sb.className = 'fill ' + bc(d.ssd_pct);

    // Uptime
    document.getElementById('uptime').textContent = d.uptime;

    // Thermals
    var th = document.getElementById('therm');
    if (d.temp) {{
        if (d.temp < 60) {{ th.textContent = d.temp.toFixed(0) + '°C'; th.className = 'vl g'; }}
        else if (d.temp < 80) {{ th.textContent = d.temp.toFixed(0) + '°C — Warm'; th.className = 'vl y'; }}
        else {{ th.textContent = d.temp.toFixed(0) + '°C — Hot'; th.className = 'vl r'; }}
    }} else {{ th.textContent = 'Nominal'; th.className = 'vl g'; }}

    // Battery
    if (d.bat_charge !== null) {{
        document.getElementById('batSec').style.display = 'block';
        document.getElementById('batC').textContent = d.bat_charge.toFixed(0) + '%' + (d.bat_plugged ? ' ⚡' : '');
        document.getElementById('batCy').textContent = d.bat_cycles || '--';
        document.getElementById('batCo').textContent = d.bat_condition;
    }} else {{
        document.getElementById('batSec').style.display = 'none';
    }}

    // Network
    document.getElementById('netU').textContent = d.net_up;
    document.getElementById('netD').textContent = d.net_dn;

    // Health badge
    var badge = document.getElementById('badge');
    var sub = document.getElementById('sub');
    var s = d.score || 0;
    if (s >= 80) {{
        badge.textContent = '● Healthy'; badge.className = 'badge g';
        sub.textContent = 'All key metrics normal';
    }} else if (s >= 60) {{
        badge.textContent = '● Warning'; badge.className = 'badge y';
        sub.textContent = 'Some metrics need attention';
    }} else {{
        badge.textContent = '● Critical'; badge.className = 'badge r';
        sub.textContent = 'System needs optimization';
    }}
}}
</script></body></html>"""


# ── PyObjC: WKScriptMessageHandler ──────────────────────────────────────

_app_instance = None


class _MessageHandler(NSObject, protocols=[objc.protocolNamed("WKScriptMessageHandler")]):
    """Recibe mensajes del JavaScript en el WKWebView."""

    def userContentController_didReceiveScriptMessage_(self, controller, message):
        body = message.body()
        action = body.get("action", "") if hasattr(body, "get") else ""
        if _app_instance and action:
            _app_instance.handle_action(action)


# ── PyObjC: Status Bar App ──────────────────────────────────────────────

class MacBoostStatusBar(NSObject):
    """NSStatusItem + NSPopover con WKWebView."""

    def init(self):
        self = objc.super(MacBoostStatusBar, self).init()
        if self is None:
            return None

        global _app_instance
        _app_instance = self

        self._orch = Orchestrator()
        self._metrics = {}
        self._running = True
        self._net_sent_prev = 0
        self._net_recv_prev = 0

        # ── Status Item ──
        self._statusItem = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        btn = self._statusItem.button()
        btn.setTitle_("⚡ --")
        btn.setTarget_(self)
        btn.setAction_(objc.selector(self.togglePopover_, signature=b"v@:@"))

        # ── Popover ──
        self._popover = NSPopover.alloc().init()
        self._popover.setContentSize_(NSMakeSize(340, 530))
        self._popover.setBehavior_(1)  # NSPopoverBehaviorTransient
        self._popover.setAnimates_(True)

        dark = NSAppearance.appearanceNamed_("NSAppearanceNameVibrantDark")
        if dark:
            self._popover.setAppearance_(dark)

        # ── WebView ──
        config = WKWebViewConfiguration.alloc().init()
        handler = _MessageHandler.alloc().init()
        config.userContentController().addScriptMessageHandler_name_(
            handler, "macboost"
        )

        vc = NSViewController.alloc().init()
        self._webview = WKWebView.alloc().initWithFrame_configuration_(
            NSMakeRect(0, 0, 340, 530), config
        )
        self._webview.setValue_forKey_(False, "drawsBackground")

        from macboost import __version__
        html = _build_html(_get_mac_name(), __version__)
        self._webview.loadHTMLString_baseURL_(html, None)

        vc.setView_(self._webview)
        self._popover.setContentViewController_(vc)

        # ── Background metrics thread ──
        t = threading.Thread(target=self._monitor_loop, daemon=True)
        t.start()

        # ── Main-thread timer to push metrics to WebView ──
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            4.0, self, "pushMetrics:", None, True
        )

        return self

    # ── Toggle popover ──

    @objc.typedSelector(b"v@:@")
    def togglePopover_(self, sender):
        if self._popover.isShown():
            self._popover.close()
        else:
            btn = self._statusItem.button()
            self._popover.showRelativeToRect_ofView_preferredEdge_(
                btn.bounds(), btn, 1  # NSMinYEdge
            )

    # ── Push metrics to JS (runs on main thread via NSTimer) ──

    @objc.typedSelector(b"v@:@")
    def pushMetrics_(self, timer):
        if not self._metrics:
            return
        js = f"updateMetrics({json.dumps(self._metrics)})"
        self._webview.evaluateJavaScript_completionHandler_(js, None)
        score = self._metrics.get("score", 0)
        self._statusItem.button().setTitle_(f"⚡ {score:.0f}")

    # ── Metrics collection (background thread) ──

    def _monitor_loop(self):
        while self._running:
            try:
                self._collect_metrics()
            except Exception:
                pass
            time.sleep(4)

    def _collect_metrics(self):
        cpu = psutil.cpu_percent(interval=1)

        mem = psutil.virtual_memory()
        disk = shutil.disk_usage("/")
        ssd_pct = round((disk.used / disk.total) * 100, 1)

        bat = psutil.sensors_battery()
        bat_cycles, bat_cond = _get_battery_details()

        boot = psutil.boot_time()
        up = time.time() - boot
        d, rem = divmod(int(up), 86400)
        h, rem = divmod(rem, 3600)
        m = rem // 60
        uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"

        temp = _get_cpu_temp()

        net = psutil.net_io_counters()
        sent_d = (net.bytes_sent - self._net_sent_prev) if self._net_sent_prev else 0
        recv_d = (net.bytes_recv - self._net_recv_prev) if self._net_recv_prev else 0
        self._net_sent_prev = net.bytes_sent
        self._net_recv_prev = net.bytes_recv
        net_up = _bytes_human(sent_d / 5) + "/s"
        net_dn = _bytes_human(recv_d / 5) + "/s"

        try:
            score = calculate_health_score()["total"]
        except Exception:
            score = 0

        self._metrics = {
            "cpu": cpu,
            "ram_pct": mem.percent,
            "ram_used": round(mem.used / (1024**3), 2),
            "ram_total": round(mem.total / (1024**3), 0),
            "ssd_pct": ssd_pct,
            "ssd_total": round(disk.total / (1024**3), 0),
            "ssd_free": round(disk.free / (1024**3), 0),
            "uptime": uptime,
            "temp": temp,
            "bat_charge": bat.percent if bat else None,
            "bat_plugged": bat.power_plugged if bat else None,
            "bat_cycles": bat_cycles,
            "bat_condition": bat_cond,
            "net_up": net_up,
            "net_dn": net_dn,
            "score": score,
        }

    # ── Actions from JS ──

    def handle_action(self, action: str):
        if action == "quit":
            self._running = False
            PID_FILE.unlink(missing_ok=True)
            NSApplication.sharedApplication().terminate_(None)
        elif action == "prefs":
            subprocess.Popen(["open", str(APP_DIR)])
        elif action == "quick":
            threading.Thread(target=self._do_action, args=("quick",), daemon=True).start()
        elif action == "scan":
            threading.Thread(target=self._do_action, args=("scan",), daemon=True).start()
        elif action == "clean":
            threading.Thread(target=self._do_action, args=("clean",), daemon=True).start()

    def _do_action(self, name: str):
        _notify("MacBoost", f"Running {name}...")
        ok = True
        try:
            if name == "quick":
                self._orch.quick_optimize()
                _notify("MacBoost", "✓ Quick optimization complete")
            elif name == "scan":
                report = self._orch.scan_all()
                _notify("MacBoost", f"✓ Scan done — {report.total_issues} issues found")
            elif name == "clean":
                self._orch.fix_module("storage")
                _notify("MacBoost", "✓ Storage cleaned")
        except Exception as e:
            ok = False
            _notify("MacBoost", f"Error: {e}")
        # Update button in JS
        js = f'actionDone("{name}", {"true" if ok else "false"})'
        self._webview.performSelectorOnMainThread_withObject_waitUntilDone_(
            objc.selector(self._evalJS_, signature=b"v@:@"), js, False
        )

    @objc.typedSelector(b"v@:@")
    def _evalJS_(self, js_string):
        self._webview.evaluateJavaScript_completionHandler_(js_string, None)

    # ── App delegate: cleanup on terminate ──

    @objc.typedSelector(b"v@:@")
    def applicationWillTerminate_(self, notification):
        self._running = False
        PID_FILE.unlink(missing_ok=True)


# ── Daemon / Launcher ────────────────────────────────────────────────────

def _write_pid():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def _is_running() -> bool:
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
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
    """Ejecuta la app (usado por el daemon)."""
    _write_pid()
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory — no dock icon

    delegate = MacBoostStatusBar.alloc().init()
    app.setDelegate_(delegate)
    app.run()
