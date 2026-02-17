"""Tests for search functionality."""

import db_init
import db_save
import db_search
import db_utils


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


def _seed_data_with_snippets(isolated_db):
    """Create test data including code snippets for search tests."""
    _seed_data(isolated_db)
    db_save.save_full_session(
        session_id="search-session-3",
        project_path="/tmp/webapp",
        messages=[
            {"role": "user", "content": "Write a React component for login"},
            {"role": "assistant", "content": "Here is the LoginForm component..."},
        ],
        summary={
            "brief": "Created React login form with validation",
            "detailed": "Built a LoginForm component with email/password fields and client-side validation",
            "key_decisions": ["Use controlled components", "Validate on blur"],
            "problems_solved": ["Form validation UX"],
            "technologies": ["react", "typescript"],
            "outcome": "success",
        },
        topics=["react", "frontend", "forms"],
        code_snippets=[
            {
                "code": "function LoginForm() {\n  return <form>...</form>;\n}",
                "language": "tsx",
                "description": "LoginForm React component",
                "file_path": "src/components/LoginForm.tsx",
            }
        ],
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


class TestSearchTier1CodeSnippets:
    def test_finds_session_via_code_snippet(self, isolated_db):
        """Tier 1 should find sessions matching code snippet content."""
        _seed_data_with_snippets(isolated_db)
        results = db_search.search_tier1("LoginForm")
        assert len(results) >= 1
        # Should find the session with the React component
        session_ids = [r["session_id"] for r in results]
        assert "search-session-3" in session_ids

    def test_finds_session_via_snippet_description(self, isolated_db):
        """Tier 1 should find sessions matching code snippet description."""
        _seed_data_with_snippets(isolated_db)
        results = db_search.search_tier1("React component")
        assert len(results) >= 1

    def test_finds_session_via_snippet_file_path(self, isolated_db):
        """Tier 1 should find sessions matching code snippet file path terms."""
        _seed_data_with_snippets(isolated_db)
        # FTS5 tokenizes on punctuation, so search for a path component
        results = db_search.search_tier1("components")
        assert len(results) >= 1


class TestSearchTier1Ranking:
    def test_topic_tag_does_not_outrank_strong_summary(self, isolated_db):
        """A topic-only match must not outrank a summary match.

        Regression test for cross-table BM25 score contamination: topic FTS scores
        lived on a different scale than summary scores, so merging and sorting by
        raw BM25 let topic-only matches outrank strong summary matches.
        """
        db_init.init_database()

        # Session A: matches "authentication" in summary
        sid_a = db_save.save_session("sess-strong-summary", "/tmp/p")
        db_save.save_summary(sid_a, brief="Implemented authentication system",
                             detailed="Built complete authentication with JWT tokens and refresh rotation")
        db_save.save_topics(sid_a, ["backend", "security"])

        # Session B: NO summary match for authentication, only a topic tag
        sid_b = db_save.save_session("sess-topic-only", "/tmp/p")
        db_save.save_summary(sid_b, brief="Caching improvements",
                             detailed="Improved cache hit ratios and eviction policies")
        db_save.save_topics(sid_b, ["caching", "authentication"])

        results = db_search.search_tier1("authentication")
        result_ids = [r["session_id"] for r in results]

        assert "sess-strong-summary" in result_ids, "Summary match should appear in results"
        assert "sess-topic-only" in result_ids, "Topic-only match should appear in results"
        assert result_ids.index("sess-strong-summary") < result_ids.index("sess-topic-only"), \
            "Summary match should rank above topic-only match"

    def test_multi_source_match_ranks_higher_than_single(self, isolated_db):
        """Sessions matching in summary + topic + snippet should rank above summary-only
        matches when summary scores are similar."""
        db_init.init_database()

        # Session A: matches in summary + topic + snippet
        sid_a = db_save.save_session("sess-multi-source", "/tmp/p")
        db_save.save_summary(sid_a, brief="Fixed authentication bug in login flow",
                             detailed="Resolved authentication token expiration issue")
        db_save.save_topics(sid_a, ["authentication", "bugfix"])
        db_save.save_code_snippet(sid_a, code="verify_auth_token()", language="python",
                                  description="Authentication token verification")

        # Session B: matches only in summary with similar text
        sid_b = db_save.save_session("sess-summary-only", "/tmp/p")
        db_save.save_summary(sid_b, brief="Refactored authentication middleware layer",
                             detailed="Cleaned up authentication code in middleware")
        db_save.save_topics(sid_b, ["refactoring", "cleanup"])

        results = db_search.search_tier1("authentication")
        result_ids = [r["session_id"] for r in results]

        assert "sess-multi-source" in result_ids
        assert "sess-summary-only" in result_ids
        assert result_ids.index("sess-multi-source") < result_ids.index("sess-summary-only"), \
            "3-source match should rank above 1-source match with similar summary score"


class TestSearchTier1ProjectFilter:
    def test_filters_by_project_path(self, isolated_db):
        """Tier 1 should filter results to the specified project."""
        db_init.init_database()
        db_save.save_full_session(
            session_id="proj-a-1",
            project_path="/tmp/project-a",
            summary={"brief": "Working on authentication"},
            topics=["auth"],
        )
        db_save.save_full_session(
            session_id="proj-b-1",
            project_path="/tmp/project-b",
            summary={"brief": "Working on authentication in another project"},
            topics=["auth"],
        )

        results = db_search.search_tier1("authentication", project_path="/tmp/project-a")
        session_ids = [r["session_id"] for r in results]
        assert "proj-a-1" in session_ids
        assert "proj-b-1" not in session_ids


class TestSearchTier2Flags:
    def test_include_messages_false(self, isolated_db):
        """Tier 2 with include_messages=False should omit messages key."""
        _seed_data(isolated_db)
        tier1 = db_search.search_tier1("authentication")
        ids = [r["id"] for r in tier1]
        tier2 = db_search.search_tier2(ids, include_messages=False)
        assert len(tier2) >= 1
        assert "messages" not in tier2[0]
        assert "topics" in tier2[0]
        assert "code_snippets" in tier2[0]

    def test_include_snippets_false(self, isolated_db):
        """Tier 2 with include_snippets=False should omit code_snippets key."""
        _seed_data(isolated_db)
        tier1 = db_search.search_tier1("authentication")
        ids = [r["id"] for r in tier1]
        tier2 = db_search.search_tier2(ids, include_snippets=False)
        assert len(tier2) >= 1
        assert "code_snippets" not in tier2[0]
        assert "messages" in tier2[0]
        assert "topics" in tier2[0]

    def test_both_flags_false(self, isolated_db):
        """Tier 2 with both flags False should still return session + summary data."""
        _seed_data(isolated_db)
        tier1 = db_search.search_tier1("authentication")
        ids = [r["id"] for r in tier1]
        tier2 = db_search.search_tier2(ids, include_messages=False, include_snippets=False)
        assert len(tier2) >= 1
        assert "messages" not in tier2[0]
        assert "code_snippets" not in tier2[0]
        assert "brief" in tier2[0]
        assert "topics" in tier2[0]


class TestSearchTier2MalformedJson:
    def test_malformed_key_decisions(self, isolated_db):
        """Tier 2 should handle malformed JSON in key_decisions gracefully."""
        db_init.init_database()
        session_db_id = db_save.save_session("malformed-session", "/tmp/test")
        # Insert a summary with malformed JSON directly
        with db_utils.get_connection() as conn:
            conn.execute("""
                INSERT INTO summaries (session_id, brief, key_decisions, problems_solved, technologies)
                VALUES (?, ?, ?, ?, ?)
            """, (session_db_id, "Test brief", "not valid json [", "also {bad", '["valid"]'))
            conn.commit()

        tier2 = db_search.search_tier2([session_db_id])
        assert len(tier2) == 1
        # Malformed fields should remain as strings (not parsed)
        assert tier2[0]["key_decisions"] == "not valid json ["
        assert tier2[0]["problems_solved"] == "also {bad"
        # Valid JSON should be parsed
        assert tier2[0]["technologies"] == ["valid"]

    def test_nonexistent_session_ids(self, isolated_db):
        """Tier 2 with IDs that don't exist should return empty list."""
        db_init.init_database()
        result = db_search.search_tier2([9999, 8888])
        assert result == []


class TestFormatResultsMarkdownDetailed:
    def test_detailed_with_messages_and_snippets(self, isolated_db):
        """format_results_markdown(detailed=True) should include expandable content."""
        _seed_data_with_snippets(isolated_db)
        results = db_search.full_search("React login", detailed=True)
        md = db_search.format_results_markdown(results, detailed=True)

        assert "<details>" in md
        assert "<summary>Full Context</summary>" in md
        assert "### Detailed Summary" in md
        assert "### Key Messages" in md
        assert "### Code Snippets" in md
        assert "```tsx" in md
        assert "LoginForm" in md
        assert "</details>" in md

    def test_detailed_with_decisions(self, isolated_db):
        """Detailed mode should render key decisions."""
        _seed_data_with_snippets(isolated_db)
        results = db_search.full_search("React login", detailed=True)
        md = db_search.format_results_markdown(results, detailed=True)

        assert "**Decisions**:" in md
        assert "- Use controlled components" in md

    def test_detailed_without_content_no_details_block(self, isolated_db):
        """Detailed mode with no detailed/messages/snippets should not add details block."""
        db_init.init_database()
        db_save.save_full_session(
            session_id="bare-session",
            project_path="/tmp/bare",
            summary={"brief": "Bare session with no details"},
        )
        results = db_search.full_search("Bare session", detailed=True)
        md = db_search.format_results_markdown(results, detailed=True)

        assert "Bare session" in md
        assert "<details>" not in md

    def test_technologies_as_json_string(self, isolated_db):
        """Technologies stored as a JSON string should be parsed for display."""
        db_init.init_database()
        session_db_id = db_save.save_session("tech-session", "/tmp/test")
        with db_utils.get_connection() as conn:
            conn.execute("""
                INSERT INTO summaries (session_id, brief, technologies)
                VALUES (?, ?, ?)
            """, (session_db_id, "Tech test", '["python", "rust"]'))
            conn.commit()

        results = db_search.full_search("Tech test")
        md = db_search.format_results_markdown(results)

        assert "python" in md
        assert "rust" in md

    def test_date_formatting(self, isolated_db):
        """Dates with T separator should be displayed as date only."""
        _seed_data(isolated_db)
        results = db_search.full_search("authentication")
        md = db_search.format_results_markdown(results)

        # Should not contain the time portion (T...) in the header
        for line in md.split("\n"):
            if line.startswith("## "):
                assert "T" not in line.split("|")[0]

    def test_project_name_from_path(self, isolated_db):
        """Project path should be shortened to just the directory name."""
        _seed_data(isolated_db)
        results = db_search.full_search("authentication")
        md = db_search.format_results_markdown(results)

        assert "webapp" in md
        # Full path should not appear in headers
        for line in md.split("\n"):
            if line.startswith("## "):
                assert "/tmp/webapp" not in line
