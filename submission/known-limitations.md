# CmdBuddy: Known Limitations & Technical Scope

**Competition Track:** NoHandsChallenge — Track 1: Builders  

---

## 1. Honest Scope & Current MVP Boundaries

In accordance with competition rules and sound engineering practices, CmdBuddy is scoped as a focused, robust MVP. The following limitations are recognized:

1. **PowerShell-First Focus**:
   - CmdBuddy is tailored specifically for Windows PowerShell (PowerShell 5.1 and PowerShell 7+).
   - Linux Bash / macOS Zsh shells are not currently supported in this MVP.

2. **Error Capture Mechanisms**:
   - Full automated OS-level terminal output scraping without wrapping commands is inherently limited on Windows consoles.
   - For commands run outside of `cmb`, CmdBuddy uses Windows clipboard inspection or prompt fallback rather than kernel-level terminal hooking.

3. **Runtime Verification**:
   - Runtime verification is only performed on commands that the developer explicitly approves and executes. CmdBuddy does not run unapproved commands in an isolated sandbox ahead of time.

4. **Curated Heuristic Patterns**:
   - Offline heuristic diagnoses focus on high-frequency frontend and fullstack patterns: missing scripts, malformed `package.json`, port collisions (`EADDRINUSE`), Git author identity, and Python virtual environment activation.
   - Highly bespoke compiler errors outside of Node.js, Vite, TypeScript, and Python fall back to Gemini API analysis or `insufficient_evidence`.

5. **No Web Dashboard**:
   - CmdBuddy is an intentional terminal-first tool. No web-based frontend or electron dashboard is included in this phase.

6. **Not an Autonomous Terminal Agent**:
   - CmdBuddy intentionally requires human approval before executing modifying or destructive commands. It does not act as an unguided autonomous agent capable of modifying repositories unsupervised.

---

## 2. Future Improvements Post-Competition

- **PowerShell `$PROFILE` Hook**: Native PSReadLine event hooks for automatic zero-click error capture.
- **Cross-Platform Shell Adapters**: Support for Bash, Zsh, and fish shells.
- **Visual File Diffs**: Inline Rich diffs showing exactly which lines of configuration files will change before approving a fix.
