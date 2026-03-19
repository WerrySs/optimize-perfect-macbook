"""Formatters — Output con Rich (tablas, barras, colores)."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text

console = Console()


def print_header():
    console.print(Panel.fit(
        "[bold cyan]⚡ MacBoost[/bold cyan] — Optimización total para macOS",
        border_style="cyan",
    ))


def print_health_score(score_data: dict):
    total = score_data["total"]
    scores = score_data["scores"]

    if total >= 80:
        color = "green"
        status = "Excelente"
    elif total >= 60:
        color = "yellow"
        status = "Aceptable"
    else:
        color = "red"
        status = "Necesita atención"

    console.print(f"\n[bold {color}]Health Score: {total}/100 — {status}[/bold {color}]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Métrica", style="white")
    table.add_column("Score", justify="right")
    table.add_column("Barra", width=30)

    for name, value in scores.items():
        bar = _make_bar(value)
        v_color = "green" if value >= 80 else "yellow" if value >= 60 else "red"
        table.add_row(name.upper(), f"[{v_color}]{value}[/{v_color}]", bar)

    console.print(table)


def print_scan_result(result):
    status_icon = {"ok": "✓", "warning": "⚠", "error": "✗", "info": "ℹ"}.get(result.status, "?")
    status_color = {"ok": "green", "warning": "yellow", "error": "red", "info": "blue"}.get(result.status, "white")

    console.print(f"[{status_color}]{status_icon}[/{status_color}] [bold]{result.module}[/bold]: {result.summary}")

    if result.issues:
        for issue in result.issues:
            severity_color = {"high": "red", "medium": "yellow", "low": "dim"}.get(issue.get("severity", "low"), "white")
            fixable = " [green](corregible)[/green]" if issue.get("fixable") else ""
            console.print(f"  [{severity_color}]→[/{severity_color}] {issue['description']}{fixable}")


def print_full_scan(report):
    print_header()
    console.print(f"\n[bold]Escaneo completado en {report.duration_seconds:.1f}s[/bold]\n")

    for name, result in report.results.items():
        print_scan_result(result)
        console.print()

    console.print(f"[bold]Total: {report.total_issues} problemas, {report.total_fixable} corregibles[/bold]")


def print_fix_result(result):
    status_icon = "✓" if result.status == "ok" else "✗"
    status_color = "green" if result.status == "ok" else "red"
    preview_tag = " [dim](PREVIEW)[/dim]" if result.preview_only else ""

    console.print(f"[{status_color}]{status_icon}[/{status_color}] [bold]{result.module}[/bold]{preview_tag}: {result.summary}")

    for action in result.actions:
        icon = "→" if not action.get("skipped") else "⊘"
        color = "dim" if action.get("skipped") or action.get("preview") else "green"
        console.print(f"  [{color}]{icon}[/{color}] {action['detail']}")


def print_fix_results(results: dict):
    print_header()
    console.print()
    for name, result in results.items():
        print_fix_result(result)
        console.print()


def print_status(status: dict):
    print_header()
    score = status["health_score"]
    if score >= 80:
        color = "green"
    elif score >= 60:
        color = "yellow"
    else:
        color = "red"

    console.print(f"\n[bold {color}]⚡ Health Score: {score}/100[/bold {color}]")
    console.print(f"[dim]Módulos activos: {', '.join(status['modules_enabled'])}[/dim]")

    scores = status["scores"]
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Métrica", style="bold")
    table.add_column("Valor", justify="right")
    table.add_column("Barra", width=25)

    for name, value in scores.items():
        bar = _make_bar(value)
        v_color = "green" if value >= 80 else "yellow" if value >= 60 else "red"
        table.add_row(name.upper(), f"[{v_color}]{value}[/{v_color}]", bar)

    console.print(table)

    last_undo = status.get("last_undo")
    if last_undo:
        console.print(f"\n[dim]Último undo disponible: {last_undo.description} (ID: {last_undo.id})[/dim]")


def print_undo_list(entries: list):
    if not entries:
        console.print("[dim]No hay operaciones para deshacer.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan")
    table.add_column("Módulo")
    table.add_column("Descripción")
    table.add_column("Fecha", style="dim")

    from datetime import datetime
    for entry in entries:
        dt = datetime.fromtimestamp(entry.timestamp).strftime("%d/%m %H:%M")
        table.add_row(entry.id, entry.module, entry.description, dt)

    console.print(table)


def print_process_table(processes: list):
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("PID", justify="right", style="dim")
    table.add_column("Proceso")
    table.add_column("RAM (MB)", justify="right")
    table.add_column("", width=20)

    for p in processes:
        bar = _make_bar(min(p["rss_mb"] / 10, 100))  # Escala relativa
        color = "red" if p["rss_mb"] > 1000 else "yellow" if p["rss_mb"] > 500 else "white"
        table.add_row(
            str(p["pid"]),
            p["name"],
            f"[{color}]{p['rss_mb']}[/{color}]",
            bar,
        )

    console.print(table)


def print_agents_table(agents: list):
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Label")
    table.add_column("Estado", justify="center")
    table.add_column("Tipo")
    table.add_column("Gestionable", justify="center")

    for a in agents:
        state = "[green]ON[/green]" if a.get("enabled") else "[red]OFF[/red]"
        manageable = "✓" if a.get("manageable") else "—"
        loc = a.get("location", "").replace("_", " ").title()
        table.add_row(a["label"], state, loc, manageable)

    console.print(table)


def _make_bar(value: float, width: int = 20) -> str:
    filled = int(value / 100 * width)
    empty = width - filled
    if value >= 80:
        color = "green"
    elif value >= 60:
        color = "yellow"
    else:
        color = "red"
    return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"
