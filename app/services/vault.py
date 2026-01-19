import re
import logging
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.constants import CATEGORIES

logger = logging.getLogger(__name__)

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
