# Contributing to CmdBuddy

Thank you for your interest in contributing to **CmdBuddy**! We welcome bug reports, test improvements, and new diagnostic heuristics.

---

## Development Setup

1. **Clone & Setup**:
   ```powershell
   git clone https://github.com/your-username/cmdbuddy.git
   cd cmdbuddy
   ```

2. **Install in Editable Mode with Dev Dependencies**:
   ```powershell
   python -m pip install -e ".[dev]"
   ```

3. **Run Unit Tests**:
   ```powershell
   pytest -q
   ```

---

## Coding & Safety Standards

- **Python Version**: Tested on Python 3.11+.
- **Windows / PowerShell First**: Ensure commands work natively in Windows PowerShell (PowerShell 5.1 and 7+).
- **Safety First**: Every new command must be categorized into the 5-tier safety model (`read-only`, `write`, `network`, `destructive`, `blocked`).
- **Privacy Guarantee**: Never introduce logic that reads, scans, or transmits `.env` files, SSH keys, or raw codebases.
- **Strict Typing**: Use Pydantic models for structured outputs and type annotations throughout.
