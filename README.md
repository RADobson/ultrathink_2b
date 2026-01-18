# Ultrathink

A self-hosted "Second Brain" Telegram bot. Send text or voice notes, get them auto-classified and filed as markdown.

Based on [Nate B Jones' Second Brain architecture](https://youtu.be/0TpON5T-Sw4).

## How It Works

```
You (Telegram) ──► ultrathink.py ──► Claude API (classify)
      │                   │
      │                   ▼
      │            ./vault/
      │            ├── People/
      │            ├── Projects/
      │            ├── Ideas/
      │            └── Admin/
      │
      └── Voice notes ──► OpenAI Whisper ──► transcribed text ──► classify
```

## The 4 Categories

| Category | What goes here |
|----------|----------------|
| **People** | Relationships, contacts, follow-ups |
| **Projects** | Multi-step work items with next actions |
| **Ideas** | Thoughts to explore later |
| **Admin** | Tasks, errands, appointments |

## Features

- **Text capture**: Send any text, gets classified and filed
- **Voice notes**: Transcribed via Whisper, then classified
- **Confidence threshold**: Low-confidence notes ask for clarification
- **Fix command**: Reply `fix: people` to reclassify
- **Morning briefing**: Daily at 7 AM (or `/briefing`)
- **Weekly review**: Sundays at 4 PM (or `/review`)
- **Vault status**: `/status` shows note counts

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/yourusername/ultrathink.git
cd ultrathink
cp .env.example .env
# Edit .env with your API keys
```

### 2. Get your API keys

- **Telegram**: Message `@BotFather` → `/newbot` → copy token
- **Telegram Chat ID**: Message `@userinfobot` → copy your ID
- **Anthropic**: https://console.anthropic.com/
- **OpenAI**: https://platform.openai.com/api-keys (for voice transcription)

### 3. Launch

```bash
docker compose up -d
```

### 4. Test

Send a message to your bot:
```
Call Sarah about Q3 budget by Friday
```

Bot responds:
```
Filed as PROJECTS: 'Sarah Q3 Budget Call' (87%)
```

Send a voice note - it will be transcribed and classified the same way.

## Commands

| Command | Description |
|---------|-------------|
| `/briefing` | Get morning briefing now |
| `/review` | Get weekly review now |
| `/status` | Show vault note counts |

## Fix Misclassifications

Reply to any bot confirmation:
```
fix: people
```

The note moves to the correct category.

## Vault Structure

```
vault/
├── People/
│   └── Sarah-Johnson.md
├── Projects/
│   └── Q3-Budget-Review.md
├── Ideas/
│   └── Blue-Ocean-Strategy.md
├── Admin/
│   └── Call-Dentist.md
└── Inbox-Log.md
```

Notes are markdown with YAML frontmatter:
```markdown
---
type: projects
status: active
created: 2024-01-15
---

# Q3 Budget Review

## Next Action
Call Sarah to discuss numbers

## Notes
Need figures by end of month
```

## Optional: Sync & Browse

The docker-compose includes optional services:

- **Syncthing** (port 8384): Sync vault to your devices
- **FileBrowser** (port 8080): Web UI to browse/edit notes

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | From @BotFather |
| `TELEGRAM_CHAT_ID` | Yes | Your chat ID |
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `OPENAI_API_KEY` | Yes | For Whisper transcription |
| `TIMEZONE` | No | Default: Australia/Brisbane |
| `CONFIDENCE_THRESHOLD` | No | Default: 0.6 |

## License

MIT
