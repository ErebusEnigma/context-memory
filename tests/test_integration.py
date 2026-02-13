"""Integration tests for context-memory plugin."""

import json
import os
import subprocess
import sys

import db_init
import db_prune
import db_save
import db_search
import db_utils

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills", "context-memory", "scripts"
)


class TestSaveSearchFlow:
    """End-to-end: save sessions then search and verify results."""

    def test_save_then_search(self, isolated_db):
        db_init.init_database()
        db_save.save_full_session(
            session_id="integration-1",
            project_path="/tmp/myproject",
            summary={"brief": "Implemented user authentication with JWT tokens"},
            topics=["authentication", "jwt", "security"],
            messages=[
                {"role": "user", "content": "How do I implement JWT auth?"},
                {"role": "assistant", "content": "Here's how to implement JWT authentication..."},
            ],
        )
        results = db_search.search_tier1("authentication")
        assert len(results) >= 1
        assert any("authentication" in r.get("brief", "").lower() or
                    "authentication" in [t.lower() for t in r.get("topics", [])]
                    for r in results)

    def test_detailed_search_returns_messages(self, isolated_db):
        db_init.init_database()
        db_save.save_full_session(
            session_id="integration-2",
            project_path="/tmp/myproject",
            summary={"brief": "Database migration strategy"},
            messages=[
                {"role": "user", "content": "What migration tool should we use?"},
                {"role": "assistant", "content": "I recommend using Alembic for migrations."},
            ],
        )
        results = db_search.full_search("migration", detailed=True)
        assert results["result_count"] >= 1
        session = results["sessions"][0]
        assert "messages" in session
        assert len(session["messages"]) == 2

    def test_project_scoped_isolation(self, isolated_db):
        db_init.init_database()
        db_save.save_full_session(
            session_id="proj-a-1",
            project_path="/tmp/project-a",
            summary={"brief": "Configured webpack bundler"},
            topics=["webpack"],
        )
        db_save.save_full_session(
            session_id="proj-b-1",
            project_path="/tmp/project-b",
            summary={"brief": "Configured webpack for project B"},
            topics=["webpack"],
        )
        results_a = db_search.search_tier1("webpack", project_path="/tmp/project-a")
        results_b = db_search.search_tier1("webpack", project_path="/tmp/project-b")
        assert len(results_a) == 1
        assert results_a[0]["session_id"] == "proj-a-1"
        assert len(results_b) == 1
        assert results_b[0]["session_id"] == "proj-b-1"

    def test_full_pipeline_to_markdown(self, isolated_db):
        db_init.init_database()
        db_save.save_full_session(
            session_id="markdown-1",
            project_path="/tmp/proj",
            summary={
                "brief": "Built REST API endpoints",
                "detailed": "Created CRUD endpoints for users and posts",
                "technologies": ["python", "fastapi"],
                "outcome": "success",
            },
            topics=["api", "rest"],
        )
        results = db_search.full_search("REST API", detailed=True)
        markdown = db_search.format_results_markdown(results, detailed=True)
        assert "REST API" in markdown or "rest" in markdown.lower()
        assert "Built REST API endpoints" in markdown
        assert results["result_count"] >= 1


class TestCLIEntryPoints:
    """Test CLI entry points via subprocess with CONTEXT_MEMORY_DB_PATH."""

    def test_db_init_cli(self, isolated_db):
        env = {**os.environ, "CONTEXT_MEMORY_DB_PATH": str(isolated_db)}
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "db_init.py")],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0
        assert "initialized" in result.stdout.lower() or "exists" in result.stdout.lower()

    def test_db_save_cli(self, isolated_db):
        env = {**os.environ, "CONTEXT_MEMORY_DB_PATH": str(isolated_db)}
        # Init first
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "db_init.py")],
            capture_output=True, text=True, env=env,
        )
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "db_save.py"),
             "--session-id", "cli-test-1",
             "--project-path", "/tmp/cli-project",
             "--brief", "CLI test session",
             "--topics", "cli,testing"],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "session_id" in output

    def test_db_save_auto_mode(self, isolated_db):
        env = {**os.environ, "CONTEXT_MEMORY_DB_PATH": str(isolated_db)}
        # Init and save a rich session first
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "db_init.py")],
            capture_output=True, text=True, env=env,
        )
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "db_save.py"),
             "--session-id", "rich-1",
             "--project-path", "/tmp/cli-project",
             "--brief", "Rich session with details"],
            capture_output=True, text=True, env=env,
        )
        # Auto-save should be skipped
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "db_save.py"),
             "--auto",
             "--session-id", "auto-1",
             "--project-path", "/tmp/cli-project",
             "--brief", "Auto-saved session: cli-project"],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output.get("skipped") is True

    def test_db_search_cli(self, isolated_db):
        env = {**os.environ, "CONTEXT_MEMORY_DB_PATH": str(isolated_db)}
        # Init and save
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "db_init.py")],
            capture_output=True, text=True, env=env,
        )
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "db_save.py"),
             "--session-id", "search-1",
             "--brief", "Debugging memory leaks",
             "--topics", "debugging,memory"],
            capture_output=True, text=True, env=env,
        )
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "db_search.py"),
             "memory", "--format", "json"],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["result_count"] >= 1

    def test_db_prune_dry_run_cli(self, isolated_db):
        env = {**os.environ, "CONTEXT_MEMORY_DB_PATH": str(isolated_db)}
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "db_init.py")],
            capture_output=True, text=True, env=env,
        )
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "db_save.py"),
             "--session-id", "prune-1", "--brief", "Session to prune"],
            capture_output=True, text=True, env=env,
        )
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "db_prune.py"),
             "--max-sessions", "5", "--dry-run"],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["pruned"] == 0  # Only 1 session, keeping 5


class TestDeduplicationIntegration:
    def test_rich_session_prevents_auto_save(self, isolated_db):
        db_init.init_database()
        db_save.save_full_session(
            session_id="rich-1",
            project_path="/tmp/dedup-proj",
            summary={"brief": "Detailed implementation of feature X"},
            topics=["feature-x"],
        )
        assert db_save.should_skip_auto_save("/tmp/dedup-proj") is True

    def test_auto_save_proceeds_with_only_auto_saves(self, isolated_db):
        db_init.init_database()
        db_save.save_full_session(
            session_id="auto-1",
            project_path="/tmp/dedup-proj",
            summary={"brief": "Auto-saved session"},
        )
        assert db_save.should_skip_auto_save("/tmp/dedup-proj") is False


class TestPruningIntegration:
    def test_prune_then_search_finds_only_remaining(self, isolated_db):
        db_init.init_database()
        db_save.save_full_session(
            session_id="keep-1",
            project_path="/tmp/proj",
            summary={"brief": "Important feature implementation"},
            topics=["important"],
        )
        db_save.save_full_session(
            session_id="keep-2",
            project_path="/tmp/proj",
            summary={"brief": "Another critical change"},
            topics=["critical"],
        )
        # Prune to keep only 2
        db_prune.prune_sessions(max_sessions=2)
        results = db_search.search_tier1("important")
        assert len(results) >= 1
        results = db_search.search_tier1("critical")
        assert len(results) >= 1

    def test_fts_cleaned_after_prune_integration(self, isolated_db):
        db_init.init_database()
        # Create sessions with unique keywords
        db_save.save_full_session(
            session_id="unique-alpha",
            project_path="/tmp/proj",
            summary={"brief": "Implemented alpha algorithm"},
            topics=["alpha"],
        )
        db_save.save_full_session(
            session_id="unique-beta",
            project_path="/tmp/proj",
            summary={"brief": "Implemented beta algorithm"},
            topics=["beta"],
        )
        db_save.save_full_session(
            session_id="unique-gamma",
            project_path="/tmp/proj",
            summary={"brief": "Implemented gamma algorithm"},
            topics=["gamma"],
        )
        # Keep only newest (gamma)
        db_prune.prune_sessions(max_sessions=1)
        # Alpha and beta should not be findable
        results_alpha = db_search.search_tier1("alpha")
        results_gamma = db_search.search_tier1("gamma")
        assert len(results_alpha) == 0
        assert len(results_gamma) >= 1


class TestErrorHandling:
    def test_search_nonexistent_db(self, isolated_db):
        """Search on nonexistent DB returns empty results gracefully."""
        results = db_search.full_search("anything")
        assert results["result_count"] == 0
        assert results["sessions"] == []

    def test_unicode_content(self, isolated_db):
        db_init.init_database()
        db_save.save_full_session(
            session_id="unicode-1",
            project_path="/tmp/proj",
            summary={"brief": "Implemented internationalization with \u65e5\u672c\u8a9e and \u4e2d\u6587 support"},
            topics=["\u56fd\u969b\u5316", "i18n"],
            messages=[
                {"role": "user", "content": "How do I add \u65e5\u672c\u8a9e support?"},
                {"role": "assistant", "content": "Here's how to handle \u65e5\u672c\u8a9e characters..."},
            ],
        )
        results = db_search.search_tier1("internationalization")
        assert len(results) >= 1

    def test_long_content(self, isolated_db):
        db_init.init_database()
        long_text = "x" * 10000
        db_save.save_full_session(
            session_id="long-1",
            project_path="/tmp/proj",
            summary={"brief": "Session with long content", "detailed": long_text},
            messages=[{"role": "user", "content": long_text}],
        )
        results = db_search.search_tier1("long content")
        assert len(results) >= 1

    def test_legacy_db_migration_on_save(self, isolated_db):
        """Saving to a legacy DB (no schema_version) triggers auto-migration."""
        # Create legacy DB
        with db_utils.get_connection() as conn:
            legacy_sql = db_init.SCHEMA_SQL.split("-- Schema versioning")[0]
            conn.executescript(legacy_sql)
            conn.commit()

        # Save should trigger migration
        db_save.save_full_session(
            session_id="legacy-1",
            project_path="/tmp/proj",
            summary={"brief": "Post-migration session"},
        )

        # Verify migration happened
        with db_utils.get_connection(readonly=True) as conn:
            version = db_init.get_schema_version(conn)
        assert version == db_init.CURRENT_SCHEMA_VERSION

        # Verify the session was saved
        results = db_search.search_tier1("migration")
        assert len(results) >= 1
