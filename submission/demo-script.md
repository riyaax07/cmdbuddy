# CmdBuddy: 2-Minute Competition Demo Script

**Track:** NoHandsChallenge — Track 1: Builders  
**Target Duration:** Exactly 2 minutes (120 seconds)  
**Presenter Flow:** Terminal screen share with narration  

---

### [0:00 – 0:15] The Hook & The Problem
**Visual:** PowerShell terminal open in a clean directory.  
**Spoken Narration:**  
> "As developers on Windows, we spend half our day switching back and forth between PowerShell and browser AI chats—copy-pasting stack traces, explaining our tech stack over and over, and praying the AI doesn't suggest a command that breaks our project. Today, that stops. Meet **CmdBuddy**, your PowerShell-first AI command assistant."

---

### [0:15 – 0:35] Automated Project Context
**Visual:** Type `cd demo-react-vite-project; cmb context`. Rich formatted table renders instantly.  
**Spoken Narration:**  
> "Notice what happened when I ran `cmb context`. CmdBuddy automatically identified that we are in a React, Vite, and TypeScript project using npm. It read our scripts and configs, while strictly ignoring sensitive `.env` files and binaries. You never have to explain your project setup to an AI again."

---

### [0:35 – 0:55] The Error & Frictionless `cmb fix`
**Visual:** Run `npm run dev`. The red terminal error appears: `Missing script: "dev"`. Immediately type `cmb fix`.  
**Spoken Narration:**  
> "Now, let's start our dev server: `npm run dev`. It fails because the dev script is missing. Normally, you'd copy this error into ChatGPT. With CmdBuddy, I just type `cmb fix`. No copy-pasting, no tab-switching."

---

### [0:55 – 1:20] Evidence-Based Diagnosis & Safety Approval
**Visual:** CmdBuddy renders the Diagnosis Panel, Evidence Table citing `package.json`, and the suggested fix `npm pkg set scripts.dev="vite"` with a yellow `[WRITE]` risk badge.  
**Spoken Narration:**  
> "Look at this diagnosis: CmdBuddy doesn't guess. It cites real evidence from `package.json`, gives a 98% confidence score, and suggests the exact PowerShell fix: `npm pkg set scripts.dev='vite'`. CmdBuddy's 5-tier safety engine classifies this as a `WRITE` command, requiring explicit approval before anything touches disk."

---

### [1:20 – 1:40] The Fix in Action
**Visual:** Type `y`. Output shows `[OK] Fix applied successfully!`. Run `npm run dev`. Vite boots with `Local: http://localhost:5173/`.  
**Spoken Narration:**  
> "I hit `y` to approve. The command runs, updates `package.json`, and when I run `npm run dev` again—boom! Vite is running live on port 5173. The entire problem was diagnosed, verified, and fixed without leaving the terminal."

---

### [1:40 – 2:00] Command Memory, Safety Model & Impact
**Visual:** Run `cmb history`, then `cmb find "vite"`. Show blocked guardrails.  
**Spoken Narration:**  
> "CmdBuddy remembers everything locally in SQLite. I can search past commands with `cmb find`, rerun them with `cmb run`, and know that dangerous commands like `rmdir C:\` or secret leakage are unconditionally blocked. CmdBuddy keeps developers in their flow state—fast, verified, and safe. Thank you!"
