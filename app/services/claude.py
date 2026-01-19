import json
import re
import anthropic
import openai
from app.constants import (
    CLASSIFY_PROMPT,
    EXTRACT_PROMPT,
    BRIEFING_PROMPT,
    WEEKLY_PROMPT
)

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
