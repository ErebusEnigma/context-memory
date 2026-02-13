---
name: "context-memory"
description: >
  Persistent cross-session memory for Claude Code using SQLite + FTS5.
  Use when the user wants to save session context (/remember) or search
  past sessions (/recall). Triggers: 'remember this', 'save this session',
  'recall', 'search past sessions', 'what did we discuss about',
  'find previous work on'. Do NOT use for general file storage,
  note-taking, or bookmark management.
license: "MIT"
metadata:
  author: "ErebusEnigma"
  version: "1.0.5"
---

# Context Memory Skill

Persistent, searchable context storage across Claude Code sessions.

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
- `--detailed`: Include full message content
- `--limit N`: Maximum results (default: 10)

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

4. Save with JSON for full data:
```bash
python "~/.claude/skills/context-memory/scripts/db_save.py" --json /tmp/session_data.json
```

Or with individual arguments:
```bash
python "~/.claude/skills/context-memory/scripts/db_save.py" \
  --session-id "<SESSION_ID>" \
  --project-path "<PROJECT_PATH>" \
  --brief "<BRIEF_SUMMARY>" \
  --topics "<COMMA_SEPARATED_TOPICS>" \
  --user-note "<USER_NOTE>"
```

5. Report back: confirmation, brief summary, topics extracted, user note included.

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

1. **When saving**: Always ask user if they want to add a note/annotation
2. **When searching**: Start with tier 1 (summaries), offer detailed search if needed
3. **Topics**: Use consistent, lowercase topic names
4. **Summaries**: Focus on the "why" not just the "what"
5. **Code snippets**: Only save truly reusable or significant code

## Related Files

- [Schema Reference](references/schema-reference.md) — Full database schema
- Scripts in `scripts/` directory
