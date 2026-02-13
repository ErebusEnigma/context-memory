# context-memory

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.8-blue.svg)](https://www.python.org/)
[![Latest Release](https://img.shields.io/github/v/release/ErebusEnigma/context-memory)](https://github.com/ErebusEnigma/context-memory/releases)

Persistent, searchable context storage across Claude Code sessions using SQLite + FTS5.

## Table of Contents

- [Why?](#why)
- [Features](#features)
- [Installation](#installation)
- [Uninstalling](#uninstalling)
- [Requirements](#requirements)
- [Commands](#commands)
- [How It Works](#how-it-works)
- [Usage Examples](#usage-examples)
- [Trigger Phrases](#trigger-phrases)
- [Database Management](#database-management)
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
- **Sub-50ms search** - It's SQLite with FTS5, not an API call. Searching thousands of sessions feels instant.
- **Two words to save everything** - `/remember` and Claude does the rest: summarizes, extracts topics, identifies key code, stores it all. Add a note if you want, or don't.

Without it, every session is a blank slate. With it, Claude Code has a long-term memory that grows more valuable the more you use it.

## Features

- **Cross-session memory** - Save and recall past work across Claude Code sessions
- **Full-text search** - FTS5 with Porter stemming for fast, fuzzy search
- **Two-tier retrieval** - Fast summary search (<10ms) + deep content fetch (<50ms)
- **Project-scoped or global** - Filter by current project or search everything
- **Topic categorization** - Auto-extracted topics for browsable history
- **Code snippet storage** - Preserve important code with language and context

## Installation

```bash
git clone https://github.com/ErebusEnigma/context-memory.git
cd context-memory
python install.py
```

The installer copies the skill, commands, and stop hook to the correct Claude Code locations (`~/.claude/`) and initializes the database. It's idempotent — run it again to upgrade.

After installation, the cloned directory is no longer needed and can be deleted (or kept for future upgrades):

```bash
cd .. && rm -rf context-memory   # optional cleanup
```

Use `--symlink` for development (symlinks the skill directory instead of copying):

```bash
python install.py --symlink
```

> **Windows note**: The stop hook uses Bash syntax (`test -f`, `$(date +%s)`). It works in Git Bash / MSYS2 but not in PowerShell or CMD.

## Uninstalling

```bash
python ~/.claude/context-memory/uninstall.py
```

This removes the skill, commands, and stop hook. Your saved sessions are preserved by default. Use `--remove-data` to also delete the database, or `--keep-data` to skip the prompt.

## Requirements

- Python >= 3.8
- SQLite with FTS5 support (included in Python's standard library)

## Commands

### `/remember [note]`

Save the current session to context memory.

```
/remember
/remember "Fixed the auth bug with refresh tokens"
/remember "Important: OAuth2 implementation details"
```

Claude will automatically:
1. Generate a structured summary (brief + detailed)
2. Extract topics and key decisions
3. Identify important code snippets
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
- **Summaries** - AI-generated brief/detailed summaries, key decisions, outcomes
- **Topics** - Categorical tags for each session
- **Messages** - Key message excerpts
- **Code Snippets** - Important code with language and file path

### Search

Search uses FTS5 (Full-Text Search 5) with two tiers:

1. **Tier 1 (Fast)** - Searches summaries and topics using BM25 ranking (<10ms)
2. **Tier 2 (Deep)** - Fetches full messages and code snippets for selected sessions (<50ms)

Porter stemming is enabled, so "running" matches "run" and "authentication" matches "authenticate".

### Auto-Save Hook

The plugin includes an optional Stop hook that auto-saves a basic session record when Claude Code exits. This pairs with `/remember` for richer, annotated saves.

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

## Trigger Phrases

The context-memory skill also activates on natural language:
- "remember this" / "save this session"
- "recall" / "search past sessions"
- "what did we discuss about..."
- "find previous work on..."

## Database Management

Initialize or verify the database manually:

```bash
python skills/context-memory/scripts/db_init.py
python skills/context-memory/scripts/db_init.py --verify
python skills/context-memory/scripts/db_init.py --stats
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.

## License

MIT - See [LICENSE](LICENSE) for details.

## Author

**ErebusEnigma**
