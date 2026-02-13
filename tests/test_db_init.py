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
        for table in ['sessions', 'messages', 'summaries', 'topics', 'code_snippets']:
            assert table in schema['existing']
        for fts in ['summaries_fts', 'messages_fts', 'topics_fts', 'code_snippets_fts']:
            assert fts in schema['existing']

    def test_get_stats_empty_db(self, isolated_db):
        db_init.init_database()
        stats = db_init.get_stats()
        for table in db_utils.VALID_TABLES:
            assert stats[table] == 0
        assert stats['db_size_bytes'] > 0
