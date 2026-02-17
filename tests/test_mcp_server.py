"""Tests for the MCP server tool functions."""
# isort: skip_file
from __future__ import annotations

import pytest

pytest.importorskip("mcp", reason="mcp package not installed")

import mcp_server  # noqa: E402
from db_init import init_database  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_and_seed(summary_brief="Fixed auth bug", topics=None, user_note=None):
    """Initialize DB and save a sample session, returning the result dict."""
    init_database()
    return mcp_server.context_save(
        session_id="test-session-1",
        project_path="/tmp/test-project",
        messages=[
            {"role": "user", "content": "How do I fix the auth bug?"},
            {"role": "assistant", "content": "Here is the fix..."},
        ],
        summary={"brief": summary_brief, "outcome": "success"},
        topics=topics or ["authentication", "bugfix"],
        user_note=user_note,
    )


# ---------------------------------------------------------------------------
# TestContextInit
# ---------------------------------------------------------------------------

class TestContextInit:
    def test_init_creates_database(self):
        result = mcp_server.context_init()
        assert result["created"] is True

    def test_init_idempotent(self):
        mcp_server.context_init()
        result = mcp_server.context_init()
        assert result["created"] is False
        assert "already exists" in result["message"]

    def test_init_force(self):
        mcp_server.context_init()
        result = mcp_server.context_init(force=True)
        assert result["created"] is True


# ---------------------------------------------------------------------------
# TestContextSave
# ---------------------------------------------------------------------------

class TestContextSave:
    def test_save_returns_session_id(self):
        result = _init_and_seed()
        assert "session_id" in result
        assert isinstance(result["session_id"], int)

    def test_save_includes_summary(self):
        result = _init_and_seed()
        assert "summary_id" in result

    def test_save_counts_messages(self):
        result = _init_and_seed()
        assert result.get("messages_count") == 2

    def test_save_counts_topics(self):
        result = _init_and_seed()
        assert result.get("topics_count") == 2

    def test_save_with_code_snippets(self):
        init_database()
        result = mcp_server.context_save(
            session_id="snippet-session",
            code_snippets=[{"code": "print('hi')", "language": "python", "description": "greeting"}],
        )
        assert "snippets" in result
        assert len(result["snippets"]) == 1

    def test_save_with_user_note_only(self):
        init_database()
        result = mcp_server.context_save(
            session_id="note-session",
            user_note="Remember: use JWT for auth",
        )
        assert "summary_id" in result


# ---------------------------------------------------------------------------
# TestContextSearch
# ---------------------------------------------------------------------------

class TestContextSearch:
    def test_search_empty_db(self):
        init_database()
        result = mcp_server.context_search(query="anything")
        assert result["result_count"] == 0

    def test_search_finds_saved_session(self):
        _init_and_seed()
        result = mcp_server.context_search(query="auth")
        assert result["result_count"] >= 1

    def test_search_respects_limit(self):
        _init_and_seed()
        result = mcp_server.context_search(query="auth", limit=1)
        assert len(result["sessions"]) <= 1

    def test_search_project_filter(self):
        _init_and_seed()
        result = mcp_server.context_search(query="auth", project_path="/tmp/test-project")
        assert result["result_count"] >= 1

    def test_search_project_filter_excludes(self):
        _init_and_seed()
        result = mcp_server.context_search(query="auth", project_path="/tmp/other-project")
        assert result["result_count"] == 0

    def test_search_detailed(self):
        _init_and_seed()
        result = mcp_server.context_search(query="auth", detailed=True)
        assert result["result_count"] >= 1


# ---------------------------------------------------------------------------
# TestContextStats
# ---------------------------------------------------------------------------

class TestContextStats:
    def test_stats_empty_when_no_db(self):
        result = mcp_server.context_stats()
        assert result == {}

    def test_stats_after_save(self):
        _init_and_seed()
        result = mcp_server.context_stats()
        assert result.get("sessions", 0) >= 1
        assert "db_size_bytes" in result


# ---------------------------------------------------------------------------
# TestMCPServerRegistration
# ---------------------------------------------------------------------------

class TestCaptureStdout:
    """Verify that _capture_stdout suppresses print() and returns the function result."""

    def test_suppresses_print(self, capsys):
        """Stdout from the wrapped function should not leak."""
        def noisy_fn():
            print("this should be captured")
            return 42

        result = mcp_server._capture_stdout(noisy_fn)
        assert result == 42
        captured = capsys.readouterr()
        assert "this should be captured" not in captured.out

    def test_returns_function_result(self):
        """The wrapped function's return value should pass through."""
        result = mcp_server._capture_stdout(lambda: {"key": "value"})
        assert result == {"key": "value"}

    def test_passes_args_and_kwargs(self):
        """Arguments should be forwarded to the wrapped function."""
        def add(a, b, extra=0):
            return a + b + extra

        result = mcp_server._capture_stdout(add, 1, 2, extra=10)
        assert result == 13

    def test_init_database_stdout_suppressed(self, capsys):
        """context_init should not leak init_database's print() to stdout."""
        mcp_server.context_init()
        captured = capsys.readouterr()
        assert "initialized" not in captured.out.lower()


class TestContextSaveWithMetadata:
    def test_metadata_passed_through(self):
        """context_save should forward metadata to save_full_session."""
        init_database()
        result = mcp_server.context_save(
            session_id="meta-mcp-1",
            metadata={"source": "mcp", "custom": True},
        )
        assert "session_id" in result
        import db_utils
        import json
        with db_utils.get_connection(readonly=True) as conn:
            row = conn.execute(
                "SELECT metadata FROM sessions WHERE id = ?", (result["session_id"],)
            ).fetchone()
        meta = json.loads(row["metadata"])
        assert meta["source"] == "mcp"
        assert meta["custom"] is True


class TestMCPServerRegistration:
    """Verify the FastMCP instance is configured correctly."""

    def test_server_name(self):
        assert mcp_server.mcp.name == "context-memory"

    def test_tools_registered(self):
        tools = mcp_server.mcp._tool_manager._tools
        names = set(tools.keys())
        assert {"context_search", "context_save", "context_stats", "context_init"} <= names
