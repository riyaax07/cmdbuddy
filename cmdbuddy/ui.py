"""Rich terminal UI formatting for CmdBuddy."""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Safe stdout/stderr reconfiguration for Windows consoles
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

console = Console(safe_box=True)


def get_risk_badge(risk: str) -> Text:
    """Return a styled Rich Text badge for a given risk level."""
    r = risk.lower().strip()
    if r == "read-only":
        return Text(" READ-ONLY ", style="bold black on green")
    elif r == "write":
        return Text(" WRITE ", style="bold black on yellow")
    elif r == "network":
        return Text(" NETWORK ", style="bold white on blue")
    elif r == "destructive":
        return Text(" DESTRUCTIVE ", style="bold white on red")
    elif r == "blocked":
        return Text(" BLOCKED ", style="bold white on dark_red")
    return Text(f" {r.upper()} ", style="bold white on grey50")


def print_banner() -> None:
    """Print the CmdBuddy ASCII header."""
    text = Text("CmdBuddy", style="bold cyan")
    text.append(" - PowerShell-First AI Command Assistant", style="dim")
    console.print(Panel(text, border_style="cyan", expand=False))


def display_context(context_data: Dict[str, Any]) -> None:
    """Render the detected project context in a clean Rich UI."""
    cwd = context_data.get("cwd", "Unknown")
    project_type = context_data.get("project_type", "Unknown")
    package_manager = context_data.get("package_manager", "Unknown")
    project_name = context_data.get("project_name", "")
    project_version = context_data.get("project_version")
    git_branch = context_data.get("git_branch")
    git_status = context_data.get("git_status")
    git_last_commit = context_data.get("git_last_commit")
    scripts = context_data.get("scripts", {})
    dependencies = context_data.get("dependencies", [])
    dev_dependencies = context_data.get("dev_dependencies", [])
    config_files = context_data.get("config_files", [])
    node_version = context_data.get("node_version")
    npm_version = context_data.get("npm_version")
    known_facts = context_data.get("known_facts", [])
    unknowns = context_data.get("unknowns", [])

    # Metadata Table
    table = Table(title="Detected Project Context", title_style="bold cyan", border_style="dim")
    table.add_column("Property", style="bold yellow", width=22)
    table.add_column("Value", style="white")

    table.add_row("Directory", cwd)
    table.add_row("Project Name", project_name or "(unnamed)")
    if project_version:
        table.add_row("Version", project_version)
    table.add_row("Project Type", project_type)
    table.add_row("Package Manager", package_manager)
    if git_branch:
        table.add_row("Git Branch", git_branch)
    if git_status:
        table.add_row("Git Status", git_status)
    if git_last_commit:
        table.add_row("Git Last Commit", f'"{git_last_commit}"')
    if node_version:
        table.add_row("Node Version", node_version)
    if npm_version:
        table.add_row("npm Version", npm_version)
    if config_files:
        table.add_row("Config Files", ", ".join(config_files))

    console.print(table)

    # Scripts Table (if present)
    if scripts:
        scripts_table = Table(title="Defined Project Scripts", title_style="bold green", border_style="dim")
        scripts_table.add_column("Script Name", style="bold magenta", width=18)
        scripts_table.add_column("Command", style="white")
        for name, cmd in scripts.items():
            scripts_table.add_row(name, str(cmd))
        console.print(scripts_table)

    # Dependencies preview
    dep_summary = []
    if dependencies:
        dep_summary.append(f"[bold]Dependencies:[/bold] {len(dependencies)} ({', '.join(dependencies[:6])}{'...' if len(dependencies) > 6 else ''})")
    if dev_dependencies:
        dep_summary.append(f"[bold]DevDependencies:[/bold] {len(dev_dependencies)} ({', '.join(dev_dependencies[:6])}{'...' if len(dev_dependencies) > 6 else ''})")

    if dep_summary:
        console.print(Panel("\n".join(dep_summary), title="Packages", border_style="dim", expand=False))

    # Knowledge Summary: What CmdBuddy knows & what it does not know
    facts_lines = [f"[green]+[/green] {fact}" for fact in known_facts]
    unknowns_lines = [f"[yellow]?[/yellow] {unk}" for unk in unknowns]

    knowledge_text = ""
    if facts_lines:
        knowledge_text += "[bold]What CmdBuddy knows:[/bold]\n" + "\n".join(facts_lines)
    if unknowns_lines:
        if knowledge_text:
            knowledge_text += "\n\n"
        knowledge_text += "[bold]What CmdBuddy does not know / missing:[/bold]\n" + "\n".join(unknowns_lines)

    if knowledge_text:
        console.print(Panel(knowledge_text, title="Context Knowledge Summary", border_style="cyan", expand=False))

    # Security guarantee footer
    console.print("[dim green][OK] Safe scan: .env, credentials, secrets, and binary files were strictly excluded.[/dim green]\n")


def display_history(history_entries: List[Dict[str, Any]]) -> None:
    """Render recent command execution history."""
    if not history_entries:
        console.print("[dim yellow]No command history found.[/dim yellow]")
        return

    table = Table(title="Recent CmdBuddy History", title_style="bold cyan", border_style="dim")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Timestamp", style="dim", width=19)
    table.add_column("Prompt / Command", style="white")
    table.add_column("Status", width=12)
    table.add_column("Exit", width=6)

    for item in history_entries:
        ts = item.get("timestamp", "")[:19].replace("T", " ")
        prompt_or_cmd = item.get("prompt") or item.get("executed_command") or "N/A"

        status = item.get("status", "unknown")
        if status in ("executed", "success"):
            status_style = "[green]executed[/green]"
        elif status == "failed":
            status_style = "[red]failed[/red]"
        elif status == "copied":
            status_style = "[cyan]copied[/cyan]"
        else:
            status_style = f"[yellow]{status}[/yellow]"

        exit_code = str(item.get("exit_code")) if item.get("exit_code") is not None else "-"
        table.add_row(str(item.get("id")), ts, prompt_or_cmd, status_style, exit_code)

    console.print(table)
