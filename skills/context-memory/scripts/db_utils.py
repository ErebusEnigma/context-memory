"""
Database utilities for context-memory plugin.
Provides connection management and helper functions.
"""
from __future__ import annotations

import hashlib
import os
import platform
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Database location — override with CONTEXT_MEMORY_DB_PATH env var
_db_path_override = os.environ.get("CONTEXT_MEMORY_DB_PATH")
if _db_path_override:
    DB_PATH = Path(_db_path_override)
    DB_DIR = DB_PATH.parent
else:
    DB_DIR = Path.home() / ".claude" / "context-memory"
    DB_PATH = DB_DIR / "context.db"


def ensure_db_dir() -> None:
    """Ensure the database directory exists."""
    DB_DIR.mkdir(parents=True, exist_ok=True)


def get_db_path() -> Path:
    """Get the database file path."""
    return DB_PATH


@contextmanager
def get_connection(readonly: bool = False) -> Iterator[sqlite3.Connection]:
    """
    Context manager for database connections.
    Uses WAL mode for better concurrent access.

    Args:
        readonly: If True, open in read-only mode
    """
    ensure_db_dir()

    if readonly:
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")

    try:
        yield conn
    finally:
        conn.close()


def hash_project_path(project_path: str) -> str:
    """
    Create a consistent hash for a project path.
    Useful for quick project-scoped queries.
    """
    normalized = os.path.normpath(os.path.abspath(project_path))

    # Fix MSYS2/Git Bash paths: /c/Users/... becomes C:\c\Users\... after abspath
    if platform.system() == 'Windows' and len(normalized) > 3:
        parts = normalized.split(os.sep)
        if len(parts) >= 3 and len(parts[1]) == 1 and parts[1].isalpha():
            normalized = parts[1].upper() + ':\\' + os.sep.join(parts[2:])

    # Case-insensitive on Windows
    if platform.system() == 'Windows':
        normalized = normalized.lower()

    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def normalize_project_path(project_path: str) -> str:
    """Normalize a project path for consistent cross-platform storage."""
    return project_path.replace('\\', '/')


def format_fts_query(query: str, use_prefix: bool = True) -> str:
    """
    Format a query string for FTS5 search.

    Args:
        query: The search query
        use_prefix: If True, add * suffix for prefix matching
    """
    terms = query.strip().split()
    if not terms:
        return '""'

    formatted_terms = []
    for term in terms:
        # Escape any special characters
        clean_term = ''.join(c for c in term if c.isalnum() or c in '-_')
        if clean_term:
            if use_prefix:
                formatted_terms.append(f'"{clean_term}"*')
            else:
                formatted_terms.append(f'"{clean_term}"')

    return ' OR '.join(formatted_terms) if formatted_terms else '""'


def db_exists() -> bool:
    """Check if the database file exists."""
    return DB_PATH.exists()


VALID_TABLES = {'sessions', 'messages', 'summaries', 'topics', 'code_snippets', 'schema_version', 'context_checkpoints'}

# Tables to include in stats output (skip internal tables)
STATS_TABLES = VALID_TABLES - {'schema_version'}


def get_table_count(table_name: str) -> int:
    """Get the number of rows in a table."""
    if table_name not in VALID_TABLES:
        raise ValueError(f"Unknown table: {table_name}")
    if not db_exists():
        return 0

    with get_connection(readonly=True) as conn:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cursor.fetchone()[0]


def get_session_count() -> int:
    """Get the total number of stored sessions."""
    return get_table_count("sessions")


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to a maximum length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
