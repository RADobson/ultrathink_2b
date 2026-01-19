import re
import logging
import pytz
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from app.config import Config
from app.constants import CATEGORIES
from app.services.vault import VaultService
from app.services.claude import ClaudeService
from app.state import StateManager

logger = logging.getLogger(__name__)

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
        self,
        message_text: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
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
            "Reply with a category (People/Projects/Ideas/Admin) or 'fix: <category>'")

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
        """Mark a checkbox task as done, or fall back to marking entire note done."""
        note_hint = note_hint.strip().lower()

        # First, search for checkbox task matching hint
        checkbox_pattern = re.compile(r"- \[ \] (.+)", re.IGNORECASE)
        found_path = None
        found_task = None

        for category in CATEGORIES:
            category_path = self.config.vault_path / category
            if category_path.exists():
                for file_path in category_path.glob("*.md"):
                    try:
                        content = file_path.read_text()
                        for match in checkbox_pattern.finditer(content):
                            task_text = match.group(1)
                            if note_hint in task_text.lower():
                                found_path = file_path
                                found_task = task_text
                                break
                    except Exception:
                        pass
                    if found_path:
                        break
            if found_path:
                break

        if found_path and found_task:
            # Mark specific checkbox task as done
            content = found_path.read_text()
            content = content.replace(f"- [ ] {found_task}", f"- [x] {found_task}")
            found_path.write_text(content)
            note_name = found_path.stem.replace("-", " ").title()
            await update.message.reply_text(f"✓ '{found_task}' in '{note_name}'")
            return

        # Fallback: search for note by name/content and mark entire note as done
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
            await update.message.reply_text(f"Marked note '{found_name}' as done (no checkbox found)")
        else:
            await update.message.reply_text(f"No task or note found matching: {note_hint}")

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
        self,
        update: Update,
        original_msg,
        category: str
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
        # Handle tasks array (new format)
        if fields.get("tasks"):
            content += "## Tasks\n"
            for task in fields["tasks"]:
                content += f"- [ ] {task}\n"
            content += "\n"
        # Backward compatibility: handle single next_action
        elif fields.get("next_action"):
            content += f"## Tasks\n- [ ] {fields['next_action']}\n\n"
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