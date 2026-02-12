# Changelog

## [1.0.2] - 2026-02-12

### Fixed
- `--force` flag on `db_init.py` now properly resets the database by deleting the file before recreating (#19)
- Code snippets are now searchable via FTS5 — added `code_snippets_fts` virtual table indexing `code`, `description`, and `file_path` (#16b)

### Added
- FTS sync triggers (`code_snippets_ai`, `code_snippets_ad`, `code_snippets_au`) for automatic code snippet indexing
- Code snippet FTS search in `search_tier1()` alongside summaries and topics
- Integration test suite (`test_bugfixes.py`) covering force reset and snippet search

## [1.0.1] - 2026-02-12

### Fixed
- `--project` flag now works as both a bare flag (uses cwd) and with a path argument
- BM25 relevance display no longer shows `0.0` — replaced with rank-based `Match #N`
- Windows path hashing mismatch between MSYS/Git Bash (`/c/Users/...`) and native Windows (`C:\Users\...`) paths; added case-insensitive normalization
- Stop hook no longer references undefined `$CLAUDE_PLUGIN_ROOT` and `$CLAUDE_SESSION_ID` environment variables
- SQL injection vector in `get_table_count()` and `get_stats()` via table name validation

### Added
- `--decisions`, `--problems`, `--technologies`, and `--outcome` CLI arguments to `db_save.py`

## [1.0.0] - 2026-02-12

### Added
- `/remember [note]` command for saving sessions with optional annotations
- `/recall <query>` command with `--project`, `--detailed`, and `--limit` options
- Context-memory skill with natural language trigger phrases
- SQLite + FTS5 database with two-tier search (summaries + messages)
- BM25 relevance ranking with Porter stemming
- Topic extraction and categorization
- Code snippet storage with language detection
- Project-scoped and global search modes
- Optional Stop hook for auto-saving sessions
- Full database schema with FTS sync triggers
