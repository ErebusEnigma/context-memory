"""
Context Memory Scripts Package

Database utilities for persistent, searchable context storage.
"""

__version__ = "1.3.0"

from .db_init import get_stats, init_database, verify_schema
from .db_prune import prune_sessions
from .db_save import (
    save_code_snippet,
    save_full_session,
    save_messages,
    save_session,
    save_summary,
    save_topics,
    should_skip_auto_save,
)
from .db_search import (
    format_results_markdown,
    full_search,
    search_messages,
    search_tier1,
    search_tier2,
)
from .db_utils import (
    db_exists,
    format_fts_query,
    get_connection,
    get_db_path,
    get_session_count,
    hash_project_path,
    truncate_text,
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
    'should_skip_auto_save',
    # Search
    'search_tier1',
    'search_tier2',
    'search_messages',
    'full_search',
    'format_results_markdown',
    # Prune
    'prune_sessions',
]
