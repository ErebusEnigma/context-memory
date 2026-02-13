#!/usr/bin/env python3
"""
Database pruning for context-memory plugin.
Removes old or excess sessions to manage database size.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

try:
    from .db_utils import VALID_TABLES, db_exists, get_connection
except ImportError:
    from db_utils import VALID_TABLES, db_exists, get_connection

# Child tables that must be deleted before sessions (FTS triggers need row-level DELETE)
CHILD_TABLES = ['messages', 'summaries', 'topics', 'code_snippets']


def prune_sessions(
    max_age_days: Optional[int] = None,
    max_sessions: Optional[int] = None,
    dry_run: bool = False
) -> dict:
    """
    Prune sessions by age and/or count.

    Uses OR logic: sessions matching either condition are pruned.
    Child rows are deleted explicitly before sessions to ensure
    FTS5 sync triggers fire correctly (CASCADE doesn't trigger them).

    Args:
        max_age_days: Delete sessions older than this many days
        max_sessions: Keep only this many newest sessions
        dry_run: If True, report what would be deleted without deleting

    Returns:
        Dict with pruned count and details
    """
    if max_age_days is None and max_sessions is None:
        return {"pruned": 0, "reason": "no criteria specified"}

    if not db_exists():
        return {"pruned": 0, "reason": "database does not exist"}

    with get_connection() as conn:
        ids_to_prune = set()

        # Collect IDs by age
        if max_age_days is not None:
            cursor = conn.execute(
                "SELECT id FROM sessions WHERE created_at < datetime('now', ?)",
                (f'-{max_age_days} days',)
            )
            ids_to_prune.update(row[0] for row in cursor.fetchall())

        # Collect IDs by count (keep newest max_sessions)
        if max_sessions is not None:
            cursor = conn.execute(
                "SELECT id FROM sessions ORDER BY created_at DESC, id DESC"
            )
            all_ids = [row[0] for row in cursor.fetchall()]
            if len(all_ids) > max_sessions:
                ids_to_prune.update(all_ids[max_sessions:])

        if not ids_to_prune:
            return {"pruned": 0, "dry_run": dry_run}

        ids_list = sorted(ids_to_prune)
        placeholders = ','.join('?' for _ in ids_list)

        if dry_run:
            # Report what would be pruned
            cursor = conn.execute(
                f"SELECT id, session_id, project_path, created_at FROM sessions WHERE id IN ({placeholders})",
                ids_list
            )
            sessions_info = [dict(row) for row in cursor.fetchall()]
            return {
                "pruned": len(ids_list),
                "dry_run": True,
                "sessions": sessions_info,
            }

        # Delete child rows explicitly to fire FTS sync triggers
        for table in CHILD_TABLES:
            if table not in VALID_TABLES:
                continue
            conn.execute(
                f"DELETE FROM {table} WHERE session_id IN ({placeholders})",
                ids_list
            )

        # Delete sessions
        conn.execute(
            f"DELETE FROM sessions WHERE id IN ({placeholders})",
            ids_list
        )

        # Rebuild FTS indexes to ensure consistency after bulk deletes
        for fts_table in ['summaries_fts', 'messages_fts', 'topics_fts', 'code_snippets_fts']:
            conn.execute(f"INSERT INTO {fts_table}({fts_table}) VALUES('rebuild')")

        conn.commit()

        return {"pruned": len(ids_list), "dry_run": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prune context-memory sessions")
    parser.add_argument('--max-age', type=int, metavar='DAYS',
                        help="Delete sessions older than DAYS days")
    parser.add_argument('--max-sessions', type=int, metavar='N',
                        help="Keep only the N newest sessions")
    parser.add_argument('--dry-run', action='store_true',
                        help="Report what would be deleted without deleting")

    args = parser.parse_args()

    if args.max_age is None and args.max_sessions is None:
        parser.error("At least one of --max-age or --max-sessions is required")

    result = prune_sessions(
        max_age_days=args.max_age,
        max_sessions=args.max_sessions,
        dry_run=args.dry_run,
    )

    print(json.dumps(result, indent=2, default=str))
    sys.exit(0)
