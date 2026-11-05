# CmdBuddy: Problem Statement & Value Proposition

**Competition Track:** NoHandsChallenge — Track 1: Builders  

---

## 1. The Real-World Pain Points

Modern software development on Windows requires navigating thousands of CLI commands, shell syntaxes, package managers, and configuration flags. Even experienced engineers face four major friction points daily:

1. **Remembering Arcane PowerShell Syntax**:
   - Modern tooling often defaults to Bash conventions. Developers struggle translating commands into PowerShell (e.g., parameter escaping, environment variables, execution policies).
   - Complex scaffolding commands (e.g. `npm create vite@latest my-app -- --template react-ts`) require remembering specific flag separators and templates.

2. **The Endless Copy-Paste Loop**:
   - When a command fails, developers switch away from the terminal to an AI chat in a web browser.
   - They copy-paste terminal stack traces back and forth between applications, breaking their flow state.

3. **Context Amnesia & Repetitive Explanation**:
   - Web AI assistants have zero knowledge of the developer's local project.
   - The developer must repeatedly describe: *"I am on Windows 11, using PowerShell, in a React + Vite + TypeScript project with npm, and here is my package.json..."*

4. **Hallucinated and Unsafe AI Suggestions**:
   - Generic AI chats frequently hallucinate file paths, non-existent flags, or dangerous commands (e.g. `rm -rf`, `git reset --hard`) without checking whether the referenced files actually exist.
   - There is no safety barrier stopping a user from pasting and running a command that destroys state or corrupts dependencies.

---

## 2. The Solution: CmdBuddy (`cmb`)

**CmdBuddy** is a terminal-native, PowerShell-first AI command assistant designed to eliminate context-switching and terminal friction:

- **Terminal-First Intent**: Developers type natural language directly in PowerShell (`cmb "create a react vite typescript app"`).
- **Automated Local Project Context**: CmdBuddy automatically scans local metadata (project type, scripts, package managers, Git state) without uploading raw source code or exposing `.env` secrets.
- **3-Tier Error Capture**: When a terminal error occurs, `cmb fix` captures the failure from prior session state, the Windows clipboard, or interactive input—without requiring manual copy-pasting.
- **Grounded Evidence**: Every diagnosis is cross-checked against the local filesystem. CmdBuddy only suggests fixes supported by actual files on disk.
- **5-Tier Safety Engine**: Every command is categorized (`read-only`, `write`, `network`, `destructive`, `blocked`). Dangerous OS commands and secret file access are strictly blocked; state modifications require explicit approval.
- **Local Persistence**: Built on local SQLite. Remembers command history, saves reusable snippets (`cmb save`, `cmb find`, `cmb run`), and requires zero cloud accounts.
