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
   - **detailed**: 2-3 paragraphs with full context
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

4. **Save to Database**

   Run the save script:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/context-memory/scripts/db_save.py" --json /tmp/session_data.json
   ```

   Or with individual arguments:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/context-memory/scripts/db_save.py" \
     --session-id "$(uuidgen || cat /proc/sys/kernel/random/uuid)" \
     --project-path "$(pwd)" \
     --brief "Brief summary here" \
     --topics "topic1,topic2,topic3" \
     --user-note "User's note if provided"
   ```

5. **Confirm to User**

   Report back to the user:
   - Confirmation that session was saved
   - The brief summary that was stored
   - Topics that were extracted
   - Any user note that was included

## Output Example

```
Session saved to context memory.

**Summary**: Implemented JWT authentication with refresh token rotation
**Topics**: authentication, jwt, security, nodejs, express
**Note**: "Fixed the auth bug with refresh tokens"

You can find this session later with:
  /recall authentication
  /recall "refresh tokens"
```

## Notes

- Sessions are stored globally and can be searched across all projects
- Use `--project` flag in `/recall` to limit to current project
- If database doesn't exist, it will be created automatically
- User notes are searchable in addition to generated summaries
