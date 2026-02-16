#!/usr/bin/env python3
"""
MCP server for context-memory plugin.

Exposes search, save, stats, and init operations as MCP tools
via stdio transport using FastMCP.

Requires the optional `mcp` package: pip install mcp
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

# Ensure sibling modules (db_init, db_save, db_search) are importable regardless
# of the working directory Claude Code launches this server from.
_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    # When run directly, print a helpful message and exit.
    # When imported (e.g. by tests), let the ImportError propagate
    # so callers can handle it gracefully.
    if __name__ == "__main__":
        print(
            "Error: the 'mcp' package is required for the MCP server.\n"
            "Install it with: pip install mcp",
            file=sys.stderr,
        )
        sys.exit(1)
    raise

from db_init import get_stats, init_database  # noqa: E402
from db_save import save_full_session  # noqa: E402
from db_search import full_search  # noqa: E402

mcp = FastMCP(
    "context-memory",
    instructions=(
        "Persistent, searchable context storage across Claude Code sessions. "
        "Save sessions with context_save, search past work with context_search."
    ),
)


def _capture_stdout(fn, *args, **kwargs):
    """Call *fn* while capturing any stray stdout (e.g. print() in db_init)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return fn(*args, **kwargs)


@mcp.tool()
def context_search(
    query: str,
    project_path: str | None = None,
    detailed: bool = False,
    limit: int = 10,
) -> dict:
    """Search past Claude Code sessions stored in context memory.

    Uses FTS5 full-text search with BM25 ranking across summaries,
    topics, and code snippets (tier 1), optionally fetching full
    messages and code (tier 2).

    Args:
        query: Search terms (supports stemming — "running" matches "run").
        project_path: Limit results to a specific project directory.
        detailed: Include full messages and code snippets (tier 2).
        limit: Maximum number of results to return (default 10).

    Returns:
        Dict with keys: query, project_path, result_count, sessions.
    """
    return full_search(
        query=query,
        project_path=project_path,
        detailed=detailed,
        limit=limit,
    )


@mcp.tool()
def context_save(
    session_id: str,
    project_path: str | None = None,
    messages: list[dict] | None = None,
    summary: dict | None = None,
    topics: list[str] | None = None,
    code_snippets: list[dict] | None = None,
    user_note: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Save a Claude Code session to context memory.

    Stores the session with its messages, AI-generated summary,
    topics, and code snippets in the local SQLite database.

    Args:
        session_id: Unique session identifier.
        project_path: Path to the project directory.
        messages: List of message dicts with 'role' and 'content' keys.
        summary: Summary dict (brief, detailed, key_decisions, etc.).
        topics: List of topic/tag strings.
        code_snippets: List of dicts with code, language, description, file_path.
        user_note: Optional user annotation.
        metadata: Additional metadata dict.

    Returns:
        Dict with saved database IDs (session_id, summary_id, etc.).
    """
    return _capture_stdout(
        save_full_session,
        session_id=session_id,
        project_path=project_path,
        messages=messages,
        summary=summary,
        topics=topics,
        code_snippets=code_snippets,
        user_note=user_note,
        metadata=metadata,
    )


@mcp.tool()
def context_stats() -> dict:
    """Get database statistics for context memory.

    Returns row counts for each table and the database file size.

    Returns:
        Dict mapping table names to row counts, plus db_size_bytes.
        Empty dict if the database does not exist.
    """
    return _capture_stdout(get_stats)


@mcp.tool()
def context_init(force: bool = False) -> dict:
    """Initialize (or reinitialize) the context memory database.

    Creates all tables, FTS5 indexes, and triggers. Safe to call
    repeatedly — returns early if the database already exists
    (unless force=True).

    Args:
        force: Drop and recreate the database from scratch.

    Returns:
        Dict with 'created' (bool) and 'message' (str).
    """
    created = _capture_stdout(init_database, force=force)
    if created:
        return {"created": True, "message": "Database initialized."}
    return {"created": False, "message": "Database already exists."}


if __name__ == "__main__":
    mcp.run()
