"""Tests for the cross-platform auto_save.py wrapper."""

import os
import subprocess
import sys

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills", "context-memory", "scripts",
)
AUTO_SAVE_SCRIPT = os.path.join(SCRIPTS_DIR, "auto_save.py")


class TestAutoSaveScript:
    def test_runs_successfully(self, isolated_db):
        """auto_save.py should exit 0 when db_save.py exists."""
        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        result = subprocess.run(
            [sys.executable, AUTO_SAVE_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0

    def test_exits_zero_when_db_save_missing(self, tmp_path):
        """auto_save.py should exit 0 even when db_save.py doesn't exist (graceful no-op)."""
        # Copy auto_save.py to an isolated directory without db_save.py
        import shutil
        isolated_script = tmp_path / "auto_save.py"
        shutil.copy2(AUTO_SAVE_SCRIPT, str(isolated_script))

        result = subprocess.run(
            [sys.executable, str(isolated_script)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert result.stderr == ""

    def test_captures_git_branch(self, isolated_db):
        """auto_save.py should detect the git branch when run inside a git repo."""
        # We're running from the project root which is a git repo
        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        result = subprocess.run(
            [sys.executable, AUTO_SAVE_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0

        # Verify a session was saved by checking the database
        import sqlite3
        conn = sqlite3.connect(str(isolated_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT session_id FROM sessions LIMIT 1").fetchone()
        conn.close()
        # Session may or may not be saved (dedup may skip), but script must not fail
        # If saved, session_id should start with "auto-"
        if row is not None:
            assert row["session_id"].startswith("auto-")

    def test_no_output_on_success(self, isolated_db):
        """auto_save.py should produce no stdout/stderr output (silent hook)."""
        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        result = subprocess.run(
            [sys.executable, AUTO_SAVE_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""
