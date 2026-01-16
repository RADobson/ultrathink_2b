# Ultrathink

A self-hosted "Second Brain" system using Telegram, n8n, Obsidian, and CouchDB.

Based on [Nate B Jones' Second Brain architecture](https://youtu.be/0TpON5T-Sw4) - adapted for privacy-first, self-hosted infrastructure.

## The Stack

| Component | Role |
|-----------|------|
| **Telegram** | Capture interface (mobile-first) |
| **n8n** | Automation brain |
| **Claude API** | Classification + summarization |
| **Obsidian** | Storage (local markdown) |
| **CouchDB** | Sync (via LiveSync plugin) |

## The 4 Categories

Every thought is classified into one of four buckets:

| Category | What goes here | Key fields |
|----------|----------------|------------|
| **People** | Relationships, contacts, follow-ups | context, follow_ups |
| **Projects** | Multi-step deliverables with outcomes | status, next_action, notes |
| **Ideas** | Thoughts to explore later | oneliner, notes |
| **Admin** | Simple tasks, errands, appointments | due_date, status |

## Key Concepts

### The Bouncer (Confidence Threshold)
When Claude classifies a note with <60% confidence, it doesn't auto-file. Instead:
1. Logs the note as "needs_review"
2. Asks you via Telegram: "Which category?"
3. Waits for your reply to file correctly

### The Fix Button
Made a mistake? Reply to any confirmation with:
```
fix: should be people
```
The system will re-file the note to the correct category.

### The Receipt (Audit Trail)
Every capture is logged to `Inbox-Log.md`:
- Original text
- Where it was filed
- Confidence score
- Status (filed/needs_review)

## Architecture

```
You (Telegram)
     │
     ▼
   n8n ──────► Claude API (classify + extract fields)
     │
     ├── confidence >= 0.6 ──► Route to People/Projects/Ideas/Admin
     │                              │
     │                              ▼
     │                      Obsidian (markdown files)
     │                              │
     │                              ▼
     │                      LiveSync ──► CouchDB ──► Your devices
     │
     └── confidence < 0.6 ──► Bouncer (ask for clarification)
```

The "Headless Ghost": A Docker container runs Obsidian 24/7 on your server. When n8n writes a file, Obsidian sees it and syncs via LiveSync to CouchDB. Your iPad/phone pulls from CouchDB within seconds.

## Vault Structure

```
/Vault/
├── People/
│   └── John Smith.md
├── Projects/
│   └── Website Relaunch.md
├── Ideas/
│   └── Blue Ocean Strategy.md
├── Admin/
│   └── Call dentist.md
├── Inbox-Log.md
└── Daily/
```

## Workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| telegram-capture | Telegram message | Classify → Route → File → Confirm |
| bouncer-clarify | Reply to bot | Handle manual classification or "fix:" commands |
| morning-briefing | 7AM daily | Read all folders → Summarize → Send top 3 actions |
| weekly-review | Sunday 4PM | Review week → Open loops → Suggested actions |

## Quick Start

### Prerequisites
- Oracle Cloud Always Free account (or any VM with 4GB+ RAM)
- Domain with DNS pointing to your VM
- Telegram account
- Anthropic API key

### 1. Server Setup

```bash
ssh ubuntu@your-vm-ip

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Get the code
git clone https://github.com/yourusername/ultrathink.git
cd ultrathink
```

### 2. Configure

```bash
cp .env.example .env
nano .env  # Fill in your values
```

### 3. Launch

```bash
docker compose up -d
```

### 4. Configure Obsidian (one-time)

1. Open `https://obsidian.yourdomain.com`
2. Create vault at `/vault` named `Vault`
3. Create folders: `People`, `Projects`, `Ideas`, `Admin`
4. Create `Inbox-Log.md` with header:
   ```markdown
   # Inbox Log

   | Timestamp | Captured | Filed To | Name | Confidence | Status |
   |-----------|----------|----------|------|------------|--------|
   ```
5. Install "Self-hosted LiveSync" plugin
6. Connect to `http://couchdb:5984` with your credentials

### 5. Create Telegram Bot

1. Open Telegram and message `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the **API token** (looks like `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. Message your new bot to start a chat
5. Get your **chat ID** by messaging `@userinfobot` - it will reply with your ID

### 6. Configure n8n Credentials

Open `https://n8n.yourdomain.com` and log in.

#### Create Telegram Credential

1. Go to **Settings** (gear icon) → **Credentials**
2. Click **Add Credential** → search "Telegram"
3. Select **Telegram API**
4. Enter your bot token from step 5
5. Name it `Telegram Bot` and save

#### Create Anthropic API Credential

1. Go to **Settings** → **Credentials**
2. Click **Add Credential** → search "Header Auth"
3. Select **Header Auth**
4. Configure:
   - **Name**: `Anthropic API Key`
   - **Name** (header field): `x-api-key`
   - **Value**: Your Anthropic API key (from console.anthropic.com)
5. Save

### 7. Import n8n Workflows

For each workflow file in the `workflows/` folder:

1. In n8n, click **Add Workflow** (+ button)
2. Click the **three dots menu** (⋮) → **Import from File**
3. Select the JSON file (e.g., `telegram-capture.json`)
4. The workflow will load with all nodes

Import in this order:
1. `telegram-capture.json` - main capture workflow
2. `bouncer-clarify.json` - handles clarifications and fixes
3. `morning-briefing.json` - daily digest
4. `weekly-review.json` - weekly summary

### 8. Configure Workflow Credentials

After importing, you need to connect your credentials to each workflow:

#### For telegram-capture.json:
1. Open the workflow
2. Click on **Telegram Trigger** node → select your `Telegram Bot` credential
3. Click on **Claude Classify** node → select your `Anthropic API Key` credential
4. Click on **Bouncer: Ask Clarification** node → select `Telegram Bot`
5. Click on **Confirm Filed** node → select `Telegram Bot`
6. Save the workflow

#### For bouncer-clarify.json:
1. Click on **Telegram Trigger** node → select `Telegram Bot`
2. Click on **Claude Extract Fields** node → select `Anthropic API Key`
3. Click on **Confirm Clarified** node → select `Telegram Bot`
4. Click on **Confirm Fix** node → select `Telegram Bot`
5. Save

#### For morning-briefing.json:
1. Click on **Claude Summarize** node → select `Anthropic API Key`
2. Click on **Send Briefing** node → select `Telegram Bot`
3. Save

#### For weekly-review.json:
1. Click on **Claude Weekly Review** node → select `Anthropic API Key`
2. Click on **Send Weekly Review** node → select `Telegram Bot`
3. Save

### 9. Set Environment Variables in n8n

The workflows use environment variables for your Telegram chat ID:

1. Go to **Settings** → **Variables** (or edit your docker-compose environment)
2. Ensure `TELEGRAM_CHAT_ID` is set to your chat ID from step 5

Alternatively, you can hardcode the chat ID:
1. In each workflow, find nodes that reference `$env.TELEGRAM_CHAT_ID`
2. Replace with your actual chat ID number

### 10. Activate Workflows

1. Open each workflow
2. Toggle the **Active** switch in the top-right corner
3. For `telegram-capture` and `bouncer-clarify`, n8n will register webhooks with Telegram

**Important**: The Telegram trigger workflows need your n8n instance to be publicly accessible (via HTTPS) for webhooks to work.

### 11. Verify Webhook Registration

After activating `telegram-capture`:
1. Check the **Telegram Trigger** node
2. It should show a webhook URL like `https://n8n.yourdomain.com/webhook/xxx`
3. If webhooks fail, check:
   - Your domain is correctly pointed to your server
   - Caddy is running and providing HTTPS
   - Port 443 is open in your firewall

## Testing

**Basic capture:**
```
You: "Call Sarah about the Q3 budget by Friday"
Bot: Filed as PROJECTS: "Sarah Q3 Budget Call" (87% confident)
     Reply "fix: [category]" if wrong.
```

**Low confidence (triggers bouncer):**
```
You: "blue ocean"
Bot: I'm not confident how to classify this note (42% sure):
     "blue ocean"
     Which category? people/projects/ideas/admin
You: ideas
Bot: Got it! Filed as IDEAS: "Blue Ocean"
```

**Fix button:**
```
Bot: Filed as PROJECTS: "Sarah Meeting" (75% confident)
You: fix: should be people
Bot: Fixed! Moved "Sarah Meeting" from PROJECTS to PEOPLE.
```

## Cost

$0/month on Oracle Cloud Always Free tier.

## File Structure

```
ultrathink/
├── docker-compose.yml
├── .env.example
├── Caddyfile
├── workflows/
│   ├── telegram-capture.json
│   ├── bouncer-clarify.json
│   ├── morning-briefing.json
│   └── weekly-review.json
├── README.md
└── blog-post.md
```

## License

MIT
