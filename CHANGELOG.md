# Changelog

## [1.3.1] - 2026-02-17

### Fixed
- `install.py`: generalized hook installation to loop over all hook types (Stop, PreCompact, etc.) instead of hardcoding Stop-only
- `uninstall.py`: generalized hook removal to iterate all hook type keys, not just Stop
- `_hook_matches()` in both install/uninstall: now recognizes `pre_compact_save.py` alongside `auto_save.py` and `db_save.py`
- `tests/test_dashboard.py`: added `pytest.importorskip("flask_cors")` guard to prevent import errors when flask-cors is not installed

### Changed
- Extracted shared `read_hook_input()` and `extract_text_content(content, max_length=None)` to `db_utils.py`, replacing duplicate implementations in `auto_save.py` and `pre_compact_save.py`
- `__init__.py`: added exports for `save_checkpoint`, `prune_checkpoints`, `read_hook_input`, and `extract_text_content`
- Comprehensive README rewrite: added Architecture section, CI/test badges, CLI Tools section, Testing section; expanded Features, Installation, How It Works, and Web Dashboard sections to match actual codebase capabilities
- `schema-reference.md`: added `context_checkpoints` table documentation and Schema Migrations section

## [1.3.0] - 2026-02-17

### Added
- **Pre-compact context checkpoints** — saves the full conversation transcript to the database before context compaction, enabling seamless recovery of lost detail
  - `pre_compact_save.py` hook handler: captures all messages without truncation or sampling
  - Schema v4: `context_checkpoints` table with session/project indexes
  - `context_load_checkpoint` MCP tool for on-demand retrieval by session ID or project path
  - Checkpoint pruning in `db_prune.py` (per-session and age-based)
  - PreCompact hook registered in `hooks/hooks.json`
- CLAUDE.md compact instructions: guides the summarizer on what to preserve during compaction
- Post-compaction context recovery instructions in CLAUDE.md
- 50 comprehensive dashboard API tests covering all 17 REST endpoints
- 37 new tests for the pre-compact checkpoint system (571 lines)
- `pytest.importorskip` pattern for optional Flask dependency in dashboard tests

### Changed
- `db_utils.py`: `VALID_TABLES` and `STATS_TABLES` now include `context_checkpoints`
- `db_init.py`: schema version bumped to 4; added `_migrate_v3_to_v4` migration
- `mcp_server.py`: registered `context_load_checkpoint` tool
- `.github/workflows/ci.yml`: added Flask to CI test dependencies
- `conftest.py`: `isolated_db` fixture now patches `pre_compact_save` module

## [1.2.0] - 2026-02-17

### Added
- **Web dashboard** (`dashboard.py`) — Flask-based single-page app for browsing, searching, managing, and analyzing stored sessions
  - REST API with 17 endpoints: sessions CRUD, full-text search, analytics (timeline, topics, projects, outcomes, technologies), database management (init, prune, export), and search hint chips
  - Frontend SPA with hash-based routing, dark/light theme toggle, session detail views, code syntax highlighting (Highlight.js), and interactive charts (Chart.js)
  - Session editing (summary, topics, user notes) and deletion from the UI
  - Database export as JSON, prune with dry-run preview
- `context_dashboard` MCP tool to launch the web dashboard from any MCP-compatible client
- 73 new tests covering high and medium priority gaps across install, uninstall, search, save, init, utils, and auto-save modules

### Changed
- `.gitignore` expanded with additional patterns: build artifacts (`*.whl`, `*.tar.gz`, `MANIFEST`), SQLite journal files, coverage variants, test framework caches (`.tox/`, `.nox/`, `.hypothesis/`), log files

## [1.1.0] - 2026-02-16

### Added
- MCP server (`mcp_server.py`) exposing `context_search`, `context_save`, `context_stats`, and `context_init` tools via stdio transport using FastMCP (requires Python >= 3.10)
- `.mcp.json` project-level MCP server configuration (dev-only; uses relative paths)
- `install.py`: `install_mcp()` function and `--skip-mcp` flag for automatic MCP server registration
- `pyproject.toml`: optional `[project.optional-dependencies] mcp` group
- `uninstall.py`: `--force` flag to remove modified command files without ownership check
- `uninstall.py`: `uninstall_mcp()` removes `context-memory` entry from `~/.claude/mcp_servers.json`
- `auto_save.py`: `read_hook_input()`, `extract_text_content()`, `parse_transcript()`, `build_brief()` functions
- `auto_save.py`: Loop prevention via `stop_hook_active` flag from hook input
- 72 new tests across `test_auto_save.py` (26), `test_mcp_server.py` (19), `test_install.py` (16), `test_uninstall.py` (11)

### Fixed
- `db_init.py`: Recursive `sessions_updated` trigger — added `WHEN NEW.updated_at = OLD.updated_at` guard to prevent infinite recursion (schema migration v3)
- `db_save.py`: `save_topics()` returned `len(topics)` instead of counting actually inserted topics (blank entries were skipped but still counted)
- `db_save.py`: `save_messages()` set `message_count` to batch size instead of total rows when appending (`replace=False`)
- `db_save.py`: Missing `encoding='utf-8'` on `open()` for `--json` file path
- `db_init.py`: `verify_schema()` crashed with `OperationalError` when database file didn't exist; now returns a descriptive dict
- `db_search.py`: N+1 query problem in `search_tier1` (per-result topic fetch) and `search_tier2` (per-session loop with 4 queries); replaced with batch `WHERE IN` queries
- `auto_save.py`: Silent `except Exception: pass` replaced with `traceback.print_exc()` to stderr for debuggability
- `tests/test_db_save.py`: Environment variable leak — `os.environ["CONTEXT_MEMORY_DB_PATH"]` set without cleanup; replaced with direct sqlite3 access
- `__init__.py`: Version `1.0.6` out of sync — updated to `1.1.0`
- `_hook_matches()` in `install.py` and `uninstall.py` now normalizes backslashes to forward slashes, fixing orphan hook detection on Windows
- `mcp_server.py` adds its own directory to `sys.path` so sibling imports (`db_init`, `db_save`, `db_search`) work regardless of working directory
- `install_mcp()` writes directly to `~/.claude/mcp_servers.json` instead of shelling out to `claude mcp add`, which fails inside a Claude Code session
- `.mcp.json` now includes `cwd` field for local dev robustness
- `uninstall_commands()` now warns about orphan files when skipping modified commands (with `--force` override)

### Changed
- `auto_save.py`: Reads Claude Code's stdin JSON payload (`session_id`, `transcript_path`, `stop_hook_active`, `cwd`) instead of generating synthetic IDs
- `auto_save.py`: Parses JSONL transcript to extract real user/assistant messages (head+tail sampling when >15 messages)
- `auto_save.py`: Brief now uses first user message text instead of generic project name
- `auto_save.py`: Rich path pipes full JSON to `db_save.py --auto --json -`; fallback path preserves old CLI-args behaviour
- `hooks/hooks.json`: Added `"timeout": 120` to Stop hook (was using default 600s)
- `db_save.py`: `save_full_session()` accepts `metadata` parameter, passed through to `save_session()`
- `db_save.py`: `--auto` + `--json` combined now injects `{"auto_save": true}` into payload metadata
- `db_prune.py`: Removed redundant FTS index rebuild after pruning — FTS sync triggers already handle row-level deletes
- `db_utils.py`: Removed dead `escape_fts_query()` function (unused; `format_fts_query()` is used instead)
- `db_init.py`: `get_stats()` now validates table names against `VALID_TABLES` before use in SQL
- `.github/workflows/ci.yml`: Added `mcp` to CI dependencies so MCP tests run instead of being silently skipped

## [1.0.9] - 2026-02-15

### Fixed
- Windows: stop hook failed because `cmd.exe` does not expand `~` in paths — installer now resolves `~` to the full home directory at install time on Windows

### Changed
- `install.py`: `install_hooks()` now updates outdated hooks in-place (supports upgrades from v1.0.8)
- `install.py`: added `_platform_hook_command()` helper for platform-specific path expansion

### Added
- `tests/test_install.py` — tests for hook path expansion and upgrade logic

## [1.0.8] - 2026-02-15

### Fixed
- Stop hook now works on Windows (CMD, PowerShell) — replaced Bash one-liner with cross-platform `auto_save.py` Python wrapper

### Changed
- `hooks/hooks.json` command simplified to `python ~/.claude/skills/context-memory/scripts/auto_save.py`
- `_hook_matches()` in `install.py` and `uninstall.py` now detects both old (`db_save.py`) and new (`auto_save.py`) hook formats
- README: removed Windows shell warning, noted cross-platform hook support

### Added
- `skills/context-memory/scripts/auto_save.py` — cross-platform stop hook wrapper
- `tests/test_auto_save.py` — tests for the new wrapper script

## [1.0.7] - 2026-02-15

### Fixed
- Windows: backslash paths in `project_path` no longer cause `json.JSONDecodeError` (normalized to forward slashes)
- Write tool pre-read requirement no longer blocks saves: `--json -` reads from stdin

### Added
- `--json -` reads JSON from stdin, eliminating temp file requirements
- `normalize_project_path()` in `db_utils.py` for cross-platform path storage

### Changed
- SKILL.md and remember.md now use `--json -` heredoc pipe instead of temp files
- `save_session()` normalizes `project_path` before storage

## [1.0.6] - 2026-02-13

### Added
- Schema versioning with `schema_version` table and migration system
- `get_schema_version()`, `apply_migrations()`, `ensure_schema_current()` for automatic DB upgrades
- Session deduplication: `should_skip_auto_save()` prevents redundant auto-saves when `/remember` was used recently
- `--auto` and `--dedup-window` CLI flags for `db_save.py`
- `db_prune.py` for database maintenance: prune by age (`--max-age`), count (`--max-sessions`), or both
- `--dry-run` flag for prune to preview deletions without executing
- FTS index rebuild after pruning for guaranteed consistency
- `CONTEXT_MEMORY_DB_PATH` environment variable override for custom DB location
- `STATS_TABLES` constant to exclude internal tables from statistics
- Integration tests: save/search flow, CLI entry points, deduplication, pruning, error handling

### Fixed
- `/remember` now saves complete session data (detailed summary, decisions, messages, code snippets) via `--json` path instead of the subset-only CLI args path
- `--detailed` recall now returns full content instead of being identical to standard search
- Installer no longer leaves an orphaned clone directory; clones to CWD and copies `uninstall.py` to `~/.claude/context-memory/`
- Uninstaller works standalone without requiring the original clone directory

### Changed
- `/remember` workflow in remember.md and SKILL.md now uses `--json` as the only save path
- Stop hook now uses `--auto` flag for deduplication, includes project name in brief, captures git branch as topic
- `get_stats()` now skips `schema_version` table in output
- Legacy databases (v1) are automatically migrated to v2 on first save
- README install instructions clone to current directory instead of `~/.claude/plugins/`

## [1.0.5] - 2026-02-13

### Added
- `install.py` for one-command setup (copies skill, commands, hooks, inits DB)
- `uninstall.py` for clean removal
- Negative triggers in SKILL.md to prevent over-activation
- Error handling instructions in SKILL.md
- Helpful first-use message when searching an empty database

### Fixed
- `hooks/hooks.json` uses correct nested matcher-group format for settings.json
- SKILL.md frontmatter expanded to match Claude Code skill guide spec
- Script paths in SKILL.md and commands updated from plugins/ to skills/ directory

### Changed
- SKILL.md restructured for progressive disclosure (lean body, details in references/)
- README simplified: install.py replaces manual post-install steps

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
