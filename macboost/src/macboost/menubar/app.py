"""Menu Bar App — MacBoost Multi-Tool Panel with tabs, light theme, real app icons."""

from __future__ import annotations

import base64
import hashlib
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
    NSBitmapImageRep,
    NSColor,
    NSImage,
    NSPasteboard,
    NSPopover,
    NSStatusBar,
    NSVariableStatusItemLength,
    NSViewController,
    NSWorkspace,
)
from Foundation import NSMakeRect, NSMakeSize, NSObject, NSTimer
from WebKit import WKWebView, WKWebViewConfiguration, WKUserContentController

from macboost.core.config import APP_DIR
from macboost.core.health import calculate_health_score
from macboost.core.orchestrator import Orchestrator

PID_FILE = APP_DIR / "menubar.pid"
APPS_CONFIG = APP_DIR / "quick_launch.json"
CLIP_FILE = APP_DIR / "clipboard.enc"
NOTES_FILE = APP_DIR / "notes.json"

AVAILABLE_APPS = [
    "Finder", "Safari", "Google Chrome", "Firefox", "Arc",
    "Terminal", "iTerm", "Visual Studio Code", "Xcode",
    "Notes", "Calendar", "Mail", "Messages", "Music",
    "Photos", "FaceTime", "Maps", "Reminders", "Weather",
    "System Settings", "Activity Monitor", "Disk Utility",
    "Preview", "TextEdit", "Calculator", "App Store",
    "Shortcuts", "Contacts",
]

DEFAULT_SELECTED = [
    "Finder", "Safari", "Terminal", "Notes", "Calculator", "System Settings",
]


# ── Helpers ──────────────────────────────────────────────────────────────

def _bytes_human(b: int | float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _time_ago(ts: float) -> str:
    d = time.time() - ts
    if d < 60:
        return "now"
    if d < 3600:
        return f"{int(d / 60)}m"
    if d < 86400:
        return f"{int(d / 3600)}h"
    return f"{int(d / 86400)}d"


def _get_mac_name() -> str:
    try:
        r = subprocess.run(["scutil", "--get", "ComputerName"],
                           capture_output=True, text=True, timeout=3)
        if r.stdout.strip():
            return r.stdout.strip()
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


def _is_dark_mode() -> bool:
    try:
        r = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                           capture_output=True, text=True, timeout=2)
        return "Dark" in r.stdout
    except Exception:
        return False


def _get_wifi_ssid() -> str | None:
    try:
        r = subprocess.run(["networksetup", "-getairportnetwork", "en0"],
                           capture_output=True, text=True, timeout=3)
        if "Current Wi-Fi Network:" in r.stdout:
            return r.stdout.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


def _notify(title: str, message: str):
    safe_msg = message.replace('"', '\\"').replace("'", "\\'")
    subprocess.Popen(["osascript", "-e",
                       f'display notification "{safe_msg}" with title "{title}"'])


def _create_status_icon() -> NSImage:
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


def _load_selected_apps() -> list[str]:
    if APPS_CONFIG.exists():
        try:
            return json.loads(APPS_CONFIG.read_text())
        except Exception:
            pass
    return list(DEFAULT_SELECTED)


def _save_selected_apps(apps: list[str]):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    APPS_CONFIG.write_text(json.dumps(apps))


# ── Clipboard encryption ─────────────────────────────────────────────────

def _get_fernet():
    from cryptography.fernet import Fernet
    try:
        r = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                           capture_output=True, text=True, timeout=3)
        hw_uuid = "macboost-default"
        for line in r.stdout.splitlines():
            if "IOPlatformUUID" in line:
                hw_uuid = line.split('"')[-2]
                break
    except Exception:
        hw_uuid = "macboost-default"
    key = base64.urlsafe_b64encode(hashlib.sha256(hw_uuid.encode()).digest())
    return Fernet(key)


def _save_clipboard_encrypted(history: list):
    try:
        f = _get_fernet()
        data = json.dumps(history).encode()
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CLIP_FILE.write_bytes(f.encrypt(data))
    except Exception:
        pass


def _load_clipboard_encrypted() -> list:
    if not CLIP_FILE.exists():
        return []
    try:
        f = _get_fernet()
        return json.loads(f.decrypt(CLIP_FILE.read_bytes()).decode())
    except Exception:
        return []


# ── Notes persistence ────────────────────────────────────────────────────

def _save_notes(notes: list):
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        NOTES_FILE.write_text(json.dumps(notes))
    except Exception:
        pass


def _load_notes() -> list:
    if not NOTES_FILE.exists():
        return []
    try:
        return json.loads(NOTES_FILE.read_text())
    except Exception:
        return []


# ── App Icons ────────────────────────────────────────────────────────────

def _get_app_icon_b64(app_name: str, size: int = 32) -> str:
    try:
        ws = NSWorkspace.sharedWorkspace()
        app_path = ws.fullPathForApplication_(app_name)
        if not app_path:
            return ""
        icon = ws.iconForFile_(app_path)
        icon.setSize_(NSMakeSize(size, size))
        tiff = icon.TIFFRepresentation()
        if not tiff:
            return ""
        rep = NSBitmapImageRep.imageRepWithData_(tiff)
        if not rep:
            return ""
        png = rep.representationUsingType_properties_(4, None)
        if not png:
            return ""
        return base64.b64encode(bytes(png)).decode()
    except Exception:
        return ""


def _get_all_app_icons() -> tuple[dict[str, str], list[str]]:
    icons = {}
    installed = []
    for app in AVAILABLE_APPS:
        b64 = _get_app_icon_b64(app)
        if b64:
            icons[app] = b64
            installed.append(app)
    return icons, installed


# ── SVG Icons ────────────────────────────────────────────────────────────

_IC = {
    "bolt": '<svg width="14" height="14" viewBox="0 0 16 16"><path d="M9 1L3.5 8.5H7L5 15l8-8.5H9.5z" fill="currentColor"/></svg>',
    "cpu": '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="4" y="4" width="8" height="8" rx="1.5"/><line x1="6" y1="1.5" x2="6" y2="4"/><line x1="10" y1="1.5" x2="10" y2="4"/><line x1="6" y1="12" x2="6" y2="14.5"/><line x1="10" y1="12" x2="10" y2="14.5"/><line x1="1.5" y1="6" x2="4" y2="6"/><line x1="1.5" y1="10" x2="4" y2="10"/><line x1="12" y1="6" x2="14.5" y2="6"/><line x1="12" y1="10" x2="14.5" y2="10"/></svg>',
    "ssd": '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><rect x="2" y="3" width="12" height="10" rx="2"/><circle cx="5" cy="8" r="1" fill="currentColor" stroke="none"/><line x1="8" y1="6.5" x2="12" y2="6.5"/><line x1="8" y1="9.5" x2="11" y2="9.5"/></svg>',
    "bat": '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><rect x="1.5" y="4.5" width="11" height="7" rx="1.5"/><path d="M13.5 7v2" stroke-width="2"/></svg>',
    "net": '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M3 10l5-5 5 5"/><path d="M3 14l5-5 5 5"/></svg>',
    "clk": '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><circle cx="8" cy="8" r="6.5"/><path d="M8 4.5V8l2.5 1.5"/></svg>',
    "gear": '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="8" cy="8" r="2.5"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41"/></svg>',
    "clip": '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><rect x="3" y="1" width="10" height="14" rx="2"/><line x1="6" y1="5" x2="10" y2="5"/><line x1="6" y1="8" x2="10" y2="8"/><line x1="6" y1="11" x2="9" y2="11"/></svg>',
    "search": '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><circle cx="7" cy="7" r="5"/><path d="M11 11l3.5 3.5"/></svg>',
    "copy": '<svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><rect x="5" y="5" width="9" height="9" rx="1.5"/><path d="M2 11V3a1.5 1.5 0 011.5-1.5H11"/></svg>',
    "trash": '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M2 4h12M5 4V2.5a1 1 0 011-1h4a1 1 0 011 1V4M6 7v5M10 7v5"/><path d="M3 4l1 10a1 1 0 001 1h6a1 1 0 001-1l1-10"/></svg>',
    "moon": '<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M6.2 2A6 6 0 0014 9.8 6 6 0 116.2 2z"/></svg>',
    "lock": '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><rect x="3" y="7" width="10" height="7" rx="2"/><path d="M5 7V5a3 3 0 016 0v2"/></svg>',
    "camera": '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><rect x="1.5" y="4" width="13" height="9" rx="2"/><circle cx="8" cy="8.5" r="2.5"/><path d="M5.5 4L6.5 2h3l1 2"/></svg>',
    "timer": '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><circle cx="8" cy="9" r="5.5"/><path d="M8 6v3l2 1"/><path d="M6.5 1h3"/><path d="M8 1v2"/></svg>',
    "pencil": '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><path d="M11.5 1.5l3 3L5 14H2v-3z"/><path d="M9.5 3.5l3 3"/></svg>',
}

CIRC = 188.5  # 2*pi*30


# ── HTML Panel ───────────────────────────────────────────────────────────

def _build_html(mac_name: str, version: str, icons: dict, installed: list, selected: list) -> str:
    icons_json = json.dumps(icons)
    installed_json = json.dumps(installed)
    selected_json = json.dumps(selected)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{
    font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',sans-serif;
    font-size:13px;color:#1d1d1f;background:transparent;
    padding:14px 16px;user-select:none;-webkit-user-select:none;
    -webkit-font-smoothing:antialiased;overflow-y:auto;
}}
.ic{{display:inline-flex;align-items:center;color:#8e8e93;flex-shrink:0;width:20px}}

.card{{
    background:rgba(255,255,255,0.55);
    border:1px solid rgba(0,0,0,0.06);
    border-radius:14px;padding:10px 12px;margin-bottom:8px;
    box-shadow:0 0.5px 2px rgba(0,0,0,0.04),inset 0 0.5px 0 rgba(255,255,255,0.7);
}}

.hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:2px}}
.hdr-l{{display:flex;align-items:center;gap:6px}}
.hdr-l svg{{color:#8e8e93}}
.mac{{font-size:14px;font-weight:600;letter-spacing:-.2px;color:#1d1d1f}}
.badge{{font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px;
    display:inline-flex;align-items:center;gap:4px;letter-spacing:.3px;}}
.badge svg{{width:6px;height:6px}}
.badge.g{{background:rgba(52,199,89,.12);color:#34C759;border:1px solid rgba(52,199,89,.2)}}
.badge.y{{background:rgba(255,149,0,.12);color:#FF9500;border:1px solid rgba(255,149,0,.2)}}
.badge.r{{background:rgba(255,59,48,.12);color:#FF3B30;border:1px solid rgba(255,59,48,.2)}}
.sub{{font-size:10px;color:#8e8e93;margin-bottom:10px}}

.tabs{{display:flex;background:rgba(0,0,0,0.05);border-radius:8px;padding:2px;margin-bottom:10px}}
.tab-btn{{flex:1;padding:5px 0;border:none;background:none;border-radius:6px;
    font-size:12px;font-weight:500;color:#636366;cursor:pointer;font-family:inherit;transition:all .2s}}
.tab-btn.active{{background:rgba(255,255,255,0.85);color:#1d1d1f;font-weight:600;
    box-shadow:0 1px 3px rgba(0,0,0,0.08)}}

.spark-wrap{{position:relative;height:34px;margin-bottom:4px;border-radius:8px;overflow:hidden;
    background:rgba(0,0,0,0.025)}}
.spark-wrap svg{{width:100%;height:100%;display:block}}
.spark-lbl{{position:absolute;top:4px;right:6px;font-size:10px;color:#8e8e93}}

.pbar{{display:flex;align-items:center;gap:8px;padding:3px 0}}
.pbar .lb{{font-size:12px;color:#636366;width:52px;display:flex;align-items:center;gap:5px}}
.pbar .trk{{flex:1;height:5px;background:rgba(0,0,0,0.06);border-radius:3px;overflow:hidden}}
.pbar .fill{{height:100%;border-radius:3px;transition:width .6s ease}}
.pbar .vl{{font-size:11px;color:#3a3a3c;font-variant-numeric:tabular-nums;min-width:36px;text-align:right}}
.fill.g{{background:linear-gradient(90deg,#007AFF,#5AC8FA)}}
.fill.y{{background:linear-gradient(90deg,#FF9500,#FFCC00)}}
.fill.r{{background:linear-gradient(90deg,#FF6961,#FF3B30)}}

.gauges{{display:flex;gap:8px;margin-bottom:8px}}
.gauge-card{{flex:1;display:flex;flex-direction:column;align-items:center;
    background:rgba(255,255,255,0.5);border:1px solid rgba(0,0,0,0.05);
    border-radius:14px;padding:10px 4px 8px}}
.gauge-sub{{font-size:10px;color:#8e8e93;margin-top:2px}}

.irow{{display:flex;align-items:center;padding:3px 0;font-size:12px}}
.irow .ic{{color:#8e8e93}}.irow .lb{{flex:1;color:#636366}}
.irow .vl{{color:#3a3a3c;font-weight:500;font-variant-numeric:tabular-nums}}

.acts{{display:flex;gap:6px;margin-bottom:4px}}
.abtn{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
    padding:8px 4px;gap:4px;background:rgba(0,0,0,0.03);border:1px solid rgba(0,0,0,0.06);
    border-radius:12px;color:#3a3a3c;font-size:11px;cursor:pointer;transition:all .15s;font-family:inherit}}
.abtn svg{{color:#8e8e93;transition:color .15s}}
.abtn:hover{{background:rgba(0,0,0,0.06);border-color:rgba(0,0,0,0.1)}}
.abtn:hover svg{{color:#636366}}.abtn:active{{background:rgba(0,0,0,0.1)}}
.abtn.running{{opacity:.5;pointer-events:none}}

.toggles{{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px}}
.toggle{{display:flex;align-items:center;gap:8px;padding:10px 12px;
    background:rgba(0,0,0,0.03);border:1px solid rgba(0,0,0,0.05);
    border-radius:12px;font-size:12px;color:#3a3a3c;cursor:pointer;transition:all .15s;font-family:inherit}}
.toggle svg{{color:#8e8e93;transition:color .15s}}
.toggle:hover{{background:rgba(0,0,0,0.06)}}.toggle:active{{background:rgba(0,0,0,0.1)}}
.toggle.active{{background:rgba(0,122,255,0.1);border-color:rgba(0,122,255,0.2);color:#007AFF}}
.toggle.active svg{{color:#007AFF}}

.timer-card{{text-align:center;padding:12px;margin-bottom:8px;
    background:rgba(255,255,255,0.5);border:1px solid rgba(0,0,0,0.05);border-radius:14px}}
.timer-disp{{font-size:28px;font-weight:300;font-variant-numeric:tabular-nums;
    color:#1d1d1f;letter-spacing:1px;margin-bottom:8px}}
.timer-btns{{display:flex;gap:8px;justify-content:center}}
.timer-b{{padding:5px 16px;border-radius:8px;font-size:12px;cursor:pointer;
    border:1px solid rgba(0,0,0,0.08);background:rgba(0,0,0,0.03);color:#3a3a3c;
    font-family:inherit;transition:all .15s}}
.timer-b:hover{{background:rgba(0,0,0,0.06)}}
.timer-b.primary{{background:#007AFF;color:#fff;border-color:#007AFF}}
.timer-b.primary:hover{{background:#0071E3}}

.sec{{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;padding:0 2px}}
.sec h3{{font-size:11px;font-weight:600;color:#8e8e93;letter-spacing:.5px;text-transform:uppercase;
    display:flex;align-items:center;gap:5px}}
.sec a{{font-size:10px;color:#007AFF;cursor:pointer;text-decoration:none;font-weight:500}}
.sec a:hover{{text-decoration:underline}}

.clips{{max-height:140px;overflow-y:auto;border-radius:10px;
    background:rgba(0,0,0,0.02);border:1px solid rgba(0,0,0,0.04)}}
.clips::-webkit-scrollbar{{width:4px}}
.clips::-webkit-scrollbar-track{{background:transparent}}
.clips::-webkit-scrollbar-thumb{{background:rgba(0,0,0,0.12);border-radius:2px}}
.clip-item{{display:flex;align-items:center;padding:7px 10px;gap:8px;cursor:pointer;
    border-bottom:1px solid rgba(0,0,0,0.03);transition:background .1s}}
.clip-item:last-child{{border-bottom:none}}
.clip-item:hover{{background:rgba(0,0,0,0.04)}}
.clip-ic{{color:#8e8e93;flex-shrink:0}}.clip-ic.url{{color:#007AFF}}
.clip-txt{{flex:1;font-size:11px;color:#3a3a3c;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.clip-time{{font-size:10px;color:#aeaeb2;flex-shrink:0}}
.clip-copy{{color:#aeaeb2;flex-shrink:0;opacity:0;transition:opacity .15s}}
.clip-item:hover .clip-copy{{opacity:1}}
.clip-empty{{padding:16px;text-align:center;font-size:11px;color:#aeaeb2}}

.note-input{{display:none;margin-bottom:8px}}
.note-ta{{width:100%;height:56px;border-radius:10px;border:1px solid rgba(0,0,0,0.08);
    padding:8px 10px;font-size:12px;font-family:inherit;resize:none;
    background:rgba(255,255,255,0.6);color:#1d1d1f;outline:none}}
.note-ta:focus{{border-color:rgba(0,122,255,0.4)}}
.note-acts{{display:flex;gap:6px;justify-content:flex-end;margin-top:6px}}
.note-del{{color:#aeaeb2;cursor:pointer;flex-shrink:0;transition:color .15s}}
.note-del:hover{{color:#FF3B30}}

.apps-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:8px}}
.app-item{{display:flex;flex-direction:column;align-items:center;gap:3px;
    padding:8px 4px;border-radius:12px;cursor:pointer;transition:all .15s;border:1px solid transparent}}
.app-item:hover{{background:rgba(0,0,0,0.04);border-color:rgba(0,0,0,0.04)}}
.app-item:active{{background:rgba(0,0,0,0.08)}}
.app-item img{{width:32px;height:32px;border-radius:7px}}
.app-item span{{font-size:9px;color:#636366;text-align:center;line-height:1.2;
    max-width:60px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}

.picker{{position:fixed;top:0;left:0;right:0;bottom:0;
    background:rgba(245,245,247,0.95);backdrop-filter:blur(20px);
    z-index:100;padding:14px;overflow-y:auto;display:none}}
.picker.show{{display:block}}
.picker-hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}}
.picker-hdr h3{{font-size:15px;font-weight:600;color:#1d1d1f}}
.picker-done{{font-size:13px;color:#007AFF;font-weight:600;border:none;background:none;
    cursor:pointer;font-family:inherit}}
.picker-done:hover{{text-decoration:underline}}
.picker-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}
.picker-item{{display:flex;flex-direction:column;align-items:center;gap:4px;
    padding:8px 4px;border-radius:12px;cursor:pointer;border:2px solid transparent;transition:all .15s}}
.picker-item.sel{{border-color:#007AFF;background:rgba(0,122,255,0.06)}}
.picker-item img{{width:36px;height:36px;border-radius:8px}}
.picker-item span{{font-size:9px;color:#636366;text-align:center;line-height:1.2}}

</style></head><body>

<div class="hdr">
    <div class="hdr-l">{_IC['bolt']}<span class="mac">{mac_name}</span></div>
    <span class="badge g" id="badge"><svg viewBox="0 0 8 8"><circle cx="4" cy="4" r="4" fill="currentColor"/></svg>Healthy</span>
</div>
<div class="sub" id="sub">All key metrics normal &middot; v{version}</div>

<div class="tabs">
    <button class="tab-btn active" data-tab="monitor" onclick="showTab('monitor')">Monitor</button>
    <button class="tab-btn" data-tab="tools" onclick="showTab('tools')">Tools</button>
    <button class="tab-btn" data-tab="apps" onclick="showTab('apps')">Apps</button>
</div>

<!-- MONITOR -->
<div id="tab-monitor" class="tab-content">
    <div class="card" style="padding:8px 10px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
            <span style="font-size:11px;color:#636366;display:flex;align-items:center;gap:5px">{_IC['cpu']} CPU</span>
            <span style="font-size:12px;font-weight:600;font-variant-numeric:tabular-nums;color:#1d1d1f" id="cpuV">--%</span>
        </div>
        <div class="spark-wrap">
            <svg id="sparkSvg" viewBox="0 0 300 34" preserveAspectRatio="none">
                <defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#007AFF" stop-opacity="0.2"/>
                    <stop offset="100%" stop-color="#007AFF" stop-opacity="0"/>
                </linearGradient></defs>
                <path id="sparkArea" fill="url(#sg)" d="M0 34 L300 34 Z"/>
                <path id="sparkLine" fill="none" stroke="#007AFF" stroke-width="1.5" d="M0 34"/>
            </svg>
            <span class="spark-lbl" id="cpuCores">-- cores</span>
        </div>
    </div>
    <div class="gauges">
        <div class="gauge-card">
            <svg width="78" height="78" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="30" fill="none" stroke="rgba(0,0,0,0.06)" stroke-width="6"/>
                <circle id="ramRing" cx="40" cy="40" r="30" fill="none" stroke="#007AFF" stroke-width="6"
                    stroke-dasharray="{CIRC}" stroke-dashoffset="{CIRC}" stroke-linecap="round"
                    transform="rotate(-90 40 40)" style="transition:stroke-dashoffset .8s ease,stroke .3s ease"/>
                <text x="40" y="38" text-anchor="middle" fill="#1d1d1f" font-size="17" font-weight="600"
                    font-family="-apple-system,sans-serif" id="ramRV">--%</text>
                <text x="40" y="52" text-anchor="middle" fill="#8e8e93" font-size="8.5" font-weight="500"
                    letter-spacing=".8" font-family="-apple-system,sans-serif">MEMORY</text>
            </svg>
            <span class="gauge-sub" id="ramSub">-- / -- GB</span>
        </div>
        <div class="gauge-card">
            <svg width="78" height="78" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="30" fill="none" stroke="rgba(0,0,0,0.06)" stroke-width="6"/>
                <circle id="tempRing" cx="40" cy="40" r="30" fill="none" stroke="#007AFF" stroke-width="6"
                    stroke-dasharray="{CIRC}" stroke-dashoffset="{CIRC}" stroke-linecap="round"
                    transform="rotate(-90 40 40)" style="transition:stroke-dashoffset .8s ease,stroke .3s ease"/>
                <text x="40" y="38" text-anchor="middle" fill="#1d1d1f" font-size="17" font-weight="600"
                    font-family="-apple-system,sans-serif" id="tempRV">--</text>
                <text x="40" y="52" text-anchor="middle" fill="#8e8e93" font-size="8.5" font-weight="500"
                    letter-spacing=".8" font-family="-apple-system,sans-serif">THERMALS</text>
            </svg>
            <span class="gauge-sub" id="tempSub">Nominal</span>
        </div>
    </div>
    <div class="card" style="padding:8px 12px">
        <div class="pbar">
            <span class="lb">{_IC['ssd']} Storage</span>
            <div class="trk"><div class="fill g" id="ssdB" style="width:0%"></div></div>
            <span class="vl" id="ssdV">--</span>
        </div>
        <div class="irow" id="batRow">
            <span class="ic">{_IC['bat']}</span><span class="lb">Battery</span>
            <span class="vl" id="batV">--</span>
        </div>
        <div class="irow">
            <span class="ic">{_IC['net']}</span><span class="lb" id="netLbl">Network</span>
            <span class="vl" id="netV">--</span>
        </div>
        <div class="irow">
            <span class="ic">{_IC['clk']}</span><span class="lb">Uptime</span>
            <span class="vl" id="uptime">--</span>
        </div>
    </div>
    <div class="acts">
        <button class="abtn" data-a="quick" onclick="doA(this)">{_IC['bolt']}<span>Optimize</span></button>
        <button class="abtn" data-a="scan" onclick="doA(this)">{_IC['search']}<span>Scan</span></button>
        <button class="abtn" data-a="clean" onclick="doA(this)">{_IC['trash']}<span>Clean</span></button>
    </div>
</div>

<!-- TOOLS -->
<div id="tab-tools" class="tab-content" style="display:none">
    <div class="sec"><h3>{_IC['gear']} Quick Toggles</h3></div>
    <div class="toggles">
        <button class="toggle" id="tgl-dark" onclick="doS('toggle_dark')">{_IC['moon']} Dark Mode</button>
        <button class="toggle" onclick="doS('lock_screen')">{_IC['lock']} Lock Screen</button>
        <button class="toggle" onclick="doS('screenshot')">{_IC['camera']} Screenshot</button>
        <button class="toggle" onclick="doS('empty_trash')">{_IC['trash']} Empty Trash</button>
    </div>
    <div class="sec"><h3>{_IC['timer']} Stopwatch</h3></div>
    <div class="timer-card">
        <div class="timer-disp" id="timerDisp">00:00:00</div>
        <div class="timer-btns">
            <button class="timer-b primary" id="timerBtn" onclick="toggleTimer()">Start</button>
            <button class="timer-b" onclick="resetTimer()">Reset</button>
        </div>
    </div>
    <div class="sec"><h3>{_IC['clip']} Clipboard</h3><a onclick="doS('clip_clear')">Clear</a></div>
    <div class="clips" id="clipList">
        <div class="clip-empty">Clipboard history will appear here</div>
    </div>

    <div style="height:8px"></div>
    <div class="sec"><h3>{_IC['pencil']} Notes</h3><a onclick="showNoteInput()">Add</a></div>
    <div class="note-input" id="noteInput">
        <textarea class="note-ta" id="noteText" placeholder="Write a note..."></textarea>
        <div class="note-acts">
            <button class="timer-b" onclick="cancelNote()">Cancel</button>
            <button class="timer-b primary" onclick="saveNote()">Save</button>
        </div>
    </div>
    <div class="clips" id="notesList" style="max-height:120px">
        <div class="clip-empty">No notes yet</div>
    </div>
</div>

<!-- APPS -->
<div id="tab-apps" class="tab-content" style="display:none">
    <div class="sec"><h3>Quick Launch</h3><a onclick="openPicker()">Edit</a></div>
    <div class="apps-grid" id="appsGrid"></div>
</div>

<div id="appPicker" class="picker">
    <div class="picker-hdr">
        <h3>Select Apps</h3>
        <button class="picker-done" onclick="closePicker()">Done</button>
    </div>
    <div class="picker-grid" id="pickerGrid"></div>
</div>


<script>
var cpuHist=[],maxP=25,circ={CIRC};
var allIcons={icons_json};
var installedApps={installed_json};
var selectedApps={selected_json};
var timerRunning=false,timerSec=0,timerInt=null;

function showTab(t){{
    document.querySelectorAll('.tab-content').forEach(function(el){{el.style.display='none'}});
    document.getElementById('tab-'+t).style.display='block';
    document.querySelectorAll('.tab-btn').forEach(function(el){{el.classList.remove('active')}});
    document.querySelector('[data-tab="'+t+'"]').classList.add('active');
}}
function doA(el){{var a=el.getAttribute('data-a');el.classList.add('running');
    window.webkit.messageHandlers.macboost.postMessage({{action:a}})}}
function doS(a){{window.webkit.messageHandlers.macboost.postMessage({{action:a}})}}
function copyClip(i){{window.webkit.messageHandlers.macboost.postMessage({{action:'clip_copy',idx:i}})}}
function bc(p){{return p<60?'g':p<80?'y':'r'}}
function rc(p){{return p<60?'#007AFF':p<80?'#FF9500':'#FF3B30'}}
function actionDone(name){{var el=document.querySelector('[data-a="'+name+'"]');if(el)el.classList.remove('running')}}

function updateSparkline(cpu){{
    cpuHist.push(cpu);if(cpuHist.length>maxP)cpuHist.shift();
    if(cpuHist.length<2)return;
    var w=300,h=34,step=w/(maxP-1);
    var pts=cpuHist.map(function(v,i){{return[i*step,h-(v/100*h)]}});
    var d='M'+pts.map(function(p){{return p[0].toFixed(1)+','+p[1].toFixed(1)}}).join(' L');
    document.getElementById('sparkLine').setAttribute('d',d);
    document.getElementById('sparkArea').setAttribute('d',d+' L'+pts[pts.length-1][0].toFixed(1)+','+h+' L0,'+h+' Z');
}}
function setRing(id,pct,mx){{
    var el=document.getElementById(id);
    el.style.strokeDashoffset=circ*(1-Math.min(pct,mx)/mx);
    el.setAttribute('stroke',rc(pct));
}}
function renderClips(clips){{
    var el=document.getElementById('clipList');
    if(!clips||!clips.length){{el.innerHTML='<div class="clip-empty">Clipboard history will appear here</div>';return}}
    var h='';
    for(var i=0;i<clips.length;i++){{
        var c=clips[i];var icCls=c.tp==='url'?'clip-ic url':'clip-ic';
        var ic=c.tp==='url'?'{_IC["net"]}':'{_IC["clip"]}';
        h+='<div class="clip-item" onclick="copyClip('+i+')">'
          +'<span class="'+icCls+'">'+ic+'</span>'
          +'<span class="clip-txt">'+c.p.replace(/</g,'&lt;')+'</span>'
          +'<span class="clip-time">'+c.t+'</span>'
          +'<span class="clip-copy">{_IC["copy"]}</span></div>';
    }}
    el.innerHTML=h;
}}

function toggleTimer(){{
    if(timerRunning){{clearInterval(timerInt);timerRunning=false;
        document.getElementById('timerBtn').textContent='Start';
        document.getElementById('timerBtn').classList.add('primary');
    }}else{{timerInt=setInterval(function(){{timerSec++;updTimerDisp()}},1000);
        timerRunning=true;document.getElementById('timerBtn').textContent='Stop';
        document.getElementById('timerBtn').classList.remove('primary');}}
}}
function resetTimer(){{clearInterval(timerInt);timerRunning=false;timerSec=0;updTimerDisp();
    document.getElementById('timerBtn').textContent='Start';
    document.getElementById('timerBtn').classList.add('primary');}}
function updTimerDisp(){{
    var h=Math.floor(timerSec/3600),m=Math.floor((timerSec%3600)/60),s=timerSec%60;
    document.getElementById('timerDisp').textContent=
        String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
}}

/* ── Notes ── */
var notes=[];
function showNoteInput(){{document.getElementById('noteInput').style.display='block';document.getElementById('noteText').focus()}}
function cancelNote(){{document.getElementById('noteInput').style.display='none';document.getElementById('noteText').value=''}}
function saveNote(){{
    var t=document.getElementById('noteText').value.trim();if(!t)return;
    window.webkit.messageHandlers.macboost.postMessage({{action:'add_note',text:t}});
    cancelNote();
}}
function deleteNote(i){{window.webkit.messageHandlers.macboost.postMessage({{action:'delete_note',idx:i}})}}
function renderNotes(nn){{
    notes=nn||notes;var el=document.getElementById('notesList');
    if(!notes.length){{el.innerHTML='<div class="clip-empty">No notes yet</div>';return}}
    var h='';
    for(var i=0;i<notes.length;i++){{
        h+='<div class="clip-item">'
          +'<span class="clip-txt">'+notes[i].text.replace(/</g,'&lt;')+'</span>'
          +'<span class="clip-time">'+notes[i].t+'</span>'
          +'<span class="note-del" onclick="deleteNote('+i+')">{_IC["trash"]}</span></div>';
    }}
    el.innerHTML=h;
}}

function renderApps(){{
    var g=document.getElementById('appsGrid');var h='';
    for(var i=0;i<selectedApps.length;i++){{
        var n=selectedApps[i];var ic=allIcons[n];if(!ic)continue;
        var short=n.replace('Google ','').replace('Visual Studio ','VS ').split(' ')[0];
        h+='<div class="app-item" onclick="openApp(this.dataset.n)" data-n="'+n.replace(/"/g,'&quot;')+'">'
          +'<img src="data:image/png;base64,'+ic+'"><span>'+short+'</span></div>';
    }}
    if(!h)h='<div style="grid-column:1/-1;text-align:center;font-size:11px;color:#aeaeb2;padding:16px">Tap Edit to add apps</div>';
    g.innerHTML=h;
}}
function openApp(n){{window.webkit.messageHandlers.macboost.postMessage({{action:'open_app',app:n}})}}
function openPicker(){{
    var g=document.getElementById('pickerGrid');var h='';
    for(var i=0;i<installedApps.length;i++){{
        var n=installedApps[i];var ic=allIcons[n];if(!ic)continue;
        var sel=selectedApps.indexOf(n)>=0?'sel':'';
        var short=n.replace('Google ','').replace('Visual Studio ','VS ');
        h+='<div class="picker-item '+sel+'" data-app="'+n.replace(/"/g,'&quot;')+'" onclick="toggleAppSel(this)">'
          +'<img src="data:image/png;base64,'+ic+'"><span>'+short+'</span></div>';
    }}
    g.innerHTML=h;document.getElementById('appPicker').classList.add('show');
}}
function toggleAppSel(el){{
    var name=el.dataset.app;var idx=selectedApps.indexOf(name);
    if(idx>=0){{selectedApps.splice(idx,1);el.classList.remove('sel')}}
    else{{selectedApps.push(name);el.classList.add('sel')}}
}}
function closePicker(){{
    document.getElementById('appPicker').classList.remove('show');renderApps();
    window.webkit.messageHandlers.macboost.postMessage({{action:'save_apps',apps:selectedApps}});
}}

function updateMetrics(d){{
    document.getElementById('cpuV').textContent=d.cpu.toFixed(1)+'%';
    document.getElementById('cpuCores').textContent=d.cpu_cores+' cores';
    updateSparkline(d.cpu);
    setRing('ramRing',d.ram_pct,100);
    document.getElementById('ramRV').textContent=d.ram_pct.toFixed(0)+'%';
    document.getElementById('ramSub').textContent=d.ram_used.toFixed(1)+' / '+d.ram_total.toFixed(0)+' GB';
    var t=d.temp||0;setRing('tempRing',Math.min(t,100),100);
    document.getElementById('tempRV').textContent=t?t.toFixed(0)+'\\u00B0':'--';
    document.getElementById('tempSub').textContent=!t||t<60?'Nominal':t<80?'Warm':'Hot';
    document.getElementById('ssdV').textContent=d.ssd_free.toFixed(0)+' GB free';
    var sb=document.getElementById('ssdB');sb.style.width=d.ssd_pct+'%';sb.className='fill '+bc(d.ssd_pct);
    var br=document.getElementById('batRow');
    if(d.bat_charge!==null){{br.style.display='flex';
        document.getElementById('batV').textContent=d.bat_charge.toFixed(0)+'%'+(d.bat_plugged?' charging':'')+(d.bat_cycles?' \\u00B7 '+d.bat_cycles+' cyc':'');
    }}else{{br.style.display='none'}}
    document.getElementById('netLbl').textContent=d.wifi||'Network';
    document.getElementById('netV').textContent=d.net_up+' \\u2191 \\u00B7 '+d.net_dn+' \\u2193';
    document.getElementById('uptime').textContent=d.uptime;
    var badge=document.getElementById('badge'),sub=document.getElementById('sub'),s=d.score||0;
    if(s>=80){{badge.innerHTML='<svg viewBox="0 0 8 8"><circle cx="4" cy="4" r="4" fill="currentColor"/></svg>Healthy';badge.className='badge g';sub.textContent='All key metrics normal \\u00B7 v{version}'}}
    else if(s>=60){{badge.innerHTML='<svg viewBox="0 0 8 8"><circle cx="4" cy="4" r="4" fill="currentColor"/></svg>Warning';badge.className='badge y';sub.textContent='Some metrics need attention \\u00B7 v{version}'}}
    else{{badge.innerHTML='<svg viewBox="0 0 8 8"><circle cx="4" cy="4" r="4" fill="currentColor"/></svg>Critical';badge.className='badge r';sub.textContent='System needs optimization \\u00B7 v{version}'}}
    if(d.clips)renderClips(d.clips);
    var dm=document.getElementById('tgl-dark');
    if(d.dark_mode)dm.classList.add('active');else dm.classList.remove('active');
    if(d.notes)renderNotes(d.notes);
}}
renderApps();
</script></body></html>"""


# ── PyObjC: WKScriptMessageHandler ──────────────────────────────────────

_app_instance = None


class _MessageHandler(NSObject, protocols=[objc.protocolNamed("WKScriptMessageHandler")]):
    def userContentController_didReceiveScriptMessage_(self, controller, message):
        body = message.body()
        if hasattr(body, "get") and _app_instance:
            _app_instance.handle_action(body)


# ── PyObjC: Status Bar App ──────────────────────────────────────────────

class MacBoostStatusBar(NSObject):

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
        self._clip_history = _load_clipboard_encrypted()
        self._last_clip_count = NSPasteboard.generalPasteboard().changeCount()
        self._selected_apps = _load_selected_apps()
        self._notes = _load_notes()

        # Load real app icons
        self._all_icons, self._installed_apps = _get_all_app_icons()

        # Status item
        self._statusItem = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength)
        btn = self._statusItem.button()
        btn.setImage_(_create_status_icon())
        btn.setTitle_(" --")
        btn.setTarget_(self)
        btn.setAction_(objc.selector(self.togglePopover_, signature=b"v@:@"))

        # Popover — light frosted glass
        self._popover = NSPopover.alloc().init()
        self._popover.setContentSize_(NSMakeSize(380, 580))
        self._popover.setBehavior_(1)
        self._popover.setAnimates_(True)
        light = NSAppearance.appearanceNamed_("NSAppearanceNameVibrantLight")
        if light:
            self._popover.setAppearance_(light)

        # WebView
        config = WKWebViewConfiguration.alloc().init()
        handler = _MessageHandler.alloc().init()
        config.userContentController().addScriptMessageHandler_name_(handler, "macboost")

        vc = NSViewController.alloc().init()
        self._webview = WKWebView.alloc().initWithFrame_configuration_(
            NSMakeRect(0, 0, 380, 580), config)
        self._webview.setValue_forKey_(False, "drawsBackground")

        from macboost import __version__
        html = _build_html(
            _get_mac_name(), __version__,
            self._all_icons, self._installed_apps, self._selected_apps,
        )
        self._webview.loadHTMLString_baseURL_(html, None)
        vc.setView_(self._webview)
        self._popover.setContentViewController_(vc)

        # Monitor thread
        threading.Thread(target=self._monitor_loop, daemon=True).start()

        # UI update timer (main thread)
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            4.0, self, "pushMetrics:", None, True)

        return self

    @objc.typedSelector(b"v@:@")
    def togglePopover_(self, sender):
        if self._popover.isShown():
            self._popover.close()
        else:
            btn = self._statusItem.button()
            self._popover.showRelativeToRect_ofView_preferredEdge_(
                btn.bounds(), btn, 1)

    @objc.typedSelector(b"v@:@")
    def pushMetrics_(self, timer):
        if not self._metrics:
            return
        js = f"updateMetrics({json.dumps(self._metrics)})"
        self._webview.evaluateJavaScript_completionHandler_(js, None)
        score = self._metrics.get("score", 0)
        self._statusItem.button().setTitle_(f" {score:.0f}")

    # ── Monitoring ──

    def _monitor_loop(self):
        while self._running:
            try:
                self._check_clipboard()
                self._collect_metrics()
            except Exception:
                pass
            time.sleep(3)

    def _check_clipboard(self):
        pb = NSPasteboard.generalPasteboard()
        count = pb.changeCount()
        if count == self._last_clip_count:
            return
        self._last_clip_count = count
        text = pb.stringForType_("public.utf8-plain-text")
        if not text:
            return
        text_str = str(text)
        if self._clip_history and self._clip_history[0].get("full") == text_str:
            return
        is_url = text_str.startswith("http://") or text_str.startswith("https://")
        self._clip_history.insert(0, {
            "full": text_str,
            "preview": text_str[:100].replace("\n", " ").strip(),
            "time": time.time(),
            "type": "url" if is_url else "text",
        })
        if len(self._clip_history) > 50:
            self._clip_history.pop()
        _save_clipboard_encrypted(self._clip_history)

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

        try:
            score = calculate_health_score()["total"]
        except Exception:
            score = 0

        clips = [{"p": c["preview"], "t": _time_ago(c["time"]), "tp": c["type"]}
                 for c in self._clip_history[:15]]

        self._metrics = {
            "cpu": cpu, "cpu_cores": cores,
            "ram_pct": mem.percent,
            "ram_used": round(mem.used / (1024**3), 2),
            "ram_total": round(mem.total / (1024**3), 0),
            "ssd_pct": ssd_pct,
            "ssd_total": round(disk.total / (1024**3), 0),
            "ssd_free": round(disk.free / (1024**3), 0),
            "uptime": uptime, "temp": temp,
            "bat_charge": bat.percent if bat else None,
            "bat_plugged": bat.power_plugged if bat else None,
            "bat_cycles": bat_cycles, "bat_condition": bat_cond,
            "net_up": _bytes_human(sent_d / 4) + "/s",
            "net_dn": _bytes_human(recv_d / 4) + "/s",
            "score": score, "clips": clips,
            "notes": [{"text": n["text"], "t": _time_ago(n["ts"])} for n in self._notes[:30]],
            "dark_mode": _is_dark_mode(),
            "wifi": _get_wifi_ssid(),
        }

    # ── Actions ──

    def handle_action(self, msg):
        action = msg.get("action", "") if hasattr(msg, "get") else str(msg)

        if action == "quit":
            self._running = False
            PID_FILE.unlink(missing_ok=True)
            NSApplication.sharedApplication().terminate_(None)
        elif action == "prefs":
            subprocess.Popen(["open", str(APP_DIR)])
        elif action == "open_app":
            app = msg.get("app", "")
            if app:
                subprocess.Popen(["open", "-a", str(app)])
        elif action == "clip_copy":
            idx = msg.get("idx", -1)
            if isinstance(idx, (int, float)) and 0 <= int(idx) < len(self._clip_history):
                text = self._clip_history[int(idx)]["full"]
                pb = NSPasteboard.generalPasteboard()
                pb.clearContents()
                pb.setString_forType_(text, "public.utf8-plain-text")
                self._last_clip_count = pb.changeCount()
                _notify("MacBoost", "Copied to clipboard")
        elif action == "clip_clear":
            self._clip_history.clear()
            _save_clipboard_encrypted(self._clip_history)
            js = 'renderClips([])'
            self._webview.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(self._evalJS_, signature=b"v@:@"), js, False)
        elif action == "add_note":
            text = msg.get("text", "")
            if text:
                self._notes.insert(0, {"text": str(text), "ts": time.time()})
                _save_notes(self._notes)
        elif action == "delete_note":
            idx = msg.get("idx", -1)
            if isinstance(idx, (int, float)) and 0 <= int(idx) < len(self._notes):
                self._notes.pop(int(idx))
                _save_notes(self._notes)
        elif action == "save_apps":
            apps = msg.get("apps")
            if apps:
                self._selected_apps = [str(a) for a in apps]
                _save_selected_apps(self._selected_apps)
        elif action == "toggle_dark":
            subprocess.Popen(["osascript", "-e",
                'tell app "System Events" to tell appearance preferences to set dark mode to not dark mode'])
        elif action == "lock_screen":
            subprocess.Popen(["pmset", "displaysleepnow"])
        elif action == "screenshot":
            subprocess.Popen(["screencapture", "-ic"])
        elif action == "empty_trash":
            subprocess.Popen(["osascript", "-e", 'tell app "Finder" to empty trash'])
            _notify("MacBoost", "Trash emptied")
        elif action in ("quick", "scan", "clean"):
            threading.Thread(target=self._do_action, args=(action,), daemon=True).start()

    def _do_action(self, name):
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
            objc.selector(self._evalJS_, signature=b"v@:@"), js, False)

    @objc.typedSelector(b"v@:@")
    def _evalJS_(self, js_string):
        self._webview.evaluateJavaScript_completionHandler_(js_string, None)

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
            stdout=log, stderr=log, stdin=subprocess.DEVNULL)
    PID_FILE.write_text(str(proc.pid))
    print(f"MacBoost iniciado en segundo plano (PID: {proc.pid})")
    print("  Busca el icono en tu barra de menu")
    print("  Para detener: macboost menubar stop")


def stop_daemon():
    if not PID_FILE.exists():
        try:
            r = subprocess.run(["pgrep", "-f", "macboost.menubar"], capture_output=True, text=True)
            if r.stdout.strip():
                for pid in r.stdout.strip().splitlines():
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
    running = _is_running()
    pid = None
    if running and PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
    return {"running": running, "pid": pid}


def run_menubar():
    _write_pid()
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)
    delegate = MacBoostStatusBar.alloc().init()
    app.setDelegate_(delegate)
    app.run()
