#!/usr/bin/env python3
"""
Cross-platform auto-save wrapper for the context-memory stop hook.

Replaces the Bash one-liner in hooks.json so the hook works on Windows
(CMD, PowerShell) as well as Unix shells. Exits silently on any failure
because hooks must never block Claude Code.

Usage (from hooks.json):
    python ~/.claude/skills/context-memory/scripts/auto_save.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    scripts_dir = Path(__file__).resolve().parent
    db_save_script = scripts_dir / "db_save.py"

    if not db_save_script.exists():
        return

    project_path = os.getcwd()
    project_name = os.path.basename(project_path)

    # Get git branch (best-effort)
    git_branch = ""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            git_branch = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass

    topics = "auto-save"
    if git_branch:
        topics = f"{topics},{git_branch}"

    session_id = f"auto-{int(time.time())}"
    brief = f"Auto-saved session: {project_name}"

    subprocess.run(
        [
            sys.executable,
            str(db_save_script),
            "--auto",
            "--session-id", session_id,
            "--project-path", project_path,
            "--brief", brief,
            "--topics", topics,
        ],
        capture_output=True,
        timeout=30,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
