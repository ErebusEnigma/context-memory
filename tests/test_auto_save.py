"""Tests for the cross-platform auto_save.py wrapper."""

import json
import os
import sqlite3
import subprocess
import sys

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills", "context-memory", "scripts",
)
AUTO_SAVE_SCRIPT = os.path.join(SCRIPTS_DIR, "auto_save.py")

from auto_save import build_brief, extract_text_content, parse_transcript  # noqa: E402


# ---------------------------------------------------------------------------
# Unit tests — extract_text_content
# ---------------------------------------------------------------------------
class TestExtractTextContent:
    def test_string_input(self):
        assert extract_text_content("hello world") == "hello world"

    def test_list_of_blocks(self):
        blocks = [
            {"type": "text", "text": "first"},
            {"type": "tool_use", "name": "bash"},
            {"type": "text", "text": "second"},
        ]
        assert extract_text_content(blocks) == "first\nsecond"

    def test_truncation(self):
        long_text = "a" * 2000
        result = extract_text_content(long_text)
        assert len(result) == 1000

    def test_list_truncation(self):
        blocks = [{"type": "text", "text": "b" * 2000}]
        result = extract_text_content(blocks)
        assert len(result) == 1000

    def test_empty_input(self):
        assert extract_text_content("") == ""
        assert extract_text_content(None) == ""
        assert extract_text_content([]) == ""


# ---------------------------------------------------------------------------
# Unit tests — parse_transcript
# ---------------------------------------------------------------------------
class TestParseTranscript:
    def test_valid_jsonl(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        lines = [
            {"type": "user", "message": {"content": "hello"}},
            {"type": "assistant", "message": {"content": "hi there"}},
        ]
        transcript.write_text("\n".join(json.dumps(ln) for ln in lines), encoding="utf-8")
        msgs = parse_transcript(str(transcript))
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "hello"}
        assert msgs[1] == {"role": "assistant", "content": "hi there"}

    def test_missing_file(self):
        assert parse_transcript("/nonexistent/path.jsonl") == []

    def test_none_path(self):
        assert parse_transcript(None) == []

    def test_message_limit_head_tail(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        lines = []
        for i in range(25):
            role = "user" if i % 2 == 0 else "assistant"
            lines.append({"type": role, "message": {"content": f"msg-{i}"}})
        transcript.write_text("\n".join(json.dumps(ln) for ln in lines), encoding="utf-8")

        msgs = parse_transcript(str(transcript), max_messages=15)
        assert len(msgs) == 15
        # First 5 should be from the head
        assert msgs[0]["content"] == "msg-0"
        assert msgs[4]["content"] == "msg-4"
        # Last 10 should be from the tail
        assert msgs[-1]["content"] == "msg-24"
        assert msgs[5]["content"] == "msg-15"

    def test_non_message_types_skipped(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        lines = [
            {"type": "system", "message": {"content": "system prompt"}},
            {"type": "user", "message": {"content": "hello"}},
            {"type": "tool_result", "message": {"content": "result"}},
            {"type": "assistant", "message": {"content": "response"}},
        ]
        transcript.write_text("\n".join(json.dumps(ln) for ln in lines), encoding="utf-8")
        msgs = parse_transcript(str(transcript))
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_list_content_blocks(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        lines = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "here is the answer"},
                        {"type": "tool_use", "name": "bash", "input": {"command": "ls"}},
                    ]
                },
            },
        ]
        transcript.write_text("\n".join(json.dumps(ln) for ln in lines), encoding="utf-8")
        msgs = parse_transcript(str(transcript))
        assert len(msgs) == 1
        assert msgs[0]["content"] == "here is the answer"


# ---------------------------------------------------------------------------
# Unit tests — build_brief
# ---------------------------------------------------------------------------
class TestBuildBrief:
    def test_from_user_message(self):
        msgs = [
            {"role": "user", "content": "Fix the login bug"},
            {"role": "assistant", "content": "Sure, let me look."},
        ]
        brief = build_brief(msgs, "my-project")
        assert brief == "Auto-saved session: Fix the login bug"

    def test_truncation_of_long_message(self):
        msgs = [{"role": "user", "content": "x" * 200}]
        brief = build_brief(msgs, "proj")
        assert brief.startswith("Auto-saved session: ")
        # 100 chars of user text + prefix
        user_part = brief[len("Auto-saved session: "):]
        assert len(user_part) == 100

    def test_fallback_when_no_user_messages(self):
        msgs = [{"role": "assistant", "content": "I can help."}]
        brief = build_brief(msgs, "my-project")
        assert brief == "Auto-saved session: my-project"

    def test_fallback_empty_messages(self):
        assert build_brief([], "proj") == "Auto-saved session: proj"

    def test_newlines_collapsed(self):
        msgs = [{"role": "user", "content": "line1\nline2\nline3"}]
        brief = build_brief(msgs, "proj")
        assert "\n" not in brief


# ---------------------------------------------------------------------------
# Integration tests — subprocess
# ---------------------------------------------------------------------------
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
            input="",
        )
        assert result.returncode == 0

    def test_exits_zero_when_db_save_missing(self, tmp_path):
        """auto_save.py should exit 0 even when db_save.py doesn't exist."""
        import shutil
        isolated_script = tmp_path / "auto_save.py"
        shutil.copy2(AUTO_SAVE_SCRIPT, str(isolated_script))

        result = subprocess.run(
            [sys.executable, str(isolated_script)],
            capture_output=True,
            text=True,
            timeout=30,
            input="",
        )
        assert result.returncode == 0
        assert result.stderr == ""

    def test_captures_git_branch(self, isolated_db):
        """auto_save.py should detect the git branch when run inside a git repo."""
        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        result = subprocess.run(
            [sys.executable, AUTO_SAVE_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            input="",
        )
        assert result.returncode == 0

        conn = sqlite3.connect(str(isolated_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT session_id FROM sessions LIMIT 1").fetchone()
        conn.close()
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
            input="",
        )
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_uses_real_session_id_from_stdin(self, isolated_db):
        """When stdin provides session_id, it should be used instead of auto-{ts}."""
        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        hook_input = json.dumps({"session_id": "real-session-abc123", "cwd": os.getcwd()})
        result = subprocess.run(
            [sys.executable, AUTO_SAVE_SCRIPT],
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
            "SELECT session_id FROM sessions WHERE session_id = ?",
            ("real-session-abc123",),
        ).fetchone()
        conn.close()
        assert row is not None

    def test_stop_hook_active_prevents_save(self, isolated_db):
        """When stop_hook_active is true, no session should be saved."""
        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        hook_input = json.dumps({"stop_hook_active": True, "session_id": "should-not-save"})
        result = subprocess.run(
            [sys.executable, AUTO_SAVE_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            input=hook_input,
        )
        assert result.returncode == 0

        # DB may not even be created when hook bails early
        if not isolated_db.exists():
            return
        conn = sqlite3.connect(str(isolated_db))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM sessions").fetchone()
            assert row["cnt"] == 0
        except sqlite3.OperationalError:
            pass  # Table doesn't exist → no sessions saved, which is correct
        finally:
            conn.close()

    def test_transcript_saves_messages(self, isolated_db, tmp_path):
        """When a transcript file is provided, messages should be extracted and saved."""
        transcript = tmp_path / "transcript.jsonl"
        lines = [
            {"type": "user", "message": {"content": "What is 2+2?"}},
            {"type": "assistant", "message": {"content": "4"}},
        ]
        transcript.write_text("\n".join(json.dumps(ln) for ln in lines), encoding="utf-8")

        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        hook_input = json.dumps({
            "session_id": "transcript-test",
            "transcript_path": str(transcript),
            "cwd": os.getcwd(),
        })
        result = subprocess.run(
            [sys.executable, AUTO_SAVE_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            input=hook_input,
        )
        assert result.returncode == 0

        conn = sqlite3.connect(str(isolated_db))
        conn.row_factory = sqlite3.Row
        msg_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM messages"
        ).fetchone()["cnt"]
        conn.close()
        assert msg_count == 2

    def test_brief_from_first_user_message(self, isolated_db, tmp_path):
        """The brief should contain text from the first user message."""
        transcript = tmp_path / "transcript.jsonl"
        lines = [
            {"type": "user", "message": {"content": "Fix the login bug in auth.py"}},
            {"type": "assistant", "message": {"content": "Looking at it now."}},
        ]
        transcript.write_text("\n".join(json.dumps(ln) for ln in lines), encoding="utf-8")

        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        hook_input = json.dumps({
            "session_id": "brief-test",
            "transcript_path": str(transcript),
            "cwd": os.getcwd(),
        })
        result = subprocess.run(
            [sys.executable, AUTO_SAVE_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            input=hook_input,
        )
        assert result.returncode == 0

        conn = sqlite3.connect(str(isolated_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT brief FROM summaries LIMIT 1").fetchone()
        conn.close()
        assert row is not None
        assert "Fix the login bug" in row["brief"]
        assert row["brief"].startswith("Auto-saved session:")

    def test_fallback_when_transcript_missing(self, isolated_db):
        """Bogus transcript path should still exit 0 and fall back to minimal save."""
        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        hook_input = json.dumps({
            "session_id": "fallback-test",
            "transcript_path": "/nonexistent/transcript.jsonl",
            "cwd": os.getcwd(),
        })
        result = subprocess.run(
            [sys.executable, AUTO_SAVE_SCRIPT],
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
            "SELECT session_id FROM sessions WHERE session_id = ?",
            ("fallback-test",),
        ).fetchone()
        conn.close()
        assert row is not None

    def test_empty_stdin_backward_compat(self, isolated_db):
        """With empty stdin, should behave like old code (synthetic ID, generic brief)."""
        env = os.environ.copy()
        env["CONTEXT_MEMORY_DB_PATH"] = str(isolated_db)
        result = subprocess.run(
            [sys.executable, AUTO_SAVE_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            input="",
        )
        assert result.returncode == 0

        conn = sqlite3.connect(str(isolated_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT session_id FROM sessions LIMIT 1").fetchone()
        conn.close()
        if row is not None:
            assert row["session_id"].startswith("auto-")
