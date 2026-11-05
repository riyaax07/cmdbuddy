"""Tests for CmdBuddy project context engine and security filtering."""

import json
from pathlib import Path
from cmdbuddy.context_engine import is_sensitive_or_ignored, scan_project_context


def test_sensitive_file_exclusion(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET_KEY=12345")

    env_local = tmp_path / ".env.local"
    env_local.write_text("DEV_KEY=abc")

    rsa_file = tmp_path / "id_rsa"
    rsa_file.write_text("PRIVATE_KEY")

    token_file = tmp_path / "api_token.key"
    token_file.write_text("token")

    normal_cfg = tmp_path / "package.json"
    normal_cfg.write_text("{}")

    assert is_sensitive_or_ignored(env_file) is True
    assert is_sensitive_or_ignored(env_local) is True
    assert is_sensitive_or_ignored(rsa_file) is True
    assert is_sensitive_or_ignored(token_file) is True
    assert is_sensitive_or_ignored(normal_cfg) is False


def test_node_vite_react_ts_project_detection(tmp_path: Path):
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(
        json.dumps(
            {
                "name": "vite-react-app",
                "version": "1.0.0",
                "scripts": {
                    "build": "vite build",
                    "preview": "vite preview",
                },
                "dependencies": {
                    "react": "^18.3.1",
                    "react-dom": "^18.3.1",
                },
                "devDependencies": {
                    "vite": "^5.4.0",
                    "typescript": "^5.5.3",
                },
            }
        )
    )
    (tmp_path / "vite.config.ts").write_text("export default {}")
    (tmp_path / "tsconfig.json").write_text("{}")

    ctx = scan_project_context(target_dir=tmp_path)
    assert ctx["is_project"] is True
    assert ctx["project_name"] == "vite-react-app"
    assert ctx["project_version"] == "1.0.0"
    assert "React" in ctx["project_type"]
    assert "Vite" in ctx["project_type"]
    assert "TypeScript" in ctx["project_type"]
    assert ctx["package_manager"] == "npm"
    assert "build" in ctx["scripts"]
    assert "dev" not in ctx["scripts"]
    assert "package.json does not define a 'dev' script" in ctx["unknowns"]
    assert "vite.config.ts" in ctx["config_files"]
    assert "tsconfig.json" in ctx["config_files"]


def test_python_project_detection(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "sample-tool"\nversion = "0.2.0"')

    reqs = tmp_path / "requirements.txt"
    reqs.write_text("httpx>=0.27.0\npytest>=8.0.0")

    ctx = scan_project_context(target_dir=tmp_path)
    assert ctx["is_project"] is True
    assert "Python" in ctx["project_type"]
    assert ctx["package_manager"] == "pip"
    assert ctx["project_name"] == "sample-tool"
    assert ctx["project_version"] == "0.2.0"
    assert "pyproject.toml" in ctx["config_files"]
    assert "requirements.txt" in ctx["config_files"]


def test_non_project_directory(tmp_path: Path):
    empty_dir = tmp_path / "empty_folder"
    empty_dir.mkdir()

    ctx = scan_project_context(target_dir=empty_dir)
    assert ctx["is_project"] is False
    assert ctx["project_type"] == "Non-project directory"
    assert ctx["package_manager"] == "unknown"
    assert any("No package.json" in u for u in ctx["unknowns"])
