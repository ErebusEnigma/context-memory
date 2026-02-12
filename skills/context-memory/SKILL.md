---
name: "context-memory"
description: "Persistent, searchable context storage across Claude Code sessions"
---

# Context Memory Skill

A persistent, searchable context storage system for Claude Code sessions.

## Trigger Phrases

Activate this skill when the user says:
- "remember this"
- "save this session"
- "store this for later"
- "recall" or "search past sessions"
- "what did we discuss about..."
- "find previous work on..."
- "look up past decisions about..."
- "context memory"

## Overview

This skill provides cross-session memory using SQLite with FTS5 full-text search. It enables:
- Saving session summaries, decisions, and key messages
- Fast retrieval of past work (<50ms)
- Project-scoped or global search
- Topic-based categorization

## Database Location

- Database: `~/.claude/context-memory/context.db`
- Scripts: `${CLAUDE_PLUGIN_ROOT}/skills/context-memory/scripts/`

## Commands

### /remember [note]
Save the current session with an optional annotation.

### /recall \<query\> [options]
Search past sessions.
- `--project`: Limit to current project
- `--detailed`: Include full message content
- `--limit N`: Maximum results (default: 10)

## Workflows

### Saving a Session

When the user wants to save/remember the current session:

1. Generate a structured summary of the conversation:
   - Brief: One-line summary of what was accomplished
   - Detailed: 2-3 paragraph detailed summary
   - Key Decisions: List of important decisions made
   - Problems Solved: List of problems that were resolved
   - Technologies: List of technologies/tools used
   - Outcome: success | partial | abandoned

2. Extract relevant topics (e.g., "authentication", "react", "debugging")

3. Identify any significant code snippets worth preserving

4. Run the save script:
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/context-memory/scripts/db_save.py" \
  --session-id "<SESSION_ID>" \
  --project-path "<PROJECT_PATH>" \
  --brief "<BRIEF_SUMMARY>" \
  --topics "<COMMA_SEPARATED_TOPICS>" \
  --user-note "<USER_NOTE>"
```

Or save with full JSON:
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/context-memory/scripts/db_save.py" --json session_data.json
```

JSON format:
```json
{
  "session_id": "unique-session-id",
  "project_path": "/path/to/project",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "summary": {
    "brief": "One-line summary",
    "detailed": "Detailed description...",
    "key_decisions": ["Decision 1", "Decision 2"],
    "problems_solved": ["Problem 1"],
    "technologies": ["Python", "SQLite"],
    "outcome": "success"
  },
  "topics": ["database", "search", "fts5"],
  "code_snippets": [
    {
      "code": "def example(): pass",
      "language": "python",
      "description": "Example function"
    }
  ],
  "user_note": "User's custom annotation"
}
```

### Searching Past Sessions

When the user wants to recall/search past sessions:

1. Run the search script:
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/context-memory/scripts/db_search.py" "<QUERY>" --format markdown
```

Options:
- `--project /path/to/project`: Filter by project
- `--detailed`: Include full messages and code
- `--limit N`: Limit results (default: 10)
- `--format json|markdown`: Output format

2. Present results to user in a clear format

3. If results are insufficient, offer to:
   - Broaden the search query
   - Search in messages directly (deeper search)
   - Remove project filter

### Initializing the Database

If the database doesn't exist, initialize it:
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/context-memory/scripts/db_init.py"
```

Verify schema:
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/context-memory/scripts/db_init.py" --verify
```

Get statistics:
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/context-memory/scripts/db_init.py" --stats
```

## Output Format

When presenting search results to the user, use this format:

```markdown
# Context Memory Results
**Query**: "authentication"
**Results**: 3 sessions

---
## 1. 2026-01-15 | my-app (Relevance: 8.5)
**Summary**: Implemented JWT auth with refresh token rotation
**Topics**: authentication, JWT, security, Node.js
**Decisions**:
- Use RS256 for token signing
- 15-minute access token expiry

<details><summary>Full Context</summary>
[Detailed content here]
</details>
```

## Best Practices

1. **When saving**: Always ask user if they want to add a note/annotation
2. **When searching**: Start with tier 1 (summaries), offer detailed search if needed
3. **Topics**: Use consistent, lowercase topic names
4. **Summaries**: Focus on the "why" not just the "what"
5. **Code snippets**: Only save truly reusable or significant code

## Error Handling

- If database doesn't exist, run `db_init.py` first
- If search returns no results, suggest broader terms
- If save fails, check file permissions on `~/.claude/context-memory/`

## Performance Targets

| Operation | Target |
|-----------|--------|
| Tier 1 Search | < 10ms |
| Tier 2 Fetch | < 50ms |
| Save Session | < 100ms |

## Related Files

- [Schema Reference](references/schema-reference.md) - Full database schema
- Scripts in `scripts/` directory
