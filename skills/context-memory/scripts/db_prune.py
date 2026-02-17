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

# Tables linked by session_id TEXT (not FK), cleaned up separately
CHECKPOINT_TABLE = 'context_checkpoints'


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

        # Fetch session_ids (TEXT) before deleting sessions — needed for checkpoint cleanup
        cursor = conn.execute(
            f"SELECT session_id FROM sessions WHERE id IN ({placeholders})",
            ids_list,
        )
        session_id_texts = [row[0] for row in cursor.fetchall()]

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

        # Clean up context_checkpoints by session_id TEXT
        if CHECKPOINT_TABLE in VALID_TABLES and session_id_texts:
            cp_placeholders = ','.join('?' for _ in session_id_texts)
            conn.execute(
                f"DELETE FROM {CHECKPOINT_TABLE} WHERE session_id IN ({cp_placeholders})",
                session_id_texts,
            )

        conn.commit()

        return {"pruned": len(ids_list), "dry_run": False}


def prune_checkpoints(
    max_per_session: int = 3,
    max_age_days: Optional[int] = None,
    dry_run: bool = False,
) -> dict:
    """
    Prune old context checkpoints.

    Keeps only the N most recent checkpoints per session_id, and optionally
    removes checkpoints older than a given age.

    Args:
        max_per_session: Keep only the N newest checkpoints per session
        max_age_days: Also delete checkpoints older than this many days
        dry_run: If True, report what would be deleted without deleting

    Returns:
        Dict with pruned count and details
    """
    if CHECKPOINT_TABLE not in VALID_TABLES:
        return {"pruned": 0, "reason": "context_checkpoints table not in VALID_TABLES"}

    if not db_exists():
        return {"pruned": 0, "reason": "database does not exist"}

    with get_connection() as conn:
        ids_to_prune = set()

        # Prune by count: keep only max_per_session newest per session_id
        cursor = conn.execute(
            "SELECT DISTINCT session_id FROM context_checkpoints"
        )
        session_ids = [row[0] for row in cursor.fetchall()]

        for sid in session_ids:
            cursor = conn.execute(
                "SELECT id FROM context_checkpoints WHERE session_id = ? ORDER BY created_at DESC, checkpoint_number DESC",
                (sid,),
            )
            all_cp_ids = [row[0] for row in cursor.fetchall()]
            if len(all_cp_ids) > max_per_session:
                ids_to_prune.update(all_cp_ids[max_per_session:])

        # Prune by age
        if max_age_days is not None:
            cursor = conn.execute(
                "SELECT id FROM context_checkpoints WHERE created_at < datetime('now', ?)",
                (f'-{max_age_days} days',),
            )
            ids_to_prune.update(row[0] for row in cursor.fetchall())

        if not ids_to_prune:
            return {"pruned": 0, "dry_run": dry_run}

        ids_list = sorted(ids_to_prune)
        placeholders = ','.join('?' for _ in ids_list)

        if dry_run:
            cursor = conn.execute(
                f"SELECT id, session_id, checkpoint_number, message_count, created_at "
                f"FROM context_checkpoints WHERE id IN ({placeholders})",
                ids_list,
            )
            checkpoints_info = [dict(row) for row in cursor.fetchall()]
            return {
                "pruned": len(ids_list),
                "dry_run": True,
                "checkpoints": checkpoints_info,
            }

        conn.execute(
            f"DELETE FROM context_checkpoints WHERE id IN ({placeholders})",
            ids_list,
        )
        conn.commit()

        return {"pruned": len(ids_list), "dry_run": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prune context-memory sessions")
    parser.add_argument('--max-age', type=int, metavar='DAYS',
                        help="Delete sessions older than DAYS days")
    parser.add_argument('--max-sessions', type=int, metavar='N',
                        help="Keep only the N newest sessions")
    parser.add_argument('--prune-checkpoints', action='store_true',
                        help="Prune old context checkpoints")
    parser.add_argument('--max-checkpoints-per-session', type=int, default=3, metavar='N',
                        help="Keep only the N newest checkpoints per session (default: 3)")
    parser.add_argument('--dry-run', action='store_true',
                        help="Report what would be deleted without deleting")

    args = parser.parse_args()

    if args.prune_checkpoints:
        result = prune_checkpoints(
            max_per_session=args.max_checkpoints_per_session,
            max_age_days=args.max_age,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)

    if args.max_age is None and args.max_sessions is None:
        parser.error("At least one of --max-age, --max-sessions, or --prune-checkpoints is required")

    result = prune_sessions(
        max_age_days=args.max_age,
        max_sessions=args.max_sessions,
        dry_run=args.dry_run,
    )

    print(json.dumps(result, indent=2, default=str))
    sys.exit(0)
