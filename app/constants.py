# Categories
CATEGORIES = ["People", "Projects", "Ideas", "Admin"]

# Prompts
CLASSIFY_PROMPT = """Analyze this message and classify it into exactly ONE category.

Categories:
- People: Notes about individuals, relationships, conversations, contact info
- Projects: Active work items, tasks, goals, things with next actions
- Ideas: Thoughts, concepts, future possibilities, things to explore
- Admin: Logistics, appointments, errands, household, finances

Message:
{message}

Respond with JSON only:
{{
  "category": "<People|Projects|Ideas|Admin>",
  "confidence": <0.0-1.0>,
  "name": "<short descriptive title, 2-5 words>",
  "reasoning": "<one sentence why>"
}}"""

EXTRACT_PROMPT = """Extract structured information from this message for the {category} category.

Message:
{message}

Return JSON with these fields based on category:

For People:
{{"name": "...", "context": "...", "tasks": ["task1", "task2"], "notes": "..."}}

For Projects:
{{"name": "...", "status": "active|someday|done", "tasks": ["task1", "task2"], "notes": "..."}}

For Ideas:
{{"name": "...", "area": "...", "notes": "..."}}

For Admin:
{{"name": "...", "due": "...", "tasks": ["task1", "task2"], "notes": "..."}}

IMPORTANT for tasks:
- Extract EACH distinct action as a SEPARATE item in the tasks array
- "read manga and clean office" = ["Read manga", "Clean office"]
- "buy milk, eggs, bread" = ["Buy milk", "Buy eggs", "Buy bread"]
- Keep each task short and actionable

Only include fields that are clearly present in the message."""

BRIEFING_PROMPT = """You are a concise personal assistant. Based on these vault contents, create a morning briefing.

IMPORTANT:
- Only suggest tasks that are NOT marked as done
- Unchecked tasks look like: - [ ] task
- Completed tasks look like: - [x] task (IGNORE these)
- Use the EXACT task text from the notes so the user can mark them done with "done: <task>"

Format (use these EXACT headers):
## TOP 3 ACTIONS
1. [Most urgent unchecked task - use exact text from note]
2. [Second priority]
3. [Third priority]

## STUCK ON
- [Any blocked items or items needing attention]

## SMALL WIN
- [One easy unchecked task to build momentum]

Keep each item to ONE line. Be specific and actionable.

Vault contents:
{vault_contents}"""

WEEKLY_PROMPT = """You are a concise personal assistant. Based on these vault contents, create a weekly review.

Format (use these EXACT headers):
## WHAT HAPPENED
- [Key completions/progress this week]

## OPEN LOOPS
- [Unfinished items needing attention]

## NEXT WEEK ACTIONS
1. [Priority 1]
2. [Priority 2]
3. [Priority 3]

## THEME
[One sentence theme or focus for next week]

Keep items brief and actionable.

Vault contents:
{vault_contents}"""
