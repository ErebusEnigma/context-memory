"""
Context Memory Scripts Package

Database utilities for persistent, searchable context storage.
"""

__version__ = "1.0.0"

from .db_utils import (
    get_connection,
    get_db_path,
    db_exists,
    hash_project_path,
    format_fts_query,
    get_session_count,
    truncate_text
)

from .db_init import init_database, verify_schema, get_stats

from .db_save import (
    save_session,
    save_messages,
    save_summary,
    save_topics,
    save_code_snippet,
    save_full_session
)

from .db_search import (
    search_tier1,
    search_tier2,
    search_messages,
    full_search,
    format_results_markdown
)

__all__ = [
    # Utils
    'get_connection',
    'get_db_path',
    'db_exists',
    'hash_project_path',
    'format_fts_query',
    'get_session_count',
    'truncate_text',
    # Init
    'init_database',
    'verify_schema',
    'get_stats',
    # Save
    'save_session',
    'save_messages',
    'save_summary',
    'save_topics',
    'save_code_snippet',
    'save_full_session',
    # Search
    'search_tier1',
    'search_tier2',
    'search_messages',
    'full_search',
    'format_results_markdown',
]
