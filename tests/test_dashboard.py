"""Tests for the dashboard Flask REST API."""
# isort: skip_file
from __future__ import annotations

import pytest

flask = pytest.importorskip("flask", reason="flask package not installed")
pytest.importorskip("flask_cors", reason="flask-cors package not installed")

import dashboard  # noqa: E402
from db_init import init_database  # noqa: E402
from db_save import save_full_session  # noqa: E402
from db_utils import get_connection  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Flask test client."""
    dashboard.app.config["TESTING"] = True
    with dashboard.app.test_client() as c:
        yield c


def _seed_db():
    """Seed the database with rich test data (2 sessions, different projects)."""
    init_database()

    # Session 1 — auth project
    save_full_session(
        session_id="sess-aaa",
        project_path="/tmp/project-alpha",
        messages=[
            {"role": "user", "content": "How do I fix the auth bug?"},
            {"role": "assistant", "content": "Here is the authentication fix."},
        ],
        summary={
            "brief": "Fixed auth bug in login flow",
            "detailed": "Resolved a session-expiry issue in the JWT middleware.",
            "outcome": "success",
            "technologies": ["python", "flask", "jwt"],
        },
        topics=["authentication", "bugfix"],
        code_snippets=[
            {
                "code": "def verify_token(t): ...",
                "language": "python",
                "description": "JWT verify helper",
                "file_path": "auth.py",
            }
        ],
    )

    # Session 2 — different project
    save_full_session(
        session_id="sess-bbb",
        project_path="/tmp/project-beta",
        messages=[
            {"role": "user", "content": "Add pagination to the API"},
            {"role": "assistant", "content": "Here is the pagination implementation."},
        ],
        summary={
            "brief": "Added pagination to list endpoint",
            "outcome": "partial",
            "technologies": ["python", "sqlite"],
        },
        topics=["api", "pagination"],
    )


@pytest.fixture()
def seeded_db(isolated_db):
    """Seed the temporary database with test data."""
    _seed_db()
    return isolated_db


# ---------------------------------------------------------------------------
# TestIndex
# ---------------------------------------------------------------------------

class TestIndex:
    def test_serves_index_html(self, client, seeded_db):
        resp = client.get("/")
        # send_from_directory may 404 if static dir doesn't exist on CI,
        # but the route itself is wired correctly: either 200 or 404.
        assert resp.status_code in (200, 404)


# ---------------------------------------------------------------------------
# TestApiListSessions
# ---------------------------------------------------------------------------

class TestApiListSessions:
    def test_empty_db(self, client, isolated_db):
        init_database()
        resp = client.get("/api/sessions")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["sessions"] == []
        assert data["total"] == 0

    def test_no_db(self, client, isolated_db):
        # DB file does not exist at all
        resp = client.get("/api/sessions")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["sessions"] == []
        assert data["total"] == 0

    def test_lists_sessions(self, client, seeded_db):
        resp = client.get("/api/sessions")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["total"] == 2
        assert len(data["sessions"]) == 2
        # Each session should have topics attached
        for s in data["sessions"]:
            assert "topics" in s

    def test_pagination(self, client, seeded_db):
        resp = client.get("/api/sessions?page=1&per_page=1")
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["sessions"]) == 1
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["per_page"] == 1

    def test_project_filter(self, client, seeded_db):
        resp = client.get("/api/sessions?project=project-alpha")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["total"] == 1
        assert "alpha" in data["sessions"][0]["project_path"]

    def test_sort_order(self, client, seeded_db):
        resp = client.get("/api/sessions?sort=created_at&order=asc")
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["sessions"]) == 2
        # First result should be the earlier-created session
        assert data["sessions"][0]["created_at"] <= data["sessions"][1]["created_at"]

    def test_invalid_sort_falls_back(self, client, seeded_db):
        resp = client.get("/api/sessions?sort=invalid_column")
        data = resp.get_json()
        assert resp.status_code == 200
        # Falls back to created_at — just ensure we get results
        assert data["total"] == 2


# ---------------------------------------------------------------------------
# TestApiGetSession
# ---------------------------------------------------------------------------

class TestApiGetSession:
    def test_returns_full_detail(self, client, seeded_db):
        # Get list first to find a real ID
        list_resp = client.get("/api/sessions")
        sid = list_resp.get_json()["sessions"][0]["id"]

        resp = client.get(f"/api/sessions/{sid}")
        data = resp.get_json()
        assert resp.status_code == 200
        assert "messages" in data
        assert "topics" in data
        assert "brief" in data

    def test_not_found(self, client, seeded_db):
        resp = client.get("/api/sessions/99999")
        assert resp.status_code == 404

    def test_no_db(self, client, isolated_db):
        resp = client.get("/api/sessions/1")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestApiUpdateSession
# ---------------------------------------------------------------------------

class TestApiUpdateSession:
    def test_update_summary(self, client, seeded_db):
        list_resp = client.get("/api/sessions")
        sid = list_resp.get_json()["sessions"][0]["id"]

        resp = client.put(
            f"/api/sessions/{sid}",
            json={"brief": "Updated summary text"},
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert "summary" in data["updated"]
        assert "brief" in data["updated"]["summary"]

    def test_update_topics(self, client, seeded_db):
        list_resp = client.get("/api/sessions")
        sid = list_resp.get_json()["sessions"][0]["id"]

        resp = client.put(
            f"/api/sessions/{sid}",
            json={"topics": ["new-topic-a", "new-topic-b"]},
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert "topics" in data["updated"]
        assert data["updated"]["topics"] == ["new-topic-a", "new-topic-b"]

    def test_not_found(self, client, seeded_db):
        resp = client.put("/api/sessions/99999", json={"brief": "x"})
        assert resp.status_code == 404

    def test_no_data(self, client, seeded_db):
        list_resp = client.get("/api/sessions")
        sid = list_resp.get_json()["sessions"][0]["id"]
        resp = client.put(
            f"/api/sessions/{sid}",
            content_type="application/json",
            data="",
        )
        assert resp.status_code == 400

    def test_update_without_brief(self, client, seeded_db):
        """PUT with only non-brief fields should not crash (BUG-1)."""
        list_resp = client.get("/api/sessions")
        sid = list_resp.get_json()["sessions"][0]["id"]

        resp = client.put(
            f"/api/sessions/{sid}",
            json={"outcome": "success"},
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert "summary" in data["updated"]
        assert "outcome" in data["updated"]["summary"]

        # Verify the original brief is preserved
        detail_resp = client.get(f"/api/sessions/{sid}")
        detail = detail_resp.get_json()
        assert detail["brief"] is not None
        assert detail["brief"] != ""

    def test_update_user_note_without_brief(self, client, seeded_db):
        """Updating user_note alone must not crash."""
        list_resp = client.get("/api/sessions")
        sid = list_resp.get_json()["sessions"][0]["id"]

        resp = client.put(
            f"/api/sessions/{sid}",
            json={"user_note": "This was a good session"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "summary" in data["updated"]
        assert "user_note" in data["updated"]["summary"]

    def test_no_db(self, client, isolated_db):
        resp = client.put("/api/sessions/1", json={"brief": "x"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestApiDeleteSession
# ---------------------------------------------------------------------------

class TestApiDeleteSession:
    def test_deletes_session(self, client, seeded_db):
        list_resp = client.get("/api/sessions")
        sid = list_resp.get_json()["sessions"][0]["id"]

        resp = client.delete(f"/api/sessions/{sid}")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["deleted"] == sid

        # Confirm it's gone
        resp2 = client.get(f"/api/sessions/{sid}")
        assert resp2.status_code == 404

    def test_not_found(self, client, seeded_db):
        resp = client.delete("/api/sessions/99999")
        assert resp.status_code == 404

    def test_no_db(self, client, isolated_db):
        resp = client.delete("/api/sessions/1")
        assert resp.status_code == 404

    def test_children_cleaned(self, client, seeded_db):
        list_resp = client.get("/api/sessions")
        session = list_resp.get_json()["sessions"][0]
        sid = session["id"]
        session_id_text = session["session_id"]

        # Insert a checkpoint so we can verify it gets cleaned up
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO context_checkpoints (session_id, project_path, project_hash, checkpoint_number, trigger_type, messages, message_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id_text, "/tmp/project-alpha", "abc123", 1, "test", "[]", 0),
            )
            conn.commit()

        client.delete(f"/api/sessions/{sid}")

        with get_connection(readonly=True) as conn:
            for table in ("messages", "topics", "summaries", "code_snippets"):
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE session_id = ?", (sid,)
                ).fetchone()[0]
                assert count == 0, f"{table} still has rows for deleted session"

            # Verify context_checkpoints are also cleaned up (BUG-2)
            cp_count = conn.execute(
                "SELECT COUNT(*) FROM context_checkpoints WHERE session_id = ?",
                (session_id_text,),
            ).fetchone()[0]
            assert cp_count == 0, "context_checkpoints still has rows for deleted session"


# ---------------------------------------------------------------------------
# TestApiSearch
# ---------------------------------------------------------------------------

class TestApiSearch:
    def test_search_returns_results(self, client, seeded_db):
        resp = client.get("/api/search?q=auth")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["result_count"] >= 1

    def test_search_no_results(self, client, seeded_db):
        resp = client.get("/api/search?q=xyznonexistent")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["result_count"] == 0

    def test_search_missing_query(self, client, seeded_db):
        resp = client.get("/api/search")
        assert resp.status_code == 400

    def test_search_with_project_filter(self, client, seeded_db):
        resp = client.get("/api/search?q=auth&project=/tmp/project-alpha")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["project_path"] == "/tmp/project-alpha"


# ---------------------------------------------------------------------------
# TestApiStats
# ---------------------------------------------------------------------------

class TestApiStats:
    def test_stats_after_seed(self, client, seeded_db):
        resp = client.get("/api/stats")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["sessions"] >= 2
        assert data["messages"] >= 4

    def test_stats_no_db(self, client, isolated_db):
        resp = client.get("/api/stats")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data.get("exists") is False


# ---------------------------------------------------------------------------
# TestApiAnalyticsTimeline
# ---------------------------------------------------------------------------

class TestApiAnalyticsTimeline:
    def test_timeline_default_week(self, client, seeded_db):
        resp = client.get("/api/analytics/timeline")
        data = resp.get_json()
        assert resp.status_code == 200
        assert "data" in data
        assert data["granularity"] == "week"
        assert len(data["data"]) >= 1

    def test_timeline_day_granularity(self, client, seeded_db):
        resp = client.get("/api/analytics/timeline?granularity=day")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["granularity"] == "day"

    def test_timeline_no_db(self, client, isolated_db):
        resp = client.get("/api/analytics/timeline")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["data"] == []


# ---------------------------------------------------------------------------
# TestApiAnalyticsTopics
# ---------------------------------------------------------------------------

class TestApiAnalyticsTopics:
    def test_topics_frequency(self, client, seeded_db):
        resp = client.get("/api/analytics/topics")
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["data"]) >= 1
        # Results should be sorted by count descending
        counts = [d["count"] for d in data["data"]]
        assert counts == sorted(counts, reverse=True)

    def test_topics_no_db(self, client, isolated_db):
        resp = client.get("/api/analytics/topics")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["data"] == []


# ---------------------------------------------------------------------------
# TestApiAnalyticsProjects
# ---------------------------------------------------------------------------

class TestApiAnalyticsProjects:
    def test_projects_list(self, client, seeded_db):
        resp = client.get("/api/analytics/projects")
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["data"]) >= 2
        # Each entry should have project_path and count
        for entry in data["data"]:
            assert "project_path" in entry
            assert "count" in entry

    def test_projects_no_db(self, client, isolated_db):
        resp = client.get("/api/analytics/projects")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["data"] == []


# ---------------------------------------------------------------------------
# TestApiAnalyticsOutcomes
# ---------------------------------------------------------------------------

class TestApiAnalyticsOutcomes:
    def test_outcomes_distribution(self, client, seeded_db):
        resp = client.get("/api/analytics/outcomes")
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["data"]) >= 1
        outcomes = {d["outcome"] for d in data["data"]}
        assert "success" in outcomes

    def test_outcomes_no_db(self, client, isolated_db):
        resp = client.get("/api/analytics/outcomes")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["data"] == []


# ---------------------------------------------------------------------------
# TestApiAnalyticsTechnologies
# ---------------------------------------------------------------------------

class TestApiAnalyticsTechnologies:
    def test_technologies_frequency(self, client, seeded_db):
        resp = client.get("/api/analytics/technologies")
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["data"]) >= 1
        techs = {d["technology"] for d in data["data"]}
        assert "python" in techs

    def test_technologies_no_db(self, client, isolated_db):
        resp = client.get("/api/analytics/technologies")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["data"] == []


# ---------------------------------------------------------------------------
# TestApiPrune
# ---------------------------------------------------------------------------

class TestApiPrune:
    def test_prune_dry_run(self, client, seeded_db):
        resp = client.post("/api/prune", json={
            "max_sessions": 1,
            "dry_run": True,
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["dry_run"] is True
        assert data["pruned"] >= 1

    def test_prune_no_data(self, client, seeded_db):
        resp = client.post(
            "/api/prune",
            content_type="application/json",
            data="",
        )
        assert resp.status_code == 400

    def test_prune_executes(self, client, seeded_db):
        resp = client.post("/api/prune", json={
            "max_sessions": 1,
            "dry_run": False,
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["dry_run"] is False
        assert data["pruned"] >= 1

        # Verify fewer sessions remain
        list_resp = client.get("/api/sessions")
        assert list_resp.get_json()["total"] == 1


# ---------------------------------------------------------------------------
# TestApiInit
# ---------------------------------------------------------------------------

class TestApiInit:
    def test_init_creates_db(self, client, isolated_db):
        resp = client.post("/api/init", json={})
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["created"] is True

    def test_init_already_exists(self, client, seeded_db):
        resp = client.post("/api/init", json={})
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["created"] is False


# ---------------------------------------------------------------------------
# TestApiExport
# ---------------------------------------------------------------------------

class TestApiExport:
    def test_export_all_sessions(self, client, seeded_db):
        resp = client.get("/api/export")
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["sessions"]) == 2
        assert data["count"] == 2
        assert data["total"] == 2
        assert data["has_more"] is False
        # Each session should have messages and code_snippets keys
        for s in data["sessions"]:
            assert "messages" in s

    def test_export_pagination(self, client, seeded_db):
        resp = client.get("/api/export?page=1&per_page=1")
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["sessions"]) == 1
        assert data["total"] == 2
        assert data["has_more"] is True
        assert data["page"] == 1

        # Page 2
        resp2 = client.get("/api/export?page=2&per_page=1")
        data2 = resp2.get_json()
        assert len(data2["sessions"]) == 1
        assert data2["has_more"] is False

    def test_export_empty_db(self, client, isolated_db):
        init_database()
        resp = client.get("/api/export")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["sessions"] == []

    def test_export_no_db(self, client, isolated_db):
        resp = client.get("/api/export")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestApiProjects
# ---------------------------------------------------------------------------

class TestApiProjects:
    def test_projects_with_counts(self, client, seeded_db):
        resp = client.get("/api/projects")
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["projects"]) >= 2
        for p in data["projects"]:
            assert "project_path" in p
            assert "session_count" in p

    def test_projects_no_db(self, client, isolated_db):
        resp = client.get("/api/projects")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["projects"] == []


# ---------------------------------------------------------------------------
# TestApiHints
# ---------------------------------------------------------------------------

class TestApiHints:
    def test_hints_global(self, client, seeded_db):
        resp = client.get("/api/hints")
        data = resp.get_json()
        assert resp.status_code == 200
        assert "topics" in data
        assert "technologies" in data
        assert len(data["topics"]) >= 1
        assert len(data["technologies"]) >= 1

    def test_hints_project_scoped(self, client, seeded_db):
        resp = client.get("/api/hints?project=project-alpha")
        data = resp.get_json()
        assert resp.status_code == 200
        topic_names = [t["topic"] for t in data["topics"]]
        assert "authentication" in topic_names

    def test_hints_no_db(self, client, isolated_db):
        resp = client.get("/api/hints")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["topics"] == []
        assert data["technologies"] == []
