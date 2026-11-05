# Security Policy

**CmdBuddy** is designed with a defense-in-depth security and privacy architecture. As an AI-assisted command runner, we treat terminal safety and credential protection as paramount requirements.

---

## Security Model & Principles

1. **API Keys from Environment Variables Only**:
   - `GEMINI_API_KEY` is loaded strictly from `os.environ`.
   - API keys are never stored in the database, logged to transcripts, or checked into version control.

2. **Strict File & Secret Exclusion**:
   - The project context engine actively filters out all sensitive files:
     - `.env`, `.env.*`
     - Private keys (`id_rsa`, `id_ed25519`, `*.pem`, `*.key`)
     - Credentials, tokens, and password files
     - Binary files and raw large assets
     - Dependencies (`node_modules`, `venv`, `.venv`)
     - Git internal objects (`.git/objects`)
   - CmdBuddy never reads, displays, or transmits these files.

3. **Grounded AI Verification**:
   - Every file path cited as evidence in an AI response is cross-checked against the local filesystem.
   - Nonexistent or fabricated paths are stripped immediately. If evidence is lacking, CmdBuddy explicitly marks the diagnosis as `insufficient_evidence`.

4. **Approval-Gated Execution**:
   - **Read-Only**: Pure information queries (`git status`, `node -v`) may run automatically only if explicitly allowlisted.
   - **Write & Network**: Commands modifying project state (`npm install`, `npm pkg set`) require interactive user confirmation (`[y/N/c]`).
   - **Destructive**: Commands that delete folders or discard git history require explicit uppercase `YES` confirmation.
   - **Blocked**: Commands that target Windows OS system directories (`C:\Windows`, `System32`), format disks, exfiltrate `.env` files, or use fork bombs are **unconditionally blocked**.

5. **User Responsibility**:
   - While CmdBuddy classifies risks and blocks known dangerous patterns, users should always review suggested commands before approving execution.

---

## Reporting Vulnerabilities

If you discover a security vulnerability or safety bypass in CmdBuddy, please open a private GitHub security advisory or report it to the maintainers. Do not post active exploit payloads in public issues.
