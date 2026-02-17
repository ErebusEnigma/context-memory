#!/usr/bin/env python3
"""
Web dashboard for context-memory plugin.

Serves a REST API and single-page app for browsing, searching,
managing, and analyzing stored Claude Code sessions.

Requires: pip install flask flask-cors
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure sibling modules are importable (same pattern as mcp_server.py)
_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

try:
    from flask import Flask, jsonify, request, send_from_directory
    from flask_cors import CORS
except ImportError:
    if __name__ == "__main__":
        print(
            "Error: flask and flask-cors are required for the dashboard.\n"
            "Install with: pip install flask flask-cors",
            file=sys.stderr,
        )
        sys.exit(1)
    raise

from db_init import get_stats, init_database  # noqa: E402
from db_prune import CHILD_TABLES, prune_sessions  # noqa: E402
from db_save import save_summary, save_topics  # noqa: E402
from db_search import full_search, search_tier2  # noqa: E402
from db_utils import DB_PATH, VALID_TABLES, db_exists, get_connection  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _escape_like(value: str) -> str:
    """Escape LIKE wildcard characters in user input."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
CORS(app)


# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")


# ---------------------------------------------------------------------------
# API: Sessions
# ---------------------------------------------------------------------------

@app.route("/api/sessions")
def api_list_sessions():
    """List sessions with pagination and optional project filter."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    project = request.args.get("project", None)
    sort = request.args.get("sort", "created_at")
    order = request.args.get("order", "desc")

    if not db_exists():
        return jsonify({"sessions": [], "total": 0, "page": page, "per_page": per_page})

    allowed_sorts = {"created_at", "updated_at", "message_count"}
    if sort not in allowed_sorts:
        sort = "created_at"
    order_dir = "ASC" if order == "asc" else "DESC"

    with get_connection(readonly=True) as conn:
        # Count total
        count_sql = "SELECT COUNT(*) FROM sessions"
        count_params = []
        if project:
            count_sql += r" WHERE project_path LIKE ? ESCAPE '\'"
            count_params.append(f"%{_escape_like(project)}%")

        total = conn.execute(count_sql, count_params).fetchone()[0]

        # Fetch page
        sql = """
            SELECT s.id, s.session_id, s.project_path, s.created_at, s.updated_at,
                   s.message_count, s.metadata,
                   sum.brief, sum.outcome, sum.technologies, sum.user_note
            FROM sessions s
            LEFT JOIN summaries sum ON sum.session_id = s.id
        """
        params = []
        if project:
            sql += r" WHERE s.project_path LIKE ? ESCAPE '\'"
            params.append(f"%{_escape_like(project)}%")

        sql += f" ORDER BY s.{sort} {order_dir} LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])

        cursor = conn.execute(sql, params)
        sessions = []
        session_ids = []
        for row in cursor.fetchall():
            s = dict(row)
            # Parse JSON fields
            for field in ["metadata", "technologies"]:
                if s.get(field) and isinstance(s[field], str):
                    try:
                        s[field] = json.loads(s[field])
                    except (json.JSONDecodeError, ValueError):
                        pass
            sessions.append(s)
            session_ids.append(s["id"])

        # Batch-fetch topics
        if session_ids:
            placeholders = ",".join("?" * len(session_ids))
            cursor = conn.execute(
                f"SELECT session_id, topic FROM topics WHERE session_id IN ({placeholders})",
                session_ids,
            )
            topics_map = {}
            for row in cursor.fetchall():
                topics_map.setdefault(row["session_id"], []).append(row["topic"])
            for s in sessions:
                s["topics"] = topics_map.get(s["id"], [])

    return jsonify({"sessions": sessions, "total": total, "page": page, "per_page": per_page})


@app.route("/api/sessions/<int:session_db_id>")
def api_get_session(session_db_id):
    """Get full session detail."""
    if not db_exists():
        return jsonify({"error": "Database does not exist"}), 404

    results = search_tier2([session_db_id], include_messages=True, include_snippets=True)
    if not results:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(results[0])


@app.route("/api/sessions/<int:session_db_id>", methods=["PUT"])
def api_update_session(session_db_id):
    """Update session summary, topics, or user_note."""
    if not db_exists():
        return jsonify({"error": "Database does not exist"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    with get_connection() as conn:
        # Verify session exists
        row = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_db_id,)).fetchone()
        if not row:
            return jsonify({"error": "Session not found"}), 404

    updated = {}

    # Update summary fields
    summary_fields = {"brief", "detailed", "key_decisions", "problems_solved", "technologies", "outcome", "user_note"}
    summary_data = {k: v for k, v in data.items() if k in summary_fields}
    if summary_data:
        save_summary(session_db_id, **summary_data)
        updated["summary"] = list(summary_data.keys())

    # Update topics
    if "topics" in data:
        save_topics(session_db_id, data["topics"], replace=True)
        updated["topics"] = data["topics"]

    return jsonify({"updated": updated})


@app.route("/api/sessions/<int:session_db_id>", methods=["DELETE"])
def api_delete_session(session_db_id):
    """Delete a single session (FTS-safe: delete children first)."""
    if not db_exists():
        return jsonify({"error": "Database does not exist"}), 404

    with get_connection() as conn:
        row = conn.execute("SELECT id, session_id FROM sessions WHERE id = ?", (session_db_id,)).fetchone()
        if not row:
            return jsonify({"error": "Session not found"}), 404

        session_id_text = row["session_id"]

        # Delete child rows explicitly so FTS triggers fire
        for table in CHILD_TABLES:
            if table not in VALID_TABLES:
                continue
            conn.execute(f"DELETE FROM {table} WHERE session_id = ?", (session_db_id,))

        # Clean up context_checkpoints (keyed by session_id TEXT, not FK INTEGER)
        conn.execute(
            "DELETE FROM context_checkpoints WHERE session_id = ?",
            (session_id_text,),
        )

        conn.execute("DELETE FROM sessions WHERE id = ?", (session_db_id,))
        conn.commit()

    return jsonify({"deleted": session_db_id})


# ---------------------------------------------------------------------------
# API: Search
# ---------------------------------------------------------------------------

@app.route("/api/search")
def api_search():
    """Full-text search across sessions."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    project_path = request.args.get("project", None)
    detailed = request.args.get("detailed", "false").lower() == "true"
    limit = request.args.get("limit", 10, type=int)

    results = full_search(query=query, project_path=project_path, detailed=detailed, limit=limit)
    return jsonify(results)


# ---------------------------------------------------------------------------
# API: Stats
# ---------------------------------------------------------------------------

@app.route("/api/stats")
def api_stats():
    """Get database statistics."""
    if not db_exists():
        return jsonify({"error": "Database does not exist", "exists": False})
    stats = get_stats()
    return jsonify(stats)


# ---------------------------------------------------------------------------
# API: Analytics
# ---------------------------------------------------------------------------

@app.route("/api/analytics/timeline")
def api_analytics_timeline():
    """Sessions per day/week/month."""
    granularity = request.args.get("granularity", "week")
    if not db_exists():
        return jsonify({"data": []})

    if granularity == "day":
        date_expr = "date(created_at)"
    elif granularity == "month":
        date_expr = "strftime('%Y-%m', created_at)"
    else:
        date_expr = "strftime('%Y-W%W', created_at)"

    with get_connection(readonly=True) as conn:
        cursor = conn.execute(f"""
            SELECT {date_expr} as period,
                   COUNT(*) as count,
                   SUM(CASE WHEN json_extract(metadata, '$.auto_save') = 1 THEN 1 ELSE 0 END) as auto_count,
                   SUM(CASE WHEN json_extract(metadata, '$.auto_save') = 1 THEN 0 ELSE 1 END) as manual_count
            FROM sessions
            GROUP BY period
            ORDER BY period
        """)
        data = [dict(row) for row in cursor.fetchall()]

    return jsonify({"data": data, "granularity": granularity})


@app.route("/api/analytics/topics")
def api_analytics_topics():
    """Topic frequency distribution."""
    limit = request.args.get("limit", 20, type=int)
    if not db_exists():
        return jsonify({"data": []})

    with get_connection(readonly=True) as conn:
        cursor = conn.execute("""
            SELECT topic, COUNT(*) as count
            FROM topics
            WHERE topic != 'auto-save'
            GROUP BY topic
            ORDER BY count DESC
            LIMIT ?
        """, (limit,))
        data = [dict(row) for row in cursor.fetchall()]

    return jsonify({"data": data})


@app.route("/api/analytics/projects")
def api_analytics_projects():
    """Sessions per project."""
    if not db_exists():
        return jsonify({"data": []})

    with get_connection(readonly=True) as conn:
        cursor = conn.execute("""
            SELECT project_path, COUNT(*) as count
            FROM sessions
            WHERE project_path IS NOT NULL AND project_path != ''
            GROUP BY project_path
            ORDER BY count DESC
            LIMIT 20
        """)
        data = [dict(row) for row in cursor.fetchall()]

    return jsonify({"data": data})


@app.route("/api/analytics/outcomes")
def api_analytics_outcomes():
    """Outcome distribution."""
    if not db_exists():
        return jsonify({"data": []})

    with get_connection(readonly=True) as conn:
        cursor = conn.execute("""
            SELECT COALESCE(outcome, 'unknown') as outcome, COUNT(*) as count
            FROM summaries
            GROUP BY outcome
            ORDER BY count DESC
        """)
        data = [dict(row) for row in cursor.fetchall()]

    return jsonify({"data": data})


@app.route("/api/analytics/technologies")
def api_analytics_technologies():
    """Technology usage frequency."""
    limit = request.args.get("limit", 15, type=int)
    if not db_exists():
        return jsonify({"data": []})

    with get_connection(readonly=True) as conn:
        cursor = conn.execute("SELECT technologies FROM summaries WHERE technologies IS NOT NULL")
        tech_counts = {}
        for row in cursor.fetchall():
            try:
                techs = json.loads(row["technologies"]) if isinstance(row["technologies"], str) else row["technologies"]
                if isinstance(techs, list):
                    for t in techs:
                        t_lower = t.strip().lower()
                        if t_lower:
                            tech_counts[t_lower] = tech_counts.get(t_lower, 0) + 1
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

    sorted_techs = sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    data = [{"technology": t, "count": c} for t, c in sorted_techs]
    return jsonify({"data": data})


# ---------------------------------------------------------------------------
# API: Management
# ---------------------------------------------------------------------------

@app.route("/api/prune", methods=["POST"])
def api_prune():
    """Prune sessions by age and/or count."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    result = prune_sessions(
        max_age_days=data.get("max_age_days"),
        max_sessions=data.get("max_sessions"),
        dry_run=data.get("dry_run", True),
    )
    return jsonify(result)


@app.route("/api/init", methods=["POST"])
def api_init():
    """Initialize or reinitialize the database."""
    data = request.get_json() or {}
    force = data.get("force", False)
    created = init_database(force=force)
    if created:
        return jsonify({"created": True, "message": "Database initialized."})
    return jsonify({"created": False, "message": "Database already exists."})


@app.route("/api/export")
def api_export():
    """Export sessions as JSON with pagination.

    Query params:
        page: Page number (default 1)
        per_page: Sessions per page (default 100, max 500)
    """
    if not db_exists():
        return jsonify({"error": "Database does not exist"}), 404

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 100, type=int), 500)

    with get_connection(readonly=True) as conn:
        total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        cursor = conn.execute(
            "SELECT id FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (per_page, (page - 1) * per_page),
        )
        session_ids = [row["id"] for row in cursor.fetchall()]

    if not session_ids:
        return jsonify({"sessions": [], "count": 0, "total": total, "page": page, "per_page": per_page, "has_more": False})

    sessions = search_tier2(session_ids, include_messages=True, include_snippets=True)
    has_more = (page * per_page) < total
    return jsonify({
        "sessions": sessions,
        "count": len(sessions),
        "total": total,
        "page": page,
        "per_page": per_page,
        "has_more": has_more,
        "db_path": str(DB_PATH),
    })


# ---------------------------------------------------------------------------
# API: Projects list (for filter dropdowns)
# ---------------------------------------------------------------------------

@app.route("/api/projects")
def api_projects():
    """List all distinct project paths with session counts."""
    if not db_exists():
        return jsonify({"projects": []})

    with get_connection(readonly=True) as conn:
        cursor = conn.execute("""
            SELECT project_path, COUNT(*) as session_count
            FROM sessions
            WHERE project_path IS NOT NULL AND project_path != ''
            GROUP BY project_path
            ORDER BY session_count DESC
        """)
        projects = [dict(row) for row in cursor.fetchall()]

    return jsonify({"projects": projects})


# ---------------------------------------------------------------------------
# API: Search hints (topics + technologies scoped to project)
# ---------------------------------------------------------------------------

@app.route("/api/hints")
def api_hints():
    """Get search hint chips (topics + technologies) for a project or globally."""
    project = request.args.get("project", None)
    if not db_exists():
        return jsonify({"topics": [], "technologies": []})

    with get_connection(readonly=True) as conn:
        # Topics scoped to project
        if project:
            cursor = conn.execute(r"""
                SELECT t.topic, COUNT(*) as count
                FROM topics t
                JOIN sessions s ON s.id = t.session_id
                WHERE t.topic != 'auto-save' AND s.project_path LIKE ? ESCAPE '\'
                GROUP BY t.topic
                ORDER BY count DESC
                LIMIT 15
            """, (f"%{_escape_like(project)}%",))
        else:
            cursor = conn.execute("""
                SELECT topic, COUNT(*) as count
                FROM topics
                WHERE topic != 'auto-save'
                GROUP BY topic
                ORDER BY count DESC
                LIMIT 15
            """)
        topics = [dict(row) for row in cursor.fetchall()]

        # Technologies scoped to project
        if project:
            cursor = conn.execute(r"""
                SELECT sum.technologies
                FROM summaries sum
                JOIN sessions s ON s.id = sum.session_id
                WHERE sum.technologies IS NOT NULL AND s.project_path LIKE ? ESCAPE '\'
            """, (f"%{_escape_like(project)}%",))
        else:
            cursor = conn.execute(
                "SELECT technologies FROM summaries WHERE technologies IS NOT NULL"
            )

        tech_counts = {}
        for row in cursor.fetchall():
            try:
                techs = json.loads(row["technologies"]) if isinstance(row["technologies"], str) else row["technologies"]
                if isinstance(techs, list):
                    for t in techs:
                        t_lower = t.strip().lower()
                        if t_lower:
                            tech_counts[t_lower] = tech_counts.get(t_lower, 0) + 1
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        sorted_techs = sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:15]
        technologies = [{"technology": t, "count": c} for t, c in sorted_techs]

    return jsonify({"topics": topics, "technologies": technologies})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def start_server(host: str = "127.0.0.1", port: int = 5111, debug: bool = False):
    """Start the Flask dashboard server."""
    print(f"Context Memory Dashboard: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Context Memory Web Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5111, help="Port to listen on (default: 5111)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")

    args = parser.parse_args()
    start_server(host=args.host, port=args.port, debug=args.debug)
