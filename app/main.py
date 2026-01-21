import sys
import os
import logging
from pathlib import Path

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import Config
from app.bot import UltrathinkBot
from app.utils import migrate_to_checkboxes

logger = logging.getLogger(__name__)

def main():
    # Handle migration command
    if len(sys.argv) > 1 and sys.argv[1] == "--migrate":
        vault_path = Path(os.environ.get("VAULT_PATH", "/vault"))
        print(f"Migrating notes in {vault_path} to checkbox format...")
        migrated = migrate_to_checkboxes(vault_path)
        if migrated:
            print(f"Migrated {len(migrated)} files:")
            for name in migrated:
                print(f"  - {name}")
        else:
            print("No files needed migration.")
        return

    try:
        config = Config.from_env()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

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
    app.add_handler(CommandHandler("help", bot.cmd_help))

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
