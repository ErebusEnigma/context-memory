#!/usr/bin/env python3
"""
Database initialization for context-memory plugin.
Creates tables, FTS5 virtual tables, indexes, and triggers.
"""

import os
import sys

try:
    from .db_utils import DB_PATH, VALID_TABLES, db_exists, ensure_db_dir, get_connection
except ImportError:
    from db_utils import DB_PATH, VALID_TABLES, db_exists, ensure_db_dir, get_connection

SCHEMA_SQL = """
-- Core Tables

-- Sessions table: stores session metadata
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    project_path TEXT,
    project_hash TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    metadata TEXT  -- JSON for extensibility
);

-- Messages table: stores key messages from sessions
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- Summaries table: stores session summaries
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER UNIQUE NOT NULL,
    brief TEXT NOT NULL,  -- One-line summary
    detailed TEXT,  -- Detailed summary
    key_decisions TEXT,  -- JSON array of decisions
    problems_solved TEXT,  -- JSON array of problems
    technologies TEXT,  -- JSON array of technologies
    outcome TEXT,  -- success, partial, abandoned
    user_note TEXT,  -- User-provided annotation from /remember
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- Topics table: categorical tags for sessions
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- Code snippets table: important code excerpts
CREATE TABLE IF NOT EXISTS code_snippets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    language TEXT,
    code TEXT NOT NULL,
    description TEXT,
    file_path TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- FTS5 Virtual Tables for full-text search

-- Summaries FTS (Tier 1 - fast search)
CREATE VIRTUAL TABLE IF NOT EXISTS summaries_fts USING fts5(
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

-- Messages FTS (Tier 2 - detailed search)
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Topics FTS
CREATE VIRTUAL TABLE IF NOT EXISTS topics_fts USING fts5(
    topic,
    content='topics',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Code Snippets FTS
CREATE VIRTUAL TABLE IF NOT EXISTS code_snippets_fts USING fts5(
    code,
    description,
    file_path,
    content='code_snippets',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Indexes for performance

CREATE INDEX IF NOT EXISTS idx_sessions_project_hash ON sessions(project_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_topics_session_id ON topics(session_id);
CREATE INDEX IF NOT EXISTS idx_topics_topic ON topics(topic);
CREATE INDEX IF NOT EXISTS idx_code_snippets_session_id ON code_snippets(session_id);
CREATE INDEX IF NOT EXISTS idx_code_snippets_language ON code_snippets(language);

-- Triggers for automatic FTS sync

-- Summaries FTS triggers
CREATE TRIGGER IF NOT EXISTS summaries_ai AFTER INSERT ON summaries BEGIN
    INSERT INTO summaries_fts(rowid, brief, detailed, key_decisions, problems_solved, technologies, user_note)
    VALUES (NEW.id, NEW.brief, NEW.detailed, NEW.key_decisions, NEW.problems_solved, NEW.technologies, NEW.user_note);
END;

CREATE TRIGGER IF NOT EXISTS summaries_ad AFTER DELETE ON summaries BEGIN
    INSERT INTO summaries_fts(summaries_fts, rowid, brief, detailed, key_decisions, problems_solved, technologies, user_note)
    VALUES ('delete', OLD.id, OLD.brief, OLD.detailed, OLD.key_decisions, OLD.problems_solved, OLD.technologies, OLD.user_note);
END;

CREATE TRIGGER IF NOT EXISTS summaries_au AFTER UPDATE ON summaries BEGIN
    INSERT INTO summaries_fts(summaries_fts, rowid, brief, detailed, key_decisions, problems_solved, technologies, user_note)
    VALUES ('delete', OLD.id, OLD.brief, OLD.detailed, OLD.key_decisions, OLD.problems_solved, OLD.technologies, OLD.user_note);
    INSERT INTO summaries_fts(rowid, brief, detailed, key_decisions, problems_solved, technologies, user_note)
    VALUES (NEW.id, NEW.brief, NEW.detailed, NEW.key_decisions, NEW.problems_solved, NEW.technologies, NEW.user_note);
END;

-- Messages FTS triggers
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (NEW.id, NEW.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES ('delete', OLD.id, OLD.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES ('delete', OLD.id, OLD.content);
    INSERT INTO messages_fts(rowid, content) VALUES (NEW.id, NEW.content);
END;

-- Topics FTS triggers
CREATE TRIGGER IF NOT EXISTS topics_ai AFTER INSERT ON topics BEGIN
    INSERT INTO topics_fts(rowid, topic) VALUES (NEW.id, NEW.topic);
END;

CREATE TRIGGER IF NOT EXISTS topics_ad AFTER DELETE ON topics BEGIN
    INSERT INTO topics_fts(topics_fts, rowid, topic) VALUES ('delete', OLD.id, OLD.topic);
END;

CREATE TRIGGER IF NOT EXISTS topics_au AFTER UPDATE ON topics BEGIN
    INSERT INTO topics_fts(topics_fts, rowid, topic) VALUES ('delete', OLD.id, OLD.topic);
    INSERT INTO topics_fts(rowid, topic) VALUES (NEW.id, NEW.topic);
END;

-- Code Snippets FTS triggers
CREATE TRIGGER IF NOT EXISTS code_snippets_ai AFTER INSERT ON code_snippets BEGIN
    INSERT INTO code_snippets_fts(rowid, code, description, file_path)
    VALUES (NEW.id, NEW.code, NEW.description, NEW.file_path);
END;

CREATE TRIGGER IF NOT EXISTS code_snippets_ad AFTER DELETE ON code_snippets BEGIN
    INSERT INTO code_snippets_fts(code_snippets_fts, rowid, code, description, file_path)
    VALUES ('delete', OLD.id, OLD.code, OLD.description, OLD.file_path);
END;

CREATE TRIGGER IF NOT EXISTS code_snippets_au AFTER UPDATE ON code_snippets BEGIN
    INSERT INTO code_snippets_fts(code_snippets_fts, rowid, code, description, file_path)
    VALUES ('delete', OLD.id, OLD.code, OLD.description, OLD.file_path);
    INSERT INTO code_snippets_fts(rowid, code, description, file_path)
    VALUES (NEW.id, NEW.code, NEW.description, NEW.file_path);
END;

-- Sessions updated_at trigger
CREATE TRIGGER IF NOT EXISTS sessions_updated AFTER UPDATE ON sessions BEGIN
    UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
"""


def init_database(force: bool = False) -> bool:
    """
    Initialize the database with schema.

    Args:
        force: If True, recreate even if database exists

    Returns:
        True if database was created/initialized, False if already exists
    """
    ensure_db_dir()

    if db_exists() and not force:
        print(f"Database already exists at {DB_PATH}")
        return False

    if force and db_exists():
        try:
            os.remove(DB_PATH)
        except OSError as e:
            print(f"Error removing database at {DB_PATH}: {e}")
            return False
        print(f"Removed existing database at {DB_PATH}")

    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()

    print(f"Database initialized at {DB_PATH}")
    return True


def verify_schema() -> dict:
    """Verify that all expected tables exist."""
    expected_tables = [
        'sessions', 'messages', 'summaries', 'topics', 'code_snippets',
        'summaries_fts', 'messages_fts', 'topics_fts', 'code_snippets_fts'
    ]

    with get_connection(readonly=True) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' OR type='virtual table'"
        )
        existing_tables = {row[0] for row in cursor.fetchall()}

    result = {
        'valid': all(t in existing_tables for t in expected_tables),
        'existing': list(existing_tables),
        'missing': [t for t in expected_tables if t not in existing_tables]
    }

    return result


def get_stats() -> dict:
    """Get database statistics."""
    if not db_exists():
        return {}

    with get_connection(readonly=True) as conn:
        stats = {}

        for table in VALID_TABLES:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]

        # Get database file size
        stats['db_size_bytes'] = DB_PATH.stat().st_size if DB_PATH.exists() else 0

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize context-memory database")
    parser.add_argument('--force', action='store_true', help="Force recreation of database")
    parser.add_argument('--verify', action='store_true', help="Verify schema only")
    parser.add_argument('--stats', action='store_true', help="Show database statistics")

    args = parser.parse_args()

    if args.verify:
        if not db_exists():
            print("Database does not exist. Run without --verify to initialize.")
            sys.exit(1)
        result = verify_schema()
        if result['valid']:
            print("Schema is valid")
            print(f"Tables: {', '.join(result['existing'])}")
        else:
            print("Schema is invalid!")
            print(f"Missing tables: {', '.join(result['missing'])}")
        sys.exit(0 if result['valid'] else 1)

    if args.stats:
        if not db_exists():
            print("Database does not exist")
            sys.exit(1)
        stats = get_stats()
        print("Database Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        sys.exit(0)

    init_database(force=args.force)
