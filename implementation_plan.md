# CmdBuddy Implementation Plan: PowerShell-First AI Command Assistant

**Project:** CmdBuddy  
**Challenge Track:** NoHandsChallenge — Track 1: Builders  
**Target Platform:** Windows PowerShell (PowerShell 5.1 / PowerShell 7+)  
**Runtime:** Python 3.11+ (Detected: Python 3.12.4, Node v22.12.0, npm 11.11.0)  

---

## 1. System Architecture & Overview

CmdBuddy (`cmb`) is a developer-centric CLI tool designed to run natively inside PowerShell. It bridges developer intent and PowerShell command execution while eliminating context-switching and copy-pasting during terminal errors.

```
+-----------------------------------------------------------------------------------+
|                                  User in PowerShell                               |
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
               |  - Reads package.json, tsconfig, git, etc.   |
               |  - Filters out .env, credentials, binaries    |
               +-----------------------------------------------+
                                       |
                                       v
               +-----------------------------------------------+
               |               Gemini API (httpx)              |
               |  - Structured JSON Output (Pydantic schema)   |
               |  - Grounded Evidence Verification             |
               +-----------------------------------------------+
                                       |
                                       v
               +-----------------------------------------------+
               |           Command Safety Classifier           |
               |  - read-only | write | network | destructive  |
               |  - blocked pattern rejection                  |
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

## 2. Directory Structure

The project will reside at `C:\Users\Dell\.gemini\antigravity\scratch\cmdbuddy` with the following layout:

```
cmdbuddy/
├── pyproject.toml                 # Package definition, Typer CLI entrypoint (`cmb`)
├── README.md                      # Comprehensive user guide, architecture, demo, safety model
├── implementation_plan.md         # This implementation blueprint
├── cmdbuddy/
│   ├── __init__.py                # Package version and exports
│   ├── cli.py                     # Typer CLI definition and command handlers
│   ├── schemas.py                 # Pydantic models for Gemini structured responses & context
│   ├── context_engine.py          # Lightweight, secure project scanner & sanitizer
│   ├── error_capture.py           # PowerShell error capture (state, clipboard, paste fallback)
│   ├── ai_client.py               # Gemini API client with schema enforcement and verification
│   ├── safety.py                  # Command risk classification and blocked command guardrails
│   ├── executor.py                # PowerShell command runner, live output, copy to clipboard
│   ├── storage.py                 # SQLite database for history, snippets, and session state
│   └── ui.py                      # Rich formatting (tables, panels, status indicators, badges)
├── demo-react-vite-project/       # Demo project for NoHandsChallenge Track 1 verification
│   ├── package.json               # Vite project deliberately missing the "dev" script
│   ├── vite.config.ts             # Standard Vite React configuration
│   ├── tsconfig.json              # Standard TypeScript configuration
│   ├── index.html                 # Valid root HTML template
│   └── src/
│       ├── App.tsx                # Functional React component
│       └── main.tsx               # Entrypoint mounting App
├── tests/
│   ├── __init__.py
│   ├── test_context_engine.py     # Context detection, metadata extraction, safety filtering
│   ├── test_safety.py             # Risk classification, blocked commands, prompt injection checks
│   ├── test_schemas.py            # Pydantic schema validation & nonexistent file checks
│   ├── test_storage.py            # SQLite CRUD for snippets and history
│   ├── test_ai_client.py          # Gemini response handling, mock fixtures, retry logic
│   └── test_end_to_end_fix.py     # Missing Vite dev script diagnosis & repair flow test
└── scripts/
    └── install.ps1                # One-click Windows PowerShell installer (`cmb` command alias)
```

---

## 3. Detailed Component Breakdown

### 3.1 Project Context Engine (`context_engine.py`)
- **Detection targets:**
  - Node.js / Web: `package.json`, `vite.config.*`, `tsconfig.json`, `next.config.*`, `webpack.config.*`
  - Python: `pyproject.toml`, `requirements.txt`, `Pipfile`, `setup.py`
  - Git repository: Current branch name, modified files from `git status --porcelain` (if `.git` exists)
- **Metadata extracted:**
  - Package manager: `npm`, `pnpm`, `yarn`, `bun`, `pip`, `poetry`
  - Project name and version
  - Scripts dictionary (e.g. `scripts` block in `package.json`)
  - Dependencies & devDependencies keys (names only, or version ranges)
  - Installed Node and npm versions (invoking quick `--version` checks)
- **Strict Data Sanitization & Safety:**
  - **Never read or send:** `.env`, `.env.*`, `*token*`, `*secret*`, `*id_rsa*`, `.pem`, `.key`, binary files, `node_modules`, `venv`, `.git/objects`.
  - Content size caps: Context payload is capped to < 8KB compact JSON to avoid token waste and latency.

### 3.2 Error Capture (`error_capture.py`)
- CmdBuddy does not require commands to have been run through CmdBuddy itself. It supports a robust 3-tier error capture mechanism:
  1. **Direct Session History / Last State:** Read the last command/error recorded in CmdBuddy session state (`~/.cmdbuddy/state.json` or SQLite), if available.
  2. **Windows Clipboard Inspection:** Checks if the Windows clipboard contains an error, stack trace, or terminal log output (e.g. copied via terminal or Ctrl+C).
  3. **Interactive Terminal Paste Fallback:** If neither state nor clipboard provides a usable error, prompts the user: `Paste the error message or press Enter to diagnose current project state:`.
  - In all cases, **the user is never required to copy-paste or explain project context**; CmdBuddy automatically attaches the detected project context.

### 3.3 AI Client & Gemini Schema Enforcement (`ai_client.py` & `schemas.py`)
- Calls Gemini 2.0 Flash / 1.5 Flash via `httpx.Client` or `httpx.AsyncClient`.
- API Key: Loaded strictly from `GEMINI_API_KEY` environment variable or `~/.cmdbuddy/config.json`.
- Uses Gemini's native `response_schema` / structured JSON output capability.
- **Pydantic Model for Diagnosis:**
  ```python
  class EvidenceItem(BaseModel):
      file: str
      observation: str

  class SuggestedCommand(BaseModel):
      command: str
      explanation: str
      risk: Literal["read-only", "write", "network", "destructive", "blocked"]
      requires_approval: bool = True

  class DiagnosisResponse(BaseModel):
      summary: str
      root_cause: str
      confidence: float
      diagnosis_status: Literal["supported", "partially_supported", "insufficient_evidence"]
      evidence: list[EvidenceItem]
      missing_information: list[str]
      suggested_commands: list[SuggestedCommand]
      limitations: list[str]
      next_step_if_fix_fails: str
  ```
- **Grounding & Validation Rules:**
  - Post-generation validation inspects each `evidence.file`. If the file does not exist on disk relative to the project root, the item is invalidated.
  - If invalid files are present, CmdBuddy retries once with a corrective prompt or degrades status to `insufficient_evidence`.
  - Disallows hallucinations of file paths, versions, or fictitious commands.

### 3.4 Command Safety Classifier (`safety.py`)
- Analyzes commands prior to display or execution:
  - **`read-only`**: Pure information queries (`Get-ChildItem`, `dir`, `git status`, `git log`, `node -v`, `npm -v`, `cat`, `Get-Content`).
  - **`write`**: Modifies files or configs (`npm pkg set`, `npm install`, `touch`, `New-Item`, `echo ... >`). Requires approval `[y/N]`.
  - **`network`**: Clones repos, downloads packages, pings endpoints (`git clone`, `npm create vite`, `curl`, `Invoke-WebRequest`). Requires approval `[y/N]`.
  - **`destructive`**: Deletes or overrides state (`Remove-Item -Recurse`, `rmdir /s`, `git reset --hard`, `git clean -fd`, `npm cache clean --force`). Highlights in bold red, requires explicit uppercase `YES` confirmation.
  - **`blocked`**: Commands that could damage the OS or exfiltrate secrets (`Remove-Item C:\Windows`, `format`, `del /f /s /q %windir%`, reading `.env` / private keys). Execution is strictly prevented.
- **Copy Option:** Users can choose `[c]` to copy the command to the Windows clipboard instead of executing it.

### 3.5 Local Persistence (`storage.py`)
- SQLite database located at `~/.cmdbuddy/cmdbuddy.db`.
- **Tables:**
  - `history`: `id`, `timestamp`, `working_dir`, `prompt`, `commands_json`, `executed_command`, `exit_code`, `status`.
  - `snippets`: `id`, `name`, `command`, `description`, `tags`, `risk`, `created_at`, `last_used_at`, `use_count`.
  - `state`: Stores `last_command`, `last_error`, `last_cwd` for instant `cmb fix` reference.

### 3.6 PowerShell CLI Interface (`cli.py`)
Built with Typer & Rich. Commands include:
- `cmb "<plain English request>"`: Parse natural language intent into verified PowerShell commands with risk badge and execution prompt.
- `cmb fix`: Capture error, assemble project context, obtain AI diagnosis, verify evidence, suggest fix command.
- `cmb explain`: Explain the last executed command or current project context.
- `cmb save <name> [--command <cmd>] [--tags <tag1,tag2>]`: Save command for future reuse.
- `cmb find <query>`: Full-text search over saved snippets.
- `cmb run <name>`: Execute a saved snippet with safety approval.
- `cmb history [--limit 10]`: View recent command generation and execution history.
- `cmb context`: Display detected project context (framework, package manager, scripts, config files).

---

## 4. Phase-by-Phase Implementation Plan

### Phase 1: Explore and Plan (Current Phase)
- [x] Inspect existing environment (Python 3.12.4, Node v22.12.0, npm 11.11.0, Windows PowerShell).
- [x] Establish project directory `C:\Users\Dell\.gemini\antigravity\scratch\cmdbuddy`.
- [x] Author comprehensive `implementation_plan.md`.
- [ ] Receive user review and approval before writing code.

### Phase 2: CLI Foundation & Local Storage
- Initialize `pyproject.toml` with dependencies: `typer`, `rich`, `pydantic`, `httpx`, `pytest`.
- Implement `storage.py` (SQLite schema, history recording, snippet management, session state).
- Implement `cli.py` skeleton with Typer:
  - Default command callback for `cmb "<prompt>"`
  - `cmb context`
  - `cmb history`
- Build PowerShell activation script `scripts/install.ps1` to alias or link `cmb` in PowerShell `$PROFILE`.

### Phase 3: Command Generation & Intent Translation
- Implement `schemas.py` for structured command generation responses.
- Implement `ai_client.py` Gemini integration using `httpx`.
- Implement `safety.py` risk classification rules.
- Implement `executor.py` for running PowerShell commands with live output, exit codes, and clipboard support.
- Implement `cmb save`, `cmb find`, and `cmb run`.

### Phase 4: Error Capture & Project Context Engine
- Implement `context_engine.py`:
  - Detect Node/Vite/TS/Python project metadata.
  - Safe file filter (ignoring `.env`, secrets, binary assets).
- Implement `error_capture.py`:
  - Capture last failed command, error message, and terminal context.
- Implement `cmb fix` and `cmb explain`:
  - Enforce evidence verification against local project files.
  - Reject hallucinated files and fallback to `insufficient_evidence` when context is inadequate.

### Phase 5: Safety Model & Automated Testing
- Implement blocked command filters and confirmation flows.
- Write and run unit & integration tests (`pytest tests/`):
  1. `test_context_engine.py`: Verify project type detection and file exclusion rules (`.env` never loaded).
  2. `test_safety.py`: Verify risk ratings for `read-only`, `write`, `network`, `destructive`, and `blocked`.
  3. `test_schemas.py`: Verify Pydantic validation, evidence checking against local files.
  4. `test_ai_client.py`: Verify Gemini payload construction, mock response handling, and retries.
  5. `test_storage.py`: Verify SQLite history logging and snippet search.
  6. `test_end_to_end_fix.py`: Verify the complete missing Vite dev script diagnosis flow.
- Execute test suite and verify 100% test pass rate.

### Phase 6: Demo Readiness & Documentation
- Build `demo-react-vite-project`:
  - Initialize valid Vite React TypeScript project files.
  - Deliberately omit the `dev` script in `package.json`.
- Verify the end-to-end interactive demo workflow:
  1. `cd demo-react-vite-project`
  2. `npm run dev` fails with error code
  3. `cmb fix`
  4. CmdBuddy detects Vite React TS project, reads `package.json`, flags missing script
  5. Suggests `npm pkg set scripts.dev="vite"`
  6. User confirms execution (`y`)
  7. `npm run dev` starts successfully
- Write detailed `README.md` including installation steps, usage guide, architecture, safety design, and limitations.

---

## 5. Verification & Testing Strategy

| Test Area | Expected Behavior | Test File |
| :--- | :--- | :--- |
| **Context Safety** | `.env`, `.env.local`, `.pem` are never read or output | `tests/test_context_engine.py` |
| **Safety Classifier** | `rmdir C:\` is blocked; `rm -rf` is destructive; `npm pkg set` is write | `tests/test_safety.py` |
| **Schema & Grounding** | Nonexistent files in AI evidence are detected and rejected | `tests/test_schemas.py` |
| **Persistence** | Snippets can be saved, searched by tag, and retrieved from SQLite | `tests/test_storage.py` |
| **Vite Demo Repair** | Missing `dev` script correctly diagnosed; `npm pkg set scripts.dev="vite"` suggested | `tests/test_end_to_end_fix.py` |
