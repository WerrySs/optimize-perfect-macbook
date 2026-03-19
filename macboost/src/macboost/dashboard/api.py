"""REST API endpoints para el dashboard."""

from __future__ import annotations

from fastapi import APIRouter

from macboost.core.health import calculate_health_score
from macboost.core.orchestrator import Orchestrator

router = APIRouter(prefix="/api")

_orch: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orch
    if _orch is None:
        _orch = Orchestrator()
    return _orch


@router.get("/status")
def api_status():
    orch = get_orchestrator()
    return orch.get_status()


@router.get("/health")
def api_health():
    return calculate_health_score()


@router.get("/scan")
def api_scan_all():
    orch = get_orchestrator()
    report = orch.scan_all()
    return {
        "duration": report.duration_seconds,
        "total_issues": report.total_issues,
        "total_fixable": report.total_fixable,
        "results": {
            name: {
                "module": r.module,
                "status": r.status,
                "summary": r.summary,
                "issues": r.issues,
                "space_recoverable": r.space_recoverable_bytes,
            }
            for name, r in report.results.items()
        },
    }


@router.get("/scan/{module}")
def api_scan_module(module: str):
    orch = get_orchestrator()
    result = orch.scan_module(module)
    return {
        "module": result.module,
        "status": result.status,
        "summary": result.summary,
        "issues": result.issues,
    }


@router.post("/fix")
def api_fix_all(preview: bool = False):
    orch = get_orchestrator()
    results = orch.fix_all(preview=preview)
    return {
        name: {
            "module": r.module,
            "status": r.status,
            "summary": r.summary,
            "actions": r.actions,
            "space_freed": r.space_freed_bytes,
            "preview": r.preview_only,
        }
        for name, r in results.items()
    }


@router.post("/fix/{module}")
def api_fix_module(module: str, preview: bool = False):
    orch = get_orchestrator()
    result = orch.fix_module(module, preview=preview)
    return {
        "module": result.module,
        "status": result.status,
        "summary": result.summary,
        "actions": result.actions,
        "preview": result.preview_only,
    }


@router.post("/quick")
def api_quick_optimize():
    orch = get_orchestrator()
    results = orch.quick_optimize()
    return {
        name: {"status": r.status, "summary": r.summary, "actions": r.actions}
        for name, r in results.items()
    }


@router.get("/undo/list")
def api_undo_list():
    orch = get_orchestrator()
    entries = orch.undo.list_entries()
    return [e.to_dict() for e in entries]


@router.post("/undo/{entry_id}")
def api_undo(entry_id: str):
    orch = get_orchestrator()
    success, msg = orch.undo.execute_undo(entry_id)
    return {"success": success, "message": msg}


@router.post("/undo/latest")
def api_undo_latest():
    orch = get_orchestrator()
    latest = orch.undo.get_latest()
    if not latest:
        return {"success": False, "message": "No hay operaciones para deshacer"}
    success, msg = orch.undo.execute_undo(latest.id)
    return {"success": success, "message": msg}


@router.get("/processes")
def api_processes(limit: int = 20):
    orch = get_orchestrator()
    ram_mod = orch.modules.get("ram")
    if ram_mod:
        return ram_mod.get_top_processes(limit)
    return []


@router.get("/agents")
def api_agents():
    orch = get_orchestrator()
    boot_mod = orch.modules.get("boot")
    if boot_mod:
        return boot_mod.get_all_agents()
    return []


@router.post("/power/{profile}")
def api_set_power_profile(profile: str):
    orch = get_orchestrator()
    power_mod = orch.modules.get("power")
    if power_mod:
        result = power_mod.set_profile(profile)
        return {"status": result.status, "summary": result.summary, "actions": result.actions}
    return {"status": "error", "summary": "Módulo de energía no disponible"}


@router.get("/metrics")
def api_metrics():
    """Métricas actuales del sistema para gráficas."""
    orch = get_orchestrator()
    monitor = orch.modules.get("monitor")
    if monitor:
        return monitor.collect_metrics()
    return {}


@router.get("/version")
def api_version():
    """Versión actual y disponibilidad de actualizaciones."""
    from macboost import __version__
    from macboost.core.updater import check_update
    info = check_update()
    return {
        "current": __version__,
        "latest": info["latest"],
        "update_available": info["available"],
        "message": info["message"],
    }
