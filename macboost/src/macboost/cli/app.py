"""CLI principal de MacBoost con Typer."""

from __future__ import annotations

import subprocess
import webbrowser
from typing import Optional

import typer
from rich.console import Console

from macboost.cli.formatters import (
    print_agents_table,
    print_fix_result,
    print_fix_results,
    print_full_scan,
    print_header,
    print_health_score,
    print_process_table,
    print_scan_result,
    print_status,
    print_undo_list,
)
from macboost.core.health import calculate_health_score
from macboost.core.orchestrator import Orchestrator

app = typer.Typer(
    name="macboost",
    help="⚡ MacBoost — Optimización total para macOS en Apple Silicon.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

# Sub-apps
power_app = typer.Typer(help="Gestión de perfiles de energía.")
menubar_app = typer.Typer(help="Control de la menu bar app.")
auto_app = typer.Typer(help="Automatización de escaneos.")
undo_app = typer.Typer(help="Deshacer operaciones anteriores.")
app.add_typer(power_app, name="power")
app.add_typer(menubar_app, name="menubar")
app.add_typer(auto_app, name="auto")
app.add_typer(undo_app, name="undo")


def _get_orchestrator() -> Orchestrator:
    return Orchestrator()


# === SCAN ===
@app.command()
def scan(
    all: bool = typer.Option(False, "--all", "-a", help="Escanear todos los módulos"),
    module: Optional[str] = typer.Option(None, "--module", "-m", help="Módulo específico a escanear"),
):
    """Escanear el sistema en busca de optimizaciones."""
    orch = _get_orchestrator()

    if all or not module:
        report = orch.scan_all()
        print_full_scan(report)
    else:
        result = orch.scan_module(module)
        print_header()
        console.print()
        print_scan_result(result)


# === FIX ===
@app.command()
def fix(
    all: bool = typer.Option(False, "--all", "-a", help="Aplicar todas las optimizaciones"),
    module: Optional[str] = typer.Option(None, "--module", "-m", help="Módulo específico"),
    preview: bool = typer.Option(False, "--preview", "-p", help="Solo mostrar qué se haría"),
):
    """Aplicar optimizaciones al sistema."""
    orch = _get_orchestrator()

    if all or not module:
        if not preview:
            confirm = typer.confirm("¿Aplicar TODAS las optimizaciones?")
            if not confirm:
                raise typer.Abort()
        results = orch.fix_all(preview=preview)
        print_fix_results(results)
    else:
        result = orch.fix_module(module, preview=preview)
        print_header()
        console.print()
        print_fix_result(result)


# === QUICK ===
@app.command()
def quick():
    """Optimización rápida: purge RAM + flush DNS + limpiar /tmp."""
    print_header()
    console.print("\n[bold cyan]Ejecutando optimización rápida...[/bold cyan]\n")
    orch = _get_orchestrator()
    results = orch.quick_optimize()
    for name, result in results.items():
        print_fix_result(result)
    console.print("\n[bold green]✓ Optimización rápida completada[/bold green]")


# === STATUS ===
@app.command()
def status():
    """Ver estado de salud del sistema."""
    orch = _get_orchestrator()
    st = orch.get_status()
    print_status(st)

    # Chequeo de actualizaciones en background (no bloquea si no hay red)
    try:
        from macboost.core.updater import check_update
        info = check_update()
        if info["available"]:
            console.print(f"\n[bold yellow]⬆ Nueva versión disponible: v{info['latest']}[/bold yellow]")
            console.print("[dim]  Actualizar con: macboost update[/dim]")
    except Exception:
        pass


# === DASHBOARD ===
@app.command()
def dashboard():
    """Abrir el dashboard web en el navegador."""
    console.print("[cyan]Iniciando dashboard en http://localhost:7777...[/cyan]")
    webbrowser.open("http://localhost:7777")

    from macboost.dashboard.server import start_server
    start_server()


# === UNDO ===
@undo_app.callback(invoke_without_command=True)
def undo_default(
    ctx: typer.Context,
    list_all: bool = typer.Option(False, "--list", "-l", help="Listar historial de operaciones"),
    entry_id: Optional[str] = typer.Option(None, "--id", help="Revertir operación específica por ID"),
):
    """Revertir la última optimización o una operación específica."""
    if ctx.invoked_subcommand is not None:
        return

    orch = _get_orchestrator()

    if list_all:
        entries = orch.undo.list_entries()
        print_undo_list(entries)
        return

    if entry_id:
        success, msg = orch.undo.execute_undo(entry_id)
    else:
        latest = orch.undo.get_latest()
        if not latest:
            console.print("[dim]No hay operaciones para deshacer.[/dim]")
            return
        console.print(f"Deshaciendo: [bold]{latest.description}[/bold]")
        confirm = typer.confirm("¿Continuar?")
        if not confirm:
            raise typer.Abort()
        success, msg = orch.undo.execute_undo(latest.id)

    color = "green" if success else "red"
    console.print(f"[{color}]{msg}[/{color}]")


# === POWER ===
@power_app.callback(invoke_without_command=True)
def power_default(
    ctx: typer.Context,
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Perfil: lowpower / balanced / performance"),
    show_status: bool = typer.Option(False, "--status", "-s", help="Ver perfil actual"),
):
    """Gestionar perfiles de energía."""
    if ctx.invoked_subcommand is not None:
        return

    orch = _get_orchestrator()

    if show_status:
        power_mod = orch.modules.get("power")
        if power_mod:
            st = power_mod.get_current_status()
            console.print(f"[bold]Perfil actual:[/bold] {st['profile']}")
            console.print(f"[dim]Spotlight indexing:[/dim] {'Sí' if st['spotlight_indexing'] else 'No'}")
            console.print(f"[dim]Perfiles disponibles:[/dim] {', '.join(st['profiles_available'])}")
        return

    if profile:
        power_mod = orch.modules.get("power")
        if power_mod:
            result = power_mod.set_profile(profile)
            print_fix_result(result)
        else:
            console.print("[red]Módulo de energía no disponible[/red]")
        return

    console.print("[dim]Usa --profile o --status. Ejemplo: macboost power --profile performance[/dim]")


# === MENUBAR ===
@menubar_app.command("start")
def menubar_start():
    """Iniciar la menu bar app."""
    console.print("[cyan]Iniciando MacBoost Menu Bar...[/cyan]")
    try:
        from macboost.menubar.app import run_menubar
        run_menubar()
    except ImportError:
        console.print("[red]Error: dependencias de menu bar no instaladas (rumps, pyobjc)[/red]")


@menubar_app.command("stop")
def menubar_stop():
    """Detener la menu bar app."""
    try:
        subprocess.run(["pkill", "-f", "macboost.menubar"], capture_output=True)
        console.print("[green]Menu bar app detenida[/green]")
    except Exception:
        console.print("[dim]No se encontró la menu bar app en ejecución[/dim]")


# === AUTO ===
@auto_app.callback(invoke_without_command=True)
def auto_default(
    ctx: typer.Context,
    interval: Optional[str] = typer.Option(None, "--interval", "-i", help="Intervalo (ej: 6h, 30m)"),
    stop: bool = typer.Option(False, "--stop", help="Detener automatización"),
    show_status: bool = typer.Option(False, "--status", "-s", help="Ver estado de automatización"),
):
    """Configurar escaneos automáticos."""
    if ctx.invoked_subcommand is not None:
        return

    if stop:
        console.print("[yellow]Automatización detenida[/yellow]")
        return

    if show_status:
        console.print("[dim]Automatización: no configurada[/dim]")
        return

    if interval:
        console.print(f"[cyan]Automatización configurada cada {interval}[/cyan]")
        orch = _get_orchestrator()
        orch.config.set("general", "auto_scan_interval", interval)
        console.print("[green]✓ Configuración guardada[/green]")
        return

    console.print("[dim]Usa --interval, --stop, o --status[/dim]")


# === Extras: top processes ===
@app.command("top")
def top_processes(
    limit: int = typer.Option(20, "--limit", "-n", help="Número de procesos"),
):
    """Mostrar los procesos que más RAM consumen."""
    orch = _get_orchestrator()
    ram_mod = orch.modules.get("ram")
    if ram_mod:
        procs = ram_mod.get_top_processes(limit)
        print_header()
        console.print(f"\n[bold]Top {limit} procesos por consumo de RAM:[/bold]\n")
        print_process_table(procs)


@app.command("agents")
def list_agents():
    """Listar todos los Launch Agents del sistema."""
    orch = _get_orchestrator()
    boot_mod = orch.modules.get("boot")
    if boot_mod:
        agents = boot_mod.get_all_agents()
        print_header()
        console.print(f"\n[bold]{len(agents)} Launch Agents/Daemons encontrados:[/bold]\n")
        print_agents_table(agents)


@app.command("health")
def health():
    """Ver Health Score detallado."""
    print_header()
    console.print()
    score_data = calculate_health_score()
    print_health_score(score_data)


# === VERSION ===
@app.command("version")
def version_cmd(
    short: bool = typer.Option(False, "--short", help="Solo mostrar número de versión"),
    check: bool = typer.Option(False, "--check", "-c", help="Verificar si hay actualizaciones"),
):
    """Mostrar versión de MacBoost y verificar actualizaciones."""
    from macboost import __version__

    if short:
        console.print(__version__)
        return

    console.print(f"[bold cyan]⚡ MacBoost[/bold cyan] v{__version__}")

    if check:
        from macboost.core.updater import check_update
        console.print("[dim]Verificando actualizaciones...[/dim]")
        info = check_update()
        if info["available"]:
            console.print(f"\n[bold yellow]Nueva versión disponible: v{info['latest']}[/bold yellow]")
            console.print(f"[dim]Versión actual: v{info['current']}[/dim]")
            console.print(f"\n  Actualizar con: [cyan]macboost update[/cyan]")
        else:
            console.print(f"\n[green]✓ {info['message']}[/green]")


# === UPDATE ===
@app.command("update")
def update_cmd(
    force: bool = typer.Option(False, "--force", "-f", help="Forzar reinstalación aunque esté actualizado"),
):
    """Actualizar MacBoost a la última versión."""
    from macboost import __version__
    from macboost.core.updater import check_update, perform_update

    print_header()
    console.print(f"\n[dim]Versión actual: v{__version__}[/dim]")
    console.print("[cyan]Verificando actualizaciones...[/cyan]\n")

    info = check_update()

    if not info["available"] and not force:
        console.print(f"[green]✓ {info['message']}[/green]")
        return

    if info["available"]:
        console.print(f"[bold yellow]Nueva versión disponible: v{info['latest']}[/bold yellow]")
        confirm = typer.confirm("¿Actualizar ahora?")
        if not confirm:
            raise typer.Abort()

    console.print("[cyan]Descargando e instalando...[/cyan]")
    success, msg = perform_update(force=force)

    if success:
        console.print(f"\n[bold green]✓ {msg}[/bold green]")
        console.print("[dim]Reinicia tu terminal para usar la nueva versión.[/dim]")
    else:
        console.print(f"\n[bold red]✗ {msg}[/bold red]")


if __name__ == "__main__":
    app()
