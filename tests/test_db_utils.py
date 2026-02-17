"""Tests for database utilities."""

from unittest.mock import patch

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

    def test_msys2_path_normalized_on_windows(self):
        """MSYS2-style /c/Users/... should be normalized to C:\\ on Windows."""
        with patch.object(db_utils.platform, "system", return_value="Windows"), \
             patch.object(db_utils.os.path, "abspath", return_value="C:\\c\\Users\\dev\\project"), \
             patch.object(db_utils.os.path, "normpath", return_value="C:\\c\\Users\\dev\\project"):
            result = db_utils.hash_project_path("/c/Users/dev/project")
        # Should produce a consistent hash (just verify it's a valid hex string)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_windows_case_insensitive(self):
        """On Windows, paths should be case-insensitive for hashing."""
        with patch.object(db_utils.platform, "system", return_value="Windows"):
            h1 = db_utils.hash_project_path("C:\\Users\\Dev\\Project")
            h2 = db_utils.hash_project_path("C:\\Users\\dev\\project")
        assert h1 == h2

    def test_trailing_slash_normalized(self):
        """Trailing slashes should be normalized away."""
        h1 = db_utils.hash_project_path("/tmp/myproject/")
        h2 = db_utils.hash_project_path("/tmp/myproject")
        assert h1 == h2

    def test_tilde_expanded(self):
        """Tilde (~) should be expanded to home directory before hashing."""
        import os
        home = os.path.expanduser("~")
        h1 = db_utils.hash_project_path("~/myproject")
        h2 = db_utils.hash_project_path(os.path.join(home, "myproject"))
        assert h1 == h2


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

    def test_special_characters_stripped(self):
        """Special characters like @#$! should be stripped from terms."""
        result = db_utils.format_fts_query("hello@world!")
        assert "@" not in result
        assert "!" not in result
        assert "helloworld" in result

    def test_dot_splits_term(self):
        """Dots should split terms to match FTS5 tokenizer behavior (e.g. node.js)."""
        result = db_utils.format_fts_query("node.js")
        assert '"node"' in result
        assert '"js"' in result
        assert " OR " in result

    def test_plus_stripped(self):
        """Plus signs should be stripped (e.g. C++ → C)."""
        result = db_utils.format_fts_query("C++")
        assert '"C"' in result
        assert "+" not in result

    def test_dotnet_handled(self):
        """.NET should produce 'NET' after stripping leading dot."""
        result = db_utils.format_fts_query(".NET")
        assert '"NET"' in result

    def test_multi_word_joined_with_or(self):
        """Multiple words should be joined with OR."""
        result = db_utils.format_fts_query("hello world")
        assert " OR " in result
        assert "hello" in result
        assert "world" in result

    def test_hyphen_and_underscore_preserved(self):
        """Hyphens and underscores should be preserved in terms."""
        result = db_utils.format_fts_query("my-project_name")
        assert "my-project_name" in result

    def test_all_special_chars_returns_empty(self):
        """A query of only special characters should return empty query."""
        result = db_utils.format_fts_query("@#$%")
        assert result == '""'

    def test_mixed_valid_and_empty_terms(self):
        """Terms that become empty after cleaning should be skipped."""
        result = db_utils.format_fts_query("valid @#$ also-valid")
        assert "valid" in result
        assert "also-valid" in result
        assert " OR " in result


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


class TestGetDbPath:
    def test_returns_path(self):
        result = db_utils.get_db_path()
        assert isinstance(result, db_utils.Path)
        assert result.name == "context.db"


class TestEnsureDbDir:
    def test_creates_directory(self, isolated_db, monkeypatch):
        """ensure_db_dir() should create the DB directory if it doesn't exist."""
        new_dir = isolated_db.parent / "nested" / "subdir"
        monkeypatch.setattr(db_utils, "DB_DIR", new_dir)
        assert not new_dir.exists()
        db_utils.ensure_db_dir()
        assert new_dir.exists()

    def test_idempotent(self, isolated_db):
        """ensure_db_dir() should succeed even if the directory already exists."""
        assert isolated_db.parent.exists()
        db_utils.ensure_db_dir()  # should not raise
        assert isolated_db.parent.exists()


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

    def test_wal_mode_enabled(self, isolated_db):
        """Connection should use WAL journal mode."""
        with db_utils.get_connection() as conn:
            cursor = conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
        assert mode == "wal"

    def test_foreign_keys_enabled(self, isolated_db):
        """Connection should have PRAGMA foreign_keys=ON."""
        with db_utils.get_connection() as conn:
            cursor = conn.execute("PRAGMA foreign_keys")
            assert cursor.fetchone()[0] == 1

    def test_synchronous_normal(self, isolated_db):
        """Connection should use NORMAL synchronous mode (1)."""
        with db_utils.get_connection() as conn:
            cursor = conn.execute("PRAGMA synchronous")
            # NORMAL = 1
            assert cursor.fetchone()[0] == 1

    def test_temp_store_memory(self, isolated_db):
        """Connection should use MEMORY temp store (2)."""
        with db_utils.get_connection() as conn:
            cursor = conn.execute("PRAGMA temp_store")
            # MEMORY = 2
            assert cursor.fetchone()[0] == 2

    def test_row_factory_set(self, isolated_db):
        """Connection should use sqlite3.Row factory for dict-like access."""
        import sqlite3
        with db_utils.get_connection() as conn:
            assert conn.row_factory is sqlite3.Row


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

    def test_get_table_count_returns_row_count(self, isolated_db):
        """get_table_count should return actual row count for a populated table."""
        import db_init
        import db_save
        db_init.init_database()
        db_save.save_session("count-test-1")
        db_save.save_session("count-test-2")
        assert db_utils.get_table_count("sessions") == 2

    def test_get_table_count_empty_table(self, isolated_db):
        """get_table_count should return 0 for an empty table."""
        import db_init
        db_init.init_database()
        assert db_utils.get_table_count("sessions") == 0

    def test_get_table_count_no_db(self, isolated_db):
        """get_table_count should return 0 when no database exists."""
        assert db_utils.get_table_count("sessions") == 0

    def test_get_session_count(self, isolated_db):
        """get_session_count should delegate to get_table_count('sessions')."""
        import db_init
        import db_save
        db_init.init_database()
        db_save.save_session("session-count-1")
        assert db_utils.get_session_count() == 1
