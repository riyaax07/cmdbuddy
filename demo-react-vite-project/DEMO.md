# CmdBuddy Demo Guide for Judges

Welcome to the **CmdBuddy** interactive verification demo for the **NoHandsChallenge (Track 1: Builders)**.

This project is a React + Vite + TypeScript application with a single intentional defect: the `"dev"` script is missing from `package.json`.

---

## 3-Step Demo Workflow

Open Windows PowerShell in this directory:

### Step 1: Run the dev server
```powershell
npm run dev
```
**Observed Result:**  
The command fails with `npm error Missing script: "dev"`.

### Step 2: Ask CmdBuddy to fix it
```powershell
cmb fix
```
**What CmdBuddy does automatically:**
1. Detects project context: React + Vite + TypeScript, package manager npm.
2. Inspects `package.json` grounded evidence: finds `scripts` block lacking `"dev"`.
3. Displays root cause and risk classification: `WRITE`.
4. Suggests: `npm pkg set scripts.dev="vite"`.
5. Prompts for approval: `Run this command? [y/N/c]`.

Type `y` and press Enter to approve.

### Step 3: Run the dev server again
```powershell
npm run dev
```
**Observed Result:**  
Vite dev server starts instantly at `http://localhost:5173/`!

---

## Verifying Persistence & History

Check that CmdBuddy recorded the diagnosis and repair:
```powershell
cmb history
```
You will see the `cmb fix` entry logged with its execution result and timestamp.
