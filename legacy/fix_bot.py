from pathlib import Path

path = Path("app/bot.py")
content = path.read_text()

# Fix the broken line
fixed = content.replace('r"^# (.+?)$"\n', 'r"^# (.+?)$", content')

path.write_text(fixed)
print("Fixed app/bot.py")
