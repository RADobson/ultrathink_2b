import os
import sys
from pathlib import Path
import shutil

# Mock env vars
os.environ["TELEGRAM_BOT_TOKEN"] = "dummy"
os.environ["TELEGRAM_CHAT_ID"] = "123456"
os.environ["ANTHROPIC_API_KEY"] = "dummy"
os.environ["OPENAI_API_KEY"] = "dummy"
os.environ["VAULT_PATH"] = "./test_vault"
os.environ["TZ"] = "UTC"
os.environ["CONFIDENCE_THRESHOLD"] = "0.7"

def test_vault():
    print("Testing VaultService...")
    from app.services.vault import VaultService
    
    vault_path = Path("./test_vault")
    if vault_path.exists():
        shutil.rmtree(vault_path)
    
    service = VaultService(vault_path)
    
    # Test writing
    service.write_note("Ideas", "Test Idea", "Some content")
    
    file_path = vault_path / "Ideas" / "Test-Idea.md"
    if file_path.exists():
        print("✅ Note created successfully")
    else:
        print("❌ Note creation failed")
        sys.exit(1)
        
    # Test reading
    content = service.read_all_notes()
    if "Test Idea" in content:
        print("✅ Read notes successfully")
    else:
        print("❌ Read notes failed")
        sys.exit(1)

    # Cleanup
    shutil.rmtree(vault_path)

def test_imports():
    print("Testing imports...")
    try:
        from app.config import Config
        from app.bot import UltrathinkBot
        from app.main import main
        print("✅ Imports successful")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_imports()
    test_vault()
    print("All checks passed!")
