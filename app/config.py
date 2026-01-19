import os
import logging
from dataclasses import dataclass
from pathlib import Path

# Configure logging
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
