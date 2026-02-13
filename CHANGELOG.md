# Changelog

## [Unreleased]

## [1.0.4] - 2026-02-13

### Fixed
- `db_init.py --verify` no longer crashes on fresh install when database doesn't exist
- `get_stats()` returns empty dict instead of crashing when database is missing

### Added
- Post-install setup instructions in README (DB init, hook registration, verify)
- Hook upgrade guide in README for users with older stop hook versions
- Tests for `--verify` and `--stats` on missing database

## [1.0.3] - 2026-02-12

### Fixed
- Bare `except:` clauses in `db_search.py` replaced with `except (json.JSONDecodeError, ValueError):`
- Version mismatch in `plugin.json` (was `1.0.0`, now `1.0.3`)
- Duplicate `VALID_TABLES` definition in `db_init.py` — now imported from `db_utils`
- Author name standardized to `ErebusEnigma` (no underscore) across LICENSE, plugin.json, README

### Added
- GitHub Actions CI workflow with ruff linting and test suite
- `pyproject.toml` with project metadata and ruff configuration
- README badges (license, Python version, latest release) and table of contents
- `CONTRIBUTING.md` with development setup and contribution guidelines
- GitHub issue templates (bug report, feature request) and PR template
- `CLAUDE.md` with project conventions for Claude Code
- Extended `.gitignore` with pytest, coverage, mypy, and ruff cache entries

## [1.0.2] - 2026-02-12

### Fixed
- `--force` flag on `db_init.py` now properly resets the database by deleting the file before recreating (#19)
- Code snippets are now searchable via FTS5 — added `code_snippets_fts` virtual table indexing `code`, `description`, and `file_path` (#16b)

### Added
- FTS sync triggers (`code_snippets_ai`, `code_snippets_ad`, `code_snippets_au`) for automatic code snippet indexing
- Code snippet FTS search in `search_tier1()` alongside summaries and topics
- Integration tests covering force reset and snippet search

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
