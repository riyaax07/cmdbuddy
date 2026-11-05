"""3-Tier Error Capture engine for CmdBuddy.

Priority:
1. Last failed command & error stored in CmdBuddy session state.
2. Windows clipboard if it contains an error message or stack trace.
3. Interactive terminal prompt fallback:
   "Paste the terminal error, or press Enter to diagnose using project context only."
"""

from __future__ import annotations

import subprocess
from typing import Dict, Optional, Tuple
from rich.panel import Panel
from rich.prompt import Prompt

from cmdbuddy.storage import StorageManager
from cmdbuddy.ui import console

ERROR_KEYWORDS = {
    "error",
    "err!",
    "exception",
    "failed",
    "failure",
    "traceback",
    "fatal",
    "not found",
    "command not found",
    "exit code",
    "errno",
    "missing script",
    "cannot find module",
    "syntaxerror",
    "typeerror",
    "referenceerror",
    "build failed",
    "npm err",
    "pnpm err",
    "yarn error",
}


def get_clipboard_text() -> Optional[str]:
    """Retrieve current text from Windows clipboard via PowerShell Get-Clipboard."""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            timeout=2,
            shell=False,
        )
        if proc.returncode == 0 and proc.stdout:
            text = proc.stdout.strip()
            return text if text else None
    except Exception:
        pass
    return None


def is_likely_error_text(text: str) -> bool:
    """Return True if text resembles a stack trace, error log, or command failure."""
    if not text or len(text.strip()) < 5:
        return False
    lower = text.lower()
    return any(keyword in lower for keyword in ERROR_KEYWORDS)


def capture_terminal_error(
    storage: Optional[StorageManager] = None,
    interactive: bool = True,
) -> Tuple[Optional[str], Optional[str], str]:
    """Capture terminal error and last command using the 3-tier strategy.

    Returns:
        (last_command, error_text, capture_source)
        capture_source is one of: 'session_state', 'clipboard', 'user_input', 'context_only', 'none'
    """
    store = storage or StorageManager()

    # Tier 1: Check CmdBuddy Session State
    last_cmd = store.get_state("last_command")
    last_err = store.get_state("last_error")
    last_exit = store.get_state("last_exit_code")

    if last_err and str(last_err).strip():
        console.print(
            Panel(
                f"[bold cyan]Command:[/bold cyan] {last_cmd or '(unknown)'}\n"
                f"[bold red]Captured Error:[/bold red] {str(last_err).strip()[:400]}",
                title="Tier 1: Captured from Previous CmdBuddy Session",
                border_style="cyan",
            )
        )
        return last_cmd, str(last_err).strip(), "session_state"

    # Tier 2: Check Windows Clipboard
    clip_content = get_clipboard_text()
    if clip_content and is_likely_error_text(clip_content):
        preview = clip_content[:250] + ("..." if len(clip_content) > 250 else "")
        console.print(
            Panel(
                f"[dim]{preview}[/dim]",
                title="Tier 2: Error Detected in Windows Clipboard",
                border_style="yellow",
            )
        )
        if interactive:
            use_clip = Prompt.ask(
                "Use error message detected on clipboard? [Y/n]",
                default="Y",
            ).strip().lower()
            if use_clip in ("y", "yes", ""):
                return last_cmd, clip_content, "clipboard"

    # Tier 3: Interactive Terminal Paste Fallback
    if interactive:
        console.print("[dim cyan]No previous failed command recorded in session.[/dim cyan]")
        pasted = Prompt.ask(
            "Paste the terminal error, or press Enter to diagnose using project context only",
            default="",
        ).strip()

        if pasted:
            return last_cmd, pasted, "user_input"

        return last_cmd, None, "context_only"

    return last_cmd, None, "none"
