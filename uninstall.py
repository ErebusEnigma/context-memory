#!/usr/bin/env python3
"""
Uninstaller for context-memory Claude Code plugin.

Removes skill, commands, hooks, and optionally the database.
Stdlib-only, Python >= 3.8 compatible.

Usage:
    python uninstall.py
    python uninstall.py --keep-data
    python uninstall.py --remove-data
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent
CLAUDE_DIR = Path.home() / ".claude"

SKILL_DST = CLAUDE_DIR / "skills" / "context-memory"
COMMANDS_DST = CLAUDE_DIR / "commands"
COMMANDS_SRC = PLUGIN_ROOT / "commands"
SETTINGS_PATH = CLAUDE_DIR / "settings.json"
DB_DIR = CLAUDE_DIR / "context-memory"


def uninstall_skill() -> str:
    """Remove ~/.claude/skills/context-memory/."""
    if SKILL_DST.is_symlink():
        SKILL_DST.unlink()
        return "Skill: symlink removed"
    if SKILL_DST.exists():
        shutil.rmtree(SKILL_DST)
        return "Skill: removed"
    return "Skill: not installed"


def uninstall_commands() -> str:
    """Remove our command files from ~/.claude/commands/."""
    results = []
    for cmd_file in ["remember.md", "recall.md"]:
        dst = COMMANDS_DST / cmd_file
        src = COMMANDS_SRC / cmd_file

        if not dst.exists():
            results.append(f"  {cmd_file}: not installed")
            continue

        # Ownership check: only remove if content matches our source
        if src.exists():
            src_content = src.read_text(encoding="utf-8")
            dst_content = dst.read_text(encoding="utf-8")
            if dst_content != src_content:
                results.append(f"  {cmd_file}: modified by user, skipped")
                continue

        dst.unlink()

        # Restore backup if present
        bak = dst.with_suffix(dst.suffix + ".bak")
        if bak.exists():
            bak.rename(dst)
            results.append(f"  {cmd_file}: removed (restored backup)")
        else:
            results.append(f"  {cmd_file}: removed")

    return "Commands:\n" + "\n".join(results)


def _hook_matches(command: str) -> bool:
    """Check if a hook command string is ours."""
    return "context-memory" in command and "db_save.py" in command


def uninstall_hooks() -> str:
    """Remove our hooks from ~/.claude/settings.json."""
    if not SETTINGS_PATH.exists():
        return "Hooks: settings.json not found"

    with open(SETTINGS_PATH, encoding="utf-8") as f:
        try:
            settings = json.load(f)
        except json.JSONDecodeError:
            return "Hooks: settings.json is malformed, skipped"

    hooks = settings.get("hooks", {})
    stop_list = hooks.get("Stop", [])

    if not stop_list:
        return "Hooks: no Stop hooks found"

    # Filter out matcher groups that contain our hook
    original_count = len(stop_list)
    filtered = []
    for matcher_group in stop_list:
        inner_hooks = matcher_group.get("hooks", [])
        has_ours = any(
            hook.get("type") == "command" and _hook_matches(hook.get("command", ""))
            for hook in inner_hooks
        )
        if not has_ours:
            filtered.append(matcher_group)

    if len(filtered) == original_count:
        return "Hooks: not installed"

    # Clean up empty structures
    if filtered:
        hooks["Stop"] = filtered
    else:
        del hooks["Stop"]

    if hooks:
        settings["hooks"] = hooks
    else:
        del settings["hooks"]

    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    return "Hooks: removed from settings.json"


def uninstall_data(remove: bool = False) -> str:
    """Handle database removal."""
    if not DB_DIR.exists():
        return "Database: no data found"

    if not remove:
        return f"Database: preserved at {DB_DIR} (use --remove-data to delete)"

    shutil.rmtree(DB_DIR)
    return "Database: removed"


def main() -> None:
    parser = argparse.ArgumentParser(description="Uninstall context-memory plugin from Claude Code")
    data_group = parser.add_mutually_exclusive_group()
    data_group.add_argument("--keep-data", action="store_true", help="Keep database (skip prompt)")
    data_group.add_argument("--remove-data", action="store_true", help="Delete database without prompting")

    args = parser.parse_args()

    print("Uninstalling context-memory plugin...\n")

    results = [
        uninstall_skill(),
        uninstall_commands(),
        uninstall_hooks(),
    ]

    # Handle database
    if args.remove_data:
        results.append(uninstall_data(remove=True))
    elif args.keep_data:
        results.append(uninstall_data(remove=False))
    else:
        # Interactive prompt
        if DB_DIR.exists():
            try:
                answer = input(f"Delete database at {DB_DIR}? [y/N] ").strip().lower()
                results.append(uninstall_data(remove=answer in ("y", "yes")))
            except (EOFError, KeyboardInterrupt):
                results.append(uninstall_data(remove=False))
        else:
            results.append("Database: no data found")

    print("\n".join(results))
    print(f"\nTo also remove the plugin source: rm -rf {PLUGIN_ROOT}")


if __name__ == "__main__":
    main()
