#!/usr/bin/env python3
"""
PreCompact hook handler for context-memory plugin.

Saves the full conversation transcript to the database before context
compaction occurs. This preserves ALL messages without truncation or
sampling, so they can be reloaded after compaction via the
context_load_checkpoint MCP tool.

Usage (from hooks.json):
    python ~/.claude/skills/context-memory/scripts/pre_compact_save.py

Hook input (JSON via stdin):
    {
        "session_id": "abc123",
        "transcript_path": "/path/to/transcript.jsonl",
        "cwd": "/project/dir",
        "hook_event_name": "PreCompact",
        "trigger": "auto"  // or "manual"
    }
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

try:
    from .db_utils import extract_text_content, read_hook_input
except ImportError:
    from db_utils import extract_text_content, read_hook_input


def parse_transcript_full(path: str) -> list[dict]:
    """
    Read a Claude Code JSONL transcript and extract ALL messages.

    Unlike auto_save.py, this does NOT sample or truncate.
    Preserves full content of every user/assistant message.

    Returns list of {"role": ..., "content": ...} dicts.
    """
    if not path or not os.path.isfile(path):
        return []

    messages = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type", "")
                if entry_type not in ("user", "assistant"):
                    continue

                msg = entry.get("message", {})
                raw_content = msg.get("content", "")
                text = extract_text_content(raw_content)
                if text:
                    messages.append({"role": entry_type, "content": text})
    except OSError:
        return []

    return messages



def save_checkpoint(
    session_id: str,
    project_path: str,
    trigger: str,
    messages: list[dict],
) -> Optional[int]:
    """
    Save a context checkpoint to the database.

    Stores the full message list as a single JSON blob for speed.
    Auto-increments checkpoint_number per session_id.

    Returns the checkpoint row ID, or None on failure.
    """
    # Import here to avoid import errors if DB modules aren't on path yet
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    import contextlib
    import io

    from db_init import ensure_schema_current, init_database
    from db_utils import db_exists, get_connection, hash_project_path, normalize_project_path

    # Capture stdout to suppress "Database initialized at ..." print from init_database
    with contextlib.redirect_stdout(io.StringIO()):
        if not db_exists():
            init_database()
        else:
            ensure_schema_current()

    norm_path = normalize_project_path(project_path) if project_path else None
    proj_hash = hash_project_path(project_path) if project_path else None
    messages_json = json.dumps(messages)

    with get_connection() as conn:
        # Get next checkpoint number for this session
        cursor = conn.execute(
            "SELECT COALESCE(MAX(checkpoint_number), 0) FROM context_checkpoints WHERE session_id = ?",
            (session_id,),
        )
        next_num = cursor.fetchone()[0] + 1

        cursor = conn.execute(
            """
            INSERT INTO context_checkpoints
                (session_id, project_path, project_hash, checkpoint_number, trigger_type, messages, message_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, norm_path, proj_hash, next_num, trigger, messages_json, len(messages)),
        )
        checkpoint_id = cursor.lastrowid
        conn.commit()

    return checkpoint_id


def main() -> None:
    hook_input = read_hook_input()
    if not hook_input:
        return

    session_id = hook_input.get("session_id")
    transcript_path = hook_input.get("transcript_path")
    cwd = hook_input.get("cwd") or os.getcwd()
    trigger = hook_input.get("trigger", "auto")

    if not session_id or not transcript_path:
        return

    messages = parse_transcript_full(transcript_path)
    if not messages:
        return

    checkpoint_id = save_checkpoint(
        session_id=session_id,
        project_path=cwd,
        trigger=trigger,
        messages=messages,
    )

    # Output result as JSON (captured by hook runner, not displayed)
    if checkpoint_id is not None:
        print(json.dumps({
            "checkpoint_id": checkpoint_id,
            "message_count": len(messages),
            "trigger": trigger,
        }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        print(traceback.format_exc(), file=sys.stderr)
