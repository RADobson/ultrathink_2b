import re
import logging
from pathlib import Path
from app.constants import CATEGORIES

logger = logging.getLogger(__name__)

def migrate_to_checkboxes(vault_path: Path) -> list[str]:
    """Migrate existing notes to checkbox format.

    Converts **Next Action:** X to - [ ] X
    Returns list of migrated file names.
    """
    migrated = []
    for category in CATEGORIES:
        category_path = vault_path / category
        if category_path.exists():
            for file_path in category_path.glob("*.md"):
                try:
                    content = file_path.read_text()
                    # Convert **Next Action:** X to - [ ] X
                    new_content = re.sub(
                        r"\*\*Next Action:\*\*\s*(.+)",
                        r"- [ ] \1",
                        content
                    )
                    if new_content != content:
                        file_path.write_text(new_content)
                        migrated.append(file_path.name)
                except Exception as e:
                    logger.error(f"Error migrating {file_path}: {e}")
    return migrated
