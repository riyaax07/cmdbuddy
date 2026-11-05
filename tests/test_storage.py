"""Tests for CmdBuddy local SQLite storage."""

from pathlib import Path
from cmdbuddy.storage import StorageManager


def test_storage_history_and_state(tmp_path: Path):
    db_file = tmp_path / "test_cmdbuddy.db"
    storage = StorageManager(db_path=db_file)

    # Test history
    h_id = storage.add_history_entry(
        working_dir=str(tmp_path),
        prompt="create vite app",
        commands=["npm create vite@latest"],
        executed_command="npm create vite@latest",
        exit_code=0,
        status="executed",
    )
    assert h_id > 0

    history = storage.get_history(limit=5)
    assert len(history) == 1
    assert history[0]["prompt"] == "create vite app"
    assert history[0]["executed_command"] == "npm create vite@latest"
    assert history[0]["exit_code"] == 0

    # Test state
    storage.set_state("last_command", "npm run dev")
    storage.set_state("last_error", "Missing dev script")
    assert storage.get_state("last_command") == "npm run dev"
    assert storage.get_state("last_error") == "Missing dev script"


def test_storage_snippets(tmp_path: Path):
    db_file = tmp_path / "test_snippets.db"
    storage = StorageManager(db_path=db_file)

    # Save snippet
    storage.save_snippet(
        name="test-cmd",
        command="npm run build",
        description="Build production bundle",
        tags="build,prod",
        risk="write",
    )

    # Retrieve exact
    snippet = storage.get_snippet("test-cmd")
    assert snippet is not None
    assert snippet["command"] == "npm run build"
    assert snippet["tags"] == "build,prod"

    # Search snippet
    results = storage.find_snippets("build")
    assert len(results) == 1
    assert results[0]["name"] == "test-cmd"

    # Increment usage
    storage.increment_snippet_usage("test-cmd")
    updated = storage.get_snippet("test-cmd")
    assert updated["use_count"] == 1
