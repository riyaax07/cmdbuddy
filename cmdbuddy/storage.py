"""SQLite storage engine for CmdBuddy.

Manages command history, saved snippets, and interactive session state.
Stored locally in ~/.cmdbuddy/cmdbuddy.db.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_cmdbuddy_dir() -> Path:
    """Return the configuration and storage directory for CmdBuddy.
    
    Tries CMDBUDDY_HOME env var, then ~/.cmdbuddy, and gracefully falls back to
    a local writable path in scratch or temp if sandbox restricts root user home.
    """
    if "CMDBUDDY_HOME" in os.environ:
        p = Path(os.environ["CMDBUDDY_HOME"])
        p.mkdir(parents=True, exist_ok=True)
        return p

    # Try ~/.cmdbuddy first
    candidate = Path.home() / ".cmdbuddy"
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        test_file = candidate / ".test_access"
        test_file.touch()
        test_file.unlink()
        return candidate
    except (PermissionError, OSError):
        pass

    # Fallback to local project scratch directory
    scratch_dir = Path("C:/Users/Dell/.gemini/antigravity/scratch/cmdbuddy/.cmdbuddy")
    try:
        scratch_dir.mkdir(parents=True, exist_ok=True)
        return scratch_dir
    except (PermissionError, OSError):
        temp_dir = Path(os.environ.get("TEMP", "/tmp")) / ".cmdbuddy"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir


def get_db_path() -> Path:
    """Return the path to the SQLite database."""
    return get_cmdbuddy_dir() / "cmdbuddy.db"


class StorageManager:
    """Handles local SQLite persistence for CmdBuddy."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # History table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    working_dir TEXT NOT NULL,
                    prompt TEXT,
                    commands_json TEXT,
                    executed_command TEXT,
                    exit_code INTEGER,
                    status TEXT,
                    error_text TEXT
                )
                """
            )

            # Saved snippets table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS snippets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    command TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    tags TEXT DEFAULT '',
                    risk TEXT DEFAULT 'write',
                    project_path TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    use_count INTEGER DEFAULT 0
                )
                """
            )

            # Session state key-value table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS session_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    # --- History Operations ---

    def add_history_entry(
        self,
        working_dir: str,
        prompt: Optional[str] = None,
        commands: Optional[List[str]] = None,
        executed_command: Optional[str] = None,
        exit_code: Optional[int] = None,
        status: str = "suggested",
        error_text: Optional[str] = None,
    ) -> int:
        """Record an entry in the command execution history."""
        now = datetime.now(timezone.utc).isoformat()
        commands_json = json.dumps(commands or [])
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO history (
                    timestamp, working_dir, prompt, commands_json,
                    executed_command, exit_code, status, error_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    working_dir,
                    prompt,
                    commands_json,
                    executed_command,
                    exit_code,
                    status,
                    error_text,
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve recent command history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, working_dir, prompt, commands_json,
                       executed_command, exit_code, status, error_text
                FROM history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                try:
                    item["commands"] = json.loads(item["commands_json"]) if item["commands_json"] else []
                except Exception:
                    item["commands"] = []
                results.append(item)
            return results

    # --- Snippet Operations ---

    def save_snippet(
        self,
        name: str,
        command: str,
        description: str = "",
        tags: str = "",
        risk: str = "write",
        project_path: str = "",
    ) -> None:
        """Save or overwrite a named command snippet."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO snippets (
                    name, command, description, tags, risk, project_path, created_at, last_used_at, use_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(name) DO UPDATE SET
                    command=excluded.command,
                    description=excluded.description,
                    tags=excluded.tags,
                    risk=excluded.risk,
                    project_path=excluded.project_path,
                    created_at=excluded.created_at
                """,
                (name, command, description, tags, risk, project_path, now, None),
            )
            conn.commit()

    def get_snippet(self, name: str) -> Optional[Dict[str, Any]]:
        """Fetch a snippet by exact name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, command, description, tags, risk, project_path, created_at, last_used_at, use_count
                FROM snippets
                WHERE name = ?
                """,
                (name,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_snippets(self, query: str) -> List[Dict[str, Any]]:
        """Search snippets by name, tags, or description."""
        search_pattern = f"%{query}%"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, command, description, tags, risk, project_path, created_at, last_used_at, use_count
                FROM snippets
                WHERE name LIKE ? OR tags LIKE ? OR description LIKE ? OR command LIKE ?
                ORDER BY use_count DESC, id DESC
                """,
                (search_pattern, search_pattern, search_pattern, search_pattern),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def list_snippets(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all saved snippets."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, command, description, tags, risk, project_path, created_at, last_used_at, use_count
                FROM snippets
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def increment_snippet_usage(self, name: str) -> None:
        """Bump the usage counter and update last_used_at timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE snippets
                SET use_count = use_count + 1, last_used_at = ?
                WHERE name = ?
                """,
                (now, name),
            )
            conn.commit()

    # --- Session State Operations ---

    def set_state(self, key: str, value: Any) -> None:
        """Save a state value (serialized to JSON)."""
        now = datetime.now(timezone.utc).isoformat()
        val_str = json.dumps(value)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO session_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                (key, val_str, now),
            )
            conn.commit()

    def get_state(self, key: str, default: Any = None) -> Any:
        """Retrieve a state value (deserialized from JSON)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM session_state WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()
            if not row:
                return default
            try:
                return json.loads(row["value"])
            except Exception:
                return row["value"]

    def get_last_error_state(self) -> Dict[str, Any]:
        """Convenience helper to retrieve last command, last error, and last cwd."""
        return {
            "last_command": self.get_state("last_command"),
            "last_error": self.get_state("last_error"),
            "last_cwd": self.get_state("last_cwd"),
            "last_exit_code": self.get_state("last_exit_code"),
        }
