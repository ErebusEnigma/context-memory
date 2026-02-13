# CLAUDE.md — context-memory

## Project Overview

A Claude Code plugin that provides persistent, searchable context storage across sessions using SQLite + FTS5. Users save sessions with `/remember` and search with `/recall`.

## Structure

```
.claude-plugin/plugin.json   # Plugin manifest (version, metadata)
skills/context-memory/        # Skill definition (SKILL.md)
  scripts/
    db_init.py               # Schema creation, verification, stats
    db_save.py               # Session storage logic
    db_search.py             # FTS5 search (tier 1 + tier 2)
    db_utils.py              # Connection management, helpers, VALID_TABLES
commands/                     # /remember and /recall command definitions
hooks/                        # Auto-save stop hook
```

## Dev Commands

```bash
python skills/context-memory/scripts/db_init.py --verify  # Verify schema
python skills/context-memory/scripts/db_init.py --stats   # DB statistics
python -m pytest tests/ -v                                # Run tests
ruff check .                                              # Lint
```

## Conventions

- Python >= 3.8 compatibility required
- Line length: 120 characters
- SQLite FTS5 for full-text search with BM25 ranking
- `VALID_TABLES` is defined once in `db_utils.py` — import it, don't redefine
- Use `get_connection()` context manager for all DB access
- All table names in SQL must be validated against `VALID_TABLES` (no raw f-strings)
- Bare `except:` is not allowed — always catch specific exceptions
