# Context Memory Database Schema Reference

## Overview

The context-memory database uses SQLite with FTS5 (Full-Text Search 5) for fast, semantic search across stored sessions.

**Location**: `~/.claude/context-memory/context.db`

## Core Tables

### sessions

Stores session metadata and identifiers.

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,     -- Unique session identifier
    project_path TEXT,                    -- Full path to project directory
    project_hash TEXT,                    -- SHA256 hash of normalized path (first 16 chars)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,      -- Number of stored messages
    metadata TEXT                         -- JSON for extensibility
);
```

**Indexes**:
- `idx_sessions_project_hash` - Fast project-scoped queries
- `idx_sessions_created_at` - Recent sessions first
- `idx_sessions_updated_at` - Recently updated sessions

### messages

Stores key messages from sessions (not all messages, just important ones).

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,          -- FK to sessions.id
    role TEXT NOT NULL,                   -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,                -- Message content
    sequence INTEGER NOT NULL,            -- Order within session
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
```

**Index**: `idx_messages_session_id`

### summaries

Stores AI-generated session summaries with structured fields.

```sql
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER UNIQUE NOT NULL,   -- FK to sessions.id (one per session)
    brief TEXT NOT NULL,                  -- One-line summary
    detailed TEXT,                        -- Multi-paragraph detailed summary
    key_decisions TEXT,                   -- JSON array of key decisions made
    problems_solved TEXT,                 -- JSON array of problems solved
    technologies TEXT,                    -- JSON array of technologies used
    outcome TEXT,                         -- 'success', 'partial', 'abandoned'
    user_note TEXT,                       -- User-provided annotation from /remember
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
```

### topics

Categorical tags for sessions, enabling topic-based filtering.

```sql
CREATE TABLE topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,          -- FK to sessions.id
    topic TEXT NOT NULL,                  -- Lowercase topic string
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
```

**Indexes**:
- `idx_topics_session_id` - Get all topics for a session
- `idx_topics_topic` - Find sessions by topic

### code_snippets

Stores important code excerpts with context.

```sql
CREATE TABLE code_snippets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,          -- FK to sessions.id
    language TEXT,                        -- Programming language
    code TEXT NOT NULL,                   -- The code content
    description TEXT,                     -- What this code does
    file_path TEXT,                       -- Source file path (if applicable)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
```

**Indexes**:
- `idx_code_snippets_session_id`
- `idx_code_snippets_language`

## FTS5 Virtual Tables

### summaries_fts

Full-text search on summaries. This is the primary search target (Tier 1).

```sql
CREATE VIRTUAL TABLE summaries_fts USING fts5(
    brief,
    detailed,
    key_decisions,
    problems_solved,
    technologies,
    user_note,
    content='summaries',
    content_rowid='id',
    tokenize='porter unicode61'
);
```

**Tokenizer**: `porter unicode61`
- Porter stemming for English (e.g., "running" matches "run")
- Unicode61 for proper Unicode handling

### messages_fts

Full-text search on message content (Tier 2 - deeper search).

```sql
CREATE VIRTUAL TABLE messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='id',
    tokenize='porter unicode61'
);
```

### topics_fts

Full-text search on topics.

```sql
CREATE VIRTUAL TABLE topics_fts USING fts5(
    topic,
    content='topics',
    content_rowid='id',
    tokenize='porter unicode61'
);
```

## Triggers

### FTS Sync Triggers

Automatically keep FTS tables in sync with content tables.

**summaries_fts triggers**:
- `summaries_ai` - After INSERT
- `summaries_ad` - After DELETE
- `summaries_au` - After UPDATE

**messages_fts triggers**:
- `messages_ai` - After INSERT
- `messages_ad` - After DELETE
- `messages_au` - After UPDATE

**topics_fts triggers**:
- `topics_ai` - After INSERT
- `topics_ad` - After DELETE
- `topics_au` - After UPDATE

### Session Updated Trigger

```sql
CREATE TRIGGER sessions_updated AFTER UPDATE ON sessions BEGIN
    UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
```

## Query Examples

### Tier 1: Fast Summary Search

```sql
SELECT
    s.id,
    s.session_id,
    s.project_path,
    s.created_at,
    sum.brief,
    sum.technologies,
    bm25(summaries_fts) as relevance
FROM summaries_fts
JOIN summaries sum ON sum.id = summaries_fts.rowid
JOIN sessions s ON s.id = sum.session_id
WHERE summaries_fts MATCH '"authentication"*'
ORDER BY relevance
LIMIT 10;
```

### Topic Search

```sql
SELECT DISTINCT s.*, sum.brief
FROM topics_fts
JOIN topics t ON t.id = topics_fts.rowid
JOIN sessions s ON s.id = t.session_id
LEFT JOIN summaries sum ON sum.session_id = s.id
WHERE topics_fts MATCH '"react"*'
ORDER BY s.created_at DESC;
```

### Project-Scoped Search

```sql
SELECT s.*, sum.brief
FROM summaries_fts
JOIN summaries sum ON sum.id = summaries_fts.rowid
JOIN sessions s ON s.id = sum.session_id
WHERE summaries_fts MATCH '"api" OR "endpoint"'
  AND s.project_hash = 'abc123...'
ORDER BY bm25(summaries_fts);
```

### Tier 2: Deep Message Search

```sql
SELECT
    s.session_id,
    s.project_path,
    m.role,
    m.content,
    bm25(messages_fts) as relevance
FROM messages_fts
JOIN messages m ON m.id = messages_fts.rowid
JOIN sessions s ON s.id = m.session_id
WHERE messages_fts MATCH '"error" AND "database"'
ORDER BY relevance
LIMIT 20;
```

## Performance Optimizations

### PRAGMA Settings

```sql
PRAGMA journal_mode=WAL;      -- Write-Ahead Logging for concurrency
PRAGMA synchronous=NORMAL;    -- Balance safety/performance
PRAGMA cache_size=-64000;     -- 64MB cache
PRAGMA temp_store=MEMORY;     -- In-memory temp tables
```

### BM25 Ranking

FTS5 uses BM25 (Best Match 25) for relevance ranking. Lower scores indicate better matches. Use `ORDER BY bm25(table_name)` for relevance-sorted results.

### Index Usage

- Always filter by `project_hash` when searching within a project
- Use `created_at DESC` for recent sessions
- Topic indexes enable fast categorical filtering

## Data Retention

The schema supports CASCADE DELETE on all foreign keys, so deleting a session removes all related data:

```sql
DELETE FROM sessions WHERE id = ?;
-- Automatically deletes related: messages, summaries, topics, code_snippets
```

## JSON Field Formats

### key_decisions

```json
["Use JWT for auth", "Store tokens in httpOnly cookies", "15-minute expiry"]
```

### problems_solved

```json
["Fixed CORS issues", "Resolved token refresh race condition"]
```

### technologies

```json
["Node.js", "Express", "JWT", "Redis"]
```

### metadata (sessions table)

```json
{
  "cli_version": "1.0.0",
  "model": "claude-3-opus",
  "custom_field": "value"
}
```
