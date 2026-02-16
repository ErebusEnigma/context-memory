---
name: "context-memory"
description: >
  Saves and searches past Claude Code sessions so context, decisions, and
  code persist across conversations. Use when user says 'remember this',
  'save this session', 'recall', 'search past sessions', 'what did we
  discuss about', or 'find previous work on'. Do NOT use for general file
  storage, note-taking, or bookmark management.
license: "MIT"
compatibility: "Requires Python >= 3.8 with sqlite3 FTS5 support (included in standard library). MCP server requires Python >= 3.10. Claude Code CLI only."
allowed-tools: "Bash(python:*)"
metadata:
  author: "ErebusEnigma"
  version: "1.1.0"
---

# Context Memory Skill

Saves and searches past Claude Code sessions so context, decisions, and code persist across conversations.

## Trigger Phrases

Activate this skill when the user says:
- "remember this" / "save this session" / "store this for later"
- "recall" / "search past sessions"
- "what did we discuss about..."
- "find previous work on..."
- "look up past decisions about..."
- "context memory"

Do NOT activate for:
- General file storage or note-taking requests
- Bookmark or URL management
- Requests about Claude's built-in memory features

## Database Location

- Database: `~/.claude/context-memory/context.db`
- Scripts: `~/.claude/skills/context-memory/scripts/`

## Commands

### /remember [note]
Save the current session with an optional annotation.

### /recall \<query\> [options]
Search past sessions.
- `--project`: Limit to current project
- `--detailed`: Include full message content and code snippets
- `--limit N`: Maximum results (default: 10)

## Examples

### Example 1: Save after a debugging session
User says: `/remember "Fixed the JWT refresh bug"`
Actions:
1. Analyze conversation, generate structured summary
2. Extract topics: `debugging`, `jwt`, `authentication`
3. Select key messages capturing the problem and fix
4. Write JSON with all fields and save via `--json`
Result: "Session saved. **Summary**: Fixed JWT refresh token expiration bug by adding clock skew tolerance. **Topics**: debugging, jwt, authentication. **Messages**: 8 saved. **Snippets**: 1 saved. **Note**: Fixed the JWT refresh bug."

### Example 2: Find past work on a topic
User says: "what did we discuss about database migrations?"
Actions:
1. Run `db_search.py "database migrations" --format markdown`
2. Present matching sessions with summaries and topics
Result: Sessions displayed with brief summaries. Offer `--detailed` for full context.

### Example 3: Deep dive into a past session
User says: `/recall authentication --detailed`
Actions:
1. Run `db_search.py "authentication" --detailed --format markdown`
2. Present full summaries, key messages, and code snippets
Result: Complete session context with decisions, messages, and code excerpts in expandable sections.

## Saving a Session

When the user wants to save/remember the current session:

1. Generate a structured summary:
   - **brief**: One-line summary of what was accomplished
   - **detailed**: 2-3 paragraph detailed summary
   - **key_decisions**: List of important decisions made
   - **problems_solved**: List of problems that were resolved
   - **technologies**: List of technologies/tools used
   - **outcome**: success | partial | abandoned

2. Extract 3-8 relevant topics (lowercase, e.g., "authentication", "react", "debugging")

3. Identify significant code snippets worth preserving

4. Select 5-15 key messages that capture the problem, decisions, and solutions

5. Pipe the JSON via stdin using `--json -`:
```bash
python "~/.claude/skills/context-memory/scripts/db_save.py" --json - << 'ENDJSON'
{
  "session_id": "<UNIQUE_ID>",
  "project_path": "<PROJECT_PATH>",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "summary": {
    "brief": "One-line summary",
    "detailed": "Full 2-3 paragraph summary...",
    "key_decisions": ["Decision 1", "Decision 2"],
    "problems_solved": ["Problem 1"],
    "technologies": ["python", "sqlite"],
    "outcome": "success"
  },
  "topics": ["topic1", "topic2"],
  "code_snippets": [
    {
      "code": "def example(): pass",
      "language": "python",
      "description": "What this does",
      "file_path": "src/example.py"
    }
  ],
  "user_note": "User's note or null"
}
ENDJSON
```

**Important**: Always use `--json -` (stdin) for /remember saves. This avoids temp file issues on Windows. The CLI args path (`--brief`, `--topics`) only saves a subset of fields and leaves `--detailed` recall empty.

6. Report back: confirmation, brief summary, topics extracted, message/snippet counts, user note included.

## Searching Past Sessions

When the user wants to recall/search past sessions:

1. Run the search:
```bash
python "~/.claude/skills/context-memory/scripts/db_search.py" "<QUERY>" --format markdown [--project "$(pwd)"] [--detailed] [--limit N]
```

2. Present results in a clear, scannable format.

3. If results are insufficient, offer to:
   - Broaden the search query
   - Remove the `--project` filter
   - Search with `--detailed` for deeper content

## Output Format

```markdown
# Context Memory Results
**Query**: "authentication"
**Results**: 3 sessions

---
## 1. 2026-01-15 | my-app (Match #1)
**Summary**: Implemented JWT auth with refresh token rotation
**Topics**: authentication, JWT, security, Node.js
**Decisions**:
- Use RS256 for token signing
- 15-minute access token expiry

<details><summary>Full Context</summary>
[Detailed content here]
</details>
```

## Error Handling

- **Database doesn't exist**: Auto-created on first save. To manually init: `python ~/.claude/skills/context-memory/scripts/db_init.py`
- **Database locked**: Another process may be using it. Ask the user to check for other Claude Code instances and retry.
- **Save fails**: Check file permissions on `~/.claude/context-memory/`. The directory must be writable.
- **Search returns no results**: Suggest broader terms, remove `--project` filter, or try related keywords.
- **Empty database (fresh install)**: Show "No sessions stored yet. Use /remember to save your first session."

## Best Practices

1. **When saving**: Always use `--json` for full data. Always ask user if they want to add a note/annotation
2. **When searching**: Start with tier 1 (summaries), offer detailed search if needed
3. **Topics**: Use consistent, lowercase topic names
4. **Summaries**: Focus on the "why" not just the "what"
5. **Code snippets**: Only save truly reusable or significant code

## Related Files

- [Schema Reference](references/schema-reference.md) — Full database schema
- Scripts in `scripts/` directory
