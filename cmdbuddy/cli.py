"""Main CLI interface for CmdBuddy (cmb)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional
import typer
from rich.panel import Panel
from rich.table import Table

from cmdbuddy import __version__
from cmdbuddy.ai_client import GeminiClient, GeminiClientError
from cmdbuddy.context_engine import scan_project_context
from cmdbuddy.error_capture import capture_terminal_error
from cmdbuddy.executor import prompt_and_execute_command
from cmdbuddy.safety import classify_command, validate_snippet_name
from cmdbuddy.storage import StorageManager
from cmdbuddy.ui import console, display_context, display_history, get_risk_badge, print_banner

_app = typer.Typer(
    name="cmb",
    help="CmdBuddy: PowerShell-first AI command assistant for developers.",
    add_completion=False,
    no_args_is_help=True,
)

storage = StorageManager()

KNOWN_SUBCOMMANDS = {
    "context",
    "history",
    "fix",
    "explain",
    "save",
    "find",
    "run",
}


def _check_api_key(cwd: Path, action_name: str) -> Optional[str]:
    """Verify GEMINI_API_KEY presence and display guidance if missing."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            Panel(
                "[bold yellow]GEMINI_API_KEY environment variable is not set.[/bold yellow]\n\n"
                f"To use CmdBuddy {action_name}, please set your API key in PowerShell:\n"
                "  [cyan]$env:GEMINI_API_KEY = 'your_actual_gemini_api_key'[/cyan]\n\n"
                "[dim]To set it permanently for your user account:[/dim]\n"
                "  [dim][Environment]::SetEnvironmentVariable('GEMINI_API_KEY', 'your_key', 'User')[/dim]",
                title="API Key Required",
                border_style="yellow",
            )
        )
        storage.add_history_entry(
            working_dir=str(cwd),
            prompt=action_name,
            status="missing_api_key",
        )
        return None
    return api_key


def handle_prompt(prompt: str) -> None:
    """Handle a plain-English request (e.g. cmb 'create a react vite typescript app')."""
    print_banner()
    cwd = Path.cwd()

    api_key = _check_api_key(cwd, f"command generation: '{prompt}'")
    if not api_key:
        return

    # Scan directory context
    with console.status("[bold cyan]Scanning project context...[/bold cyan]"):
        ctx = scan_project_context(cwd)

    if not ctx.get("is_project"):
        console.print("[dim yellow]Note: Current directory is not recognized as a project. Generating general PowerShell commands.[/dim yellow]")

    # Call Gemini
    client = GeminiClient(api_key=api_key)
    try:
        with console.status("[bold cyan]Generating PowerShell commands via Gemini...[/bold cyan]"):
            result = client.generate_commands(user_intent=prompt, project_context=ctx, target_dir=cwd)
    except GeminiClientError as e:
        console.print(Panel(f"[bold red]Command Generation Failed:[/bold red]\n{e}", border_style="red"))
        storage.add_history_entry(
            working_dir=str(cwd),
            prompt=prompt,
            status="failed",
            error_text=str(e),
        )
        return

    # Present summary
    console.print(Panel(f"[bold white]{result.summary}[/bold white]", title="CmdBuddy Plan", border_style="cyan"))

    if result.limitations:
        lims = "\n".join(f" - {lim}" for lim in result.limitations)
        console.print(f"[dim]{lims}[/dim]\n")

    # Execute / approve each command in sequence
    for idx, cmd in enumerate(result.commands, 1):
        console.print(f"[bold cyan]Step {idx} of {len(result.commands)}:[/bold cyan]")
        exec_result = prompt_and_execute_command(
            command=cmd.command,
            explanation=cmd.explanation,
            risk=cmd.risk,
            cwd=cwd,
            storage=storage,
            prompt_context=prompt,
        )

        if exec_result.get("action") == "cancel":
            console.print("[dim]Sequence aborted by user.[/dim]")
            break
        if exec_result.get("exit_code", 0) != 0 and exec_result.get("action") == "run":
            console.print(f"[bold red]Step {idx} failed with exit code {exec_result.get('exit_code')}. Stopping execution.[/bold red]")
            break


@_app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show CmdBuddy version and exit.",
    ),
) -> None:
    """CmdBuddy — PowerShell-first AI command assistant."""
    if version:
        console.print(f"[bold cyan]CmdBuddy[/bold cyan] version [green]{__version__}[/green]")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        print_banner()
        console.print(ctx.get_help())


@_app.command("context")
def context_command() -> None:
    """Inspect and display detected project context from current working directory."""
    print_banner()
    with console.status("[bold cyan]Scanning directory context...[/bold cyan]"):
        ctx = scan_project_context()
    display_context(ctx)


@_app.command("history")
def history_command(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of recent entries to show"),
) -> None:
    """Display recent command generation and execution history."""
    print_banner()
    entries = storage.get_history(limit=limit)
    display_history(entries)


@_app.command("fix")
def fix_command() -> None:
    """Diagnose the last captured terminal error using automated project context."""
    print_banner()
    cwd = Path.cwd()

    # 1. 3-Tier Error Capture
    last_cmd, error_text, capture_source = capture_terminal_error(storage, interactive=True)

    # 2. Automatically attach project context
    with console.status("[bold cyan]Analyzing local project context...[/bold cyan]"):
        ctx = scan_project_context(cwd)

    if not ctx.get("is_project"):
        console.print("[dim yellow]Note: Current directory is not recognized as a project repository.[/dim yellow]")
    else:
        console.print(f"[dim]Project Type: [bold]{ctx['project_type']}[/bold] | Manager: [bold]{ctx['package_manager']}[/bold][/dim]")

    # 3. Request Diagnosis from Gemini (with offline grounded fallback)
    api_key = os.environ.get("GEMINI_API_KEY")
    client = GeminiClient(api_key=api_key)
    try:
        with console.status("[bold cyan]Diagnosing issue...[/bold cyan]"):
            diagnosis = client.diagnose_error(
                error_text=error_text,
                last_command=last_cmd,
                project_context=ctx,
                target_dir=cwd,
            )
    except GeminiClientError as e:
        console.print(Panel(f"[bold yellow]Diagnosis Unavailable:[/bold yellow]\n{e}", border_style="yellow"))
        storage.add_history_entry(
            working_dir=str(cwd),
            prompt="cmb fix",
            status="failed",
            error_text=str(e),
        )
        return

    # 4. Display Diagnosis Results
    conf_pct = int(diagnosis.confidence * 100)
    status_color = "green" if diagnosis.diagnosis_status == "supported" else "yellow"

    diag_text = (
        f"[bold white]{diagnosis.summary}[/bold white]\n\n"
        f"[bold cyan]Root Cause:[/bold cyan] {diagnosis.root_cause}\n"
        f"[bold cyan]Confidence:[/bold cyan] {conf_pct}% "
        f"([bold {status_color}]{diagnosis.diagnosis_status.upper()}[/bold {status_color}])\n"
    )
    console.print(Panel(diag_text, title="CmdBuddy Diagnosis", border_style="cyan"))

    # Evidence Table
    if diagnosis.evidence:
        table = Table(title="Grounded Evidence From Project Files", border_style="dim")
        table.add_column("File", style="bold magenta", width=25)
        table.add_column("Observation", style="white")
        for ev in diagnosis.evidence:
            table.add_row(ev.file, ev.observation)
        console.print(table)

    if diagnosis.missing_information:
        console.print("[dim yellow]Missing Information:[/dim yellow] " + ", ".join(diagnosis.missing_information))

    # 5. Offer Suggested Fix Commands
    if not diagnosis.suggested_commands:
        console.print("[yellow]No automated fix commands were suggested.[/yellow]")
        if diagnosis.next_step_if_fix_fails:
            console.print(f"[dim]Next Step: {diagnosis.next_step_if_fix_fails}[/dim]")
        return

    console.print("\n[bold]Suggested Remediation:[/bold]")
    for idx, cmd in enumerate(diagnosis.suggested_commands, 1):
        exec_result = prompt_and_execute_command(
            command=cmd.command,
            explanation=cmd.explanation,
            risk=cmd.risk,
            cwd=cwd,
            storage=storage,
            prompt_context=f"cmb fix: {diagnosis.summary}",
        )

        action = exec_result.get("action")
        exit_code = exec_result.get("exit_code", 0)

        # Record diagnosis event in history
        storage.add_history_entry(
            working_dir=str(cwd),
            prompt=f"cmb fix ({diagnosis.root_cause[:80]})",
            commands=[cmd.command],
            executed_command=cmd.command if action == "run" else None,
            exit_code=exit_code if action == "run" else None,
            status="executed" if (action == "run" and exit_code == 0) else action,
        )

        if action == "run" and exit_code == 0:
            console.print("[bold green][OK] Fix applied successfully![/bold green]")
            # Clear previous failed error state on successful fix
            storage.set_state("last_error", None)
            storage.set_state("last_exit_code", 0)
        elif action == "cancel":
            console.print("[dim]Fix sequence cancelled.[/dim]")
            break
        elif action == "run" and exit_code != 0:
            console.print(f"[bold red]Fix command failed with exit code {exit_code}.[/bold red]")
            if diagnosis.next_step_if_fix_fails:
                console.print(f"[yellow]Recommended Next Step:[/yellow] {diagnosis.next_step_if_fix_fails}")
            break


@_app.command("explain")
def explain_command() -> None:
    """Explain the last command, terminal error, or current project context."""
    print_banner()
    cwd = Path.cwd()

    with console.status("[bold cyan]Gathering project facts...[/bold cyan]"):
        ctx = scan_project_context(cwd)

    last_cmd = storage.get_state("last_command")
    last_err = storage.get_state("last_error")
    last_exit = storage.get_state("last_exit_code")

    # 1. Facts directly from project files
    facts_table = Table(title="Facts Verified From Project Files", border_style="dim")
    facts_table.add_column("Property", style="bold yellow", width=22)
    facts_table.add_column("Observed Value", style="white")

    facts_table.add_row("Project Name", ctx.get("project_name") or "(unnamed)")
    facts_table.add_row("Framework / Type", ctx.get("project_type", "Unknown"))
    facts_table.add_row("Package Manager", ctx.get("package_manager", "Unknown"))
    if ctx.get("git_branch"):
        facts_table.add_row("Git Branch", ctx["git_branch"])
    if ctx.get("scripts"):
        facts_table.add_row("Defined Scripts", ", ".join(ctx["scripts"].keys()))
    if ctx.get("config_files"):
        facts_table.add_row("Detected Configs", ", ".join(ctx["config_files"]))

    console.print(facts_table)

    # 2. Terminal context
    if last_cmd or last_err:
        term_text = f"[bold cyan]Last Command:[/bold cyan] {last_cmd or '(none recorded)'}\n"
        if last_exit is not None:
            term_text += f"[bold cyan]Exit Code:[/bold cyan] {last_exit}\n"
        if last_err:
            term_text += f"[bold red]Last Error:[/bold red]\n{str(last_err)[:500]}"
        console.print(Panel(term_text, title="Terminal Session Context", border_style="cyan"))
    else:
        console.print("[dim cyan]No recent terminal errors recorded in session.[/dim cyan]")

    # 3. Known vs Unknowns
    if ctx.get("unknowns"):
        console.print(Panel(
            "\n".join(f"[yellow]?[/yellow] {unk}" for unk in ctx["unknowns"]),
            title="What CmdBuddy Does Not Know / Missing",
            border_style="yellow",
            expand=False,
        ))


@_app.command("save")
def save_command(
    name: str = typer.Argument(..., help="Name identifier for the snippet"),
    command: Optional[str] = typer.Option(None, "--command", "-c", help="Command text to save"),
    tags: str = typer.Option("", "--tags", "-t", help="Comma-separated tags"),
    description: str = typer.Option("", "--desc", "-d", help="Description of what this command does"),
) -> None:
    """Save a command snippet for future reuse."""
    print_banner()

    # Safety: Validate snippet name to prevent command injection
    if not validate_snippet_name(name):
        console.print("[bold red]Invalid snippet name:[/bold red] Names must only contain letters, numbers, hyphens, and underscores.")
        raise typer.Exit(code=1)

    if not command:
        last_state = storage.get_last_error_state()
        command = last_state.get("last_command")
    if not command:
        console.print("[red]Please specify --command or run a command first.[/red]")
        raise typer.Exit(code=1)

    safety = classify_command(command)
    storage.save_snippet(
        name=name,
        command=command,
        description=description,
        tags=tags,
        risk=safety.risk,
        project_path=str(Path.cwd()),
    )
    console.print(f"[green][OK] Snippet '[bold]{name}[/bold]' saved successfully![/green]")


@_app.command("find")
def find_command(
    query: str = typer.Argument(..., help="Search query (name, tag, or description)"),
) -> None:
    """Search saved command snippets by name, tags, or description."""
    print_banner()
    results = storage.find_snippets(query)
    if not results:
        console.print(f"[yellow]No snippets found matching '{query}'.[/yellow]")
        return

    table = Table(title=f"Saved Snippets Matching '{query}'", border_style="dim")
    table.add_column("Name", style="bold cyan", width=20)
    table.add_column("Command", style="white")
    table.add_column("Risk", width=14)
    table.add_column("Description", style="dim")

    for item in results:
        badge = get_risk_badge(item.get("risk", "write"))
        table.add_row(item["name"], item["command"], badge, item.get("description", ""))

    console.print(table)


@_app.command("run")
def run_command_snippet(
    name: str = typer.Argument(..., help="Name of snippet to run"),
) -> None:
    """Run a saved snippet with safety approval."""
    print_banner()

    if not validate_snippet_name(name):
        console.print("[bold red]Invalid snippet name format.[/bold red]")
        raise typer.Exit(code=1)

    snippet = storage.get_snippet(name)
    if not snippet:
        console.print(f"[red]Snippet '{name}' not found.[/red]")
        raise typer.Exit(code=1)

    exec_result = prompt_and_execute_command(
        command=snippet["command"],
        explanation=snippet.get("description", ""),
        risk=snippet.get("risk"),
        cwd=Path.cwd(),
        storage=storage,
        prompt_context=f"Run snippet '{name}'",
    )

    if exec_result.get("action") == "run" and exec_result.get("exit_code") == 0:
        storage.increment_snippet_usage(name)


class CmdBuddyCLI:
    """Intelligently dispatches between plain-English prompts and Typer subcommands."""

    def __call__(self, *args, **kwargs):
        cli_args = sys.argv[1:]
        if cli_args:
            first_arg = cli_args[0].strip().lower()
            if first_arg not in KNOWN_SUBCOMMANDS and not first_arg.startswith("-"):
                prompt_text = " ".join(cli_args)
                handle_prompt(prompt_text)
                return 0
        return _app(*args, **kwargs)


app = CmdBuddyCLI()


def run_cli() -> None:
    """Entry point for cmb executable."""
    app()


if __name__ == "__main__":
    run_cli()
