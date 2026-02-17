#!/usr/bin/env python3
"""
Two-tier search for context-memory plugin.
Tier 1: Fast summary search (<10ms)
Tier 2: Deep content search (<50ms)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Optional

try:
    from .db_utils import db_exists, format_fts_query, get_connection, hash_project_path, truncate_text
except ImportError:
    from db_utils import db_exists, format_fts_query, get_connection, hash_project_path, truncate_text

logger = logging.getLogger(__name__)

# Display limits for formatted output
MAX_DECISIONS_DISPLAY = 5
MAX_MESSAGES_DISPLAY = 10
MAX_SNIPPETS_DISPLAY = 5
MAX_MESSAGE_LENGTH = 300
MAX_SNIPPET_LENGTH = 500


def search_tier1(
    query: str,
    project_path: Optional[str] = None,
    limit: int = 10
) -> list[dict]:
    """
    Tier 1: Fast summary search.
    Searches summaries_fts, topics_fts, and code_snippets_fts.
    Target: <10ms

    Args:
        query: Search query string
        project_path: Optional project path to filter by
        limit: Maximum results to return

    Returns:
        List of matching sessions with brief info and relevance scores
    """
    if not db_exists():
        return []

    fts_query = format_fts_query(query)
    project_hash = hash_project_path(project_path) if project_path else None

    with get_connection(readonly=True) as conn:
        # Search summaries with BM25 ranking
        sql = """
            SELECT
                s.id,
                s.session_id,
                s.project_path,
                s.created_at,
                s.message_count,
                sum.brief,
                sum.outcome,
                sum.technologies,
                bm25(summaries_fts) as relevance
            FROM summaries_fts
            JOIN summaries sum ON sum.id = summaries_fts.rowid
            JOIN sessions s ON s.id = sum.session_id
            WHERE summaries_fts MATCH ?
        """
        params = [fts_query]

        if project_hash:
            sql += " AND s.project_hash = ?"
            params.append(project_hash)

        sql += " ORDER BY relevance LIMIT ?"
        params.append(limit)

        cursor = conn.execute(sql, params)
        summary_results = [dict(row) for row in cursor.fetchall()]

        # Also search topics
        sql = """
            SELECT DISTINCT
                s.id,
                s.session_id,
                s.project_path,
                s.created_at,
                s.message_count,
                sum.brief,
                sum.outcome,
                sum.technologies,
                bm25(topics_fts) as relevance
            FROM topics_fts
            JOIN topics t ON t.id = topics_fts.rowid
            JOIN sessions s ON s.id = t.session_id
            LEFT JOIN summaries sum ON sum.session_id = s.id
            WHERE topics_fts MATCH ?
        """
        params = [fts_query]

        if project_hash:
            sql += " AND s.project_hash = ?"
            params.append(project_hash)

        sql += " ORDER BY relevance LIMIT ?"
        params.append(limit)

        cursor = conn.execute(sql, params)
        topic_results = [dict(row) for row in cursor.fetchall()]

        # Also search code snippets
        sql = """
            SELECT DISTINCT
                s.id,
                s.session_id,
                s.project_path,
                s.created_at,
                s.message_count,
                sum.brief,
                sum.outcome,
                sum.technologies,
                bm25(code_snippets_fts) as relevance
            FROM code_snippets_fts
            JOIN code_snippets cs ON cs.id = code_snippets_fts.rowid
            JOIN sessions s ON s.id = cs.session_id
            LEFT JOIN summaries sum ON sum.session_id = s.id
            WHERE code_snippets_fts MATCH ?
        """
        params = [fts_query]

        if project_hash:
            sql += " AND s.project_hash = ?"
            params.append(project_hash)

        sql += " ORDER BY relevance LIMIT ?"
        params.append(limit)

        cursor = conn.execute(sql, params)
        snippet_results = [dict(row) for row in cursor.fetchall()]

        # Merge results, removing duplicates
        seen_ids = set()
        merged = []

        for result in summary_results + topic_results + snippet_results:
            if result['id'] not in seen_ids:
                seen_ids.add(result['id'])
                merged.append(result)

        # Batch-fetch topics for all merged results
        merged_ids = [r['id'] for r in merged]
        if merged_ids:
            placeholders = ','.join('?' * len(merged_ids))
            cursor = conn.execute(
                f"SELECT session_id, topic FROM topics WHERE session_id IN ({placeholders})",
                merged_ids,
            )
            topics_map = {}
            for row in cursor.fetchall():
                topics_map.setdefault(row['session_id'], []).append(row['topic'])
            for result in merged:
                result['topics'] = topics_map.get(result['id'], [])

        # Sort by relevance and limit
        merged.sort(key=lambda x: x.get('relevance', 0))
        return merged[:limit]


def search_tier2(
    session_ids: list[int],
    include_messages: bool = True,
    include_snippets: bool = True
) -> list[dict]:
    """
    Tier 2: Deep content fetch.
    Retrieves full content for specific sessions.
    Target: <50ms

    Args:
        session_ids: List of session database IDs to fetch
        include_messages: Include message content
        include_snippets: Include code snippets

    Returns:
        List of sessions with full content
    """
    if not db_exists() or not session_ids:
        return []

    with get_connection(readonly=True) as conn:
        placeholders = ','.join('?' * len(session_ids))

        # Batch-fetch sessions + summaries
        cursor = conn.execute(f"""
            SELECT s.*, sum.brief, sum.detailed, sum.key_decisions,
                   sum.problems_solved, sum.technologies, sum.outcome, sum.user_note
            FROM sessions s
            LEFT JOIN summaries sum ON sum.session_id = s.id
            WHERE s.id IN ({placeholders})
        """, session_ids)
        sessions_map = {}
        for row in cursor.fetchall():
            session = dict(row)
            for field in ['key_decisions', 'problems_solved', 'technologies']:
                if session.get(field):
                    try:
                        session[field] = json.loads(session[field])
                    except (json.JSONDecodeError, ValueError):
                        logger.warning("Failed to parse JSON in field '%s' for session %d", field, session['id'])
            session['topics'] = []
            if include_messages:
                session['messages'] = []
            if include_snippets:
                session['code_snippets'] = []
            sessions_map[session['id']] = session

        if not sessions_map:
            return []

        # Batch-fetch topics
        cursor = conn.execute(
            f"SELECT session_id, topic FROM topics WHERE session_id IN ({placeholders})",
            session_ids,
        )
        for row in cursor.fetchall():
            if row['session_id'] in sessions_map:
                sessions_map[row['session_id']]['topics'].append(row['topic'])

        # Batch-fetch messages if requested
        if include_messages:
            cursor = conn.execute(f"""
                SELECT session_id, role, content, sequence
                FROM messages
                WHERE session_id IN ({placeholders})
                ORDER BY session_id, sequence
            """, session_ids)
            for row in cursor.fetchall():
                if row['session_id'] in sessions_map:
                    sessions_map[row['session_id']]['messages'].append(dict(row))

        # Batch-fetch code snippets if requested
        if include_snippets:
            cursor = conn.execute(f"""
                SELECT session_id, language, code, description, file_path
                FROM code_snippets
                WHERE session_id IN ({placeholders})
            """, session_ids)
            for row in cursor.fetchall():
                if row['session_id'] in sessions_map:
                    sessions_map[row['session_id']]['code_snippets'].append(dict(row))

        # Return in the original order
        return [sessions_map[sid] for sid in session_ids if sid in sessions_map]


def search_messages(
    query: str,
    project_path: Optional[str] = None,
    limit: int = 10
) -> list[dict]:
    """
    Search directly in messages content.
    Use for detailed queries when tier 1 doesn't find results.

    Args:
        query: Search query
        project_path: Optional project filter
        limit: Maximum results

    Returns:
        List of matching messages with session info
    """
    if not db_exists():
        return []

    fts_query = format_fts_query(query)
    project_hash = hash_project_path(project_path) if project_path else None

    with get_connection(readonly=True) as conn:
        sql = """
            SELECT
                s.id as session_db_id,
                s.session_id,
                s.project_path,
                s.created_at,
                m.role,
                m.content,
                m.sequence,
                bm25(messages_fts) as relevance
            FROM messages_fts
            JOIN messages m ON m.id = messages_fts.rowid
            JOIN sessions s ON s.id = m.session_id
            WHERE messages_fts MATCH ?
        """
        params = [fts_query]

        if project_hash:
            sql += " AND s.project_hash = ?"
            params.append(project_hash)

        sql += " ORDER BY relevance LIMIT ?"
        params.append(limit)

        cursor = conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def full_search(
    query: str,
    project_path: Optional[str] = None,
    detailed: bool = False,
    limit: int = 10
) -> dict:
    """
    Perform a full two-tier search.

    Args:
        query: Search query
        project_path: Optional project filter
        detailed: If True, include tier 2 content
        limit: Maximum results

    Returns:
        Search results dict
    """
    # Tier 1: Fast summary search
    tier1_results = search_tier1(query, project_path, limit)

    result = {
        'query': query,
        'project_path': project_path,
        'result_count': len(tier1_results),
        'sessions': tier1_results
    }

    # Tier 2: Deep content if requested
    if detailed and tier1_results:
        session_ids = [r['id'] for r in tier1_results]
        tier2_results = search_tier2(session_ids)

        # Merge tier 2 content into tier 1 results
        tier2_map = {r['id']: r for r in tier2_results}
        for session in result['sessions']:
            if session['id'] in tier2_map:
                session.update(tier2_map[session['id']])

    return result


def format_results_markdown(results: dict, detailed: bool = False) -> str:
    """
    Format search results as markdown for Claude.

    Args:
        results: Search results from full_search
        detailed: Include expandable full content

    Returns:
        Markdown formatted string
    """
    lines = [
        "# Context Memory Results",
        f"**Query**: \"{results['query']}\"",
        f"**Results**: {results['result_count']} sessions",
        ""
    ]

    if not results['sessions']:
        if not db_exists():
            lines.append("No sessions stored yet. Use /remember to save your first session.")
        else:
            lines.append("No matching sessions found. Try broader search terms or remove the --project filter.")
        return '\n'.join(lines)

    lines.append("---")

    for i, session in enumerate(results['sessions'], 1):
        # Format date
        created = session.get('created_at', 'Unknown date')
        if isinstance(created, str) and 'T' in created:
            created = created.split('T')[0]

        # Get project name from path
        project = session.get('project_path', 'Unknown project')
        if project:
            project = project.replace('\\', '/').split('/')[-1]

        # Rank-based display (BM25 scores are already sorted)
        relevance_display = f"Match #{i}"

        lines.append(f"## {i}. {created} | {project} ({relevance_display})")

        # Brief summary
        brief = session.get('brief', 'No summary available')
        lines.append(f"**Summary**: {brief}")

        # Topics
        topics = session.get('topics', [])
        if topics:
            lines.append(f"**Topics**: {', '.join(topics)}")

        # Technologies
        techs = session.get('technologies')
        if techs:
            if isinstance(techs, str):
                try:
                    techs = json.loads(techs)
                except (json.JSONDecodeError, ValueError):
                    logger.warning("Failed to parse technologies JSON for session %s", session.get('id'))
                    techs = [techs]
            if techs:
                lines.append(f"**Technologies**: {', '.join(techs)}")

        # Key decisions (if available)
        decisions = session.get('key_decisions')
        if decisions:
            if isinstance(decisions, str):
                try:
                    decisions = json.loads(decisions)
                except (json.JSONDecodeError, ValueError):
                    logger.warning("Failed to parse decisions JSON for session %s", session.get('id'))
                    decisions = [decisions]
            if decisions:
                lines.append("**Decisions**:")
                for d in decisions[:MAX_DECISIONS_DISPLAY]:
                    lines.append(f"- {d}")

        # Detailed content in expandable section
        if detailed:
            detailed_text = session.get('detailed', '')
            messages = session.get('messages', [])
            snippets = session.get('code_snippets', [])

            if detailed_text or messages or snippets:
                lines.append("")
                lines.append("<details><summary>Full Context</summary>")
                lines.append("")

                if detailed_text:
                    lines.append("### Detailed Summary")
                    lines.append(detailed_text)
                    lines.append("")

                if messages:
                    lines.append("### Key Messages")
                    for msg in messages[:MAX_MESSAGES_DISPLAY]:
                        role = msg.get('role', 'user').capitalize()
                        content = truncate_text(msg.get('content', ''), MAX_MESSAGE_LENGTH)
                        lines.append(f"**{role}**: {content}")
                        lines.append("")

                if snippets:
                    lines.append("### Code Snippets")
                    for snip in snippets[:MAX_SNIPPETS_DISPLAY]:
                        lang = snip.get('language', '')
                        desc = snip.get('description', 'Code snippet')
                        code = truncate_text(snip.get('code', ''), MAX_SNIPPET_LENGTH)
                        lines.append(f"**{desc}**")
                        lines.append(f"```{lang}")
                        lines.append(code)
                        lines.append("```")
                        lines.append("")

                lines.append("</details>")

        lines.append("")
        lines.append("---")

    return '\n'.join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search context-memory")
    parser.add_argument('query', nargs='?', help="Search query")
    parser.add_argument('--project', nargs='?', const=os.getcwd(), default=None,
                        help="Limit to current project (or specify path)")
    parser.add_argument('--detailed', action='store_true', help="Include full content")
    parser.add_argument('--limit', type=int, default=10, help="Max results")
    parser.add_argument('--format', choices=['json', 'markdown'], default='markdown',
                        help="Output format")

    args = parser.parse_args()

    if not args.query:
        print("Usage: db_search.py <query> [--project PATH] [--detailed] [--limit N]")
        sys.exit(1)

    results = full_search(
        query=args.query,
        project_path=args.project,
        detailed=args.detailed,
        limit=args.limit
    )

    if args.format == 'json':
        print(json.dumps(results, indent=2, default=str))
    else:
        print(format_results_markdown(results, detailed=args.detailed))
