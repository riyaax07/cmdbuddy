# 🚀 CmdBuddy (`cmb`)

```
┌──────────────────────────────────────────────────────────────┐
│  CmdBuddy - PowerShell-First AI Command Assistant            │
│  Built for NoHandsChallenge — Track 1: Builders              │
└──────────────────────────────────────────────────────────────┘
```

> **PowerShell-first AI command assistant that translates developer intent into verified commands, eliminates context-switching, and diagnoses terminal errors using local project evidence.**

---

## 💡 Why CmdBuddy?

Windows developers waste hours every day caught in a frustrating loop:
1. **Forget long PowerShell commands**: Scaffolding commands with complex flag syntax (`npm create vite@latest app -- --template react-ts`) are hard to remember.
2. **Context-switch to web browsers**: When a terminal command fails, developers copy-paste error logs into browser AI chats.
3. **Repeatedly explain project context**: Web AIs know nothing about the local directory—requiring developers to explain their framework, package manager, and configs over and over.
4. **Risk dangerous or hallucinated suggestions**: Generic AI chats often suggest destructive commands (`rm -rf`, `git reset --hard`) or reference files that don't even exist.

**CmdBuddy solves this entirely inside PowerShell.**

---

## ✨ Features

- **PowerShell-First Invocation**: Type natural English directly in your terminal: `cmb "create a react vite typescript app named ingreknow"`.
- **Automated Project Context**: Detects React, Vite, Next.js, Node.js, TypeScript, Python, package managers (`npm`, `pnpm`, `yarn`, `bun`, `pip`), and Git state automatically.
- **3-Tier Error Capture**: When a command fails, `cmb fix` captures the error from prior session state, the Windows clipboard, or interactive input.
- **Grounded Evidence Diagnosis**: Correlates errors with real files on disk (`package.json`, `tsconfig.json`) instead of inventing causes.
- **5-Tier Command Safety Engine**: Classifies every command (`READ-ONLY`, `WRITE`, `NETWORK`, `DESTRUCTIVE`, `BLOCKED`). Protects system paths and stops `.env` secret leakage.
- **Approval-Gated Execution**: Modifying and destructive commands always prompt: `Run this command? [y/N/c]`.
- **Command Memory & Snippets**: Search (`cmb find`), save (`cmb save`), and rerun (`cmb run`) verified snippets stored in local SQLite persistence.
- **Zero Cloud Accounts Required**: All persistence is local SQLite (`~/.cmdbuddy/cmdbuddy.db`).

---

## 🎙️ Built for NoHandsChallenge (Track 1: Builders) & Wispr Flow

CmdBuddy was conceived and built specifically for the **NoHandsChallenge Track 1: Builders**. 

During development, **Wispr Flow** voice dictation was used to formulate complex technical prompts, dictate code documentation, and speak terminal commands hands-free:
- **Hands-Free CLI Scaffolding**: Formulating intent strings like `"create a react vite typescript app named ingreknow"` via voice without typing flags or quotes.
- **Voice-Driven Error Prompting**: Describing runtime failures to the CLI naturally without touching the keyboard.
- **Documentation & Test Authoring**: Speaking structured docstrings and architectural commit messages directly into development tools.

See [submission/wispr-usage.md](file:///C:/Users/Dell/.gemini/antigravity/scratch/cmdbuddy/submission/wispr-usage.md) for full details.

---

## 🏛️ System Architecture

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

## 📦 Installation (Windows PowerShell)

### Prerequisites
- Windows 10 or 11 with PowerShell 5.1+ or PowerShell 7+.
- Python 3.11+ installed and in PATH.
- Node.js & npm (v18+) for Node/Vite workflows.

### 1. Install via PowerShell
Clone the repository and run the setup script:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```
*Note: This script installs CmdBuddy in editable mode, detects your user script folder, and configures session access without requiring admin privileges or changing machine-wide execution policies.*

### 2. Verify Installation
```powershell
cmb --version
cmb --help
```

---

## 🔑 Gemini API Key Setup

CmdBuddy integrates with Google Gemini (Gemini 2.0 Flash) through server-side REST calls via `httpx`. It never hard-codes or exposes keys.

To set your key in PowerShell for the current session:
```powershell
$env:GEMINI_API_KEY = "your_actual_gemini_api_key"
```

To set it permanently for your user account:
```powershell
[Environment]::SetEnvironmentVariable('GEMINI_API_KEY', 'your_actual_gemini_api_key', 'User')
```

*(Note: CmdBuddy also contains built-in grounded heuristic fallbacks for common deterministic build/script errors even when operating offline).*

---

## 📖 CLI Command Reference

### Generate Commands from Plain English
```powershell
cmb "create a react vite typescript app named ingreknow"
```
CmdBuddy inspects your environment, returns the exact PowerShell commands, explains each step, shows risk badges, and asks for approval before running:
```
Step 1 of 4:
 NETWORK  npm create vite@latest ingreknow -- --template react-ts
Run this command? [y/N/c]:
```

### Diagnose & Fix Terminal Errors
```powershell
cmb fix
```
Automatically captures the last failure, detects project context, cites file-based evidence, and proposes the exact remediation command.

### Explain Commands & Project Facts
```powershell
cmb explain
```
Renders a clear breakdown of verified file facts, terminal session context, and missing information.

### Inspect Detected Project Context
```powershell
cmb context
```
Displays detected framework, package manager, installed versions, scripts, and Git state.

### Save & Reuse Verified Snippets
```powershell
# Save a command
cmb save "vite-dev" --command "npm run dev" --desc "Start Vite dev server" --tags "vite,dev"

# Search saved snippets
cmb find "vite"

# Run a saved snippet with approval
cmb run "vite-dev"
```

### View Execution History
```powershell
cmb history --limit 5
```
Displays an audit log of all generated prompts, executed commands, exit codes, and timestamps.

---

## 🛡️ Safety & Privacy Model

### 5-Tier Safety Classification

| Risk Level | Behavior & Rules |
| :--- | :--- |
| `READ-ONLY` | Safe inspection commands (`git status`, `node -v`, `Get-ChildItem`). Allowlisted queries may run automatically. |
| `WRITE` | Modifies local files, project scripts, or settings (`npm pkg set`, `New-Item`). Always requires `[y/N/c]` approval. |
| `NETWORK` | Clones repositories or installs packages (`git clone`, `npm create vite`, `curl`). Always requires `[y/N/c]` approval. |
| `DESTRUCTIVE` | Recursively removes folders, discards commits, or cleans caches (`Remove-Item -Recurse`, `git reset --hard`). Requires explicit uppercase `YES` confirmation. |
| `BLOCKED` | Attacks system paths (`C:\Windows`, `System32`), formats drives, attempts directory escape, or inspects secrets (`.env`, `id_rsa`). **Strictly blocked from execution.** |

### Project Context Privacy Guarantee
CmdBuddy scans project metadata to assist the AI without exposing your code:
- **Never reads, logs, or transmits**: `.env`, `.env.*`, `*token*`, `*secret*`, `*id_rsa*`, `.pem`, `.key`, `node_modules`, `venv`, or `.git/objects`.
- Caps AI prompt payloads to < 8KB compact metadata.
- Clearly renders **"What CmdBuddy knows"** and **"What CmdBuddy does not know"**.

---

## 🧪 Judge Demo Walkthrough

A pre-configured demo project is provided in `demo-react-vite-project/`.

```powershell
# 1. Enter the demo project
cd demo-react-vite-project

# 2. Try starting the dev server
npm run dev
# Fails with: npm error Missing script: "dev"

# 3. Diagnose and repair with CmdBuddy
cmb fix
# CmdBuddy automatically detects React + Vite + TypeScript,
# cites package.json evidence, and suggests: npm pkg set scripts.dev="vite"

# 4. Approve the command by typing 'y'
# [OK] Fix applied successfully!

# 5. Start the dev server
npm run dev
# Vite starts successfully at: http://localhost:5173/
```

---

## 📊 Test Suite & Verification

CmdBuddy is covered by 30 unit and integration tests across 5 test suites:
```powershell
pytest -q
```
```
..............................                                           [100%]
30 passed in 2.59s
```
- **`test_safety.py`**: Read-only allowlist, write classification, network calls, destructive confirmation, blocked OS paths, secret leakage prevention, chained `;` / `&&` inspection, traversal escape blocking, and snippet name validation.
- **`test_schemas.py`**: Pydantic schema validation, Literal risk levels, and confidence range constraints.
- **`test_ai_client.py`**: Missing key handling, code fence stripping, invalid JSON retry, and nonexistent file filtering.
- **`test_diagnosis.py`**: 3-tier error capture, missing `dev` script repair, evidence degradation on hallucinated files, executor blocking of dangerous AI suggestions, prompt injection resistance in error logs, and execution history recording.
- **`test_context_engine.py`**: Node/React/Vite/TS detection, Python detection, non-project directory handling, and sensitive file exclusion.

---

## ⚠️ Known Limitations & Future Roadmap

### Known Limitations in MVP
- **PowerShell Focus**: Tailored specifically for Windows PowerShell (5.1 & 7+). Linux/macOS shells are planned for future versions.
- **Error Capture**: For commands run outside of `cmb`, error capture relies on session state, clipboard inspection, or interactive paste fallback rather than OS kernel hooks.
- **Focused Heuristics**: Curated offline heuristics currently focus on high-frequency frontend and fullstack build/script patterns.

### Future Roadmap
- **PowerShell Event Hooks**: Direct integration with `PSReadLine` for zero-click automatic error capture.
- **Interactive Diffs**: Rich inline visual diffs showing exact file changes before approving configuration fixes.
- **Monorepo Awareness**: Deep workspace detection for pnpm workspaces, Turborepo, and Nx.

---

## 📜 License

Distributed under the [MIT License](file:///C:/Users/Dell/.gemini/antigravity/scratch/cmdbuddy/LICENSE).
