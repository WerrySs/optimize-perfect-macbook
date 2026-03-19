"""Menu Bar App — Panel visual estilo Healthy con NSPopover + WKWebView."""

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
    NSBezierPath,
    NSColor,
    NSImage,
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


def _create_status_icon() -> NSImage:
    """Template bolt icon for the status bar (adapts to light/dark)."""
    img = NSImage.alloc().initWithSize_(NSMakeSize(18, 18))
    img.lockFocus()
    path = NSBezierPath.bezierPath()
    path.moveToPoint_((10, 16))
    path.lineToPoint_((5, 9.5))
    path.lineToPoint_((8.5, 9.5))
    path.lineToPoint_((6, 2))
    path.lineToPoint_((13, 8.5))
    path.lineToPoint_((9.5, 8.5))
    path.closePath()
    NSColor.blackColor().set()
    path.fill()
    img.unlockFocus()
    img.setTemplate_(True)
    return img


# ── HTML Panel ───────────────────────────────────────────────────────────

def _build_html(mac_name: str, version: str) -> str:
    # SVG icons as reusable snippets
    IC_BOLT = '<svg width="14" height="14" viewBox="0 0 16 16"><path d="M9 1L3.5 8.5H7L5 15l8-8.5H9.5z" fill="currentColor"/></svg>'
    IC_CPU = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="4" y="4" width="8" height="8" rx="1.5"/><line x1="6" y1="1.5" x2="6" y2="4"/><line x1="10" y1="1.5" x2="10" y2="4"/><line x1="6" y1="12" x2="6" y2="14.5"/><line x1="10" y1="12" x2="10" y2="14.5"/><line x1="1.5" y1="6" x2="4" y2="6"/><line x1="1.5" y1="10" x2="4" y2="10"/><line x1="12" y1="6" x2="14.5" y2="6"/><line x1="12" y1="10" x2="14.5" y2="10"/></svg>'
    IC_SSD = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><rect x="2" y="3" width="12" height="10" rx="2"/><circle cx="5" cy="8" r="1" fill="currentColor" stroke="none"/><line x1="8" y1="6.5" x2="12" y2="6.5"/><line x1="8" y1="9.5" x2="11" y2="9.5"/></svg>'
    IC_BAT = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><rect x="1.5" y="4.5" width="11" height="7" rx="1.5"/><path d="M13.5 7v2" stroke-width="2"/></svg>'
    IC_NET = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M3 10l5-5 5 5"/><path d="M3 14l5-5 5 5"/></svg>'
    IC_CLK = '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><circle cx="8" cy="8" r="6.5"/><path d="M8 4.5V8l2.5 1.5"/></svg>'
    IC_THERM = '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M8 2v7.5"/><circle cx="8" cy="12" r="2.5"/><path d="M6 9V4a2 2 0 014 0v5"/></svg>'
    IC_GEAR = '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="8" cy="8" r="2.5"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41"/></svg>'

    # Ring gauge circumference for r=30 = 188.5
    CIRC = 188.5

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{
    font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',sans-serif;
    font-size:13px;color:#f5f5f7;background:transparent;
    padding:14px 16px;user-select:none;-webkit-user-select:none;
    -webkit-font-smoothing:antialiased;
}}
.ic{{display:inline-flex;align-items:center;color:#8e8e93;flex-shrink:0;width:20px}}

/* ── Glass cards ── */
.card{{
    background:rgba(255,255,255,0.04);
    border:1px solid rgba(255,255,255,0.06);
    border-radius:12px;padding:10px 12px;margin-bottom:8px;
    box-shadow:inset 0 1px 0 rgba(255,255,255,0.03);
}}

/* ── Header ── */
.hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:2px}}
.hdr-l{{display:flex;align-items:center;gap:6px}}
.hdr-l svg{{color:#8e8e93}}
.mac{{font-size:14px;font-weight:600;letter-spacing:-0.2px}}
.badge{{
    font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px;
    display:inline-flex;align-items:center;gap:4px;letter-spacing:0.3px;
}}
.badge svg{{width:6px;height:6px}}
.badge.g{{background:rgba(48,209,88,0.2);color:#30d158;border:1px solid rgba(48,209,88,0.3)}}
.badge.y{{background:rgba(255,214,10,0.15);color:#ffd60a;border:1px solid rgba(255,214,10,0.25)}}
.badge.r{{background:rgba(255,69,58,0.15);color:#ff453a;border:1px solid rgba(255,69,58,0.25)}}
.sub{{font-size:10px;color:#6e6e73;margin-bottom:10px}}

/* ── Sparkline ── */
.spark-wrap{{position:relative;height:36px;margin-bottom:6px;border-radius:8px;overflow:hidden;
    background:rgba(255,255,255,0.02)}}
.spark-wrap svg{{width:100%;height:100%;display:block}}
.spark-label{{position:absolute;top:4px;right:6px;font-size:10px;color:#6e6e73}}

/* ── Progress bars ── */
.pbar{{display:flex;align-items:center;gap:8px;padding:4px 0}}
.pbar .lb{{font-size:12px;color:#8e8e93;width:52px;display:flex;align-items:center;gap:5px}}
.pbar .trk{{flex:1;height:5px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden}}
.pbar .fill{{height:100%;border-radius:3px;transition:width .6s ease}}
.pbar .vl{{font-size:11px;color:#d1d1d6;font-variant-numeric:tabular-nums;min-width:36px;text-align:right}}
.fill.g{{background:linear-gradient(90deg,#30d158,#32d74b)}}
.fill.y{{background:linear-gradient(90deg,#ffd60a,#ff9f0a)}}
.fill.r{{background:linear-gradient(90deg,#ff6961,#ff453a)}}

/* ── Gauges ── */
.gauges{{display:flex;gap:8px;margin-bottom:8px}}
.gauge-card{{
    flex:1;display:flex;flex-direction:column;align-items:center;
    background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.05);
    border-radius:12px;padding:10px 4px 8px;
}}
.gauge-card svg{{margin-bottom:2px}}
.gauge-sub{{font-size:10px;color:#6e6e73;margin-top:2px}}

/* ── Info rows ── */
.irow{{display:flex;align-items:center;padding:4px 0;font-size:12px}}
.irow .ic{{color:#6e6e73}}
.irow .lb{{flex:1;color:#8e8e93}}
.irow .vl{{color:#d1d1d6;font-weight:500;font-variant-numeric:tabular-nums}}
.irow .vl.g{{color:#30d158}}.irow .vl.y{{color:#ffd60a}}.irow .vl.r{{color:#ff453a}}

/* ── Actions ── */
.acts{{display:flex;gap:6px;margin:4px 0}}
.abtn{{
    flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
    padding:8px 4px;
    background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);
    border-radius:10px;color:#d1d1d6;font-size:11px;cursor:pointer;
    transition:all .15s;font-family:inherit;gap:4px;
}}
.abtn svg{{color:#8e8e93;transition:color .15s}}
.abtn:hover{{background:rgba(255,255,255,0.08);border-color:rgba(255,255,255,0.1)}}
.abtn:hover svg{{color:#d1d1d6}}
.abtn:active{{background:rgba(255,255,255,0.12)}}
.abtn.running{{opacity:.5;pointer-events:none}}

/* ── Footer ── */
.ft{{display:flex;justify-content:space-between;padding-top:4px}}
.ft a{{color:#0a84ff;font-size:11px;cursor:pointer;text-decoration:none;
    display:flex;align-items:center;gap:4px}}
.ft a svg{{color:#0a84ff}}
.ft a:hover{{text-decoration:underline}}
.ft .quit{{color:#ff453a}}.ft .quit svg{{color:#ff453a}}
</style></head><body>

<!-- Header -->
<div class="hdr">
    <div class="hdr-l">{IC_BOLT}<span class="mac">{mac_name}</span></div>
    <span class="badge g" id="badge"><svg viewBox="0 0 8 8"><circle cx="4" cy="4" r="4" fill="currentColor"/></svg>Healthy</span>
</div>
<div class="sub" id="sub">All key metrics normal &middot; v{version}</div>

<!-- CPU Sparkline -->
<div class="card" style="padding:8px 10px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
        <span style="font-size:11px;color:#8e8e93;display:flex;align-items:center;gap:5px">{IC_CPU} CPU</span>
        <span style="font-size:12px;font-weight:600;font-variant-numeric:tabular-nums" id="cpuV">--%</span>
    </div>
    <div class="spark-wrap">
        <svg id="sparkSvg" viewBox="0 0 300 36" preserveAspectRatio="none">
            <defs>
                <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#0a84ff" stop-opacity="0.35"/>
                    <stop offset="100%" stop-color="#0a84ff" stop-opacity="0"/>
                </linearGradient>
            </defs>
            <path id="sparkArea" fill="url(#sg)" d="M0 36 L300 36 Z"/>
            <path id="sparkLine" fill="none" stroke="#0a84ff" stroke-width="1.5" d="M0 36"/>
        </svg>
        <span class="spark-label" id="cpuCores">-- cores</span>
    </div>
</div>

<!-- Gauges: RAM + Temp -->
<div class="gauges">
    <div class="gauge-card">
        <svg width="80" height="80" viewBox="0 0 80 80">
            <circle cx="40" cy="40" r="30" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="6"/>
            <circle id="ramRing" cx="40" cy="40" r="30" fill="none" stroke="#30d158" stroke-width="6"
                stroke-dasharray="{CIRC}" stroke-dashoffset="{CIRC}" stroke-linecap="round"
                transform="rotate(-90 40 40)" style="transition:stroke-dashoffset .8s ease,stroke .3s ease"/>
            <text x="40" y="38" text-anchor="middle" fill="#f5f5f7" font-size="17" font-weight="600"
                font-family="-apple-system,sans-serif" id="ramRingV">--%</text>
            <text x="40" y="52" text-anchor="middle" fill="#6e6e73" font-size="8.5" font-weight="500"
                letter-spacing="0.8" font-family="-apple-system,sans-serif">MEMORY</text>
        </svg>
        <span class="gauge-sub" id="ramSub">-- / -- GB</span>
    </div>
    <div class="gauge-card">
        <svg width="80" height="80" viewBox="0 0 80 80">
            <circle cx="40" cy="40" r="30" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="6"/>
            <circle id="tempRing" cx="40" cy="40" r="30" fill="none" stroke="#30d158" stroke-width="6"
                stroke-dasharray="{CIRC}" stroke-dashoffset="{CIRC}" stroke-linecap="round"
                transform="rotate(-90 40 40)" style="transition:stroke-dashoffset .8s ease,stroke .3s ease"/>
            <text x="40" y="38" text-anchor="middle" fill="#f5f5f7" font-size="17" font-weight="600"
                font-family="-apple-system,sans-serif" id="tempRingV">--</text>
            <text x="40" y="52" text-anchor="middle" fill="#6e6e73" font-size="8.5" font-weight="500"
                letter-spacing="0.8" font-family="-apple-system,sans-serif">THERMALS</text>
        </svg>
        <span class="gauge-sub" id="tempSub">Nominal</span>
    </div>
</div>

<!-- Storage bar -->
<div class="card" style="padding:8px 12px">
    <div class="pbar">
        <span class="lb">{IC_SSD} Storage</span>
        <div class="trk"><div class="fill g" id="ssdB" style="width:0%"></div></div>
        <span class="vl" id="ssdV">--</span>
    </div>
</div>

<!-- System info -->
<div class="card" style="padding:6px 12px">
    <div class="irow" id="batRow">
        <span class="ic">{IC_BAT}</span><span class="lb">Battery</span>
        <span class="vl" id="batV">--</span>
    </div>
    <div class="irow">
        <span class="ic">{IC_NET}</span><span class="lb">Network</span>
        <span class="vl" id="netV">-- / --</span>
    </div>
    <div class="irow">
        <span class="ic">{IC_CLK}</span><span class="lb">Uptime</span>
        <span class="vl" id="uptime">--</span>
    </div>
</div>

<!-- Actions -->
<div class="acts">
    <button class="abtn" data-a="quick" onclick="doA(this)">
        {IC_BOLT} <span>Optimize</span>
    </button>
    <button class="abtn" data-a="scan" onclick="doA(this)">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><circle cx="7" cy="7" r="5"/><path d="M11 11l3.5 3.5"/></svg>
        <span>Scan</span>
    </button>
    <button class="abtn" data-a="clean" onclick="doA(this)">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M2 4h12M5 4V2.5a1 1 0 011-1h4a1 1 0 011 1V4M6 7v5M10 7v5"/><path d="M3 4l1 10a1 1 0 001 1h6a1 1 0 001-1l1-10"/></svg>
        <span>Clean</span>
    </button>
</div>

<!-- Footer -->
<div class="ft">
    <a onclick="doS('prefs')">{IC_GEAR} Preferences</a>
    <a class="quit" onclick="doS('quit')">Quit</a>
</div>

<script>
var cpuHist=[];var maxP=25;var circ={CIRC};
function doA(el){{var a=el.getAttribute('data-a');el.classList.add('running');
    window.webkit.messageHandlers.macboost.postMessage({{action:a}})}}
function doS(a){{window.webkit.messageHandlers.macboost.postMessage({{action:a}})}}
function bc(p){{return p<60?'g':p<80?'y':'r'}}
function rc(p){{return p<60?'#30d158':p<80?'#ffd60a':'#ff453a'}}

function actionDone(name,ok){{
    var el=document.querySelector('[data-a="'+name+'"]');
    if(!el)return;el.classList.remove('running');
}}

function updateSparkline(cpu){{
    cpuHist.push(cpu);if(cpuHist.length>maxP)cpuHist.shift();
    var w=300,h=36,step=w/(maxP-1);
    if(cpuHist.length<2)return;
    var pts=cpuHist.map(function(v,i){{return[i*step,h-(v/100*h)]}});
    var d='M'+pts.map(function(p){{return p[0].toFixed(1)+','+p[1].toFixed(1)}}).join(' L');
    document.getElementById('sparkLine').setAttribute('d',d);
    var last=pts[pts.length-1];
    document.getElementById('sparkArea').setAttribute('d',d+' L'+last[0].toFixed(1)+','+h+' L0,'+h+' Z');
}}

function setRing(id,pct,maxVal){{
    var el=document.getElementById(id);
    var off=circ*(1-Math.min(pct,100)/maxVal);
    el.style.strokeDashoffset=off;
    el.setAttribute('stroke',rc(pct));
}}

function updateMetrics(d){{
    // CPU
    document.getElementById('cpuV').textContent=d.cpu.toFixed(1)+'%';
    document.getElementById('cpuCores').textContent=d.cpu_cores+' cores';
    updateSparkline(d.cpu);

    // RAM gauge
    setRing('ramRing',d.ram_pct,100);
    document.getElementById('ramRingV').textContent=d.ram_pct.toFixed(0)+'%';
    document.getElementById('ramSub').textContent=d.ram_used.toFixed(1)+' / '+d.ram_total.toFixed(0)+' GB';

    // Temp gauge
    var temp=d.temp||0;
    var tPct=Math.min(temp,100);
    setRing('tempRing',tPct,100);
    document.getElementById('tempRingV').textContent=temp?temp.toFixed(0)+'°':'--';
    var ts=document.getElementById('tempSub');
    if(!temp){{ts.textContent='Nominal'}}
    else if(temp<60){{ts.textContent='Nominal'}}
    else if(temp<80){{ts.textContent='Warm'}}
    else{{ts.textContent='Hot'}}

    // Storage
    document.getElementById('ssdV').textContent=d.ssd_free.toFixed(0)+' GB free';
    var sb=document.getElementById('ssdB');
    sb.style.width=d.ssd_pct+'%';sb.className='fill '+bc(d.ssd_pct);

    // Battery
    var br=document.getElementById('batRow');
    if(d.bat_charge!==null){{
        br.style.display='flex';
        var plug=d.bat_plugged?' (charging)':'';
        var cy=d.bat_cycles?' · '+d.bat_cycles+' cycles':'';
        document.getElementById('batV').textContent=d.bat_charge.toFixed(0)+'%'+plug+cy;
    }}else{{br.style.display='none'}}

    // Network
    document.getElementById('netV').textContent=d.net_up+' up · '+d.net_dn+' dn';

    // Uptime
    document.getElementById('uptime').textContent=d.uptime;

    // Health badge
    var badge=document.getElementById('badge');
    var sub=document.getElementById('sub');
    var s=d.score||0;
    if(s>=80){{
        badge.innerHTML='<svg viewBox="0 0 8 8"><circle cx="4" cy="4" r="4" fill="currentColor"/></svg>Healthy';
        badge.className='badge g';sub.textContent='All key metrics normal · v{version}';
    }}else if(s>=60){{
        badge.innerHTML='<svg viewBox="0 0 8 8"><circle cx="4" cy="4" r="4" fill="currentColor"/></svg>Warning';
        badge.className='badge y';sub.textContent='Some metrics need attention · v{version}';
    }}else{{
        badge.innerHTML='<svg viewBox="0 0 8 8"><circle cx="4" cy="4" r="4" fill="currentColor"/></svg>Critical';
        badge.className='badge r';sub.textContent='System needs optimization · v{version}';
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

        # ── Status Item with template icon ──
        self._statusItem = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        btn = self._statusItem.button()
        btn.setImage_(_create_status_icon())
        btn.setTitle_(" --")
        btn.setTarget_(self)
        btn.setAction_(objc.selector(self.togglePopover_, signature=b"v@:@"))

        # ── Popover ──
        self._popover = NSPopover.alloc().init()
        self._popover.setContentSize_(NSMakeSize(350, 540))
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
            NSMakeRect(0, 0, 350, 540), config
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
        self._statusItem.button().setTitle_(f" {score:.0f}")

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
        cores = psutil.cpu_count()

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
            "cpu_cores": cores,
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
        elif action in ("quick", "scan", "clean"):
            threading.Thread(target=self._do_action, args=(action,), daemon=True).start()

    def _do_action(self, name: str):
        _notify("MacBoost", f"Running {name}...")
        ok = True
        try:
            if name == "quick":
                self._orch.quick_optimize()
                _notify("MacBoost", "Quick optimization complete")
            elif name == "scan":
                report = self._orch.scan_all()
                _notify("MacBoost", f"Scan done - {report.total_issues} issues found")
            elif name == "clean":
                self._orch.fix_module("storage")
                _notify("MacBoost", "Storage cleaned")
        except Exception as e:
            ok = False
            _notify("MacBoost", f"Error: {e}")
        js = f'actionDone("{name}",{"true" if ok else "false"})'
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
        print(f"MacBoost ya esta corriendo (PID: {pid})")
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
    print(f"MacBoost iniciado en segundo plano (PID: {proc.pid})")
    print("  Busca el icono en tu barra de menu")
    print("  Para detener: macboost menubar stop")


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
                print("MacBoost detenido")
                return
        except Exception:
            pass
        print("MacBoost no esta corriendo")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink(missing_ok=True)
        print(f"MacBoost detenido (PID: {pid})")
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
    app.setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory

    delegate = MacBoostStatusBar.alloc().init()
    app.setDelegate_(delegate)
    app.run()
