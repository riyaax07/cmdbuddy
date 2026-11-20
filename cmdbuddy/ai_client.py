"""Gemini API client for CmdBuddy.

Calls the Gemini API with structured JSON output, validates responses against Pydantic models,
and verifies grounded evidence against existing project files.
Includes robust offline grounded heuristics for common deterministic developer errors.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx
from pydantic import ValidationError

from cmdbuddy.schemas import (
    CommandGenerationResponse,
    DiagnosisResponse,
    EvidenceItem,
    GeneratedCommand,
)


class GeminiClientError(Exception):
    """Base exception for Gemini client failures."""
    pass


class GeminiClient:
    """Client for generating PowerShell commands and diagnoses via Gemini REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3.8-flash",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout: float = 30.0,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model
        self.base_url = base_url
        self.timeout = timeout

    def _call_gemini_api(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Send a request to Gemini generateContent endpoint."""
        if not self.api_key:
            raise GeminiClientError(
                "GEMINI_API_KEY environment variable is not set.\n"
                "To set it in PowerShell for this session, run:\n"
                "  $env:GEMINI_API_KEY = 'your_actual_gemini_api_key'\n"
                "Or set it permanently in User Environment Variables."
            )

        endpoint = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

        body: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            },
        }

        if system_instruction:
            body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        headers = {"Content-Type": "application/json"}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(endpoint, json=body, headers=headers)

            if resp.status_code != 200:
                raise GeminiClientError(f"Gemini API returned HTTP {resp.status_code}: {resp.text}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise GeminiClientError("Gemini API returned no candidates.")

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise GeminiClientError("Gemini API returned an empty response part.")

            return parts[0].get("text", "").strip()

        except httpx.RequestError as e:
            raise GeminiClientError(f"Network error connecting to Gemini API: {e}")

    def generate_commands(
        self,
        user_intent: str,
        project_context: Dict[str, Any],
        target_dir: Optional[Path] = None,
    ) -> CommandGenerationResponse:
        """Generate structured PowerShell commands from developer intent with retry on invalid output."""
        cwd = target_dir or Path.cwd()

        system_instruction = (
            "You are CmdBuddy, an expert developer command assistant specializing in Windows PowerShell. "
            "Convert user requests into precise PowerShell commands. "
            "Return ONLY a JSON object conforming strictly to the requested schema. "
            "Never execute or suggest destructive commands unless specifically asked. "
            "Never output commands that read or expose .env or credentials. "
            "Prefer standard PowerShell or node/npm/python commands appropriate for the project context."
        )

        schema_hint = {
            "summary": "Short description of what the commands do",
            "commands": [
                {
                    "command": "powershell command string",
                    "explanation": "What this step does",
                    "risk": "read-only | write | network | destructive | blocked",
                    "requires_approval": True,
                }
            ],
            "limitations": ["Any assumptions or prerequisites"],
            "relevant_files": ["Existing project files referenced, if any"],
        }

        prompt = (
            f"User Intent: {user_intent}\n\n"
            f"Current Project Context:\n{json.dumps(project_context, indent=2)}\n\n"
            f"Respond with a JSON object strictly following this structure:\n"
            f"{json.dumps(schema_hint, indent=2)}\n"
        )

        raw_text = self._call_gemini_api(prompt, system_instruction=system_instruction)

        # First parsing attempt
        parsed = self._try_parse_command_response(raw_text)
        if not parsed:
            retry_prompt = (
                f"{prompt}\n\n"
                f"NOTICE: Your previous response was not valid JSON matching the schema:\n"
                f"{raw_text[:300]}\n"
                f"Please correct this and return only valid JSON matching the schema."
            )
            raw_text = self._call_gemini_api(retry_prompt, system_instruction=system_instruction)
            parsed = self._try_parse_command_response(raw_text)

        if not parsed:
            raise GeminiClientError("Failed to parse valid structured JSON from Gemini after retry.")

        valid_files, has_nonexistent = self._verify_files(parsed.relevant_files, cwd)
        if has_nonexistent:
            parsed.relevant_files = valid_files

        return parsed

    def diagnose_error(
        self,
        error_text: Optional[str],
        last_command: Optional[str],
        project_context: Dict[str, Any],
        target_dir: Optional[Path] = None,
    ) -> DiagnosisResponse:
        """Diagnose a failed command or project error using grounded evidence."""
        cwd = target_dir or Path.cwd()

        # If GEMINI_API_KEY is not set, try local grounded heuristic before failing
        if not self.api_key:
            local_diag = self._try_local_heuristic_diagnosis(error_text, last_command, project_context, cwd)
            if local_diag:
                return local_diag
            raise GeminiClientError(
                "GEMINI_API_KEY environment variable is not set.\n"
                "To set it in PowerShell for this session, run:\n"
                "  $env:GEMINI_API_KEY = 'your_actual_gemini_api_key'\n"
                "Or set it permanently in User Environment Variables."
            )

        system_instruction = (
            "You are CmdBuddy, an expert developer troubleshooter specializing in Windows PowerShell, Node.js, and modern build tooling. "
            "Analyze the terminal error and project context. "
            "Provide root cause, grounded evidence referencing real files in the project, and concrete PowerShell remediation commands. "
            "Never invent file paths, package versions, or fake causes. "
            "If there is not enough evidence to determine the root cause with certainty, set diagnosis_status to 'insufficient_evidence' "
            "and suggest a safe diagnostic inspection command first."
        )

        schema_hint = {
            "summary": "Short headline summary of diagnosis",
            "root_cause": "Precise root cause",
            "confidence": 0.95,
            "diagnosis_status": "supported | partially_supported | insufficient_evidence",
            "evidence": [
                {
                    "file": "relative/file/path",
                    "observation": "What was observed in this file"
                }
            ],
            "missing_information": [],
            "suggested_commands": [
                {
                    "command": "PowerShell command to fix or diagnose the issue",
                    "explanation": "Why this command helps",
                    "risk": "read-only | write | network | destructive | blocked",
                    "requires_approval": True
                }
            ],
            "limitations": [],
            "next_step_if_fix_fails": "What to inspect next if remediation fails"
        }

        # Compact context payload (< 8KB)
        compact_context = {
            "project_name": project_context.get("project_name"),
            "project_type": project_context.get("project_type"),
            "package_manager": project_context.get("package_manager"),
            "scripts": project_context.get("scripts", {}),
            "dependencies": project_context.get("dependencies", [])[:15],
            "dev_dependencies": project_context.get("dev_dependencies", [])[:15],
            "config_files": project_context.get("config_files", []),
            "node_version": project_context.get("node_version"),
            "npm_version": project_context.get("npm_version"),
            "git_branch": project_context.get("git_branch"),
            "known_facts": project_context.get("known_facts", []),
            "unknowns": project_context.get("unknowns", []),
        }

        prompt = (
            f"Failed Command: {last_command or '(not specified / project scan)'}\n\n"
            f"Terminal Error Output:\n{error_text or '(none provided - diagnose from project context)'}\n\n"
            f"Project Context:\n{json.dumps(compact_context, indent=2)}\n\n"
            f"Provide a grounded diagnosis JSON object matching this schema:\n"
            f"{json.dumps(schema_hint, indent=2)}\n"
        )

        raw_text = self._call_gemini_api(prompt, system_instruction=system_instruction)

        parsed = self._try_parse_diagnosis_response(raw_text)
        if not parsed:
            retry_prompt = (
                f"{prompt}\n\n"
                f"NOTICE: Your previous response was not valid JSON matching the DiagnosisResponse schema:\n"
                f"{raw_text[:300]}\n"
                f"Please correct this and return only valid JSON."
            )
            raw_text = self._call_gemini_api(retry_prompt, system_instruction=system_instruction)
            parsed = self._try_parse_diagnosis_response(raw_text)

        if not parsed:
            raise GeminiClientError("Failed to parse valid structured JSON diagnosis from Gemini after retry.")

        # Grounding check: verify evidence files exist relative to cwd
        valid_evidence: List[EvidenceItem] = []
        for item in parsed.evidence:
            item_path = cwd / item.file
            if item_path.exists():
                valid_evidence.append(item)
            else:
                parsed.missing_information.append(f"AI referenced nonexistent file: {item.file}")

        parsed.evidence = valid_evidence

        # If evidence was wiped out and AI claimed supported, downgrade to insufficient_evidence
        if not parsed.evidence and parsed.diagnosis_status == "supported":
            parsed.diagnosis_status = "insufficient_evidence"
            parsed.limitations.append("No grounded local project files supported the initial hypothesis.")

        return parsed

    def _try_local_heuristic_diagnosis(
        self,
        error_text: Optional[str],
        last_command: Optional[str],
        project_context: Dict[str, Any],
        cwd: Path,
    ) -> Optional[DiagnosisResponse]:
        """Offline grounded heuristic for common deterministic developer errors."""
        err_lower = (error_text or "").lower()
        cmd_lower = (last_command or "").lower()

        pkg_path = cwd / "package.json"

        # Case 1: Malformed package.json
        if pkg_path.exists():
            try:
                content = pkg_path.read_text(encoding="utf-8")
                json.loads(content)
            except json.JSONDecodeError as e:
                return DiagnosisResponse(
                    summary="Malformed package.json syntax error",
                    root_cause=f"package.json contains invalid JSON syntax at line {e.lineno}, column {e.colno}: {e.msg}",
                    confidence=1.0,
                    diagnosis_status="supported",
                    evidence=[
                        EvidenceItem(
                            file="package.json",
                            observation=f"JSON parsing failed around line {e.lineno}: {e.msg}"
                        )
                    ],
                    missing_information=[],
                    suggested_commands=[
                        GeneratedCommand(
                            command=f"Get-Content -Head {max(1, e.lineno + 2)} package.json",
                            explanation="Inspect the syntax around the invalid line in package.json",
                            risk="read-only",
                            requires_approval=False,
                        )
                    ],
                    limitations=[],
                    next_step_if_fix_fails="Open package.json in an editor to fix the JSON syntax.",
                )

        # Case 2: Missing npm script (e.g. dev, build, start)
        if pkg_path.exists():
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    pkg_data = json.load(f)
                scripts = pkg_data.get("scripts", {})

                if "missing script" in err_lower or "dev" in cmd_lower or "npm run dev" in cmd_lower or not error_text:
                    if "dev" not in scripts:
                        dev_cmd = "vite"
                        deps = set(list(pkg_data.get("dependencies", {}).keys()) + list(pkg_data.get("devDependencies", {}).keys()))
                        if "next" in deps:
                            dev_cmd = "next dev"
                        elif "react-scripts" in deps:
                            dev_cmd = "react-scripts start"

                        return DiagnosisResponse(
                            summary="Missing 'dev' script in package.json",
                            root_cause=f"The package.json scripts block does not define a 'dev' script to run '{dev_cmd}'.",
                            confidence=0.98,
                            diagnosis_status="supported",
                            evidence=[
                                EvidenceItem(
                                    file="package.json",
                                    observation=f"The 'scripts' object has entries [{', '.join(scripts.keys())}] but lacks 'dev'."
                                )
                            ],
                            missing_information=[],
                            suggested_commands=[
                                GeneratedCommand(
                                    command=f'npm pkg set scripts.dev="{dev_cmd}"',
                                    explanation=f"Adds the missing dev script to package.json pointing to '{dev_cmd}'.",
                                    risk="write",
                                    requires_approval=True,
                                )
                            ],
                            limitations=[f"Assumes {dev_cmd} is installed or configured in dependencies."],
                            next_step_if_fix_fails=f"Verify that {dev_cmd} is installed in devDependencies or run npm install.",
                        )
            except Exception:
                pass

        # Case 3: Port already in use (EADDRINUSE)
        if "eaddrinuse" in err_lower or "address already in use" in err_lower:
            port_match = re.search(r":::?(\d+)", error_text or "")
            port = port_match.group(1) if port_match else "5173"
            return DiagnosisResponse(
                summary=f"Port {port} is already in use by another process",
                root_cause=f"The development server failed to bind to port {port} because another application is listening on it.",
                confidence=0.95,
                diagnosis_status="supported",
                evidence=[],
                missing_information=[],
                suggested_commands=[
                    GeneratedCommand(
                        command=f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object OwningProcess, State",
                        explanation=f"Inspect which process ID is currently occupying port {port}",
                        risk="read-only",
                        requires_approval=False,
                    )
                ],
                limitations=[],
                next_step_if_fix_fails=f"Terminate the occupying process or pass a different port (e.g., npm run dev -- --port {int(port) + 1}).",
            )

        # Case 4: Missing Git user identity
        if "unable to auto-detect email address" in err_lower or "tell me who you are" in err_lower:
            return DiagnosisResponse(
                summary="Git user identity is not configured",
                root_cause="Git requires a user.name and user.email to record commits.",
                confidence=1.0,
                diagnosis_status="supported",
                evidence=[],
                missing_information=[],
                suggested_commands=[
                    GeneratedCommand(
                        command='git config --global user.name "Developer"; git config --global user.email "developer@example.com"',
                        explanation="Set global Git author identity",
                        risk="write",
                        requires_approval=True,
                    )
                ],
                limitations=["Uses placeholder developer@example.com"],
                next_step_if_fix_fails="Run 'git config --list' to verify configured credentials.",
            )

        # Case 5: Python virtual environment not activated
        if "modulenotfounderror" in err_lower or "no module named" in err_lower:
            venv_path = cwd / "venv"
            dot_venv = cwd / ".venv"
            activate_script = None
            if venv_path.exists() and (venv_path / "Scripts" / "Activate.ps1").exists():
                activate_script = ".\\venv\\Scripts\\Activate.ps1"
            elif dot_venv.exists() and (dot_venv / "Scripts" / "Activate.ps1").exists():
                activate_script = ".\\.venv\\Scripts\\Activate.ps1"

            if activate_script:
                return DiagnosisResponse(
                    summary="Python virtual environment not activated",
                    root_cause="A module import failed while a local virtual environment is present but not activated.",
                    confidence=0.90,
                    diagnosis_status="supported",
                    evidence=[
                        EvidenceItem(
                            file=activate_script.split("\\")[1],
                            observation="Virtual environment folder exists with activation script."
                        )
                    ],
                    missing_information=[],
                    suggested_commands=[
                        GeneratedCommand(
                            command=activate_script,
                            explanation="Activate the project's Python virtual environment",
                            risk="write",
                            requires_approval=True,
                        )
                    ],
                    limitations=[],
                    next_step_if_fix_fails="Install missing dependencies with: pip install -r requirements.txt",
                )

        # Case 6: Ambiguous / Insufficient evidence fallback
        return DiagnosisResponse(
            summary="Insufficient context to diagnose terminal error",
            root_cause="The provided error and project files do not provide enough evidence to identify a definitive cause without guessing.",
            confidence=0.2,
            diagnosis_status="insufficient_evidence",
            evidence=[],
            missing_information=["Specific stack trace or error log", "Build configuration details"],
            suggested_commands=[
                GeneratedCommand(
                    command="git status",
                    explanation="Inspect modified and untracked files in the working directory",
                    risk="read-only",
                    requires_approval=False,
                )
            ],
            limitations=["Heuristic engine refused to speculate without grounded file evidence."],
            next_step_if_fix_fails="Re-run the failing command with verbose/debug flags (e.g. npm run dev -- --debug).",
        )

    def _try_parse_command_response(self, text: str) -> Optional[CommandGenerationResponse]:
        """Attempt to parse JSON text into CommandGenerationResponse."""
        try:
            cleaned = self._clean_json_text(text)
            data = json.loads(cleaned)
            return CommandGenerationResponse.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            return None

    def _try_parse_diagnosis_response(self, text: str) -> Optional[DiagnosisResponse]:
        """Attempt to parse JSON text into DiagnosisResponse."""
        try:
            cleaned = self._clean_json_text(text)
            data = json.loads(cleaned)
            return DiagnosisResponse.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            return None

    @staticmethod
    def _clean_json_text(text: str) -> str:
        """Strip markdown code fences and whitespace from response text."""
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    def _verify_files(self, files: List[str], cwd: Path) -> Tuple[List[str], bool]:
        """Check if referenced files actually exist in the project directory."""
        valid: List[str] = []
        has_invalid = False
        for f in files:
            p = cwd / f
            if p.exists():
                valid.append(f)
            else:
                has_invalid = True
        return valid, has_invalid
