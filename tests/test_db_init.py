"""Tests for database initialization."""

import db_init
import db_utils


class TestInitDatabase:
    def test_creates_database(self, isolated_db):
        assert not isolated_db.exists()
        result = db_init.init_database()
        assert result is True
        assert isolated_db.exists()

    def test_skips_if_exists(self, isolated_db):
        db_init.init_database()
        result = db_init.init_database()
        assert result is False

    def test_force_recreates(self, isolated_db):
        db_init.init_database()
        result = db_init.init_database(force=True)
        assert result is True

    def test_creates_all_tables(self, isolated_db):
        db_init.init_database()
        schema = db_init.verify_schema()
        assert schema['valid'] is True
        assert len(schema['missing']) == 0

    def test_verify_schema_lists_tables(self, isolated_db):
        db_init.init_database()
        schema = db_init.verify_schema()
        for table in ['sessions', 'messages', 'summaries', 'topics', 'code_snippets', 'schema_version']:
            assert table in schema['existing']
        for fts in ['summaries_fts', 'messages_fts', 'topics_fts', 'code_snippets_fts']:
            assert fts in schema['existing']

    def test_get_stats_empty_db(self, isolated_db):
        db_init.init_database()
        stats = db_init.get_stats()
        for table in db_utils.STATS_TABLES:
            assert stats[table] == 0
        # schema_version should NOT be in stats
        assert 'schema_version' not in stats
        assert stats['db_size_bytes'] > 0

    def test_get_stats_no_db_returns_empty(self, isolated_db):
        assert not isolated_db.exists()
        stats = db_init.get_stats()
        assert stats == {}

    def test_verify_schema_no_db_returns_invalid(self, isolated_db):
        """verify_schema() returns a clear result when the DB doesn't exist."""
        assert not isolated_db.exists()
        result = db_init.verify_schema()
        assert result['valid'] is False
        assert result['error'] == 'database not found'
        assert result['existing'] == []
        assert len(result['missing']) > 0


class TestSchemaVersioning:
    def test_fresh_db_has_version_table(self, isolated_db):
        db_init.init_database()
        with db_utils.get_connection(readonly=True) as conn:
            version = db_init.get_schema_version(conn)
        assert version == db_init.CURRENT_SCHEMA_VERSION

    def test_fresh_db_has_correct_version(self, isolated_db):
        db_init.init_database()
        with db_utils.get_connection(readonly=True) as conn:
            cursor = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = cursor.fetchone()
        assert row[0] == 3

    def test_legacy_db_returns_version_1(self, isolated_db):
        """A DB without schema_version table is implicitly version 1."""
        # Create a legacy DB (without schema_version table)
        import sqlite3
        conn = sqlite3.connect(str(isolated_db))
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY, session_id TEXT)")
        conn.commit()
        # Use the init's get_schema_version
        version = db_init.get_schema_version(conn)
        conn.close()
        assert version == 1

    def test_legacy_db_auto_migrates(self, isolated_db):
        """ensure_schema_current() migrates a legacy DB to current version."""
        # Create a legacy-style DB with all tables but no schema_version
        with db_utils.get_connection() as conn:
            # Execute schema SQL but skip the schema_version part
            legacy_sql = db_init.SCHEMA_SQL.split("-- Schema versioning")[0]
            conn.executescript(legacy_sql)
            conn.commit()
            assert db_init.get_schema_version(conn) == 1

        db_init.ensure_schema_current()

        with db_utils.get_connection(readonly=True) as conn:
            version = db_init.get_schema_version(conn)
        assert version == db_init.CURRENT_SCHEMA_VERSION

    def test_migrations_are_idempotent(self, isolated_db):
        """Running ensure_schema_current() twice doesn't fail or change version."""
        db_init.init_database()
        db_init.ensure_schema_current()
        db_init.ensure_schema_current()
        with db_utils.get_connection(readonly=True) as conn:
            version = db_init.get_schema_version(conn)
        assert version == db_init.CURRENT_SCHEMA_VERSION

    def test_apply_migrations_returns_final_version(self, isolated_db):
        # Create legacy DB
        with db_utils.get_connection() as conn:
            legacy_sql = db_init.SCHEMA_SQL.split("-- Schema versioning")[0]
            conn.executescript(legacy_sql)
            conn.commit()
            final = db_init.apply_migrations(conn)
        assert final == db_init.CURRENT_SCHEMA_VERSION
