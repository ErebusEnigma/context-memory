#!/usr/bin/env python3
"""
Integration tests for Bug #19 and Bug #16b fixes.
Tests the complete flow: init, save, search, force-reset, verify.
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

# Point to scripts directory
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), 'skills', 'context-memory', 'scripts')
sys.path.insert(0, SCRIPTS_DIR)

# Use a temporary database for testing
TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="ctx_mem_test_"))
TEST_DB_PATH = TEST_DB_DIR / "test_context.db"

# Patch DB_PATH and DB_DIR before importing modules
import db_utils
db_utils.DB_DIR = TEST_DB_DIR
db_utils.DB_PATH = TEST_DB_PATH

import db_init
import db_save
import db_search

passed = 0
failed = 0


def test(name):
    """Decorator for test functions."""
    def decorator(func):
        global passed, failed
        try:
            func()
            print(f"  PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {name}")
            print(f"        {e}")
            failed += 1
    return decorator


def clean_db():
    """Remove the test database if it exists."""
    if TEST_DB_PATH.exists():
        os.remove(TEST_DB_PATH)
    # Also remove WAL/SHM files
    for suffix in ['-wal', '-shm']:
        p = TEST_DB_PATH.parent / (TEST_DB_PATH.name + suffix)
        if p.exists():
            os.remove(p)


# ─── Test Group 1: Bug #19 - --force flag ───

print("\n=== Bug #19: --force flag resets database ===\n")

clean_db()


@test("Fresh init creates database")
def _():
    result = db_init.init_database(force=False)
    assert result is True, "init_database should return True on fresh init"
    assert TEST_DB_PATH.exists(), "Database file should exist"


@test("Second init without force returns False (already exists)")
def _():
    result = db_init.init_database(force=False)
    assert result is False, "init_database should return False when DB exists and force=False"


@test("Save test data before force reset")
def _():
    sid = db_save.save_session("test-session-1", project_path="/test/project")
    db_save.save_summary(sid, brief="Test summary for force reset")
    db_save.save_topics(sid, ["testing", "force-reset"])
    db_save.save_messages(sid, [
        {"role": "user", "content": "Hello test"},
        {"role": "assistant", "content": "Hi there"}
    ])
    db_save.save_code_snippet(sid, code="print('hello')", language="python",
                              description="test snippet", file_path="test.py")
    # Verify data exists
    stats = db_init.get_stats()
    assert stats['sessions'] == 1, f"Expected 1 session, got {stats['sessions']}"
    assert stats['messages'] == 2, f"Expected 2 messages, got {stats['messages']}"
    assert stats['summaries'] == 1, f"Expected 1 summary, got {stats['summaries']}"
    assert stats['topics'] == 2, f"Expected 2 topics, got {stats['topics']}"
    assert stats['code_snippets'] == 1, f"Expected 1 snippet, got {stats['code_snippets']}"


@test("Force init resets database (0 rows in all tables)")
def _():
    result = db_init.init_database(force=True)
    assert result is True, "init_database with force should return True"
    stats = db_init.get_stats()
    for table, count in stats.items():
        if table != 'db_size_bytes':
            assert count == 0, f"Table '{table}' should have 0 rows after force, got {count}"


@test("Database file still exists after force reset")
def _():
    assert TEST_DB_PATH.exists(), "Database file should exist after force reset"


# ─── Test Group 2: Bug #16b - code_snippets_fts ───

print("\n=== Bug #16b: Code snippets searchable via FTS ===\n")

clean_db()
db_init.init_database()


@test("verify_schema includes code_snippets_fts")
def _():
    result = db_init.verify_schema()
    assert result['valid'], f"Schema should be valid, missing: {result['missing']}"
    assert 'code_snippets_fts' in result['existing'], \
        f"code_snippets_fts not in tables: {result['existing']}"


@test("code_snippets_fts table exists in sqlite_master")
def _():
    with db_utils.get_connection(readonly=True) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE name='code_snippets_fts'"
        )
        row = cursor.fetchone()
        assert row is not None, "code_snippets_fts not found in sqlite_master"


@test("FTS triggers exist for code_snippets")
def _():
    expected_triggers = ['code_snippets_ai', 'code_snippets_ad', 'code_snippets_au']
    with db_utils.get_connection(readonly=True) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        )
        triggers = {row[0] for row in cursor.fetchall()}
    for t in expected_triggers:
        assert t in triggers, f"Trigger '{t}' not found. Existing: {triggers}"


@test("Save session with code snippet containing unique term")
def _():
    sid = db_save.save_session("snippet-search-test", project_path="/test/project")
    db_save.save_summary(sid, brief="Session about database optimization")
    db_save.save_topics(sid, ["database"])
    db_save.save_code_snippet(
        sid,
        code="def xylophoneUnicorn(): return 42",
        language="python",
        description="A unique function for testing FTS",
        file_path="unique_module.py"
    )


@test("Search for unique code term finds the session")
def _():
    results = db_search.search_tier1("xylophoneUnicorn")
    assert len(results) > 0, "Search for 'xylophoneUnicorn' should return results"
    assert results[0]['session_id'] == "snippet-search-test", \
        f"Expected session 'snippet-search-test', got '{results[0]['session_id']}'"


@test("Search for snippet description term finds the session")
def _():
    results = db_search.search_tier1("unique function testing FTS")
    assert len(results) > 0, "Search for description terms should return results"


@test("Search for snippet file_path finds the session")
def _():
    results = db_search.search_tier1("unique_module")
    assert len(results) > 0, "Search for file_path terms should return results"


@test("FTS auto-syncs on insert (check code_snippets_fts directly)")
def _():
    with db_utils.get_connection(readonly=True) as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM code_snippets_fts WHERE code_snippets_fts MATCH '\"xylophoneUnicorn\"'"
        )
        count = cursor.fetchone()[0]
        assert count > 0, "code_snippets_fts should contain the inserted snippet"


# ─── Test Group 3: Existing search still works ───

print("\n=== Existing search functionality ===\n")


@test("Summary search still works")
def _():
    results = db_search.search_tier1("database optimization")
    assert len(results) > 0, "Summary search should return results"


@test("Topic search still works")
def _():
    results = db_search.search_tier1("database")
    assert len(results) > 0, "Topic search should return results"


@test("full_search returns combined results")
def _():
    results = db_search.full_search("database", detailed=True)
    assert results['result_count'] > 0, "full_search should return results"
    sessions = results['sessions']
    assert len(sessions) > 0, "Should have session data"


@test("Multiple sessions with snippets - deduplication works")
def _():
    # Save another session with a snippet containing "database"
    sid2 = db_save.save_session("dedup-test", project_path="/test/project")
    db_save.save_summary(sid2, brief="Another database session")
    db_save.save_code_snippet(
        sid2,
        code="SELECT * FROM database_table",
        language="sql",
        description="database query example",
        file_path="queries.sql"
    )
    # Search should return both sessions without duplicates
    results = db_search.search_tier1("database")
    session_ids = [r['session_id'] for r in results]
    assert len(session_ids) == len(set(session_ids)), \
        f"Duplicate session IDs in results: {session_ids}"


@test("Tier 2 deep fetch includes code snippets")
def _():
    tier1 = db_search.search_tier1("xylophoneUnicorn")
    assert len(tier1) > 0
    db_ids = [r['id'] for r in tier1]
    tier2 = db_search.search_tier2(db_ids, include_snippets=True)
    assert len(tier2) > 0, "Tier 2 should return results"
    snippets = tier2[0].get('code_snippets', [])
    assert len(snippets) > 0, "Tier 2 should include code snippets"
    assert any("xylophoneUnicorn" in s['code'] for s in snippets), \
        "Snippet content should be present in tier 2 results"


@test("Markdown formatting includes code snippets")
def _():
    results = db_search.full_search("xylophoneUnicorn", detailed=True)
    md = db_search.format_results_markdown(results, detailed=True)
    assert "xylophoneUnicorn" in md, "Markdown output should contain snippet code"


# ─── Test Group 4: FTS trigger delete/update sync ───

print("\n=== FTS trigger sync (delete/update) ===\n")


@test("Deleting a code snippet removes it from FTS")
def _():
    # Insert a snippet
    sid = db_save.save_session("delete-test", project_path="/test/project")
    snippet_id = db_save.save_code_snippet(
        sid, code="def quantumZebra(): pass", language="python",
        description="delete test snippet"
    )
    # Verify it's in FTS
    with db_utils.get_connection() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM code_snippets_fts WHERE code_snippets_fts MATCH '\"quantumZebra\"'"
        )
        assert cursor.fetchone()[0] > 0, "Snippet should be in FTS before delete"

        # Delete the snippet
        conn.execute("DELETE FROM code_snippets WHERE id = ?", (snippet_id,))
        conn.commit()

        # Verify it's gone from FTS
        cursor = conn.execute(
            "SELECT COUNT(*) FROM code_snippets_fts WHERE code_snippets_fts MATCH '\"quantumZebra\"'"
        )
        assert cursor.fetchone()[0] == 0, "Snippet should be removed from FTS after delete"


@test("Updating a code snippet syncs FTS")
def _():
    sid = db_save.save_session("update-test", project_path="/test/project")
    snippet_id = db_save.save_code_snippet(
        sid, code="def magneticPenguin(): pass", language="python",
        description="update test snippet"
    )
    with db_utils.get_connection() as conn:
        # Verify original term is in FTS
        cursor = conn.execute(
            "SELECT COUNT(*) FROM code_snippets_fts WHERE code_snippets_fts MATCH '\"magneticPenguin\"'"
        )
        assert cursor.fetchone()[0] > 0, "Original term should be in FTS"

        # Update the snippet
        conn.execute(
            "UPDATE code_snippets SET code = 'def electricFlamingo(): pass' WHERE id = ?",
            (snippet_id,)
        )
        conn.commit()

        # Old term should be gone
        cursor = conn.execute(
            "SELECT COUNT(*) FROM code_snippets_fts WHERE code_snippets_fts MATCH '\"magneticPenguin\"'"
        )
        assert cursor.fetchone()[0] == 0, "Old term should be removed from FTS after update"

        # New term should exist
        cursor = conn.execute(
            "SELECT COUNT(*) FROM code_snippets_fts WHERE code_snippets_fts MATCH '\"electricFlamingo\"'"
        )
        assert cursor.fetchone()[0] > 0, "New term should be in FTS after update"


# ─── Test Group 5: Force reset with FTS tables ───

print("\n=== Force reset with FTS tables ===\n")


@test("Force init after adding snippets resets everything including FTS")
def _():
    # There should be data from previous tests
    stats_before = db_init.get_stats()
    assert stats_before['code_snippets'] > 0, "Should have snippets before force"

    db_init.init_database(force=True)

    stats_after = db_init.get_stats()
    for table, count in stats_after.items():
        if table != 'db_size_bytes':
            assert count == 0, f"Table '{table}' should be empty after force, got {count}"

    # FTS should also be empty
    with db_utils.get_connection(readonly=True) as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM code_snippets_fts WHERE code_snippets_fts MATCH '\"xylophoneUnicorn\"'"
        )
        assert cursor.fetchone()[0] == 0, "FTS should be empty after force reset"

    # Schema should still be valid
    schema = db_init.verify_schema()
    assert schema['valid'], f"Schema should be valid after force reset, missing: {schema['missing']}"


# ─── Cleanup ───

print()
clean_db()
# Remove temp directory
try:
    TEST_DB_DIR.rmdir()
except OSError:
    pass

# ─── Summary ───

total = passed + failed
print(f"{'='*50}")
print(f"Results: {passed}/{total} passed, {failed} failed")
print(f"{'='*50}")

sys.exit(0 if failed == 0 else 1)
