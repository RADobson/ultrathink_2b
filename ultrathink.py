#!/usr/bin/env python3
"""
Ultrathink - Second Brain Telegram Bot
Single-file replacement for N8N + Obsidian + CouchDB stack
"""

import os
import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import yaml
import pytz
import anthropic
import openai
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =============================================================================
# Configuration
# =============================================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    telegram_token: str
    telegram_chat_id: int
    anthropic_api_key: str
    openai_api_key: str
    vault_path: Path
    timezone: str
    confidence_threshold: float

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            telegram_token=os.environ["TELEGRAM_BOT_TOKEN"],
            telegram_chat_id=int(os.environ["TELEGRAM_CHAT_ID"]),
            anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
            openai_api_key=os.environ["OPENAI_API_KEY"],
            vault_path=Path(os.environ.get("VAULT_PATH", "/vault")),
            timezone=os.environ.get("TZ", "Australia/Brisbane"),
            confidence_threshold=float(os.environ.get("CONFIDENCE_THRESHOLD", "0.6")),
        )


# =============================================================================
# Categories & Prompts
# =============================================================================

CATEGORIES = ["People", "Projects", "Ideas", "Admin"]

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
{{"name": "...", "context": "...", "next_action": "...", "notes": "..."}}

For Projects:
{{"name": "...", "status": "active|someday|done", "next_action": "...", "notes": "..."}}

For Ideas:
{{"name": "...", "area": "...", "notes": "..."}}

For Admin:
{{"name": "...", "due": "...", "notes": "..."}}

Only include fields that are clearly present in the message."""

BRIEFING_PROMPT = """You are a concise personal assistant. Based on these vault contents, create a morning briefing.

Format (use these EXACT headers):
## TOP 3 ACTIONS
1. [Most urgent/important action]
2. [Second priority]
3. [Third priority]

## STUCK ON
- [Any blocked items or items needing attention]

## SMALL WIN
- [One easy quick win to build momentum]

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


# =============================================================================
# Vault Service
# =============================================================================


class VaultService:
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self._ensure_structure()

    def _ensure_structure(self):
        """Create vault directories if they don't exist."""
        for category in CATEGORIES:
            (self.vault_path / category).mkdir(parents=True, exist_ok=True)
        # Ensure Inbox-Log exists
        log_path = self.vault_path / "Inbox-Log.md"
        if not log_path.exists():
            log_path.write_text("# Inbox Log\n\nCapture history and review items.\n\n")

    def write_note(
        self,
        category: str,
        name: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Path:
        """Write a markdown note with YAML frontmatter."""
        safe_name = self._sanitize_filename(name)
        file_path = self.vault_path / category / f"{safe_name}.md"

        # Build frontmatter
        frontmatter = {
            "type": category.lower(),
            "status": metadata.get("status", "active") if metadata else "active",
            "created": datetime.now().strftime("%Y-%m-%d"),
        }
        if metadata:
            frontmatter.update({k: v for k, v in metadata.items() if v})

        # Build markdown content
        md_content = "---\n"
        md_content += yaml.dump(frontmatter, default_flow_style=False)
        md_content += "---\n\n"
        md_content += f"# {name}\n\n"
        md_content += content

        file_path.write_text(md_content)
        return file_path

    def delete_note(self, category: str, name: str) -> bool:
        """Delete a note by category and name."""
        safe_name = self._sanitize_filename(name)
        file_path = self.vault_path / category / f"{safe_name}.md"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def read_all_notes(self) -> str:
        """Read all active notes for briefings (excludes done)."""
        contents = []
        for category in CATEGORIES:
            category_path = self.vault_path / category
            if category_path.exists():
                for file_path in category_path.glob("*.md"):
                    try:
                        text = file_path.read_text()
                        # Skip done notes
                        if "status: done" in text:
                            continue
                        contents.append(f"=== {category}/{file_path.name} ===\n{text}")
                    except Exception as e:
                        logger.error(f"Error reading {file_path}: {e}")
        return "\n\n".join(contents)

    def log_capture(
        self,
        message: str,
        category: str,
        name: str,
        confidence: float,
        needs_review: bool = False,
    ):
        """Log a capture to Inbox-Log.md."""
        log_path = self.vault_path / "Inbox-Log.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        status = "REVIEW" if needs_review else "FILED"

        entry = f"\n## [{timestamp}] {status}\n"
        entry += f"- **Category:** {category}\n"
        entry += f"- **Name:** {name}\n"
        entry += f"- **Confidence:** {confidence:.0%}\n"
        entry += f"- **Message:** {message[:100]}{'...' if len(message) > 100 else ''}\n"

        with open(log_path, "a") as f:
            f.write(entry)

    def _sanitize_filename(self, name: str) -> str:
        """Convert name to safe filename."""
        # Remove invalid chars, replace spaces with hyphens
        safe = re.sub(r'[<>:"/\\|?*]', "", name)
        safe = re.sub(r"\s+", "-", safe.strip())
        return safe[:50]  # Limit length


# =============================================================================
# Claude Service
# =============================================================================


class ClaudeService:
    def __init__(self, anthropic_api_key: str, openai_api_key: str):
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        self.model = "claude-sonnet-4-5-20250929"

    def classify(self, message: str) -> dict:
        """Classify a message into a category."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            messages=[
                {"role": "user", "content": CLASSIFY_PROMPT.format(message=message)}
            ],
        )
        text = response.content[0].text
        # Extract JSON from response
        try:
            # Try to parse directly
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in response
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Could not parse classification response: {text}")

    def extract_fields(self, message: str, category: str) -> dict:
        """Extract structured fields from a message."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": EXTRACT_PROMPT.format(message=message, category=category),
                }
            ],
        )
        text = response.content[0].text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"notes": message}

    def generate_briefing(self, vault_contents: str, weekly: bool = False) -> str:
        """Generate morning briefing or weekly review."""
        prompt = WEEKLY_PROMPT if weekly else BRIEFING_PROMPT
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": prompt.format(vault_contents=vault_contents),
                }
            ],
        )
        return response.content[0].text

    def transcribe_audio(self, audio_bytes: bytes) -> str:
        """Transcribe audio using OpenAI Whisper API."""
        response = self.openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.ogg", audio_bytes),
        )
        return response.text


# =============================================================================
# State Manager
# =============================================================================


class StateManager:
    """Track pending clarifications for low-confidence classifications."""

    def __init__(self):
        self.pending: dict[int, dict] = {}  # message_id -> {message, classification}

    def add_pending(self, message_id: int, original_message: str, classification: dict):
        self.pending[message_id] = {
            "message": original_message,
            "classification": classification,
        }

    def get_pending(self, message_id: int) -> Optional[dict]:
        return self.pending.get(message_id)

    def remove_pending(self, message_id: int):
        self.pending.pop(message_id, None)


# =============================================================================
# Telegram Handlers
# =============================================================================


class UltrathinkBot:
    def __init__(self, config: Config):
        self.config = config
        self.vault = VaultService(config.vault_path)
        self.claude = ClaudeService(config.anthropic_api_key, config.openai_api_key)
        self.state = StateManager()
        self.tz = pytz.timezone(config.timezone)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main capture handler for new text messages."""
        if not update.message or not update.message.text:
            return

        # Only respond to configured chat
        if update.effective_chat.id != self.config.telegram_chat_id:
            return

        message_text = update.message.text

        # Skip commands
        if message_text.startswith("/"):
            return

        # Check for done: command (works without reply)
        done_match = re.match(r"done:\s*(.+)", message_text, re.IGNORECASE)
        if done_match:
            await self._handle_done_standalone(update, done_match.group(1))
            return

        # Check for fix: command (standalone requires category + note)
        fix_match = re.match(r"fix:\s*(\w+)\s+(.+)", message_text, re.IGNORECASE)
        if fix_match:
            await self._handle_fix_standalone(update, fix_match.group(1), fix_match.group(2))
            return

        await self._process_text(message_text, update, context)

    async def _process_text(
        self, message_text: str, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Process text through classification pipeline."""
        try:
            # Classify the message
            classification = self.claude.classify(message_text)
            category = classification.get("category", "Ideas")
            confidence = classification.get("confidence", 0.5)
            name = classification.get("name", "Untitled")

            if confidence >= self.config.confidence_threshold:
                # High confidence - file immediately
                fields = self.claude.extract_fields(message_text, category)
                content = self._format_content(fields)
                self.vault.write_note(category, name, content, fields)
                self.vault.log_capture(message_text, category, name, confidence)

                await update.message.reply_text(
                    f"Filed as {category.upper()}: '{name}' ({confidence:.0%})"
                )
            else:
                # Low confidence - ask for clarification
                self.vault.log_capture(
                    message_text, category, name, confidence, needs_review=True
                )

                # Store pending state
                sent_msg = await update.message.reply_text(
                    f"Unsure ({confidence:.0%}). Which category?\n\n"
                    f"Reply with: People / Projects / Ideas / Admin\n"
                    f"Or: fix: <category> to correct later"
                )
                self.state.add_pending(
                    sent_msg.message_id,
                    message_text,
                    {"category": category, "name": name, "confidence": confidence},
                )

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text(f"Error processing message: {e}")

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages by transcribing and processing as text."""
        if not update.message or not update.message.voice:
            return

        # Only respond to configured chat
        if update.effective_chat.id != self.config.telegram_chat_id:
            return

        try:
            # Download voice file
            file = await context.bot.get_file(update.message.voice.file_id)
            audio_bytes = await file.download_as_bytearray()

            # Transcribe
            transcript = self.claude.transcribe_audio(bytes(audio_bytes))

            # Send transcription preview to user
            preview = transcript[:100] + "..." if len(transcript) > 100 else transcript
            await update.message.reply_text(f"Heard: {preview}")

            # Process through normal pipeline
            await self._process_text(transcript, update, context)

        except Exception as e:
            logger.error(f"Error handling voice message: {e}")
            await update.message.reply_text(f"Error processing voice: {e}")

    async def handle_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle replies for clarification or fixes."""
        if not update.message or not update.message.reply_to_message:
            return

        if update.effective_chat.id != self.config.telegram_chat_id:
            return

        reply_text = update.message.text.strip()
        original_msg = update.message.reply_to_message

        # Check for done command
        done_match = re.match(r"done:\s*(.+)?", reply_text, re.IGNORECASE)
        if done_match:
            await self._handle_done(update, original_msg, done_match.group(1))
            return

        # Check for fix command
        fix_match = re.match(r"fix:\s*(\w+)", reply_text, re.IGNORECASE)
        if fix_match:
            await self._handle_fix(update, original_msg, fix_match.group(1))
            return

        # Check for category answer
        category = self._match_category(reply_text)
        if category:
            await self._handle_category_answer(update, original_msg, category)
            return

        # Not a recognized command
        await update.message.reply_text(
            "Reply with a category (People/Projects/Ideas/Admin) or 'fix: <category>'"
        )

    async def _handle_fix(self, update: Update, original_msg, new_category: str):
        """Handle fix: command to move a note to different category."""
        new_category = self._match_category(new_category)
        if not new_category:
            await update.message.reply_text(
                f"Unknown category. Use: People, Projects, Ideas, Admin"
            )
            return

        # Parse the original confirmation message
        # Format: "Filed as CATEGORY: 'name' (XX%)"
        text = original_msg.text
        match = re.search(r"Filed as (\w+): '([^']+)'", text)
        if not match:
            await update.message.reply_text("Can't parse original filing. Please refile manually.")
            return

        old_category = match.group(1).title()
        name = match.group(2)

        # Move the file
        old_path = self.config.vault_path / old_category / f"{self.vault._sanitize_filename(name)}.md"
        if old_path.exists():
            content = old_path.read_text()
            # Update frontmatter type
            content = re.sub(r"type: \w+", f"type: {new_category.lower()}", content)
            new_path = self.config.vault_path / new_category / old_path.name
            new_path.write_text(content)
            old_path.unlink()

            await update.message.reply_text(f"Moved '{name}' from {old_category} to {new_category}")
        else:
            await update.message.reply_text(f"File not found: {old_path.name}")

    async def _handle_done(self, update: Update, original_msg, note_hint: str = None):
        """Mark a note as done (reply-based). Delegates to standalone handler."""
        if not note_hint:
            await update.message.reply_text("Usage: done: <note name>")
            return
        await self._handle_done_standalone(update, note_hint)

    async def _handle_done_standalone(self, update: Update, note_hint: str):
        """Mark a note as done (standalone message, not reply)."""
        note_hint = note_hint.strip().lower()
        found_path = None
        found_name = None

        for category in CATEGORIES:
            category_path = self.config.vault_path / category
            if category_path.exists():
                for file_path in category_path.glob("*.md"):
                    # Match against filename (convert hyphens to spaces)
                    if note_hint in file_path.stem.lower().replace("-", " "):
                        found_path = file_path
                        found_name = file_path.stem
                        break
                    # Match against title in content
                    try:
                        content = file_path.read_text()
                        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
                        if title_match and note_hint in title_match.group(1).lower():
                            found_path = file_path
                            found_name = title_match.group(1)
                            break
                        # Match against content body
                        if note_hint in content.lower():
                            found_path = file_path
                            found_name = title_match.group(1) if title_match else file_path.stem
                            break
                    except Exception:
                        pass
            if found_path:
                break

        if found_path:
            content = found_path.read_text()
            content = re.sub(r"status: \w+", "status: done", content)
            found_path.write_text(content)
            await update.message.reply_text(f"Marked '{found_name}' as done")
        else:
            await update.message.reply_text(f"No note found matching: {note_hint}")

    async def _handle_fix_standalone(self, update: Update, new_category: str, note_hint: str):
        """Move a note to a different category (standalone message)."""
        new_category = self._match_category(new_category)
        if not new_category:
            await update.message.reply_text("Unknown category. Use: People, Projects, Ideas, Admin")
            return

        # Find the note
        note_hint = note_hint.strip().lower()
        found_path = None
        old_category = None

        for category in CATEGORIES:
            category_path = self.config.vault_path / category
            if category_path.exists():
                for file_path in category_path.glob("*.md"):
                    # Match against filename (convert hyphens to spaces)
                    if note_hint in file_path.stem.lower().replace("-", " "):
                        found_path = file_path
                        old_category = category
                        break
                    # Match against title in content
                    try:
                        content = file_path.read_text()
                        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
                        if title_match and note_hint in title_match.group(1).lower():
                            found_path = file_path
                            old_category = category
                            break
                    except Exception:
                        pass
            if found_path:
                break

        if not found_path:
            await update.message.reply_text(f"No note found matching: {note_hint}")
            return

        # Move the file
        content = found_path.read_text()
        content = re.sub(r"type: \w+", f"type: {new_category.lower()}", content)
        new_path = self.config.vault_path / new_category / found_path.name
        new_path.write_text(content)
        found_path.unlink()

        await update.message.reply_text(f"Moved '{found_path.stem}' from {old_category} to {new_category}")

    async def _handle_category_answer(
        self, update: Update, original_msg, category: str
    ):
        """Handle category answer for pending clarification."""
        pending = self.state.get_pending(original_msg.message_id)
        if not pending:
            # Try to handle as a new classification
            await update.message.reply_text(
                "No pending clarification found. Send a new message to capture."
            )
            return

        message_text = pending["message"]
        name = pending["classification"].get("name", "Untitled")

        # Extract and file
        fields = self.claude.extract_fields(message_text, category)
        content = self._format_content(fields)
        self.vault.write_note(category, name, content, fields)

        self.state.remove_pending(original_msg.message_id)

        await update.message.reply_text(f"Filed as {category.upper()}: '{name}'")

    def _match_category(self, text: str) -> Optional[str]:
        """Match text to a category name."""
        text = text.lower().strip()
        for cat in CATEGORIES:
            if cat.lower() == text or cat.lower().startswith(text):
                return cat
        return None

    def _format_content(self, fields: dict) -> str:
        """Format extracted fields as markdown content."""
        content = ""
        if fields.get("next_action"):
            content += f"## Next Action\n{fields['next_action']}\n\n"
        if fields.get("notes"):
            content += f"## Notes\n{fields['notes']}\n\n"
        if fields.get("context"):
            content += f"## Context\n{fields['context']}\n\n"
        if fields.get("area"):
            content += f"## Area\n{fields['area']}\n\n"
        if fields.get("due"):
            content += f"## Due\n{fields['due']}\n\n"
        return content.strip()

    async def morning_briefing(self, context: ContextTypes.DEFAULT_TYPE):
        """Send morning briefing at 7 AM."""
        try:
            vault_contents = self.vault.read_all_notes()
            if not vault_contents.strip():
                briefing = "No notes in vault yet. Start capturing!"
            else:
                briefing = self.claude.generate_briefing(vault_contents, weekly=False)

            await context.bot.send_message(
                chat_id=self.config.telegram_chat_id,
                text=f"☀️ *Morning Briefing*\n\n{briefing}",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error generating morning briefing: {e}")

    async def weekly_review(self, context: ContextTypes.DEFAULT_TYPE):
        """Send weekly review at 4 PM Sunday."""
        try:
            vault_contents = self.vault.read_all_notes()
            if not vault_contents.strip():
                review = "No notes in vault yet. Start capturing!"
            else:
                review = self.claude.generate_briefing(vault_contents, weekly=True)

            await context.bot.send_message(
                chat_id=self.config.telegram_chat_id,
                text=f"📋 *Weekly Review*\n\n{review}",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error generating weekly review: {e}")

    async def cmd_briefing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manual trigger for morning briefing."""
        if update.effective_chat.id != self.config.telegram_chat_id:
            return
        await self.morning_briefing(context)

    async def cmd_review(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manual trigger for weekly review."""
        if update.effective_chat.id != self.config.telegram_chat_id:
            return
        await self.weekly_review(context)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show vault status."""
        if update.effective_chat.id != self.config.telegram_chat_id:
            return

        counts = {}
        for cat in CATEGORIES:
            path = self.config.vault_path / cat
            counts[cat] = len(list(path.glob("*.md"))) if path.exists() else 0

        total = sum(counts.values())
        status = "📊 *Vault Status*\n\n"
        for cat, count in counts.items():
            status += f"• {cat}: {count}\n"
        status += f"\n*Total: {total} notes*"

        await update.message.reply_text(status, parse_mode="Markdown")


# =============================================================================
# Main
# =============================================================================


def main():
    config = Config.from_env()
    bot = UltrathinkBot(config)

    # Build application
    app = Application.builder().token(config.telegram_token).build()

    # Add handlers
    # Reply handler must come before general message handler
    app.add_handler(
        MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, bot.handle_reply)
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message)
    )
    app.add_handler(MessageHandler(filters.VOICE, bot.handle_voice))
    app.add_handler(CommandHandler("briefing", bot.cmd_briefing))
    app.add_handler(CommandHandler("review", bot.cmd_review))
    app.add_handler(CommandHandler("status", bot.cmd_status))

    # Schedule briefings
    scheduler = AsyncIOScheduler(timezone=bot.tz)
    scheduler.add_job(
        lambda: app.job_queue.run_once(bot.morning_briefing, 0),
        "cron",
        hour=7,
        minute=0,
    )
    scheduler.add_job(
        lambda: app.job_queue.run_once(bot.weekly_review, 0),
        "cron",
        day_of_week="sun",
        hour=16,
        minute=0,
    )
    scheduler.start()

    logger.info(f"Ultrathink bot starting...")
    logger.info(f"Vault path: {config.vault_path}")
    logger.info(f"Timezone: {config.timezone}")
    logger.info(f"Confidence threshold: {config.confidence_threshold}")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
