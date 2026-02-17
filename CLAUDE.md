# CLAUDE.md — context-memory

## Project Overview

A Claude Code plugin that provides persistent, searchable context storage across sessions using SQLite + FTS5. Users save sessions with `/remember` and search with `/recall`.

## Structure

```
.claude-plugin/plugin.json   # Plugin manifest (version, metadata)
.mcp.json                    # MCP server config (project-level)
skills/context-memory/        # Skill definition (SKILL.md)
  scripts/
    __init__.py              # Package init, version, public API re-exports
    db_init.py               # Schema creation, verification, stats, migrations
    db_save.py               # Session storage logic, deduplication
    db_search.py             # FTS5 search (tier 1 + tier 2)
    db_prune.py              # Database pruning (by age/count)
    db_utils.py              # Connection management, helpers, VALID_TABLES
    mcp_server.py            # MCP server (FastMCP, stdio transport)
    dashboard.py             # Web dashboard (Flask REST API + SPA)
    auto_save.py             # Stop hook: cross-platform auto-save wrapper
    pre_compact_save.py      # PreCompact hook: saves full context before compaction
    static/                  # Dashboard frontend (vanilla JS, CSS)
  references/
    schema-reference.md      # Full database schema reference
commands/                     # /remember and /recall command definitions
hooks/                        # Auto-save stop hook + PreCompact checkpoint hook
```

## Dev Commands

```bash
python skills/context-memory/scripts/db_init.py --verify  # Verify schema
python skills/context-memory/scripts/db_init.py --stats   # DB statistics
python skills/context-memory/scripts/db_prune.py --max-sessions 100 --dry-run  # Preview prune
python skills/context-memory/scripts/dashboard.py          # Launch web dashboard (localhost:5111)
python -m pytest tests/ -v                                # Run tests
ruff check .                                              # Lint
```

## Conventions

- Python >= 3.8 compatibility required
- Line length: 120 characters
- SQLite FTS5 for full-text search with summary-ranked BM25 + multi-source boost
- `VALID_TABLES` is defined once in `db_utils.py` — import it, don't redefine
- `STATS_TABLES` excludes internal tables (like `schema_version`) from user-facing stats
- Use `get_connection()` context manager for all DB access
- All table names in SQL must be validated against `VALID_TABLES` (no raw f-strings)
- Bare `except:` is not allowed — always catch specific exceptions
- Schema changes require a new migration in `MIGRATIONS` dict and `CURRENT_SCHEMA_VERSION` bump

## Compact Instructions

When summarizing this conversation for compaction, ALWAYS preserve:
- The current task and what step we're on
- All file paths being actively modified
- Key decisions made and their rationale
- Any error states or blockers being worked on
- Test results and their pass/fail status
- The specific user request that started the current work

## Post-Compaction Context Recovery

After context has been compacted, you can restore the full pre-compaction conversation
by calling the `context_load_checkpoint` MCP tool with the current project path.
Use this when you need details that were lost during summarization — specific code
that was discussed, exact error messages, file contents that were read, etc.
Do NOT call this automatically on every compaction — only when you actually need
detail that the compaction summary doesn't provide.
