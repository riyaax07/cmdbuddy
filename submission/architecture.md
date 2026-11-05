# CmdBuddy System Architecture & Technical Design

**Challenge Track:** NoHandsChallenge — Track 1: Builders  
**Target Platform:** Windows PowerShell (PowerShell 5.1 & PowerShell 7+)  
**Runtime:** Python 3.11+  

---

## 1. Architectural Overview

CmdBuddy is engineered as a modular, single-binary-style CLI application (`cmb`) that operates directly inside PowerShell. It connects developer intent, local filesystem context, Gemini structured AI intelligence, and a defense-in-depth safety engine.

```
+-----------------------------------------------------------------------------------+
|                                 User in PowerShell                                |
+-----------------------------------------------------------------------------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
              [cmb "prompt"]                           [cmb fix]
                       |                                   |
                       v                                   v
+-----------------------------+                 +-----------------------------+
|    Command Generation Flow  |                 |    Error Diagnosis Flow     |
+-----------------------------+                 +-----------------------------+
               |                                               |
               +-----------------------+-----------------------+
                                       |
                                       v
               +-----------------------------------------------+
               |             Context Detection Engine          |
               |  - Scans package.json, tsconfig, git branch  |
               |  - Filters out .env, credentials, binaries    |
               |  - Categorizes "known facts" vs "unknowns"   |
               +-----------------------------------------------+
                                       |
                                       v
               +-----------------------------------------------+
               |               Gemini API (httpx)              |
               |  - Strict Pydantic JSON schema enforcement    |
               |  - Grounded file verification & retry guard   |
               |  - Offline heuristic fallback engine          |
               +-----------------------------------------------+
                                       |
                                       v
               +-----------------------------------------------+
               |           Command Safety Classifier           |
               |  - read-only | write | network | destructive  |
               |  - blocked pattern rejection                  |
               |  - chained command (&& / ;) token evaluation  |
               +-----------------------------------------------+
                                       |
                                       v
               +-----------------------------------------------+
               |            Interactive Execution / UI         |
               |  - Rich display (explanation, risk badges)    |
               |  - Approval: Run [y] / Copy [c] / Cancel [N]  |
               |  - Real-time PowerShell subprocess runner     |
               +-----------------------------------------------+
                                       |
                                       v
               +-----------------------------------------------+
               |          Local Persistence (SQLite)           |
               |  - History, Snippets, Last Execution State    |
               +-----------------------------------------------+
```

---

## 2. Core Subsystems

### 2.1 PowerShell CLI Layer (`cli.py`)
- Built on `Typer` and `Rich` with an intelligent dispatch wrapper (`CmdBuddyCLI`).
- Distinguishes free-form plain-English prompts (`cmb "create a vite app"`) from registered subcommands (`cmb context`, `cmb history`, `cmb fix`, `cmb explain`, `cmb save`, `cmb find`, `cmb run`).
- Reconfigures standard output for Windows `cp1252` compatibility, eliminating character encoding exceptions.

### 2.2 Project Context Engine (`context_engine.py`)
- Automatically detects framework types (React, Vite, Next.js, TypeScript, Python) and package managers (`npm`, `pnpm`, `yarn`, `bun`, `pip`, `poetry`).
- Gathers project name, version, script keys, dependency lists, and Git repository status (branch, clean/dirty state, last commit message).
- **Strict Data Sanitization**: Explicitly filters `.env`, `.env.*`, credential files, SSH keys, private tokens, binaries, and dependency folders. Context payloads are capped to < 8KB.

### 2.3 3-Tier Error Capture Flow (`error_capture.py`)
Provides seamless error recovery without forcing developers to explain their environment:
1. **Tier 1 (Session State)**: Automatically inspects the last executed command, exit code, and terminal error recorded in CmdBuddy session state.
2. **Tier 2 (Clipboard Inspection)**: If an error is copied to the Windows clipboard via Ctrl+C, CmdBuddy detects the stack trace and prompts to use it.
3. **Tier 3 (Terminal Paste Fallback)**: If neither is available, prompts: `"Paste the terminal error, or press Enter to diagnose using project context only."`

### 2.4 Gemini Structured-Output Client (`ai_client.py`)
- Connects to Google Gemini 2.0 Flash REST API via `httpx.Client`.
- Enforces strict JSON schemas using Pydantic models (`CommandGenerationResponse` and `DiagnosisResponse`).
- **Grounded Verification**: Validates all file paths cited as evidence against the local project filesystem. Any hallucinated file paths are stripped. If evidence is lost, the diagnosis gracefully degrades to `insufficient_evidence`.
- **Offline Heuristic Engine**: Includes a deterministic fallback for common developer errors (e.g. missing scripts, port in use) when operating offline or in isolated environments.

### 2.5 Safety Classifier (`safety.py`)
Categorizes commands into 5 distinct safety tiers:
- **`read-only`**: Non-modifying queries (`git status`, `node -v`). Explicitly allowlisted commands may run automatically.
- **`write`**: Modifies files or configurations (`npm pkg set`, `New-Item`). Requires interactive approval `[y/N/c]`.
- **`network`**: Outbound connections or package installs (`git clone`, `npm create vite`). Requires approval.
- **`destructive`**: Deletes directories or discards git history (`Remove-Item -Recurse`, `git reset --hard`). Requires explicit uppercase `YES` confirmation.
- **`blocked`**: Commands targeting Windows system directories (`C:\Windows`, `System32`), disk formatting, `.env` file inspection, or fork bombs. **Execution is strictly prevented.**
- **Chained Command Analysis**: Evaluates each token in compound commands (`cmd1; cmd2 && cmd3`). If any subcommand in the chain is blocked, the entire pipeline is rejected.

### 2.6 Approval-Gated Executor (`executor.py`)
- Displays the exact command, explanation, and color-coded risk badge before execution.
- Prompts for user intent: **Run** (`y`), **Copy to clipboard** (`c` via `clip.exe`), or **Cancel** (`N`).
- Executes verified commands as a PowerShell subprocess, capturing live stdout/stderr and exit codes.
- Updates session state and records every action in the local database.

### 2.7 Local Persistence (`storage.py`)
- Lightweight SQLite database stored at `~/.cmdbuddy/cmdbuddy.db` (with safe fallback for restricted sandbox environments).
- Tables:
  - `history`: Full audit trail of prompts, generated commands, execution status, and exit codes.
  - `snippets`: Named command snippets with tags, descriptions, risk ratings, and usage counters.
  - `session_state`: Key-value cache tracking `last_command`, `last_error`, `last_exit_code`, and `last_cwd`.

---

## 3. Test Strategy & Verification

CmdBuddy uses `pytest` to guarantee reliability across 5 test suites:
- **Safety & Guardrails (`test_safety.py`)**: 9 tests covering read-only allowlist, write classification, network calls, destructive confirmation, blocked OS paths, secret leakage prevention, chained commands, and snippet name validation.
- **Pydantic Schemas (`test_schemas.py`)**: 4 tests verifying model parsing, Literal constraint validation, and confidence score bounds.
- **AI Client & Grounding (`test_ai_client.py`)**: 4 tests covering API key handling, markdown code fence stripping, invalid JSON retry, and nonexistent file filtering.
- **Diagnosis & Fix Flow (`test_diagnosis.py`)**: 7 tests covering 3-tier error capture, missing `dev` script repair, evidence degradation on hallucinated files, executor blocking of dangerous suggestions, and prompt injection resistance in error messages.
- **Context Engine & Privacy (`test_context_engine.py`)**: 4 tests covering Node/React/Vite/TS detection, Python detection, non-project directory handling, and sensitive `.env` file exclusion.

**Total Test Count:** 30 unit and integration tests passing with 100% success rate.
