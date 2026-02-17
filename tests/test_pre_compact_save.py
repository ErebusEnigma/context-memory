"""Tests for the pre_compact_save.py PreCompact hook handler."""

import json
import os
import sqlite3
import subprocess
import sys

import pytest

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills", "context-memory", "scripts",
)
PRE_COMPACT_SCRIPT = os.path.join(SCRIPTS_DIR, "pre_compact_save.py")

from db_utils import extract_text_content  # noqa: E402
from pre_compact_save import (  # noqa: E402
    parse_transcript_full,
    read_hook_input,
    save_checkpoint,
)


# ---------------------------------------------------------------------------
# Unit tests — extract_text_content (no max_length = no truncation)
# ---------------------------------------------------------------------------
class TestExtractTextContentFull:
    def test_string_input_no_truncation(self):
        long_text = "a" * 5000
        assert extract_text_content(long_text) == long_text

    def test_list_of_blocks_no_truncation(self):
        blocks = [
            {"type": "text", "text": "x" * 3000},
            {"type": "tool_use", "name": "bash"},
            {"type": "text", "text": "y" * 3000},
        ]
        result = extract_text_content(blocks)
        assert len(result) == 6001  # 3000 + \n + 3000

    def test_empty_inputs(self):
        assert extract_text_content(None) == ""
        assert extract_text_content("") == ""
        assert extract_text_content([]) == ""

    def test_non_string_non_list(self):
        assert extract_text_content(42) == ""
        assert extract_text_content({"key": "val"}) == ""


# ---------------------------------------------------------------------------
# Unit tests — read_hook_input
# ---------------------------------------------------------------------------
class TestReadHookInput:
    def test_valid_json(self, monkeypatch):
        import io
        payload = json.dumps({"session_id": "s1", "trigger": "auto"})
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        result = read_hook_input()
        assert result == {"session_id": "s1", "trigger": "auto"}

    def test_empty_stdin(self, monkeypatch):
        import io
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        assert read_hook_input() is None

    def test_invalid_json(self, monkeypatch):
        import io
        monkeypatch.setattr("sys.stdin", io.StringIO("{bad"))
        assert read_hook_input() is None

    def test_none_stdin(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", None)
        assert read_hook_input() is None


# ---------------------------------------------------------------------------
# Unit tests — parse_transcript_full (no sampling, no truncation)
# ---------------------------------------------------------------------------
class TestParseTranscriptFull:
    def test_basic_parsing(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        lines = [
            {"type": "user", "message": {"content": "hello"}},
            {"type": "assistant", "message": {"content": "world"}},
        ]
        transcript.write_text("\n".join(json.dumps(ln) for ln in lines), encoding="utf-8")
        msgs = parse_transcript_full(str(transcript))
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "hello"}
        assert msgs[1] == {"role": "assistant", "content": "world"}

    def test_no_sampling_large_transcript(self, tmp_path):
        """Unlike auto_save, parse_transcript_full should keep ALL messages."""
        transcript = tmp_path / "transcript.jsonl"
        lines = []
        for i in range(100):
            role = "user" if i % 2 == 0 else "assistant"
            lines.append({"type": role, "message": {"content": f"msg-{i}"}})
        transcript.write_text("\n".join(json.dumps(ln) for ln in lines), encoding="utf-8")
        msgs = parse_transcript_full(str(transcript))
        assert len(msgs) == 100
        assert msgs[0]["content"] == "msg-0"
        assert msgs[99]["content"] == "msg-99"

    def test_no_truncation(self, tmp_path):
        """Content should NOT be truncated."""
        transcript = tmp_path / "transcript.jsonl"
        long_content = "a" * 5000
        lines = [{"type": "user", "message": {"content": long_content}}]
        transcript.write_text(json.dumps(lines[0]), encoding="utf-8")
        msgs = parse_transcript_full(str(transcript))
        assert len(msgs) == 1
        assert len(msgs[0]["content"]) == 5000

    def test_skips_non_message_types(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        lines = [
            {"type": "system", "message": {"content": "sys prompt"}},
            {"type": "user", "message": {"content": "hello"}},
            {"type": "tool_result", "message": {"content": "result"}},
            {"type": "assistant", "message": {"content": "response"}},
        ]
        transcript.write_text("\n".join(json.dumps(ln) for ln in lines), encoding="utf-8")
        msgs = parse_transcript_full(str(transcript))
        assert len(msgs) == 2

    def test_missing_file(self):
        assert parse_transcript_full("/nonexistent/path.jsonl") == []

    def test_none_path(self):
        assert parse_transcript_full(None) == []

    def test_malformed_json_lines_skipped(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        content = (
            json.dumps({"type": "user", "message": {"content": "first"}}) + "\n"
            + "bad json\n"
            + json.dumps({"type": "assistant", "message": {"content": "second"}}) + "\n"
        )
        transcript.write_text(content, encoding="utf-8")
        msgs = parse_transcript_full(str(transcript))
        assert len(msgs) == 2

    def test_list_content_blocks(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        lines = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "here is the answer"},
                        {"type": "tool_use", "name": "bash", "input": {"command": "ls"}},
                        {"type": "text", "text": "and more"},
                    ]
                },
            },
        ]
        transcript.write_text(json.dumps(lines[0]), encoding="utf-8")
        msgs = parse_transcript_full(str(transcript))
        assert len(msgs) == 1
        assert "here is the answer" in msgs[0]["content"]
        assert "and more" in msgs[0]["content"]


# ---------------------------------------------------------------------------
# Unit tests — save_checkpoint
# ---------------------------------------------------------------------------
class TestSaveCheckpoint:
    def test_basic_save(self, isolated_db):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        cp_id = save_checkpoint("sess-1", "/tmp/project", "auto", messages)
        assert cp_id is not None
        assert cp_id > 0

        conn = sqlite3.connect(str(isolated_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM context_checkpoints WHERE id = ?", (cp_id,)).fetchone()
        conn.close()

        assert row["session_id"] == "sess-1"
        assert row["checkpoint_number"] == 1
        assert row["trigger_type"] == "auto"
        assert row["message_count"] == 2
        saved_msgs = json.loads(row["messages"])
        assert len(saved_msgs) == 2
        assert saved_msgs[0]["content"] == "hello"

    def test_checkpoint_number_increments(self, isolated_db):
        messages = [{"role": "user", "content": "msg"}]
        save_checkpoint("sess-1", "/tmp/project", "auto", messages)
        save_checkpoint("sess-1", "/tmp/project", "auto", messages)
        save_checkpoint("sess-1", "/tmp/project", "manual", messages)

        conn = sqlite3.connect(str(isolated_db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT checkpoint_number FROM context_checkpoints WHERE session_id = ? ORDER BY checkpoint_number",
            ("sess-1",),
        ).fetchall()
        conn.close()

        assert [r["checkpoint_number"] for r in rows] == [1, 2, 3]

    def test_different_sessions_independent_numbering(self, isolated_db):
        messages = [{"role": "user", "content": "msg"}]
        save_checkpoint("sess-A", "/tmp/a", "auto", messages)
        save_checkpoint("sess-A", "/tmp/a", "auto", messages)
        save_checkpoint("sess-B", "/tmp/b", "auto", messages)

        conn = sqlite3.connect(str(isolated_db))
        conn.row_factory = sqlite3.Row
        rows_a = conn.execute(
            "SELECT checkpoint_number FROM context_checkpoints WHERE session_id = 'sess-A' ORDER BY checkpoint_number"
        ).fetchall()
        rows_b = conn.execute(
            "SELECT checkpoint_number FROM context_checkpoints WHERE session_id = 'sess-B' ORDER BY checkpoint_number"
        ).fetchall()
        conn.close()

        assert [r["checkpoint_number"] for r in rows_a] == [1, 2]
        assert [r["checkpoint_number"] for r in rows_b] == [1]

    def test_large_message_save(self, isolated_db):
        """Test saving a large transcript (simulating full context)."""
        messages = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i} " + "x" * 500}
            for i in range(200)
        ]
        cp_id = save_checkpoint("sess-large", "/tmp/project", "auto", messages)
        assert cp_id is not None

        conn = sqlite3.connect(str(isolated_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT message_count FROM context_checkpoints WHERE id = ?", (cp_id,)).fetchone()
        conn.close()
        assert row["message_count"] == 200

    def test_project_hash_stored(self, isolated_db):
        messages = [{"role": "user", "content": "test"}]
        save_checkpoint("sess-hash", "/tmp/my-project", "auto", messages)

        conn = sqlite3.connect(str(isolated_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT project_hash FROM context_checkpoints WHERE session_id = 'sess-hash'").fetchone()
        conn.close()
        assert row["project_hash"] is not None
        assert len(row["project_hash"]) == 16


# ---------------------------------------------------------------------------
# Integration tests — subprocess
# ---------------------------------------------------------------------------
class TestPreCompactScript:
    def test_runs_with_valid_input(self, isolated_db, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        lines = [
            {"type": "user", "message": {"content": "Fix the bug"}},
            {"type": "assistant", "message": {"content": "Looking into it..."}},
        ]
        transcript.write_text("\n".join(json.dumps(ln) for ln in lines), encoding="utf-8")

        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        hook_input = json.dumps({
            "session_id": "compact-test-1",
            "transcript_path": str(transcript),
            "cwd": str(tmp_path),
            "trigger": "auto",
        })
        result = subprocess.run(
            [sys.executable, PRE_COMPACT_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            input=hook_input,
        )
        assert result.returncode == 0

        conn = sqlite3.connect(str(isolated_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM context_checkpoints WHERE session_id = 'compact-test-1'"
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["message_count"] == 2
        assert row["trigger_type"] == "auto"
        msgs = json.loads(row["messages"])
        assert msgs[0]["content"] == "Fix the bug"

    def test_manual_trigger(self, isolated_db, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        lines = [{"type": "user", "message": {"content": "hello"}}]
        transcript.write_text(json.dumps(lines[0]), encoding="utf-8")

        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        hook_input = json.dumps({
            "session_id": "manual-test",
            "transcript_path": str(transcript),
            "cwd": str(tmp_path),
            "trigger": "manual",
        })
        result = subprocess.run(
            [sys.executable, PRE_COMPACT_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            input=hook_input,
        )
        assert result.returncode == 0

        conn = sqlite3.connect(str(isolated_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT trigger_type FROM context_checkpoints WHERE session_id = 'manual-test'"
        ).fetchone()
        conn.close()
        assert row["trigger_type"] == "manual"

    def test_empty_stdin_exits_gracefully(self, isolated_db):
        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        result = subprocess.run(
            [sys.executable, PRE_COMPACT_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            input="",
        )
        assert result.returncode == 0

    def test_missing_transcript_exits_gracefully(self, isolated_db):
        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        hook_input = json.dumps({
            "session_id": "no-transcript",
            "transcript_path": "/nonexistent/file.jsonl",
            "cwd": os.getcwd(),
        })
        result = subprocess.run(
            [sys.executable, PRE_COMPACT_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            input=hook_input,
        )
        assert result.returncode == 0

    def test_missing_session_id_exits_gracefully(self, isolated_db, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}), encoding="utf-8")

        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        hook_input = json.dumps({
            "transcript_path": str(transcript),
            "cwd": str(tmp_path),
        })
        result = subprocess.run(
            [sys.executable, PRE_COMPACT_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            input=hook_input,
        )
        assert result.returncode == 0

    def test_outputs_json_result(self, isolated_db, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        lines = [{"type": "user", "message": {"content": "test"}}]
        transcript.write_text(json.dumps(lines[0]), encoding="utf-8")

        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        hook_input = json.dumps({
            "session_id": "output-test",
            "transcript_path": str(transcript),
            "cwd": str(tmp_path),
            "trigger": "auto",
        })
        result = subprocess.run(
            [sys.executable, PRE_COMPACT_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            input=hook_input,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "checkpoint_id" in output
        assert output["message_count"] == 1
        assert output["trigger"] == "auto"


# ---------------------------------------------------------------------------
# Integration tests — MCP tool: context_load_checkpoint
# ---------------------------------------------------------------------------
class TestContextLoadCheckpoint:
    @pytest.fixture(autouse=True)
    def _skip_if_no_mcp(self):
        """Skip these tests if the mcp package is not installed."""
        pytest.importorskip("mcp")

    def test_load_by_session_id(self, isolated_db):
        messages = [
            {"role": "user", "content": "test message 1"},
            {"role": "assistant", "content": "response 1"},
        ]
        save_checkpoint("sess-load-1", "/tmp/project", "auto", messages)

        import mcp_server
        result = mcp_server.context_load_checkpoint(session_id="sess-load-1")
        assert "error" not in result
        assert result["session_id"] == "sess-load-1"
        assert len(result["messages"]) == 2
        assert result["messages"][0]["content"] == "test message 1"

    def test_load_by_project_path(self, isolated_db):
        messages = [{"role": "user", "content": "proj msg"}]
        save_checkpoint("sess-proj-1", "/tmp/my-project", "auto", messages)

        import mcp_server
        result = mcp_server.context_load_checkpoint(project_path="/tmp/my-project")
        assert "error" not in result
        assert len(result["messages"]) == 1

    def test_load_most_recent(self, isolated_db):
        msgs1 = [{"role": "user", "content": "first"}]
        msgs2 = [{"role": "user", "content": "second"}, {"role": "assistant", "content": "reply"}]
        save_checkpoint("sess-multi", "/tmp/project", "auto", msgs1)
        save_checkpoint("sess-multi", "/tmp/project", "auto", msgs2)

        import mcp_server
        result = mcp_server.context_load_checkpoint(session_id="sess-multi")
        assert result["checkpoint_number"] == 2
        assert len(result["messages"]) == 2
        assert result["messages"][0]["content"] == "second"

    def test_last_n_messages(self, isolated_db):
        messages = [{"role": "user", "content": f"msg-{i}"} for i in range(10)]
        save_checkpoint("sess-slice", "/tmp/project", "auto", messages)

        import mcp_server
        result = mcp_server.context_load_checkpoint(session_id="sess-slice", last_n_messages=3)
        assert len(result["messages"]) == 3
        assert result["messages"][0]["content"] == "msg-7"
        assert result["messages"][2]["content"] == "msg-9"

    def test_no_checkpoints_returns_error(self, isolated_db):
        from db_init import init_database
        init_database()

        import mcp_server
        result = mcp_server.context_load_checkpoint(session_id="nonexistent")
        assert "error" in result
        assert result["messages"] == []


# ---------------------------------------------------------------------------
# Integration tests — checkpoint pruning
# ---------------------------------------------------------------------------
class TestCheckpointPruning:
    def test_prune_keeps_n_newest(self, isolated_db):
        from db_prune import prune_checkpoints
        messages = [{"role": "user", "content": "msg"}]
        for _ in range(5):
            save_checkpoint("sess-prune", "/tmp/project", "auto", messages)

        result = prune_checkpoints(max_per_session=2, dry_run=False)
        assert result["pruned"] == 3

        conn = sqlite3.connect(str(isolated_db))
        count = conn.execute("SELECT COUNT(*) FROM context_checkpoints").fetchone()[0]
        conn.close()
        assert count == 2

    def test_prune_dry_run(self, isolated_db):
        from db_prune import prune_checkpoints
        messages = [{"role": "user", "content": "msg"}]
        for _ in range(5):
            save_checkpoint("sess-dry", "/tmp/project", "auto", messages)

        result = prune_checkpoints(max_per_session=2, dry_run=True)
        assert result["pruned"] == 3
        assert result["dry_run"] is True
        assert "checkpoints" in result

        conn = sqlite3.connect(str(isolated_db))
        count = conn.execute("SELECT COUNT(*) FROM context_checkpoints").fetchone()[0]
        conn.close()
        assert count == 5  # Nothing actually deleted

    def test_prune_multiple_sessions(self, isolated_db):
        from db_prune import prune_checkpoints
        messages = [{"role": "user", "content": "msg"}]
        for _ in range(4):
            save_checkpoint("sess-A", "/tmp/a", "auto", messages)
        for _ in range(3):
            save_checkpoint("sess-B", "/tmp/b", "auto", messages)

        result = prune_checkpoints(max_per_session=2, dry_run=False)
        # sess-A: 4 - 2 = 2 pruned, sess-B: 3 - 2 = 1 pruned
        assert result["pruned"] == 3

    def test_prune_no_db(self, isolated_db):
        from db_prune import prune_checkpoints
        # Don't create the DB
        result = prune_checkpoints(max_per_session=2)
        assert result["pruned"] == 0


# ---------------------------------------------------------------------------
# Schema migration test
# ---------------------------------------------------------------------------
class TestSchemaMigration:
    def test_v3_to_v4_migration(self, isolated_db):
        """Test that migrating from v3 to v4 creates context_checkpoints table."""
        from db_init import _migrate_v3_to_v4, get_schema_version

        # Create a v3 database (without context_checkpoints)
        conn = sqlite3.connect(str(isolated_db))
        # Execute the old schema minus the context_checkpoints parts
        # We just create the schema_version table with version 3
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                project_path TEXT,
                project_hash TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                metadata TEXT
            );
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO schema_version (version) VALUES (3);
        """)
        conn.commit()

        # Verify it's v3
        assert get_schema_version(conn) == 3

        # Run migration
        _migrate_v3_to_v4(conn)
        conn.commit()

        # Verify v4
        assert get_schema_version(conn) == 4

        # Verify context_checkpoints table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='context_checkpoints'"
        )
        assert cursor.fetchone() is not None
        conn.close()
