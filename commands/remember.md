---
description: "Save the current session to persistent context memory"
argument-hint: "[note]"
---

# /remember Command

Save the current session to context memory with an optional annotation.

## Usage

```
/remember [note]
```

**Arguments:**
- `note` (optional): A personal annotation or tag to help find this session later

## Examples

```
/remember
/remember "Fixed the auth bug with refresh tokens"
/remember "Important: OAuth2 implementation details"
```

## Workflow

When the user runs `/remember`:

1. **Generate Session Summary**

   Analyze the current conversation and create:

   - **brief**: A single sentence summarizing what was accomplished
   - **detailed**: 2-3 paragraphs with full context of what happened
   - **key_decisions**: List of important decisions made during the session
   - **problems_solved**: List of problems that were resolved
   - **technologies**: List of technologies, frameworks, or tools discussed
   - **outcome**: One of: `success`, `partial`, `abandoned`

2. **Extract Topics**

   Identify 3-8 relevant topics from the conversation. Use lowercase, common terms like:
   - Technology names: `react`, `python`, `sqlite`
   - Concepts: `authentication`, `debugging`, `refactoring`
   - Domains: `api`, `frontend`, `database`

3. **Identify Key Code**

   If significant code was written or discussed, extract important snippets with:
   - The code itself
   - The programming language
   - A brief description of what it does
   - The file path if applicable

4. **Extract Key Messages**

   Select 5-15 important messages from the conversation that capture:
   - The initial request/problem statement
   - Key decisions and their reasoning
   - Solution descriptions
   - Important caveats or warnings

5. **Pipe JSON via Stdin and Save to Database**

   Pipe JSON directly via `--json -` (stdin). This is the **only** save path that preserves all fields:

   ```bash
   python "~/.claude/skills/context-memory/scripts/db_save.py" --json - << 'ENDJSON'
   {
     "session_id": "<UNIQUE_ID>",
     "project_path": "<PROJECT_PATH>",
     "messages": [
       {"role": "user", "content": "The initial question or request"},
       {"role": "assistant", "content": "The response or solution"}
     ],
     "summary": {
       "brief": "One-line summary of what was accomplished",
       "detailed": "2-3 paragraphs with full context...",
       "key_decisions": ["Decision 1", "Decision 2"],
       "problems_solved": ["Problem 1", "Problem 2"],
       "technologies": ["python", "sqlite", "fts5"],
       "outcome": "success"
     },
     "topics": ["topic1", "topic2", "topic3"],
     "code_snippets": [
       {
         "code": "def example(): pass",
         "language": "python",
         "description": "What this code does",
         "file_path": "src/example.py"
       }
     ],
     "user_note": "User's note if provided, or null"
   }
   ENDJSON
   ```

   Generate the session_id with: `$(uuidgen 2>/dev/null || python -c "import uuid; print(uuid.uuid4())")`

   Set project_path to: `$(pwd)`

   **Important**: Always use `--json -` (stdin). This avoids temp file issues on Windows. The CLI args path (`--brief`, `--topics`) only saves a subset of fields and leaves `--detailed` recall empty.

6. **Confirm to User**

   Report back to the user:
   - Confirmation that session was saved
   - The brief summary that was stored
   - Topics that were extracted
   - Number of messages and code snippets saved
   - Any user note that was included

## Output Example

```
Session saved to context memory.

**Summary**: Implemented JWT authentication with refresh token rotation
**Topics**: authentication, jwt, security, nodejs, express
**Messages**: 12 key messages saved
**Code Snippets**: 2 snippets saved
**Note**: "Fixed the auth bug with refresh tokens"

You can find this session later with:
  /recall authentication
  /recall "refresh tokens"
  /recall jwt --detailed    (for full messages and code)
```

## Notes

- Always use the `--json -` (stdin) path to save complete session data
- Sessions are stored globally and can be searched across all projects
- Use `--project` flag in `/recall` to limit to current project
- If database doesn't exist, it will be created automatically
- User notes are searchable in addition to generated summaries
- Use `--detailed` in `/recall` to see the full messages and code snippets saved here
