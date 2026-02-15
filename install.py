#!/usr/bin/env python3
"""
Installer for context-memory Claude Code plugin.

Copies skill, commands, and hooks to the correct Claude Code locations.
Stdlib-only, Python >= 3.8 compatible.

Usage:
    python install.py
    python install.py --symlink
    python install.py --skip-hooks --skip-db
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent
CLAUDE_DIR = Path.home() / ".claude"

SKILL_SRC = PLUGIN_ROOT / "skills" / "context-memory"
SKILL_DST = CLAUDE_DIR / "skills" / "context-memory"

COMMANDS_SRC = PLUGIN_ROOT / "commands"
COMMANDS_DST = CLAUDE_DIR / "commands"

HOOKS_SRC = PLUGIN_ROOT / "hooks" / "hooks.json"
SETTINGS_PATH = CLAUDE_DIR / "settings.json"

DB_INIT_SCRIPT = PLUGIN_ROOT / "skills" / "context-memory" / "scripts" / "db_init.py"
DB_DIR = CLAUDE_DIR / "context-memory"


def install_skill(symlink: bool = False) -> str:
    """Copy (or symlink) the skill directory to ~/.claude/skills/context-memory/."""
    SKILL_DST.parent.mkdir(parents=True, exist_ok=True)

    if symlink:
        if SKILL_DST.is_symlink():
            SKILL_DST.unlink()
        elif SKILL_DST.exists():
            shutil.rmtree(SKILL_DST)
        SKILL_DST.symlink_to(SKILL_SRC, target_is_directory=True)
        return "Skill symlinked"

    if SKILL_DST.exists():
        shutil.rmtree(SKILL_DST)
    shutil.copytree(str(SKILL_SRC), str(SKILL_DST),
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    return "Skill copied"


def install_commands() -> str:
    """Copy command files to ~/.claude/commands/."""
    COMMANDS_DST.mkdir(parents=True, exist_ok=True)

    results = []
    for cmd_file in ["remember.md", "recall.md"]:
        src = COMMANDS_SRC / cmd_file
        dst = COMMANDS_DST / cmd_file

        if not src.exists():
            results.append(f"  {cmd_file}: source not found, skipped")
            continue

        src_content = src.read_text(encoding="utf-8")

        if dst.exists():
            dst_content = dst.read_text(encoding="utf-8")
            if dst_content == src_content:
                results.append(f"  {cmd_file}: already up to date")
                continue
            # Back up conflicting file
            bak = dst.with_suffix(dst.suffix + ".bak")
            shutil.copy2(str(dst), str(bak))
            results.append(f"  {cmd_file}: updated (backup at {bak.name})")
        else:
            results.append(f"  {cmd_file}: installed")

        dst.write_text(src_content, encoding="utf-8")

    return "Commands:\n" + "\n".join(results)


def _hook_matches(command: str) -> bool:
    """Check if a hook command string is ours (contains context-memory AND a known script)."""
    return "context-memory" in command and ("db_save.py" in command or "auto_save.py" in command)


def install_hooks() -> str:
    """Merge our stop hook into ~/.claude/settings.json."""
    if not HOOKS_SRC.exists():
        return "Hooks: hooks.json not found, skipped"

    # Read our hook definition
    with open(HOOKS_SRC, encoding="utf-8") as f:
        hooks_data = json.load(f)

    # Extract our matcher group for Stop
    our_stop_matchers = hooks_data.get("hooks", {}).get("Stop", [])
    if not our_stop_matchers:
        return "Hooks: no Stop hooks defined in hooks.json, skipped"

    # Load existing settings
    settings = {}
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            try:
                settings = json.load(f)
            except json.JSONDecodeError:
                return "Hooks: settings.json is malformed, skipped (fix manually)"

    hooks = settings.setdefault("hooks", {})
    stop_list = hooks.setdefault("Stop", [])

    # Check for existing context-memory hook
    for matcher_group in stop_list:
        inner_hooks = matcher_group.get("hooks", [])
        for hook in inner_hooks:
            if hook.get("type") == "command" and _hook_matches(hook.get("command", "")):
                return "Hooks: already installed"

    # Append our matcher group(s)
    stop_list.extend(our_stop_matchers)

    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    return "Hooks: stop hook added to settings.json"


def install_db() -> str:
    """Initialize the database if it doesn't exist."""
    db_path = DB_DIR / "context.db"
    if db_path.exists():
        return "Database: already exists"

    result = subprocess.run(
        [sys.executable, str(DB_INIT_SCRIPT)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return "Database: initialized"
    return f"Database: init failed — {result.stderr.strip() or result.stdout.strip()}"


UNINSTALL_SRC = PLUGIN_ROOT / "uninstall.py"
UNINSTALL_DST = DB_DIR / "uninstall.py"


def install_uninstaller() -> str:
    """Copy uninstall.py to ~/.claude/context-memory/ so it survives clone deletion."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    if not UNINSTALL_SRC.exists():
        return "Uninstaller: source not found, skipped"
    shutil.copy2(str(UNINSTALL_SRC), str(UNINSTALL_DST))
    return f"Uninstaller: copied to {UNINSTALL_DST}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Install context-memory plugin for Claude Code")
    parser.add_argument("--symlink", action="store_true", help="Symlink skill instead of copying (for development)")
    parser.add_argument("--skip-skill", action="store_true", help="Skip skill installation")
    parser.add_argument("--skip-commands", action="store_true", help="Skip command installation")
    parser.add_argument("--skip-hooks", action="store_true", help="Skip hook installation")
    parser.add_argument("--skip-db", action="store_true", help="Skip database initialization")

    args = parser.parse_args()

    print("Installing context-memory plugin...\n")

    results = []

    if not args.skip_skill:
        results.append(install_skill(symlink=args.symlink))

    if not args.skip_commands:
        results.append(install_commands())

    if not args.skip_hooks:
        results.append(install_hooks())

    if not args.skip_db:
        results.append(install_db())

    results.append(install_uninstaller())

    print("\n".join(results))
    print("\nRestart Claude Code for changes to take effect.")
    print(f"To uninstall later: python {UNINSTALL_DST}")


if __name__ == "__main__":
    main()
