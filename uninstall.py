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

CLAUDE_DIR = Path.home() / ".claude"
PLUGIN_ROOT = Path(__file__).resolve().parent

SKILL_DST = CLAUDE_DIR / "skills" / "context-memory"
COMMANDS_DST = CLAUDE_DIR / "commands"
# Source commands for ownership check — may not exist if clone was deleted
COMMANDS_SRC = PLUGIN_ROOT / "commands"
SETTINGS_PATH = CLAUDE_DIR / "settings.json"
DB_DIR = CLAUDE_DIR / "context-memory"

# Known command files installed by this plugin
OUR_COMMAND_FILES = ["remember.md", "recall.md"]


def uninstall_skill() -> str:
    """Remove ~/.claude/skills/context-memory/."""
    if SKILL_DST.is_symlink():
        SKILL_DST.unlink()
        return "Skill: symlink removed"
    if SKILL_DST.exists():
        shutil.rmtree(SKILL_DST)
        return "Skill: removed"
    return "Skill: not installed"


def uninstall_commands(force: bool = False) -> str:
    """Remove our command files from ~/.claude/commands/."""
    results = []
    skipped = []
    for cmd_file in OUR_COMMAND_FILES:
        dst = COMMANDS_DST / cmd_file
        src = COMMANDS_SRC / cmd_file

        if not dst.exists():
            results.append(f"  {cmd_file}: not installed")
            continue

        # Ownership check: only skip if source exists AND content differs (unless --force)
        if not force and src.exists():
            src_content = src.read_text(encoding="utf-8")
            dst_content = dst.read_text(encoding="utf-8")
            if dst_content != src_content:
                results.append(f"  {cmd_file}: modified by user, skipped (use --force to remove)")
                skipped.append(str(dst))
                continue

        dst.unlink()

        # Restore backup if present
        bak = dst.with_suffix(dst.suffix + ".bak")
        if bak.exists():
            bak.rename(dst)
            results.append(f"  {cmd_file}: removed (restored backup)")
        else:
            results.append(f"  {cmd_file}: removed")

    msg = "Commands:\n" + "\n".join(results)
    if skipped:
        msg += "\n  Warning: orphan files remain: " + ", ".join(skipped)
    return msg


def _hook_matches(command: str) -> bool:
    """Check if a hook command string is ours."""
    normalized = command.replace("\\", "/")
    return "context-memory" in normalized and (
        "db_save.py" in normalized or "auto_save.py" in normalized or "pre_compact_save.py" in normalized
    )


def uninstall_hooks() -> str:
    """Remove our hooks (Stop, PreCompact, etc.) from ~/.claude/settings.json."""
    if not SETTINGS_PATH.exists():
        return "Hooks: settings.json not found"

    with open(SETTINGS_PATH, encoding="utf-8") as f:
        try:
            settings = json.load(f)
        except json.JSONDecodeError:
            return "Hooks: settings.json is malformed, skipped"

    hooks = settings.get("hooks", {})
    if not hooks:
        return "Hooks: no hooks found"

    removed_types = []

    for hook_type in list(hooks.keys()):
        type_list = hooks[hook_type]
        if not isinstance(type_list, list):
            continue

        original_count = len(type_list)
        filtered = []
        for matcher_group in type_list:
            inner_hooks = matcher_group.get("hooks", [])
            has_ours = any(
                hook.get("type") == "command" and _hook_matches(hook.get("command", ""))
                for hook in inner_hooks
            )
            if not has_ours:
                filtered.append(matcher_group)

        if len(filtered) < original_count:
            removed_types.append(hook_type)
            if filtered:
                hooks[hook_type] = filtered
            else:
                del hooks[hook_type]

    if not removed_types:
        return "Hooks: not installed"

    if hooks:
        settings["hooks"] = hooks
    else:
        del settings["hooks"]

    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    return "Hooks: removed " + ", ".join(removed_types) + " from settings.json"


MCP_CONFIG_PATH = CLAUDE_DIR / "mcp_servers.json"


def uninstall_mcp() -> str:
    """Remove the context-memory entry from ~/.claude/mcp_servers.json."""
    if not MCP_CONFIG_PATH.exists():
        return "MCP server: mcp_servers.json not found"

    try:
        config = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "MCP server: mcp_servers.json is malformed, skipped"

    if "context-memory" not in config:
        return "MCP server: not registered"

    del config["context-memory"]

    if config:
        MCP_CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    else:
        MCP_CONFIG_PATH.unlink()

    return "MCP server: removed from mcp_servers.json"


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
    parser.add_argument("--force", action="store_true", help="Remove modified command files without ownership check")
    data_group = parser.add_mutually_exclusive_group()
    data_group.add_argument("--keep-data", action="store_true", help="Keep database (skip prompt)")
    data_group.add_argument("--remove-data", action="store_true", help="Delete database without prompting")

    args = parser.parse_args()

    print("Uninstalling context-memory plugin...\n")

    results = [
        uninstall_skill(),
        uninstall_commands(force=args.force),
        uninstall_hooks(),
        uninstall_mcp(),
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
    print("\nDone. Restart Claude Code for changes to take effect.")


if __name__ == "__main__":
    main()
