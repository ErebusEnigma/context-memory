"""Tests for session save logic."""

import db_init
import db_save
import db_utils


class TestSaveSession:
    def test_save_new_session(self, isolated_db):
        db_init.init_database()
        sid = db_save.save_session("test-session-1")
        assert sid >= 1

    def test_save_session_with_project(self, isolated_db):
        db_init.init_database()
        sid = db_save.save_session("test-session-1", project_path="/tmp/myproject")
        assert sid >= 1

    def test_update_existing_session(self, isolated_db):
        db_init.init_database()
        sid1 = db_save.save_session("test-session-1")
        sid2 = db_save.save_session("test-session-1", project_path="/tmp/updated")
        assert sid1 == sid2

    def test_auto_init_if_no_db(self, isolated_db):
        assert not isolated_db.exists()
        sid = db_save.save_session("test-session-1")
        assert sid >= 1
        assert isolated_db.exists()


class TestSaveMessages:
    def test_save_messages(self, isolated_db):
        db_init.init_database()
        sid = db_save.save_session("test-session-1")
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        count = db_save.save_messages(sid, messages)
        assert count == 2

    def test_replace_messages(self, isolated_db):
        db_init.init_database()
        sid = db_save.save_session("test-session-1")
        db_save.save_messages(sid, [{"role": "user", "content": "First"}])
        db_save.save_messages(sid, [{"role": "user", "content": "Second"}], replace=True)
        with db_utils.get_connection(readonly=True) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (sid,))
            assert cursor.fetchone()[0] == 1


class TestSaveSummary:
    def test_save_summary(self, isolated_db):
        db_init.init_database()
        sid = db_save.save_session("test-session-1")
        summary_id = db_save.save_summary(sid, brief="Test session summary")
        assert summary_id >= 1

    def test_save_summary_with_details(self, isolated_db):
        db_init.init_database()
        sid = db_save.save_session("test-session-1")
        summary_id = db_save.save_summary(
            sid,
            brief="Test session",
            detailed="Detailed description of the test session",
            key_decisions=["Used pytest", "Added fixtures"],
            technologies=["python", "sqlite"],
            outcome="success",
        )
        assert summary_id >= 1

    def test_update_summary(self, isolated_db):
        db_init.init_database()
        sid = db_save.save_session("test-session-1")
        id1 = db_save.save_summary(sid, brief="First")
        id2 = db_save.save_summary(sid, brief="Updated")
        assert id1 == id2


class TestSaveTopics:
    def test_save_topics(self, isolated_db):
        db_init.init_database()
        sid = db_save.save_session("test-session-1")
        count = db_save.save_topics(sid, ["python", "testing", "sqlite"])
        assert count == 3

    def test_replace_topics(self, isolated_db):
        db_init.init_database()
        sid = db_save.save_session("test-session-1")
        db_save.save_topics(sid, ["old-topic"])
        db_save.save_topics(sid, ["new-topic"], replace=True)
        with db_utils.get_connection(readonly=True) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM topics WHERE session_id = ?", (sid,))
            assert cursor.fetchone()[0] == 1


class TestSaveCodeSnippet:
    def test_save_snippet(self, isolated_db):
        db_init.init_database()
        sid = db_save.save_session("test-session-1")
        snippet_id = db_save.save_code_snippet(
            sid, code="print('hello')", language="python", description="Hello world"
        )
        assert snippet_id >= 1


class TestSaveFullSession:
    def test_save_full_session(self, isolated_db):
        db_init.init_database()
        result = db_save.save_full_session(
            session_id="full-session-1",
            project_path="/tmp/myproject",
            messages=[
                {"role": "user", "content": "Help me write tests"},
                {"role": "assistant", "content": "Sure, here's how"},
            ],
            summary={"brief": "Writing test suite", "outcome": "success"},
            topics=["testing", "python"],
            code_snippets=[{"code": "assert True", "language": "python"}],
        )
        assert "session_id" in result
        assert result["messages_count"] == 2
        assert result["topics_count"] == 2
        assert len(result["snippets"]) == 1


class TestDeduplication:
    def test_skip_when_rich_session_exists(self, isolated_db):
        """Auto-save should be skipped if a rich /remember session exists recently."""
        db_init.init_database()
        db_save.save_full_session(
            session_id="rich-1",
            project_path="/tmp/myproject",
            summary={"brief": "Implemented authentication flow"},
            topics=["auth"],
        )
        assert db_save.should_skip_auto_save("/tmp/myproject", window_minutes=5) is True

    def test_proceed_when_only_auto_saves(self, isolated_db):
        """Auto-save should proceed when only auto-saves exist (no rich sessions)."""
        db_init.init_database()
        db_save.save_full_session(
            session_id="auto-1",
            project_path="/tmp/myproject",
            summary={"brief": "Auto-saved session"},
        )
        assert db_save.should_skip_auto_save("/tmp/myproject", window_minutes=5) is False

    def test_proceed_when_auto_save_with_project_name(self, isolated_db):
        """Auto-save with 'Auto-saved session: proj' prefix should not block."""
        db_init.init_database()
        db_save.save_full_session(
            session_id="auto-1",
            project_path="/tmp/myproject",
            summary={"brief": "Auto-saved session: myproject"},
        )
        assert db_save.should_skip_auto_save("/tmp/myproject", window_minutes=5) is False

    def test_proceed_for_different_project(self, isolated_db):
        """Auto-save should proceed for a different project path."""
        db_init.init_database()
        db_save.save_full_session(
            session_id="rich-1",
            project_path="/tmp/project-a",
            summary={"brief": "Implemented something"},
        )
        assert db_save.should_skip_auto_save("/tmp/project-b", window_minutes=5) is False

    def test_proceed_when_no_db(self, isolated_db):
        """Auto-save should proceed when no database exists."""
        assert db_save.should_skip_auto_save("/tmp/myproject") is False

    def test_proceed_when_no_project_path(self, isolated_db):
        """Auto-save should proceed when no project path is provided."""
        db_init.init_database()
        assert db_save.should_skip_auto_save("") is False
        assert db_save.should_skip_auto_save(None) is False

    def test_proceed_when_session_outside_window(self, isolated_db):
        """Auto-save should proceed if rich session is older than dedup window."""
        db_init.init_database()
        project_hash = db_utils.hash_project_path("/tmp/myproject")
        # Insert directly with backdated timestamp to avoid sessions_updated trigger
        with db_utils.get_connection() as conn:
            conn.execute("""
                INSERT INTO sessions (session_id, project_path, project_hash,
                    created_at, updated_at)
                VALUES (?, ?, ?, datetime('now', '-10 minutes'), datetime('now', '-10 minutes'))
            """, ("rich-1", "/tmp/myproject", project_hash))
            sid = conn.execute("SELECT id FROM sessions WHERE session_id='rich-1'").fetchone()[0]
            conn.execute("""
                INSERT INTO summaries (session_id, brief) VALUES (?, ?)
            """, (sid, "Old session"))
            conn.commit()
        assert db_save.should_skip_auto_save("/tmp/myproject", window_minutes=5) is False
