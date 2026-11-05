"""Project Context Engine for CmdBuddy.

Inspects the current working directory safely:
- Detects project type (Node, React, Vite, TypeScript, Python, etc.)
- Detects package manager (npm, pnpm, yarn, bun, pip, poetry)
- Extracts key metadata (version, scripts, dependency names, config files)
- Captures Git context (branch, porcelain status, last commit subject)
- Identifies "What CmdBuddy knows" and "What CmdBuddy does not know"
- Strictly excludes sensitive files (.env, credentials, secrets, binary files)
- Caps payload size to prevent token bloating
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

# Patterns and names that must never be read, indexed, or transmitted
SENSITIVE_PATTERNS = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    ".env.staging",
    "id_rsa",
    "id_ed25519",
    "credentials",
    "secret",
}

IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    "__pycache__",
    ".next",
    ".cache",
    ".turbo",
    ".output",
}

BINARY_EXTENSIONS = {
    ".exe", ".dll", ".so", ".bin", ".iso", ".png", ".jpg", ".jpeg",
    ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".7z", ".mp4",
    ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".wav",
}


def is_sensitive_or_ignored(path: Path) -> bool:
    """Return True if path should be strictly excluded from scanning."""
    name_lower = path.name.lower()

    # Check exact sensitive names or .env variations
    if name_lower in SENSITIVE_PATTERNS or name_lower.startswith(".env"):
        return True
    if any(secret_term in name_lower for secret_term in ("secret", "token", "credential", "password", "apikey", "api_key")):
        if path.suffix.lower() in (".txt", ".json", ".yaml", ".yml", ".key", ".pem", ".p12", ".pfx"):
            return True

    # Check ignored directories in path hierarchy
    for part in path.parts:
        if part in IGNORED_DIRECTORIES:
            return True

    # Check binary extensions
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True

    return False


def get_command_output(cmd: List[str], cwd: Optional[Path] = None) -> Optional[str]:
    """Execute a quick read-only command and return stripped output, or None on error."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=2,
            shell=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return None


def detect_git_info(cwd: Path) -> Dict[str, Optional[str]]:
    """Inspect Git branch, short status, and last commit subject if .git exists."""
    git_dir = cwd / ".git"
    if not git_dir.exists():
        return {"git_branch": None, "git_status": None, "git_last_commit": None}

    branch = get_command_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    status_raw = get_command_output(["git", "status", "--porcelain"], cwd=cwd)
    last_commit = get_command_output(["git", "log", "-1", "--format=%s"], cwd=cwd)

    short_status = None
    if status_raw is not None:
        lines = [line.strip() for line in status_raw.splitlines() if line.strip()]
        if not lines:
            short_status = "Clean working tree"
        else:
            short_status = f"{len(lines)} modified/untracked file(s)"

    return {
        "git_branch": branch,
        "git_status": short_status,
        "git_last_commit": last_commit,
    }


def detect_package_manager(cwd: Path) -> str:
    """Detect package manager from lockfiles or available executables."""
    if (cwd / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (cwd / "yarn.lock").exists():
        return "yarn"
    if (cwd / "bun.lockb").exists() or (cwd / "bun.lock").exists():
        return "bun"
    if (cwd / "package-lock.json").exists():
        return "npm"
    if (cwd / "poetry.lock").exists():
        return "poetry"
    if (cwd / "Pipfile.lock").exists():
        return "pipenv"
    if (cwd / "requirements.txt").exists() or (cwd / "pyproject.toml").exists():
        return "pip"

    if (cwd / "package.json").exists():
        return "npm"
    return "unknown"


def scan_project_context(target_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Build a compact, privacy-safe project context summary from the directory."""
    cwd = (target_dir or Path.cwd()).resolve()

    context: Dict[str, Any] = {
        "cwd": str(cwd),
        "is_project": False,
        "project_type": "Non-project directory",
        "package_manager": "unknown",
        "project_name": cwd.name,
        "project_version": None,
        "scripts": {},
        "dependencies": [],
        "dev_dependencies": [],
        "config_files": [],
        "git_branch": None,
        "git_status": None,
        "git_last_commit": None,
        "node_version": None,
        "npm_version": None,
        "python_version": None,
        "known_facts": [],
        "unknowns": [],
    }

    # Detect Git Info
    git_info = detect_git_info(cwd)
    context["git_branch"] = git_info["git_branch"]
    context["git_status"] = git_info["git_status"]
    context["git_last_commit"] = git_info["git_last_commit"]

    if context["git_branch"]:
        context["known_facts"].append(f"Git repository on branch '{context['git_branch']}'")
        if context["git_last_commit"]:
            context["known_facts"].append(f"Last commit: \"{context['git_last_commit']}\"")
    else:
        context["unknowns"].append("No Git repository detected")

    # Detect Package Manager
    context["package_manager"] = detect_package_manager(cwd)

    # Detect installed runtimes
    if shutil.which("node"):
        context["node_version"] = get_command_output(["node", "-v"])
        if context["node_version"]:
            context["known_facts"].append(f"Node.js runtime: {context['node_version']}")
    else:
        context["unknowns"].append("Node.js runtime not installed or not in PATH")

    if shutil.which("npm"):
        context["npm_version"] = get_command_output(["npm", "-v"])
        if context["npm_version"]:
            context["known_facts"].append(f"npm package manager: {context['npm_version']}")
    else:
        context["unknowns"].append("npm CLI not found")

    if shutil.which("python"):
        context["python_version"] = get_command_output(["python", "--version"])
        if context["python_version"]:
            context["known_facts"].append(f"Python runtime: {context['python_version']}")

    # Collect prominent config files safely
    known_configs = [
        "package.json",
        "tsconfig.json",
        "jsconfig.json",
        "vite.config.ts",
        "vite.config.js",
        "next.config.js",
        "next.config.mjs",
        "webpack.config.js",
        "tailwind.config.js",
        "tailwind.config.ts",
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "Dockerfile",
        "docker-compose.yml",
    ]
    for cfg in known_configs:
        cfg_path = cwd / cfg
        if cfg_path.exists() and cfg_path.is_file() and not is_sensitive_or_ignored(cfg_path):
            context["config_files"].append(cfg)

    # Deep scan Node.js / TypeScript / React metadata
    package_json_path = cwd / "package.json"
    if package_json_path.exists() and not is_sensitive_or_ignored(package_json_path):
        context["is_project"] = True
        try:
            with open(package_json_path, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)

            context["project_name"] = pkg_data.get("name", cwd.name)
            context["project_version"] = pkg_data.get("version")
            context["scripts"] = pkg_data.get("scripts", {})

            deps = list(pkg_data.get("dependencies", {}).keys())
            dev_deps = list(pkg_data.get("devDependencies", {}).keys())
            context["dependencies"] = deps
            context["dev_dependencies"] = dev_deps

            # Determine project specialization
            all_deps = set(deps + dev_deps)
            features = []
            if "react" in all_deps:
                features.append("React")
            if "vue" in all_deps:
                features.append("Vue")
            if "next" in all_deps:
                features.append("Next.js")
            if "vite" in all_deps or any("vite.config" in c for c in context["config_files"]):
                features.append("Vite")
            if "typescript" in all_deps or (cwd / "tsconfig.json").exists():
                features.append("TypeScript")

            if features:
                context["project_type"] = " + ".join(features) + " Application"
            else:
                context["project_type"] = "Node.js Application"

            context["known_facts"].append(f"Project name: '{context['project_name']}'")
            context["known_facts"].append(f"Framework: {context['project_type']}")
            context["known_facts"].append(f"Available scripts: {', '.join(context['scripts'].keys()) if context['scripts'] else 'none'}")

            # Check common missing scripts
            if "dev" not in context["scripts"]:
                context["unknowns"].append("package.json does not define a 'dev' script")

        except Exception as e:
            context["unknowns"].append(f"Could not parse package.json: {e}")

    # Check for Python project
    elif (cwd / "pyproject.toml").exists() or (cwd / "requirements.txt").exists():
        context["is_project"] = True
        py_features = ["Python"]
        if (cwd / "pyproject.toml").exists():
            py_features.append("pyproject.toml")
            # Try reading project name / version from pyproject.toml
            try:
                content = (cwd / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
                for line in content.splitlines():
                    if line.strip().startswith("name ="):
                        context["project_name"] = line.split("=", 1)[1].strip().strip('"\'')
                    if line.strip().startswith("version ="):
                        context["project_version"] = line.split("=", 1)[1].strip().strip('"\'')
            except Exception:
                pass
        if (cwd / "requirements.txt").exists():
            py_features.append("requirements.txt")

        context["project_type"] = " + ".join(py_features)
        context["known_facts"].append(f"Python project: {context['project_type']}")

    elif context["git_branch"]:
        context["is_project"] = True
        context["project_type"] = "Git Repository"

    # Note unknowns if anything is missing
    if not context["is_project"]:
        context["unknowns"].append("No package.json, pyproject.toml, or recognized framework config detected in this directory.")

    return context
