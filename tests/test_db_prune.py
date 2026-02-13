"""Tests for database pruning."""

import db_init
import db_prune
import db_save
import db_utils


class TestPruneSessions:
    def _create_sessions(self, isolated_db, count=5, project_path="/tmp/proj"):
        """Helper to create N sessions with summaries and topics."""
        db_init.init_database()
        for i in range(count):
            db_save.save_full_session(
                session_id=f"session-{i}",
                project_path=project_path,
                summary={"brief": f"Session {i} summary"},
                topics=[f"topic-{i}"],
                messages=[{"role": "user", "content": f"Message {i}"}],
                code_snippets=[{"code": f"print({i})", "language": "python"}],
            )
        return count

    def test_prune_by_count_keeps_newest(self, isolated_db):
        self._create_sessions(isolated_db, count=5)
        result = db_prune.prune_sessions(max_sessions=3)
        assert result["pruned"] == 2
        # Verify 3 remain
        with db_utils.get_connection(readonly=True) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            assert cursor.fetchone()[0] == 3

    def test_prune_by_age(self, isolated_db):
        db_init.init_database()
        project_hash = db_utils.hash_project_path("/tmp/proj")
        # Insert old session directly
        with db_utils.get_connection() as conn:
            conn.execute("""
                INSERT INTO sessions (session_id, project_path, project_hash,
                    created_at, updated_at)
                VALUES ('old-1', '/tmp/proj', ?, datetime('now', '-30 days'), datetime('now', '-30 days'))
            """, (project_hash,))
            old_id = conn.execute("SELECT id FROM sessions WHERE session_id='old-1'").fetchone()[0]
            conn.execute("INSERT INTO summaries (session_id, brief) VALUES (?, 'Old session')", (old_id,))
            conn.commit()
        # Insert new session
        db_save.save_full_session(session_id="new-1", project_path="/tmp/proj",
                                  summary={"brief": "New session"})
        result = db_prune.prune_sessions(max_age_days=7)
        assert result["pruned"] == 1
        with db_utils.get_connection(readonly=True) as conn:
            cursor = conn.execute("SELECT session_id FROM sessions")
            remaining = [row[0] for row in cursor.fetchall()]
        assert "new-1" in remaining
        assert "old-1" not in remaining

    def test_dry_run_doesnt_delete(self, isolated_db):
        self._create_sessions(isolated_db, count=5)
        result = db_prune.prune_sessions(max_sessions=2, dry_run=True)
        assert result["pruned"] == 3
        assert result["dry_run"] is True
        assert len(result["sessions"]) == 3
        # Verify nothing was actually deleted
        with db_utils.get_connection(readonly=True) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            assert cursor.fetchone()[0] == 5

    def test_cascade_cleans_children(self, isolated_db):
        self._create_sessions(isolated_db, count=3)
        result = db_prune.prune_sessions(max_sessions=1)
        assert result["pruned"] == 2
        with db_utils.get_connection(readonly=True) as conn:
            for table in ['messages', 'summaries', 'topics', 'code_snippets']:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                assert cursor.fetchone()[0] == 1, f"{table} should have 1 row after prune"

    def test_fts_cleaned_after_prune(self, isolated_db):
        """FTS indexes should be cleaned up after pruning (via DELETE triggers)."""
        self._create_sessions(isolated_db, count=3)
        db_prune.prune_sessions(max_sessions=1)
        with db_utils.get_connection(readonly=True) as conn:
            # Search for pruned content should yield no results
            cursor = conn.execute(
                "SELECT COUNT(*) FROM summaries_fts WHERE summaries_fts MATCH '\"Session 0\"'"
            )
            assert cursor.fetchone()[0] == 0

    def test_empty_db(self, isolated_db):
        db_init.init_database()
        result = db_prune.prune_sessions(max_sessions=5)
        assert result["pruned"] == 0

    def test_missing_db(self, isolated_db):
        result = db_prune.prune_sessions(max_sessions=5)
        assert result["pruned"] == 0
        assert result["reason"] == "database does not exist"

    def test_no_criteria(self, isolated_db):
        db_init.init_database()
        result = db_prune.prune_sessions()
        assert result["pruned"] == 0
        assert result["reason"] == "no criteria specified"

    def test_combined_age_and_count(self, isolated_db):
        """OR logic: sessions matching either age or count criteria are pruned."""
        db_init.init_database()
        project_hash = db_utils.hash_project_path("/tmp/proj")
        # Insert 2 old sessions
        with db_utils.get_connection() as conn:
            for i in range(2):
                conn.execute("""
                    INSERT INTO sessions (session_id, project_path, project_hash,
                        created_at, updated_at)
                    VALUES (?, '/tmp/proj', ?, datetime('now', '-30 days'), datetime('now', '-30 days'))
                """, (f"old-{i}", project_hash))
            conn.commit()
        # Insert 5 new sessions
        for i in range(5):
            db_save.save_session(f"new-{i}", "/tmp/proj")

        # max_age=7 catches 2 old ones, max_sessions=3 catches 2 newest overflow -> OR = up to 4
        result = db_prune.prune_sessions(max_age_days=7, max_sessions=3)
        assert result["pruned"] == 4  # 2 old + 2 excess new
        with db_utils.get_connection(readonly=True) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            assert cursor.fetchone()[0] == 3
