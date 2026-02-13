"""Tests for search functionality."""

import db_init
import db_save
import db_search


def _seed_data(isolated_db):
    """Create test data for search tests."""
    db_init.init_database()
    db_save.save_full_session(
        session_id="search-session-1",
        project_path="/tmp/webapp",
        messages=[
            {"role": "user", "content": "How do I set up authentication with JWT?"},
            {"role": "assistant", "content": "Here is how to implement JWT auth..."},
        ],
        summary={
            "brief": "Implemented JWT authentication for the web application",
            "detailed": "Added login endpoint, token generation, and middleware",
            "technologies": ["python", "flask", "jwt"],
            "outcome": "success",
        },
        topics=["authentication", "jwt", "flask"],
    )
    db_save.save_full_session(
        session_id="search-session-2",
        project_path="/tmp/webapp",
        messages=[
            {"role": "user", "content": "Help me write database migrations"},
            {"role": "assistant", "content": "We can use alembic for migrations..."},
        ],
        summary={
            "brief": "Set up database migrations with alembic",
            "technologies": ["python", "sqlalchemy", "alembic"],
            "outcome": "success",
        },
        topics=["database", "migrations", "alembic"],
    )


class TestSearchTier1:
    def test_search_returns_results(self, isolated_db):
        _seed_data(isolated_db)
        results = db_search.search_tier1("authentication")
        assert len(results) >= 1
        assert results[0]["brief"] is not None

    def test_search_no_results(self, isolated_db):
        _seed_data(isolated_db)
        results = db_search.search_tier1("xyznonexistent")
        assert len(results) == 0

    def test_search_empty_db(self, isolated_db):
        results = db_search.search_tier1("anything")
        assert results == []

    def test_search_with_limit(self, isolated_db):
        _seed_data(isolated_db)
        results = db_search.search_tier1("python", limit=1)
        assert len(results) <= 1


class TestSearchTier2:
    def test_tier2_returns_details(self, isolated_db):
        _seed_data(isolated_db)
        tier1 = db_search.search_tier1("authentication")
        assert len(tier1) >= 1
        ids = [r["id"] for r in tier1]
        tier2 = db_search.search_tier2(ids)
        assert len(tier2) >= 1
        assert "messages" in tier2[0]
        assert "topics" in tier2[0]

    def test_tier2_empty_ids(self, isolated_db):
        results = db_search.search_tier2([])
        assert results == []


class TestFullSearch:
    def test_full_search(self, isolated_db):
        _seed_data(isolated_db)
        results = db_search.full_search("authentication")
        assert results["result_count"] >= 1
        assert results["query"] == "authentication"

    def test_full_search_detailed(self, isolated_db):
        _seed_data(isolated_db)
        results = db_search.full_search("authentication", detailed=True)
        assert results["result_count"] >= 1

    def test_full_search_no_results(self, isolated_db):
        _seed_data(isolated_db)
        results = db_search.full_search("xyznonexistent")
        assert results["result_count"] == 0


class TestFormatResultsMarkdown:
    def test_format_empty_results_no_db(self, isolated_db):
        results = {"query": "test", "result_count": 0, "sessions": []}
        md = db_search.format_results_markdown(results)
        assert "No sessions stored yet" in md

    def test_format_empty_results_with_db(self, isolated_db):
        db_init.init_database()
        results = {"query": "test", "result_count": 0, "sessions": []}
        md = db_search.format_results_markdown(results)
        assert "No matching sessions found" in md

    def test_format_with_results(self, isolated_db):
        _seed_data(isolated_db)
        results = db_search.full_search("authentication")
        md = db_search.format_results_markdown(results)
        assert "Context Memory Results" in md
        assert "authentication" in md.lower()


class TestSearchMessages:
    def test_search_messages(self, isolated_db):
        _seed_data(isolated_db)
        results = db_search.search_messages("JWT")
        assert len(results) >= 1

    def test_search_messages_no_results(self, isolated_db):
        _seed_data(isolated_db)
        results = db_search.search_messages("xyznonexistent")
        assert len(results) == 0
