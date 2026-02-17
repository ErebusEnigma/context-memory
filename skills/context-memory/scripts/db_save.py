#!/usr/bin/env python3
"""
Session save logic for context-memory plugin.
Handles storing sessions, summaries, messages, and topics.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional

try:
    from .db_init import ensure_schema_current, init_database
    from .db_utils import db_exists, get_connection, hash_project_path, normalize_project_path
except ImportError:
    from db_init import ensure_schema_current, init_database
    from db_utils import db_exists, get_connection, hash_project_path, normalize_project_path

logger = logging.getLogger(__name__)


def save_session(
    session_id: str,
    project_path: Optional[str] = None,
    metadata: Optional[dict] = None
) -> int:
    """
    Create or update a session record.

    Args:
        session_id: Unique session identifier
        project_path: Path to the project directory
        metadata: Additional metadata as dict

    Returns:
        Database ID of the session
    """
    if not db_exists():
        init_database()
    else:
        ensure_schema_current()

    if project_path:
        project_path = normalize_project_path(project_path)

    project_hash = hash_project_path(project_path) if project_path else None
    metadata_json = json.dumps(metadata) if metadata else None

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO sessions (session_id, project_path, project_hash, metadata)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                project_path = COALESCE(excluded.project_path, project_path),
                project_hash = COALESCE(excluded.project_hash, project_hash),
                metadata = COALESCE(excluded.metadata, metadata),
                updated_at = CURRENT_TIMESTAMP
        """, (session_id, project_path, project_hash, metadata_json))
        conn.commit()

        # Fetch the id (works for both insert and update)
        row = conn.execute(
            "SELECT id FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        session_db_id = row['id']

    return session_db_id


def save_messages(
    session_db_id: int,
    messages: list[dict],
    replace: bool = False
) -> int:
    """
    Save messages for a session.

    Args:
        session_db_id: Database ID of the session
        messages: List of message dicts with 'role' and 'content'
        replace: If True, delete existing messages first

    Returns:
        Number of messages saved
    """
    with get_connection() as conn:
        if replace:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_db_id,))
            offset = 0
        else:
            cursor = conn.execute(
                "SELECT COALESCE(MAX(sequence), -1) FROM messages WHERE session_id = ?",
                (session_db_id,),
            )
            offset = cursor.fetchone()[0] + 1

        for i, msg in enumerate(messages):
            conn.execute("""
                INSERT INTO messages (session_id, role, content, sequence)
                VALUES (?, ?, ?, ?)
            """, (session_db_id, msg.get('role', 'user'), msg.get('content', ''), offset + i))

        # Update message count from actual rows (correct even on append)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_db_id,)
        )
        total = cursor.fetchone()[0]
        conn.execute("UPDATE sessions SET message_count = ? WHERE id = ?", (total, session_db_id))

        conn.commit()

    return len(messages)


def save_summary(
    session_db_id: int,
    brief: Optional[str] = None,
    detailed: Optional[str] = None,
    key_decisions: Optional[list[str]] = None,
    problems_solved: Optional[list[str]] = None,
    technologies: Optional[list[str]] = None,
    outcome: Optional[str] = None,
    user_note: Optional[str] = None
) -> int:
    """
    Save or update a session summary.

    Args:
        session_db_id: Database ID of the session
        brief: One-line summary (required for new summaries, optional for updates)
        detailed: Detailed summary
        key_decisions: List of key decisions made
        problems_solved: List of problems solved
        technologies: List of technologies used
        outcome: Session outcome (success, partial, abandoned)
        user_note: User-provided annotation

    Returns:
        Database ID of the summary
    """
    with get_connection() as conn:
        # Check if summary exists
        cursor = conn.execute(
            "SELECT id FROM summaries WHERE session_id = ?",
            (session_db_id,)
        )
        existing = cursor.fetchone()

        decisions_json = json.dumps(key_decisions) if key_decisions else None
        problems_json = json.dumps(problems_solved) if problems_solved else None
        tech_json = json.dumps(technologies) if technologies else None

        if existing:
            conn.execute("""
                UPDATE summaries
                SET brief = COALESCE(?, brief),
                    detailed = COALESCE(?, detailed),
                    key_decisions = COALESCE(?, key_decisions),
                    problems_solved = COALESCE(?, problems_solved),
                    technologies = COALESCE(?, technologies),
                    outcome = COALESCE(?, outcome),
                    user_note = COALESCE(?, user_note)
                WHERE session_id = ?
            """, (brief, detailed, decisions_json, problems_json, tech_json,
                  outcome, user_note, session_db_id))
            summary_id = existing['id']
        else:
            if brief is None:
                raise ValueError("brief is required when creating a new summary")
            cursor = conn.execute("""
                INSERT INTO summaries
                (session_id, brief, detailed, key_decisions, problems_solved, technologies, outcome, user_note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_db_id, brief, detailed, decisions_json, problems_json,
                  tech_json, outcome, user_note))
            summary_id = cursor.lastrowid

        conn.commit()

    return summary_id


def save_topics(session_db_id: int, topics: list[str], replace: bool = True) -> int:
    """
    Save topics for a session.

    Args:
        session_db_id: Database ID of the session
        topics: List of topic strings
        replace: If True, delete existing topics first

    Returns:
        Number of topics saved
    """
    with get_connection() as conn:
        if replace:
            conn.execute("DELETE FROM topics WHERE session_id = ?", (session_db_id,))

        count = 0
        for topic in topics:
            topic_lower = topic.lower().strip()
            if topic_lower:
                conn.execute("""
                    INSERT INTO topics (session_id, topic) VALUES (?, ?)
                """, (session_db_id, topic_lower))
                count += 1

        conn.commit()

    return count


def save_code_snippet(
    session_db_id: int,
    code: str,
    language: Optional[str] = None,
    description: Optional[str] = None,
    file_path: Optional[str] = None
) -> int:
    """
    Save a code snippet for a session.

    Args:
        session_db_id: Database ID of the session
        code: The code content
        language: Programming language
        description: Description of the snippet
        file_path: Source file path

    Returns:
        Database ID of the snippet
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO code_snippets (session_id, language, code, description, file_path)
            VALUES (?, ?, ?, ?, ?)
        """, (session_db_id, language, code, description, file_path))
        conn.commit()

    return cursor.lastrowid


def should_skip_auto_save(project_path: str, window_minutes: int = 5) -> bool:
    """
    Check if an auto-save should be skipped because a rich session
    (from /remember) was recently saved for the same project.

    Args:
        project_path: Project directory path
        window_minutes: How many minutes back to check

    Returns:
        True if a rich session exists (auto-save is redundant)
    """
    if not project_path or not db_exists():
        return False

    project_hash = hash_project_path(project_path)

    with get_connection(readonly=True) as conn:
        cursor = conn.execute("""
            SELECT COUNT(*) FROM sessions s
            JOIN summaries sum ON sum.session_id = s.id
            WHERE s.project_hash = ?
              AND sum.brief != 'Auto-saved session'
              AND NOT sum.brief LIKE 'Auto-saved session:%'
              AND s.updated_at >= datetime('now', ?)
        """, (project_hash, f'-{window_minutes} minutes'))
        count = cursor.fetchone()[0]

    return count > 0


def save_full_session(
    session_id: str,
    project_path: Optional[str] = None,
    messages: Optional[list[dict]] = None,
    summary: Optional[dict] = None,
    topics: Optional[list[str]] = None,
    code_snippets: Optional[list[dict]] = None,
    user_note: Optional[str] = None,
    metadata: Optional[dict] = None
) -> dict:
    """
    Save a complete session with all related data.

    Args:
        session_id: Unique session identifier
        project_path: Path to the project directory
        messages: List of message dicts
        summary: Summary dict with brief, detailed, etc.
        topics: List of topic strings
        code_snippets: List of code snippet dicts
        user_note: User-provided annotation
        metadata: Additional metadata dict

    Returns:
        Dict with saved IDs
    """
    # Save session
    session_db_id = save_session(session_id, project_path, metadata=metadata)

    result = {'session_id': session_db_id}

    # Save messages if provided
    if messages:
        result['messages_count'] = save_messages(session_db_id, messages, replace=True)

    # Save summary if provided
    if summary:
        summary_data = {**summary}
        if user_note:
            summary_data['user_note'] = user_note
        result['summary_id'] = save_summary(session_db_id, **summary_data)
    elif user_note:
        # Save just the user note as a brief summary
        result['summary_id'] = save_summary(session_db_id, brief=user_note, user_note=user_note)

    # Save topics if provided
    if topics:
        result['topics_count'] = save_topics(session_db_id, topics)

    # Save code snippets if provided
    if code_snippets:
        result['snippets'] = []
        for snippet in code_snippets:
            snippet_id = save_code_snippet(session_db_id, **snippet)
            result['snippets'].append(snippet_id)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Save session to context-memory")
    parser.add_argument('--session-id', help="Session ID (required unless --json is used)")
    parser.add_argument('--project-path', help="Project path")
    parser.add_argument('--brief', help="Brief summary")
    parser.add_argument('--detailed', help="Detailed summary")
    parser.add_argument('--topics', help="Comma-separated topics")
    parser.add_argument('--decisions', help="Comma-separated key decisions")
    parser.add_argument('--problems', help="Comma-separated problems solved")
    parser.add_argument('--technologies', help="Comma-separated technologies")
    parser.add_argument('--outcome', choices=['success', 'partial', 'abandoned'],
                        help="Session outcome")
    parser.add_argument('--user-note', help="User annotation")
    parser.add_argument('--json', help="JSON file with full session data, or '-' to read from stdin (standalone, no other args required)")
    parser.add_argument('--auto', action='store_true',
                        help="Auto-save mode: skip if rich session exists recently")
    parser.add_argument('--dedup-window', type=int, default=5,
                        help="Dedup window in minutes (default: 5)")

    args = parser.parse_args()

    # --session-id is required unless --json is provided
    if not args.json and not args.session_id:
        parser.error("--session-id is required when --json is not provided")

    if args.json:
        # Load from JSON file or stdin
        try:
            if args.json == '-':
                data = json.load(sys.stdin)
            else:
                with open(args.json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
        except FileNotFoundError:
            print(f"Error: File not found: {args.json}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            source = "stdin" if args.json == '-' else args.json
            print(f"Error: Invalid JSON in {source}: {e}")
            sys.exit(1)

        # Dedup check for auto-saves: use project_path from JSON payload
        dedup_path = data.get("project_path") or args.project_path
        if args.auto and dedup_path:
            if should_skip_auto_save(dedup_path, args.dedup_window):
                print(json.dumps({"skipped": True, "reason": "rich session exists within dedup window"}))
                sys.exit(0)

        # Inject auto_save metadata when --auto is combined with --json
        if args.auto:
            existing_meta = data.get("metadata") or {}
            existing_meta["auto_save"] = True
            data["metadata"] = existing_meta

        result = save_full_session(**data)
    else:
        # Deduplication check for auto-saves (CLI-args path)
        if args.auto and args.project_path:
            if should_skip_auto_save(args.project_path, args.dedup_window):
                print(json.dumps({"skipped": True, "reason": "rich session exists within dedup window"}))
                sys.exit(0)

        # Save from arguments
        topics = args.topics.split(',') if args.topics else None
        metadata = {"auto_save": True} if args.auto else None
        summary = None
        if args.brief:
            summary = {
                'brief': args.brief,
                'detailed': args.detailed,
                'key_decisions': args.decisions.split(',') if args.decisions else None,
                'problems_solved': args.problems.split(',') if args.problems else None,
                'technologies': args.technologies.split(',') if args.technologies else None,
                'outcome': args.outcome,
            }

        session_db_id = save_session(
            session_id=args.session_id,
            project_path=args.project_path,
            metadata=metadata,
        )

        result = {'session_id': session_db_id}

        if summary:
            result['summary_id'] = save_summary(session_db_id, **summary)

        if topics:
            result['topics_count'] = save_topics(session_db_id, topics)

    print(json.dumps(result, indent=2))
