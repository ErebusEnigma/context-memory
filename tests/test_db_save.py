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
