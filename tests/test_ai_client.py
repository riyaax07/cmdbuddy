"""Unit tests for Gemini client JSON parsing, retries, and file verification."""

import pytest
from pathlib import Path
from cmdbuddy.ai_client import GeminiClient, GeminiClientError


def test_ai_client_missing_key_error():
    client = GeminiClient(api_key=None)
    # Ensure env var is unset for this test call
    client.api_key = None
    with pytest.raises(GeminiClientError, match="GEMINI_API_KEY environment variable is not set"):
        client._call_gemini_api("test prompt")


def test_ai_client_json_parsing_with_code_fences():
    client = GeminiClient(api_key="mock_key")
    raw_markdown_json = """```json
    {
        "summary": "Sample response with code block",
        "commands": [
            {
                "command": "git status",
                "explanation": "Check git status",
                "risk": "read-only",
                "requires_approval": false
            }
        ],
        "limitations": [],
        "relevant_files": []
    }
    ```"""
    parsed = client._try_parse_command_response(raw_markdown_json)
    assert parsed is not None
    assert parsed.summary == "Sample response with code block"
    assert len(parsed.commands) == 1
    assert parsed.commands[0].command == "git status"


def test_ai_client_invalid_json_handling():
    client = GeminiClient(api_key="mock_key")
    invalid_raw = "This is not valid json at all!"
    parsed = client._try_parse_command_response(invalid_raw)
    assert parsed is None


def test_ai_client_nonexistent_file_filter(tmp_path: Path):
    client = GeminiClient(api_key="mock_key")

    # Create real file
    real_file = tmp_path / "package.json"
    real_file.write_text("{}")

    files = ["package.json", "nonexistent_config.json", "fake_file.ts"]
    valid, has_invalid = client._verify_files(files, cwd=tmp_path)

    assert valid == ["package.json"]
    assert has_invalid is True
