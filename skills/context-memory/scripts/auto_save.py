#!/usr/bin/env python3
"""
Cross-platform auto-save wrapper for the context-memory stop hook.

Reads the JSON payload that Claude Code pipes via stdin (contains session_id,
transcript_path, stop_hook_active, cwd) and, when a transcript is available,
saves a rich session with actual conversation messages.  Falls back to a
minimal CLI-args save when stdin or the transcript is unavailable.

Usage (from hooks.json):
    python ~/.claude/skills/context-memory/scripts/auto_save.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


def read_hook_input() -> Optional[dict]:
    """Read the JSON payload from stdin. Return dict or None on failure."""
    try:
        if sys.stdin is None or sys.stdin.closed:
            return None
        raw = sys.stdin.read()
        if not raw or not raw.strip():
            return None
        return json.loads(raw)
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def extract_text_content(content) -> str:
    """
    Extract plain text from a message's content field.

    Handles both plain string content and the list-of-blocks format
    (keeps only "type": "text" blocks, skips tool_use/tool_result).
    Truncates to 1000 chars.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content[:1000]
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if text:
                    parts.append(text)
        joined = "\n".join(parts)
        return joined[:1000]
    return ""


def parse_transcript(path: str, max_messages: int = 15) -> list[dict]:
    """
    Read a Claude Code JSONL transcript and extract user/assistant messages.

    If more than max_messages are found, keeps first 5 + last (max_messages-5)
    to preserve context from the beginning and end of the conversation.

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

    # Head + tail sampling when over the limit
    if len(messages) > max_messages:
        head = 5
        tail = max_messages - head
        messages = messages[:head] + messages[-tail:]

    return messages


def build_brief(messages: list[dict], project_name: str) -> str:
    """
    Build a descriptive brief from the first user message.

    Falls back to "Auto-saved session: {project_name}" when no user messages
    are available.  The "Auto-saved session:" prefix is required so that
    the dedup LIKE pattern in should_skip_auto_save() continues to work.
    """
    for msg in messages:
        if msg.get("role") == "user":
            text = msg["content"].strip().replace("\n", " ")[:100]
            return f"Auto-saved session: {text}"
    return f"Auto-saved session: {project_name}"


def main() -> None:
    scripts_dir = Path(__file__).resolve().parent
    db_save_script = scripts_dir / "db_save.py"

    if not db_save_script.exists():
        return

    # ── Read hook stdin ──────────────────────────────────────────────
    hook_input = read_hook_input()

    # Loop-prevention: if Claude Code tells us a hook is already active, bail
    if hook_input and hook_input.get("stop_hook_active"):
        return

    # Extract fields from hook input (all optional)
    session_id = (hook_input or {}).get("session_id") or f"auto-{int(time.time())}"
    transcript_path = (hook_input or {}).get("transcript_path")
    cwd = (hook_input or {}).get("cwd") or os.getcwd()

    project_path = cwd
    project_name = os.path.basename(project_path)

    # ── Git branch (best-effort) ─────────────────────────────────────
    git_branch = ""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_path,
        )
        if result.returncode == 0:
            git_branch = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass

    topics = ["auto-save"]
    if git_branch:
        topics.append(git_branch)

    # ── Parse transcript ─────────────────────────────────────────────
    messages = parse_transcript(transcript_path) if transcript_path else []
    brief = build_brief(messages, project_name)

    # ── Save ─────────────────────────────────────────────────────────
    if messages:
        # Rich path: pipe full JSON payload to db_save.py --auto --json -
        payload = {
            "session_id": session_id,
            "project_path": project_path,
            "summary": {"brief": brief},
            "topics": topics,
            "messages": messages,
        }
        subprocess.run(
            [
                sys.executable,
                str(db_save_script),
                "--auto",
                "--json", "-",
                "--project-path", project_path,
            ],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=30,
        )
    else:
        # Fallback path: minimal CLI-args save (same as old behaviour)
        subprocess.run(
            [
                sys.executable,
                str(db_save_script),
                "--auto",
                "--session-id", session_id,
                "--project-path", project_path,
                "--brief", brief,
                "--topics", ",".join(topics),
            ],
            capture_output=True,
            timeout=30,
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        print(traceback.format_exc(), file=sys.stderr)
