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

### 3b. Web Vault UI

Open `http://<server-ip>:8080` and log in with `WEB_USERNAME` / `WEB_PASSWORD`.

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

## Web Vault UI

The docker-compose includes a built-in web UI for browsing and editing notes.

- **Web UI** (port 8080): Simple login + markdown editor for the vault

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | From @BotFather |
| `TELEGRAM_CHAT_ID` | Yes | Your chat ID |
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `OPENAI_API_KEY` | Yes | For Whisper transcription |
| `TIMEZONE` | No | Default: Australia/Brisbane |
| `CONFIDENCE_THRESHOLD` | No | Default: 0.6 |
| `PUID` | No | Container user ID (match host owner of vault) |
| `PGID` | No | Container group ID (match host owner of vault) |
| `WEB_USERNAME` | No | Web UI login username (default: admin) |
| `WEB_PASSWORD` | Yes (for web UI) | Web UI login password |
| `WEB_SECRET` | No | Session secret for web UI (auto-generated if omitted) |

## Multi-User Onboarding (Per Linux User)

This keeps each user fully isolated with their own Linux account and vault at
`/home/<user>/vault`, while reusing the same app code. Each user runs their own
Docker Compose stack with a unique bot token and web port.

### Manual Steps

1. Create a Linux user
   ```bash
   sudo useradd -m -s /bin/bash <username>
   sudo usermod -aG docker <username>
   ```

2. Create a vault
   ```bash
   sudo -u <username> mkdir -p /home/<username>/vault
   ```

3. Clone the repo into the user's home
   ```bash
   sudo -u <username> git clone https://github.com/yourusername/ultrathink.git /home/<username>/ultrathink
   ```

4. Create a per-user `.env`
   ```bash
   sudo -u <username> cp /home/<username>/ultrathink/.env.example /home/<username>/ultrathink/.env
   sudo -u <username> nano /home/<username>/ultrathink/.env
   ```

   Set:
   - `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` for that user
   - `WEB_PASSWORD`
   - `PUID`/`PGID` to match the Linux user (see `id -u` / `id -g`)
   - Optional: `WEB_USERNAME`, `TIMEZONE`

5. Pick a unique web port and update `docker-compose.yml` if needed
   ```bash
   sudo -u <username> sed -n '1,120p' /home/<username>/ultrathink/docker-compose.yml
   ```

   Change the `web` service port mapping to a free port (e.g., `8081:8000`).

6. Start the user's stack
   ```bash
   sudo -u <username> docker compose -p <username> -f /home/<username>/ultrathink/docker-compose.yml up -d --build
   ```

7. Verify
   - Send a message to their bot
   - Open `http://<server-ip>:<port>` and log in

### Optional: Use the onboarding script

See `scripts/onboard_user.sh` for a guided setup that creates the user, vault,
`.env`, and starts the compose stack.

## License

MIT
