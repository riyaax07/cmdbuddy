"""PowerShell command execution engine for CmdBuddy.

Handles interactive approval prompts, clipboard copying, and live PowerShell subprocess execution.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from rich.panel import Panel
from rich.prompt import Prompt

from cmdbuddy.safety import CommandSafetyInfo, classify_command
from cmdbuddy.storage import StorageManager
from cmdbuddy.ui import console, get_risk_badge


def copy_to_clipboard(text: str) -> bool:
    """Copy text to Windows clipboard using clip.exe."""
    try:
        proc = subprocess.Popen("clip", stdin=subprocess.PIPE, shell=True)
        proc.communicate(text.encode("utf-8"))
        return proc.returncode == 0
    except Exception:
        return False


def run_powershell_command(command: str, cwd: Optional[Path] = None) -> Tuple[int, str]:
    """Execute a command in PowerShell and capture output and returncode."""
    target_cwd = cwd or Path.cwd()
    console.print(f"[dim]Running in {target_cwd}...[/dim]")

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            cwd=str(target_cwd),
            capture_output=True,
            text=True,
            shell=False,
        )
        combined_output = ""
        if proc.stdout:
            combined_output += proc.stdout
            console.print(proc.stdout.rstrip())
        if proc.stderr:
            combined_output += ("\n" if combined_output else "") + proc.stderr
            console.print(f"[red]{proc.stderr.rstrip()}[/red]")

        return proc.returncode, combined_output
    except Exception as e:
        err_msg = f"Failed to execute command: {e}"
        console.print(f"[bold red]{err_msg}[/bold red]")
        return 1, err_msg


def prompt_and_execute_command(
    command: str,
    explanation: str = "",
    risk: Optional[str] = None,
    cwd: Optional[Path] = None,
    storage: Optional[StorageManager] = None,
    prompt_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Present a command to the user, handle safety verification and execution."""
    store = storage or StorageManager()
    target_cwd = cwd or Path.cwd()

    # Determine safety classification
    safety: CommandSafetyInfo = classify_command(command)
    effective_risk = risk or safety.risk

    # Header display
    badge = get_risk_badge(effective_risk)
    console.print()
    console.print(badge, f"[bold white]{command}[/bold white]")
    if explanation:
        console.print(f"[dim]{explanation}[/dim]")

    # Blocked check
    if safety.is_blocked:
        reason = safety.block_reason or "Dangerous command execution blocked."
        console.print(
            Panel(
                f"[bold red]EXECUTION BLOCKED[/bold red]\n{reason}",
                border_style="red",
            )
        )
        store.add_history_entry(
            working_dir=str(target_cwd),
            prompt=prompt_context,
            commands=[command],
            status="blocked",
            error_text=reason,
        )
        return {"action": "blocked", "exit_code": 1, "output": reason}

    # If allowlisted read-only and requires no approval
    if safety.is_allowlisted_auto and not safety.requires_approval:
        console.print("[dim green](Auto-running allowlisted read-only query)[/dim green]")
        code, out = run_powershell_command(command, cwd=target_cwd)
        store.add_history_entry(
            working_dir=str(target_cwd),
            prompt=prompt_context,
            commands=[command],
            executed_command=command,
            exit_code=code,
            status="executed" if code == 0 else "failed",
            error_text=out if code != 0 else None,
        )
        return {"action": "run", "exit_code": code, "output": out}

    # Interactive choice: Run [y] / Copy [c] / Cancel [N]
    if effective_risk == "destructive":
        console.print("[bold red]WARNING: This command is destructive and may cause data or state loss.[/bold red]")
        choice = Prompt.ask(
            "Type 'YES' to run, 'c' to copy, or Enter to cancel",
            default="N",
        ).strip()
        should_run = (choice == "YES")
    else:
        choice = Prompt.ask(
            "Run this command? [y/N/c] (y: run, c: copy, N: cancel)",
            default="N",
        ).strip().lower()
        should_run = (choice == "y" or choice == "yes")

    if should_run:
        code, out = run_powershell_command(command, cwd=target_cwd)
        status = "executed" if code == 0 else "failed"
        
        # Save to history
        store.add_history_entry(
            working_dir=str(target_cwd),
            prompt=prompt_context,
            commands=[command],
            executed_command=command,
            exit_code=code,
            status=status,
            error_text=out if code != 0 else None,
        )

        # Update last session state if it failed so `cmb fix` can immediately inspect it
        store.set_state("last_command", command)
        store.set_state("last_cwd", str(target_cwd))
        store.set_state("last_exit_code", code)
        if code != 0:
            store.set_state("last_error", out)

        return {"action": "run", "exit_code": code, "output": out}

    elif choice == "c" or choice == "copy":
        if copy_to_clipboard(command):
            console.print("[cyan][OK] Command copied to clipboard.[/cyan]")
        else:
            console.print("[yellow]Clipboard copy failed, command text shown above.[/yellow]")

        store.add_history_entry(
            working_dir=str(target_cwd),
            prompt=prompt_context,
            commands=[command],
            executed_command=command,
            status="copied",
        )
        return {"action": "copy", "exit_code": 0, "output": ""}

    else:
        console.print("[dim]Command cancelled.[/dim]")
        store.add_history_entry(
            working_dir=str(target_cwd),
            prompt=prompt_context,
            commands=[command],
            status="cancelled",
        )
        return {"action": "cancel", "exit_code": 0, "output": ""}
