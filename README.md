# context-memory

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.8-blue.svg)](https://www.python.org/)
[![Latest Release](https://img.shields.io/github/v/release/ErebusEnigma/context-memory)](https://github.com/ErebusEnigma/context-memory/releases)
[![CI](https://github.com/ErebusEnigma/context-memory/actions/workflows/ci.yml/badge.svg)](https://github.com/ErebusEnigma/context-memory/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-351_passing-brightgreen.svg)](tests/)

Persistent, searchable context storage across Claude Code sessions using SQLite + FTS5.

## Table of Contents

- [Why?](#why)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Uninstalling](#uninstalling)
- [Requirements](#requirements)
- [Commands](#commands)
- [How It Works](#how-it-works)
- [Usage Examples](#usage-examples)
- [Trigger Phrases](#trigger-phrases)
- [Web Dashboard](#web-dashboard)
- [CLI Tools](#cli-tools)
- [Database Management](#database-management)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)

## Why?

Claude Code sessions are **ephemeral** - every conversation starts from zero. Close the terminal and everything you discussed, decided, and solved is gone. The only way to get that context back is to re-explain it or hope Claude reads the right files.

**context-memory fixes this.**

- **"How did we fix that auth bug last week?"** - Instead of re-debugging, `/recall authentication` pulls up exactly what you did, what you decided, and why.
- **Decisions have context** - You chose JWT over sessions for a reason. Three months later, you can't remember why. Your past sessions can.
- **Code patterns survive sessions** - That elegant retry pattern you built? It's saved with the language, file path, and description of what it does. `/recall retry pattern --detailed` brings it back.
- **Projects you haven't touched in months** - `/recall --project` scopes to whatever you're working in. Instant refresher on where you left off.
- **Cross-project learning** - Solved a CORS issue in one project? When it hits another, `/recall CORS` finds it regardless of which project it came from.
- **Sub-50ms search** - It's SQLite with FTS5 and tuned PRAGMAs (WAL mode, 64MB cache, in-memory temp store). Searching thousands of sessions feels instant.
- **Two words to save everything** - `/remember` and Claude does the rest: summarizes, extracts topics, identifies key code, stores it all. Add a note if you want, or don't.

Without it, every session is a blank slate. With it, Claude Code has a long-term memory that grows more valuable the more you use it.

## Features

**Core:**
- **Cross-session memory** - Save and recall past work across Claude Code sessions
- **Structured AI summaries** - `/remember` generates rich summaries with brief/detailed text, key decisions, problems solved, technologies used, and outcome classification (success/partial/abandoned)
- **Full-text search** - FTS5 with Porter stemming for fast, fuzzy search
- **Two-tier retrieval** - Fast summary search (<10ms) + deep content fetch (<50ms)
- **Project-scoped or global** - Filter by current project or search everything
- **Topic categorization** - Auto-extracted topics for browsable history
- **Code snippet storage** - Preserve important code with language and context
- **Outcome tracking** - Every session is classified as success, partial, or abandoned — searchable and charted in the dashboard

**Hooks:**
- **Auto-save on exit** - Stop hook captures session context automatically when Claude Code exits, with smart head+tail transcript sampling (first 5 + last 10 messages) to preserve the problem statement and resolution
- **Git branch capture** - Auto-save detects the current git branch and adds it as a topic, so `/recall feature/auth-refactor` finds sessions from that branch
- **Pre-compact checkpoints** - Saves full conversation before context compaction for zero context loss, recoverable via the `context_load_checkpoint` MCP tool
- **Session deduplication** - Auto-save checks for a rich `/remember` save in the same project within a configurable window (default 5 minutes) and skips if one exists
- **Loop prevention** - Auto-save checks `stop_hook_active` to prevent recursive hook invocation

**Extras:**
- **Web dashboard** - Full SPA with 17 REST API endpoints, dark/light theme, Chart.js analytics, Highlight.js code rendering, session CRUD, and search autocomplete
- **MCP server** - Six tools for programmatic access from any MCP-compatible client
- **CLI tools** - All core scripts (`db_save.py`, `db_search.py`, `db_prune.py`, `db_init.py`) have full argparse CLIs with `--help`
- **Database pruning** - Prune old sessions by age or count, and old checkpoints per session, with dry-run preview

**Engineering:**
- **Cross-platform** - Windows (CMD/PowerShell), macOS, and Linux
- **Zero external dependencies** - Stdlib-only Python 3.8+ for core functionality
- **Schema auto-migration** - Forward-only automatic upgrades (v1 through v4) on first DB access after upgrade, preserving all existing data
- **SQLite performance tuning** - WAL mode, 64MB cache, `PRAGMA synchronous=NORMAL`, `PRAGMA temp_store=MEMORY`
- **351 tests across 12 modules** - CI runs on Python 3.8, 3.11, and 3.12 with ruff linting

## Architecture

```
.claude-plugin/plugin.json        # Plugin manifest (version, metadata)
.mcp.json                         # MCP server config (project-level)
install.py                        # Installer (idempotent, selective flags)
uninstall.py                      # Uninstaller (copies itself to survive clone deletion)
hooks/hooks.json                  # Hook definitions (Stop + PreCompact)
commands/                         # /remember and /recall command definitions
skills/context-memory/            # Skill definition (SKILL.md)
  scripts/
    __init__.py                   # Package init, version, public API re-exports
    db_init.py                    # Schema creation, verification, stats, migrations
    db_save.py                    # Session storage logic, deduplication
    db_search.py                  # FTS5 search (tier 1 + tier 2)
    db_prune.py                   # Database pruning (by age/count/checkpoints)
    db_utils.py                   # Connection management, helpers, shared utilities
    mcp_server.py                 # MCP server (FastMCP, stdio transport)
    dashboard.py                  # Web dashboard (Flask REST API + SPA)
    auto_save.py                  # Stop hook: cross-platform auto-save wrapper
    pre_compact_save.py           # PreCompact hook: saves full context before compaction
    static/                       # Dashboard frontend (~2,400 lines vanilla JS/CSS/HTML)
      index.html                  # SPA entry point (Chart.js, Highlight.js CDN)
      dashboard.css               # Dual-theme CSS with custom properties
      js/app.js                   # Router, theme toggle, navigation
      js/api.js                   # REST API client
      js/components/              # Charts, code blocks, modals, toasts, session cards
      js/views/                   # Search, sessions, detail, analytics, settings
  references/
    schema-reference.md           # Full database schema reference
tests/                            # 351 tests across 12 modules
.github/workflows/ci.yml          # CI: lint (ruff) + test (Python 3.8, 3.11, 3.12)
```

## Installation

```bash
git clone https://github.com/ErebusEnigma/context-memory.git
cd context-memory
python install.py
```

The installer copies the skill, commands, and hooks (Stop + PreCompact) to the correct Claude Code locations (`~/.claude/`) and initializes the database. It's idempotent — run it again to upgrade. On upgrade, the installer detects outdated hooks (old command paths, unexpanded `~` on Windows) and updates them in-place.

After installation, the cloned directory is no longer needed and can be deleted (or kept for future upgrades). The uninstaller is copied to `~/.claude/context-memory/uninstall.py` so it works even after deleting the clone.

```bash
cd .. && rm -rf context-memory   # optional cleanup
```

**Installer flags:**

| Flag | Description |
|------|-------------|
| `--symlink` | Symlink skill instead of copying (for development) |
| `--skip-skill` | Skip skill installation |
| `--skip-commands` | Skip command installation |
| `--skip-hooks` | Skip hook installation |
| `--skip-db` | Skip database initialization |
| `--skip-mcp` | Skip MCP server registration (useful if Python < 3.10) |

> **Note**: The hooks use Python wrappers (`auto_save.py`, `pre_compact_save.py`) and work cross-platform — Windows (CMD, PowerShell), macOS, and Linux.

## Uninstalling

```bash
python ~/.claude/context-memory/uninstall.py
```

This removes the skill, commands, hooks (both Stop and PreCompact), and MCP server registration. Your saved sessions are preserved by default. Use `--remove-data` to also delete the database, or `--keep-data` to skip the prompt. Use `--force` to remove command files even if they've been modified.

## Requirements

- Python >= 3.8
- SQLite with FTS5 support (included in Python's standard library)
- MCP server (optional): Python >= 3.10 and `pip install mcp`
- Web dashboard (optional): `pip install context-memory[dashboard]` or `pip install flask flask-cors`

## Commands

### `/remember [note]`

Save the current session to context memory.

```
/remember
/remember "Fixed the auth bug with refresh tokens"
/remember "Important: OAuth2 implementation details"
```

Claude will automatically:
1. Generate a structured summary (brief + detailed text, key decisions, problems solved, technologies used)
2. Classify the session outcome (success, partial, or abandoned)
3. Extract topics and identify important code snippets
4. Store everything in the local SQLite database

### `/recall <query> [options]`

Search past sessions.

```
/recall authentication
/recall "database migration" --project
/recall jwt --detailed --limit 5
```

**Options:**
- `--project` - Limit search to the current project
- `--detailed` - Include full message content and code snippets
- `--limit N` - Maximum number of results (default: 10)

## How It Works

### Storage

Sessions are stored in a SQLite database at `~/.claude/context-memory/context.db` with the following structure:

- **Sessions** - Metadata, project path, timestamps
- **Summaries** - AI-generated brief/detailed summaries, key decisions, problems solved, technologies, outcome (success/partial/abandoned), user notes
- **Topics** - Categorical tags for each session
- **Messages** - Key message excerpts
- **Code Snippets** - Important code with language and file path
- **Context Checkpoints** - Full conversation snapshots saved before context compaction (schema v4)

### Search

Search uses FTS5 (Full-Text Search 5) with two tiers:

1. **Tier 1 (Fast)** - Searches summaries, topics, and code snippets using BM25 ranking (<10ms)
2. **Tier 2 (Deep)** - Fetches full messages and code snippets for selected sessions (<50ms)

Porter stemming is enabled, so "running" matches "run" and "authentication" matches "authenticate".

Performance is backed by SQLite tuning: WAL mode for concurrent access, 64MB cache, `PRAGMA synchronous=NORMAL` for balanced safety/speed, and `PRAGMA temp_store=MEMORY` for in-memory temp tables.

### Hooks

The plugin registers two hooks:

- **Stop hook** (`auto_save.py`) — Automatically saves session context when Claude Code exits. Reads the JSON payload from Claude Code's stdin (session ID, transcript path) and parses the JSONL transcript to extract conversation messages. For long conversations, uses head+tail sampling (first 5 + last 10 messages) to keep the problem statement and resolution while trimming the middle. Detects the current git branch and adds it as a topic. Checks `stop_hook_active` to prevent recursive invocation. Skips saving if a rich `/remember` session already exists for the same project within a configurable dedup window (default 5 minutes) — identified by checking for a non-null detailed summary, which distinguishes `/remember` saves from thin auto-saves.

- **PreCompact hook** (`pre_compact_save.py`) — Saves a full conversation checkpoint to the database before Claude Code compacts context. This preserves all messages without truncation or sampling. The recovery workflow: context gets compacted and detail is lost → Claude calls the `context_load_checkpoint` MCP tool → the full pre-compaction conversation is restored from the checkpoint.

### Schema Migrations

The database schema auto-migrates forward on first access after an upgrade. Migrations are forward-only and preserve all existing data. The current schema version is 4:

| Version | Description |
|---------|-------------|
| 1 | Core tables: sessions, messages, summaries, topics, code_snippets + FTS5 |
| 2 | Add `schema_version` table for migration tracking |
| 3 | Replace `sessions_updated` trigger with WHEN-guarded version |
| 4 | Add `context_checkpoints` table + indexes for pre-compact saves |

### MCP Server

An optional MCP (Model Context Protocol) server exposes context-memory operations as tools that any MCP-compatible client can call directly — no shell commands or subprocess overhead required.

**Tools provided:**
- `context_search` — Search past sessions (FTS5 + BM25)
- `context_save` — Save a session with messages, summary, topics, snippets
- `context_stats` — Database statistics
- `context_init` — Initialize/verify database
- `context_load_checkpoint` — Load a pre-compact context checkpoint to restore full conversation after compaction
- `context_dashboard` — Launch the web dashboard (see [Web Dashboard](#web-dashboard))

**Setup:**

```bash
pip install mcp                    # Install the optional dependency
python install.py                  # Registers the MCP server automatically
```

To register manually (outside a Claude Code session), add an entry to `~/.claude/mcp_servers.json`:

```json
{
  "context-memory": {
    "command": "python",
    "args": ["/full/path/to/.claude/skills/context-memory/scripts/mcp_server.py"],
    "cwd": "/full/path/to/.claude/skills/context-memory/scripts"
  }
}
```

The MCP server uses stdio transport and imports the existing Python modules directly (no subprocess calls). The `mcp` package is an optional dependency — the core plugin remains zero-dependency Python 3.8+. A project-level `.mcp.json` is also included for local development.

## Usage Examples

### Save after a productive session

```
/remember "Implemented user authentication with JWT"
```

### Find past work on a topic

```
/recall database migration
```

### Deep-dive into a specific session

```
/recall "API refactoring" --detailed
```

### Search within current project only

```
/recall authentication --project
```

### Find sessions from a git branch

```
/recall feature/auth-refactor
```

## Trigger Phrases

The context-memory skill also activates on natural language:
- "remember this" / "save this session"
- "recall" / "search past sessions"
- "what did we discuss about..."
- "find previous work on..."

## Web Dashboard

A full single-page application for browsing, searching, and managing your stored sessions. Built with ~2,400 lines of vanilla JS/CSS/HTML plus a 500-line Flask backend exposing 17 REST API endpoints.

```bash
pip install context-memory[dashboard]   # or: pip install flask flask-cors
python skills/context-memory/scripts/dashboard.py
```

Then open [http://127.0.0.1:5111](http://127.0.0.1:5111).

**Features:**
- **Search** — Full-text search with topic/technology hint chips for autocomplete (via `/api/hints`)
- **Sessions** — Browse all sessions with pagination, project filtering, and sorting
- **Session detail** — View full summaries, messages, and code snippets; edit summaries, topics, and notes inline; delete sessions with confirmation modal
- **Code rendering** — Syntax highlighting via Highlight.js for stored code snippets
- **Analytics** — Interactive Chart.js charts: timeline (configurable day/week/month granularity), topic frequency bar chart, project distribution doughnut, outcome breakdown, technology usage
- **Settings** — Initialize or reinitialize the database, prune old sessions (with dry-run preview), export all data as JSON
- **Dark/light theme** — Toggle between themes with CSS custom properties, persisted in localStorage
- **Toast notifications** — Feedback on save, delete, and error operations

Use `--port` to change the default port:

```bash
python skills/context-memory/scripts/dashboard.py --port 8080
```

The dashboard can also be launched via the MCP `context_dashboard` tool, which starts it in the background.

**REST API:** The dashboard backend exposes 17 endpoints under `/api/` — sessions CRUD, search, analytics (timeline, topics, projects, outcomes, technologies), pruning, initialization, export, project listing, and search hints. These can be consumed by alternative frontends or external integrations.

> **Note**: The dashboard requires `flask` and `flask-cors` (`pip install flask flask-cors`). These are not needed for the core plugin.

## CLI Tools

All core scripts have full argparse CLIs and can be run directly:

**`db_save.py`** — Save sessions from the command line:
```bash
python scripts/db_save.py --session-id abc123 --project-path /my/project \
    --brief "Fixed auth bug" --topics "auth,jwt" --outcome success
python scripts/db_save.py --json session.json    # or --json - for stdin
python scripts/db_save.py --auto --dedup-window 5  # auto-save mode with dedup
```

**`db_search.py`** — Search from the command line:
```bash
python scripts/db_search.py "authentication" --project /my/project --format json
python scripts/db_search.py "CORS" --detailed --limit 5
```

**`db_prune.py`** — Prune old data:
```bash
python scripts/db_prune.py --max-sessions 100 --dry-run
python scripts/db_prune.py --max-age 90          # delete sessions older than 90 days
python scripts/db_prune.py --prune-checkpoints --max-checkpoints-per-session 3
```

**`db_init.py`** — Database management:
```bash
python scripts/db_init.py              # initialize database
python scripts/db_init.py --verify     # verify schema integrity
python scripts/db_init.py --stats      # show database statistics
python scripts/db_init.py --force      # force recreation
```

## Database Management

Initialize or verify the database manually:

```bash
python skills/context-memory/scripts/db_init.py
python skills/context-memory/scripts/db_init.py --verify
python skills/context-memory/scripts/db_init.py --stats
```

## Testing

The project has 351 tests across 12 test modules. CI runs on Python 3.8, 3.11, and 3.12 via GitHub Actions with ruff linting.

```bash
python -m pytest tests/ -v    # run all tests
ruff check .                  # lint
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.

## License

MIT - See [LICENSE](LICENSE) for details.

## Author

**ErebusEnigma**
