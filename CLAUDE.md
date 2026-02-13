# CLAUDE.md — context-memory

## Project Overview

A Claude Code plugin that provides persistent, searchable context storage across sessions using SQLite + FTS5. Users save sessions with `/remember` and search with `/recall`.

## Structure

```
.claude-plugin/plugin.json   # Plugin manifest (version, metadata)
skills/context-memory/        # Skill definition (SKILL.md)
  scripts/
    db_init.py               # Schema creation, verification, stats, migrations
    db_save.py               # Session storage logic, deduplication
    db_search.py             # FTS5 search (tier 1 + tier 2)
    db_prune.py              # Database pruning (by age/count)
    db_utils.py              # Connection management, helpers, VALID_TABLES
commands/                     # /remember and /recall command definitions
hooks/                        # Auto-save stop hook (with dedup)
```

## Dev Commands

```bash
python skills/context-memory/scripts/db_init.py --verify  # Verify schema
python skills/context-memory/scripts/db_init.py --stats   # DB statistics
python skills/context-memory/scripts/db_prune.py --max-sessions 100 --dry-run  # Preview prune
python -m pytest tests/ -v                                # Run tests
ruff check .                                              # Lint
```

## Conventions

- Python >= 3.8 compatibility required
- Line length: 120 characters
- SQLite FTS5 for full-text search with BM25 ranking
- `VALID_TABLES` is defined once in `db_utils.py` — import it, don't redefine
- `STATS_TABLES` excludes internal tables (like `schema_version`) from user-facing stats
- Use `get_connection()` context manager for all DB access
- All table names in SQL must be validated against `VALID_TABLES` (no raw f-strings)
- Bare `except:` is not allowed — always catch specific exceptions
- Schema changes require a new migration in `MIGRATIONS` dict and `CURRENT_SCHEMA_VERSION` bump
