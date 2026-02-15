"""Tests for database utilities."""

import db_utils


class TestHashProjectPath:
    def test_returns_hex_string(self):
        result = db_utils.hash_project_path("/tmp/myproject")
        assert isinstance(result, str)
        assert len(result) == 16

    def test_consistent_hashing(self):
        h1 = db_utils.hash_project_path("/tmp/myproject")
        h2 = db_utils.hash_project_path("/tmp/myproject")
        assert h1 == h2

    def test_different_paths_different_hashes(self):
        h1 = db_utils.hash_project_path("/tmp/project-a")
        h2 = db_utils.hash_project_path("/tmp/project-b")
        assert h1 != h2


class TestEscapeFtsQuery:
    def test_simple_query(self):
        result = db_utils.escape_fts_query("hello world")
        assert '"hello"' in result
        assert '"world"' in result

    def test_special_chars_escaped(self):
        result = db_utils.escape_fts_query('hello "world" (test)')
        assert '(' not in result.replace('"', '')
        assert ')' not in result.replace('"', '')

    def test_empty_query(self):
        result = db_utils.escape_fts_query("")
        assert result == '""'


class TestFormatFtsQuery:
    def test_simple_query(self):
        result = db_utils.format_fts_query("hello")
        assert "hello" in result

    def test_prefix_matching(self):
        result = db_utils.format_fts_query("hello", use_prefix=True)
        assert "*" in result

    def test_no_prefix(self):
        result = db_utils.format_fts_query("hello", use_prefix=False)
        assert "*" not in result

    def test_empty_query(self):
        result = db_utils.format_fts_query("")
        assert result == '""'


class TestTruncateText:
    def test_short_text_unchanged(self):
        assert db_utils.truncate_text("hello", 500) == "hello"

    def test_long_text_truncated(self):
        text = "a" * 100
        result = db_utils.truncate_text(text, 50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_exact_length(self):
        text = "a" * 500
        assert db_utils.truncate_text(text, 500) == text


class TestGetConnection:
    def test_connection_works(self, isolated_db):
        with db_utils.get_connection() as conn:
            cursor = conn.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1

    def test_readonly_connection(self, isolated_db):
        # Create db first
        with db_utils.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()
        # Open readonly
        with db_utils.get_connection(readonly=True) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM test")
            assert cursor.fetchone()[0] == 0


class TestDbExists:
    def test_no_db(self, isolated_db):
        assert db_utils.db_exists() is False

    def test_db_exists_after_creation(self, isolated_db):
        with db_utils.get_connection() as conn:
            conn.execute("SELECT 1")
        assert db_utils.db_exists() is True


class TestNormalizeProjectPath:
    def test_backslash_to_forward(self):
        result = db_utils.normalize_project_path("C:\\Users\\dev\\project")
        assert result == "C:/Users/dev/project"

    def test_forward_slash_unchanged(self):
        result = db_utils.normalize_project_path("/home/dev/project")
        assert result == "/home/dev/project"

    def test_mixed_slashes(self):
        result = db_utils.normalize_project_path("C:\\Users/dev\\project/src")
        assert result == "C:/Users/dev/project/src"

    def test_empty_string(self):
        result = db_utils.normalize_project_path("")
        assert result == ""


class TestValidTables:
    def test_valid_tables_defined(self):
        assert "sessions" in db_utils.VALID_TABLES
        assert "messages" in db_utils.VALID_TABLES
        assert "summaries" in db_utils.VALID_TABLES
        assert "topics" in db_utils.VALID_TABLES
        assert "code_snippets" in db_utils.VALID_TABLES

    def test_get_table_count_validates(self):
        import pytest
        with pytest.raises(ValueError):
            db_utils.get_table_count("nonexistent_table")
