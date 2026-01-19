from typing import Optional

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
