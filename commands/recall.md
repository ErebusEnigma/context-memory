---
description: "Search past sessions stored in context memory"
argument-hint: "<query> [--project] [--detailed] [--limit N]"
---

# /recall Command

Search past sessions stored in context memory.

## Usage

```
/recall <query> [options]
```

**Arguments:**
- `query` (required): Search terms to find relevant sessions

**Options:**
- `--project`: Limit search to current project only
- `--detailed`: Include full message content and code snippets
- `--limit N`: Maximum number of results (default: 10)

## Examples

```
/recall authentication
/recall "database migration" --project
/recall jwt --detailed --limit 5
/recall "error handling" --project --detailed
```

## Workflow

When the user runs `/recall`:

1. **Parse Query and Options**

   Extract the search query and any flags:
   - `--project` -> filter by current project path
   - `--detailed` -> include tier 2 content
   - `--limit N` -> cap results

2. **Execute Search**

   Run the search script:

   ```bash
   python "~/.claude/skills/context-memory/scripts/db_search.py" "<query>" [--project "$(pwd)"] [--detailed] [--limit N] --format markdown
   ```

3. **Present Results**

   Display results in a clear, scannable format:

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
   [Detailed content when --detailed flag is used]
   </details>
   ```

4. **Offer Follow-up Actions**

   If results are helpful, offer to:
   - Show more details for a specific session
   - Apply learnings from a past session to current work
   - Search with different terms

   If results are insufficient:
   - Suggest broader search terms
   - Offer to search in messages (deeper search)
   - Suggest removing `--project` filter

## Search Tips

The search uses FTS5 full-text search with Porter stemming:

- **Stemming**: "running" matches "run", "authentication" matches "authenticate"
- **Multiple terms**: Space-separated terms are OR'd together
- **Phrases**: Use quotes for exact phrases (handled internally)

Good search queries:
- `authentication` - Find auth-related sessions
- `react hooks` - Find React or hooks sessions
- `database migration` - Find database or migration sessions
- `bug fix error` - Find debugging sessions

## Output Modes

### Standard (default)

Shows brief summaries, topics, and key decisions. Fast overview of matching sessions.

### Detailed (`--detailed`)

Includes:
- Full detailed summaries
- Key message excerpts
- Code snippets with language highlighting

Use `--detailed` when you need to deeply understand a past session or reference specific code.

## No Results

If no sessions match the query:

```
# Context Memory Results
**Query**: "quantum computing"
**Results**: 0 sessions

No matching sessions found.

Try:
- Using broader search terms
- Removing the --project filter
- Checking related topics
```

## Notes

- Search is case-insensitive
- Results are ranked by relevance (BM25 algorithm)
- Database is located at `~/.claude/context-memory/context.db`
- First search may be slower as database warms up; subsequent searches are faster
