"""Command safety classification engine for CmdBuddy.

Categorizes PowerShell and shell commands into 5 safety tiers:
- read-only: Pure inspection commands (allowlisted ones can run without prompt)
- write: Modifies local files, project scripts, or settings
- network: Clones repos, downloads packages, or makes outbound calls
- destructive: Recursively deletes folders, discards git history, or forces state changes
- blocked: Dangerous commands that damage the OS or exfiltrate secrets (strictly rejected)

Includes chained command analysis, path-traversal prevention, and snippet name validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Set
from cmdbuddy.schemas import RiskLevel


@dataclass
class CommandSafetyInfo:
    risk: RiskLevel
    is_blocked: bool = False
    block_reason: Optional[str] = None
    requires_approval: bool = True
    is_allowlisted_auto: bool = False


# Commands that can run automatically without approval
READ_ONLY_ALLOWLIST: Set[str] = {
    "get-childitem",
    "dir",
    "ls",
    "get-location",
    "pwd",
    "git status",
    "git log",
    "git branch",
    "git diff",
    "node -v",
    "node --version",
    "npm -v",
    "npm --version",
    "python --version",
    "python -v",
    "py --version",
    "git --version",
    "pnpm -v",
    "yarn -v",
    "tsc -v",
    "get-command",
}

# Regex patterns that indicate blocked / unacceptable actions
BLOCKED_PATTERNS = [
    (re.compile(r"(format\s+[a-z]:)", re.IGNORECASE), "Formatting disk drives is blocked for system safety."),
    (re.compile(r"(remove-item|del|rmdir|rm)\s+.*([a-z]:\\windows|[a-z]:\\system32|/etc|/var|/usr|system32)", re.IGNORECASE), "Targeting critical operating system directories is strictly blocked."),
    (re.compile(r"(remove-item|del|rmdir|rm)\s+.*[a-z]:\\(\s|$|\*)", re.IGNORECASE), "Deleting root drive path is strictly blocked."),
    (re.compile(r"(get-content|type|cat|select-string|copy-item|cp|curl|iwr|wget)\s+.*(\.env|\.env\.local|id_rsa|id_ed25519|\.pem|\.key|credential|secret)", re.IGNORECASE), "Attempting to inspect, copy, or exfiltrate private keys, tokens, or environment secret files is strictly blocked."),
    (re.compile(r"(:\(\)\s*\{\s*:\|:&\s*\};:)", re.IGNORECASE), "Fork bomb attack pattern detected and blocked."),
    (re.compile(r"(diskpart|bcdedit|vssadmin\s+delete|reg\s+delete)", re.IGNORECASE), "Low-level system disk or registry manipulation is blocked."),
    (re.compile(r"(curl|wget|invoke-webrequest|iwr)\s+.*(-d\s+@\.env|--data\s+@\.env)", re.IGNORECASE), "Exfiltrating secret files over HTTP is strictly blocked."),
    (re.compile(r"(remove-item|rmdir|del|rm)\s+.*(\.\.\\\.\.\\\.\.|/\.\./\.\./\.\.)", re.IGNORECASE), "Directory traversal escaping project root during deletion is blocked."),
]

# Patterns indicating destructive actions
DESTRUCTIVE_PATTERNS = [
    re.compile(r"(remove-item|rmdir|del|rm)\s+.*(-recurse|/s|-r)", re.IGNORECASE),
    re.compile(r"git\s+reset\s+--hard", re.IGNORECASE),
    re.compile(r"git\s+clean\s+(-[a-z]*f[a-z]*d|-[a-z]*d[a-z]*f)", re.IGNORECASE),
    re.compile(r"git\s+branch\s+-D", re.IGNORECASE),
    re.compile(r"npm\s+cache\s+clean\s+--force", re.IGNORECASE),
    re.compile(r"npm\s+unpublish\s+--force", re.IGNORECASE),
    re.compile(r"drop\s+(database|table)", re.IGNORECASE),
]

# Patterns indicating network operations
NETWORK_PATTERNS = [
    re.compile(r"git\s+(clone|fetch|pull|push)", re.IGNORECASE),
    re.compile(r"npm\s+(install|i|ci|add|create|init)", re.IGNORECASE),
    re.compile(r"npx\s+", re.IGNORECASE),
    re.compile(r"pnpm\s+(install|i|add|create)", re.IGNORECASE),
    re.compile(r"yarn\s+(add|install|create)", re.IGNORECASE),
    re.compile(r"pip\s+(install|download)", re.IGNORECASE),
    re.compile(r"curl\s+", re.IGNORECASE),
    re.compile(r"wget\s+", re.IGNORECASE),
    re.compile(r"(invoke-webrequest|iwr|invoke-restmethod|irm)\s+", re.IGNORECASE),
]

# Patterns indicating file writes or configuration changes
WRITE_PATTERNS = [
    re.compile(r"npm\s+pkg\s+set", re.IGNORECASE),
    re.compile(r"(new-item|set-content|add-content|out-file)", re.IGNORECASE),
    re.compile(r"(mkdir|touch|echo\s+.*>)", re.IGNORECASE),
    re.compile(r"git\s+(add|commit|checkout\s+-b|switch\s+-c)", re.IGNORECASE),
    re.compile(r"npm\s+run\s+", re.IGNORECASE),
    re.compile(r"(>|>>)", re.IGNORECASE),
]

SAFE_SNIPPET_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


def validate_snippet_name(name: str) -> bool:
    """Ensure snippet name contains no shell metacharacters or injection attempts."""
    if not name or len(name) > 64:
        return False
    return bool(SAFE_SNIPPET_NAME_REGEX.match(name))


def split_chained_commands(command_str: str) -> List[str]:
    """Split a command string into subcommands separated by ;, &&, or ||."""
    # Split on ; or && or || while keeping tokens clean
    parts = re.split(r"(?:;|&&|\|\|)", command_str)
    return [p.strip() for p in parts if p.strip()]


def classify_single_command(stripped: str) -> CommandSafetyInfo:
    """Classify an individual unchained command token."""
    # 1. Check Blocked Patterns
    for pattern, reason in BLOCKED_PATTERNS:
        if pattern.search(stripped):
            return CommandSafetyInfo(
                risk="blocked",
                is_blocked=True,
                block_reason=reason,
                requires_approval=True,
                is_allowlisted_auto=False,
            )

    # 2. Check Destructive Patterns
    for pattern in DESTRUCTIVE_PATTERNS:
        if pattern.search(stripped):
            return CommandSafetyInfo(
                risk="destructive",
                requires_approval=True,
                is_allowlisted_auto=False,
            )

    # 3. Check Network Patterns
    for pattern in NETWORK_PATTERNS:
        if pattern.search(stripped):
            return CommandSafetyInfo(
                risk="network",
                requires_approval=True,
                is_allowlisted_auto=False,
            )

    # 4. Check Allowlisted Read-Only
    cmd_lower = stripped.lower()
    normalized = " ".join(cmd_lower.split())
    if normalized in READ_ONLY_ALLOWLIST:
        return CommandSafetyInfo(
            risk="read-only",
            requires_approval=False,
            is_allowlisted_auto=True,
        )

    read_only_tokens = ["get-content", "cat", "type", "select-string", "grep", "findstr", "head", "tail"]
    first_token = normalized.split()[0] if normalized else ""
    if first_token in read_only_tokens and not any(w.search(stripped) for w in WRITE_PATTERNS):
        return CommandSafetyInfo(
            risk="read-only",
            requires_approval=True,
            is_allowlisted_auto=False,
        )

    # 5. Check Write Patterns
    for pattern in WRITE_PATTERNS:
        if pattern.search(stripped):
            return CommandSafetyInfo(
                risk="write",
                requires_approval=True,
                is_allowlisted_auto=False,
            )

    # Default to write for unknown commands to maintain safe approval guarantees
    return CommandSafetyInfo(
        risk="write",
        requires_approval=True,
        is_allowlisted_auto=False,
    )


def classify_command(cmd: str) -> CommandSafetyInfo:
    """Classify a PowerShell command string (including chained commands) into safety categories."""
    stripped = cmd.strip()
    if not stripped:
        return CommandSafetyInfo(risk="read-only", requires_approval=False, is_allowlisted_auto=True)

    # 1. Check Blocked Patterns on the entire command string first
    for pattern, reason in BLOCKED_PATTERNS:
        if pattern.search(stripped):
            return CommandSafetyInfo(
                risk="blocked",
                is_blocked=True,
                block_reason=reason,
                requires_approval=True,
                is_allowlisted_auto=False,
            )

    subcommands = split_chained_commands(stripped)
    if not subcommands:
        return CommandSafetyInfo(risk="read-only", requires_approval=False, is_allowlisted_auto=True)

    # If single command
    if len(subcommands) == 1:
        return classify_single_command(subcommands[0])

    # If chained command: evaluate each subcommand
    sub_results = [classify_single_command(sub) for sub in subcommands]

    # If any subcommand is blocked -> entire chain is blocked
    for res in sub_results:
        if res.is_blocked:
            return res

    # If any subcommand is destructive -> entire chain is destructive
    if any(r.risk == "destructive" for r in sub_results):
        return CommandSafetyInfo(risk="destructive", requires_approval=True, is_allowlisted_auto=False)

    # If any subcommand is network -> entire chain is network
    if any(r.risk == "network" for r in sub_results):
        return CommandSafetyInfo(risk="network", requires_approval=True, is_allowlisted_auto=False)

    # If any subcommand is write -> entire chain is write
    if any(r.risk == "write" for r in sub_results):
        return CommandSafetyInfo(risk="write", requires_approval=True, is_allowlisted_auto=False)

    # Only if ALL subcommands are allowlisted read-only is it auto-run
    all_auto = all(r.is_allowlisted_auto for r in sub_results)
    return CommandSafetyInfo(
        risk="read-only",
        requires_approval=not all_auto,
        is_allowlisted_auto=all_auto,
    )
