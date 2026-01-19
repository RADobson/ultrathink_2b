# Building "Ultrathink": A Private, Self-Hosted Second Brain

*How I adapted Nate B Jones' Second Brain architecture for privacy-first, self-hosted infrastructure using Telegram, n8n, Obsidian, and a "Headless Ghost"*

---

I recently watched [Nate B Jones' video on building a Second Brain with AI](https://youtu.be/0TpON5T-Sw4), and it crystallized something I'd been thinking about for a while: the tools exist now to build a system that actively works on your information while you sleep.

But his stack (Slack + Notion + Zapier) didn't fit my requirements:
- I wanted **privacy** - my thoughts in local Markdown files, not SaaS databases
- I wanted **control** - no API rate limits or "you've hit your automation cap"
- I wanted **cost efficiency** - $0/month, not $50+

Here's how I adapted his architecture for a self-hosted stack: Telegram + n8n + Obsidian + CouchDB.

## Why This Moment Matters

For the first time in human history, we have access to systems that don't just store information - they actively classify, route, summarize, and surface information without us having to remember to do any of those things.

The shift isn't from "no notes" to "notes." It's from "storage" to "behavior-changing system."

## The 8 Building Blocks

Nate describes eight core components that make a Second Brain work. Here's how I implemented each one:

### 1. The Dropbox (Capture Point)

**Principle**: One place, one action, zero decisions at capture time.

The number one reason second brains fail is they require taxonomy work at capture time. They ask you to decide where something goes when you're walking into a meeting.

**My implementation**: A private Telegram chat with my bot. I open Telegram, type or voice-note my thought, hit send. Done. No folders, no tags, no decisions.

### 2. The Sorter (Classifier)

**Principle**: Let AI decide what bucket your thought belongs in.

This is the magic. Claude receives my raw thought and classifies it into one of four categories:

| Category | What goes here | Example |
|----------|----------------|---------|
| **People** | Relationships, contacts, follow-ups | "Met Sarah at the conference, she knows ML" |
| **Projects** | Multi-step deliverables | "Need to finish the API docs by Friday" |
| **Ideas** | Thoughts to explore later | "What if we applied BOS framework here?" |
| **Admin** | Simple tasks, errands | "Call the dentist" |

Why only four? More categories feel more precise but create more decisions, more confusion, more drift. Four buckets is enough. You can always add more later if evidence says it's needed.

### 3. The Form (Schema)

**Principle**: Consistent fields make automation possible.

Each category has a defined schema that Claude extracts:

**People:**
```yaml
name: John Smith
context: Met at DevConf, works at Acme Corp
follow_ups: Ask about his startup idea
last_touched: 2026-01-15
```

**Projects:**
```yaml
name: Website Relaunch
status: active
next_action: Email Sarah to confirm copy deadline by Friday
notes: Target launch March 1
```

The critical field is `next_action`. It must be **specific and executable**.
- Bad: "work on website"
- Good: "Email Sarah to confirm copy deadline by Friday"

### 4. The Filing Cabinet (Storage)

**Principle**: Writable by automation, readable by humans.

In Nate's stack, this is Notion. In mine, it's Obsidian with a folder structure:

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
└── Inbox-Log.md
```

Each file uses YAML frontmatter for metadata, making it queryable with Obsidian's Dataview plugin.

### 5. The Receipt (Audit Trail)

**Principle**: You stop trusting systems because errors feel mysterious.

Every capture gets logged to `Inbox-Log.md`:

| Timestamp | Captured | Filed To | Name | Confidence | Status |
|-----------|----------|----------|------|------------|--------|
| 2026-01-16 14:32 | Call Sarah about budget | projects | Sarah Budget Call | 0.85 | filed |
| 2026-01-16 15:01 | blue ocean thing | ideas | Blue Ocean | 0.42 | needs_review |

When something looks off, you can trace it. Trust comes from visibility.

### 6. The Bouncer (Confidence Filter)

**Principle**: Prevent low-quality outputs from polluting your memory.

When Claude classifies with less than 60% confidence, the system doesn't file. Instead:

1. Logs it as "needs_review"
2. Sends a Telegram message: "I'm not sure where this goes. Is this a project, idea, person, or admin task?"
3. Waits for your reply

This single mechanism keeps your second brain from becoming a junk drawer.

### 7. The Tap on Shoulder (Proactive Surfacing)

**Principle**: Humans don't retrieve consistently. We respond to what shows up.

Two scheduled workflows:

**Daily Briefing (7 AM):**
```
TOP 3 ACTIONS
1. Email Sarah to confirm copy deadline
2. Review Q3 budget with John
3. Call dentist

STUCK ON
- API documentation (sitting for 5 days)

SMALL WIN
- Completed website mockups yesterday
```

Format: Under 150 words. Fits on a phone screen. Read in 2 minutes.

**Weekly Review (Sunday 4 PM):**
```
WHAT HAPPENED
Captured 12 notes this week. 3 projects advanced, 2 new people added.

BIGGEST OPEN LOOPS
- API documentation still blocked
- Haven't followed up with Sarah
- Q3 budget review pending

SUGGESTED ACTIONS FOR NEXT WEEK
1. Block 2 hours for API docs
2. Message Sarah about coffee
3. Schedule budget review meeting

RECURRING THEME
- Lots of "waiting on others" - consider what you can unblock yourself
```

### 8. The Fix Button (Correction Mechanism)

**Principle**: Corrections must be trivial or people won't make them.

If the filing was wrong, reply to the confirmation message:
```
fix: should be people
```

The system re-files to the correct category. No dashboards, no navigation, no friction.

## The "Headless Ghost" Architecture

Here's where it gets interesting. Nate's video uses Notion because "cloud automation writing to local files is hard."

It's not hard. You just need a trick.

**The Problem**: n8n runs in the cloud. Obsidian stores files locally. If n8n writes a file on the server, your iPad doesn't know about it.

**The Solution**: Run the actual Obsidian desktop app on your server, 24/7, inside a Docker container. It's headless - no monitor - but it's real Obsidian.

```
Telegram → n8n → writes to /Vault/Projects/new-file.md
                        ↓
              Obsidian (running in Docker) sees file change
                        ↓
              LiveSync plugin pushes to CouchDB
                        ↓
              Your iPad pulls from CouchDB (seconds later)
```

The "ghost" is always watching the filesystem. When n8n writes, Obsidian syncs. Your devices update within seconds.

## The 12 Principles

These are engineering principles translated for non-engineers:

### 1. Reduce the human's job to one reliable behavior
If your system requires three behaviors, you don't have a system. The human's job is capture. Everything else is automation.

### 2. Separate memory from compute from interface
- **Memory**: Obsidian (where truth lives)
- **Compute**: n8n + Claude (where logic runs)
- **Interface**: Telegram (where humans interact)

You can swap any layer without rebuilding the others.

### 3. Treat prompts like APIs, not creative writing
A scalable prompt is a contract: fixed input format, fixed output format, no surprises. JSON schema in, JSON out.

### 4. Always build a trust mechanism
The inbox log, confidence scores, and fix button aren't features - they're trust mechanisms. Without them, small errors compound until you abandon the system.

### 5. Default to safe behavior when uncertain
The bouncer exists because the safest default when Claude isn't sure is: don't file, ask for clarification.

### 6. Make output small, frequent, and actionable
Daily digest: under 150 words. Weekly review: under 250 words. Small outputs reduce cognitive load and increase follow-through.

### 7. Use next action as the unit of execution
"Work on the website" is not executable. "Email Sarah to confirm the copy deadline" is. Projects without concrete next actions become motivational, not operational.

### 8. Prefer routing over organizing
Humans hate organizing. Claude is good at routing. Don't make users maintain structures - let the system route into stable buckets.

### 9. Keep fields painfully small
Each category has 3-5 fields max. Richness creates friction; friction kills adoption. Start simple, add sophistication only when evidence demands it.

### 10. Design for restart, not perfection
Life happens. You'll fall off for a week. The system should be easy to restart without guilt. Just do a 10-minute brain dump and resume tomorrow.

### 11. Build one workflow, then attach modules
Core loop first: capture → classify → file → surface. Once that works, add voice capture, calendar integration, email forwarding.

### 12. Optimize for maintainability over cleverness
Fewer tools, fewer steps, clear logs, easy reconnects. When your Telegram token expires, you want to fix it in 5 minutes, not debug for an hour.

## The Stack

| Component | What it does | Why this choice |
|-----------|--------------|-----------------|
| **Telegram** | Capture interface | Free, fast, everywhere, great bot API |
| **n8n** | Automation | Self-hosted, no limits, visual workflow builder |
| **Claude API** | Classification + summarization | Best at structured extraction |
| **Obsidian** | Storage | Local markdown, excellent mobile apps |
| **CouchDB** | Sync | Used by LiveSync plugin |
| **Caddy** | Reverse proxy | Automatic HTTPS |

Total cost: **$0/month** on Oracle Cloud Always Free tier.

## The Workflows

Four n8n workflows power the system:

1. **telegram-capture.json**: Telegram message → Claude classify → Route to folder → Log → Confirm
2. **bouncer-clarify.json**: Handle "fix:" commands and manual classifications
3. **morning-briefing.json**: 7AM cron → Read all folders → Claude summary → Telegram
4. **weekly-review.json**: Sunday 4PM → Review week → Open loops → Suggestions

## Getting Started

### Step 1: Server Setup

Spin up an Oracle Cloud Always Free VM (or any server with 4GB+ RAM):

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Clone the repo
git clone https://github.com/yourusername/ultrathink.git
cd ultrathink

# Configure environment
cp .env.example .env
nano .env  # Fill in your values

# Launch
docker compose up -d
```

### Step 2: Create Your Telegram Bot

1. Message `@BotFather` on Telegram
2. Send `/newbot` and follow prompts
3. Save the API token (e.g., `1234567890:ABCdefGHI...`)
4. Message `@userinfobot` to get your chat ID

### Step 3: Configure Obsidian (One-Time)

1. Open `https://obsidian.yourdomain.com` (VNC in browser)
2. Create vault at `/vault` named `Vault`
3. Create folders: `People/`, `Projects/`, `Ideas/`, `Admin/`
4. Create `Inbox-Log.md` with this header:
   ```markdown
   # Inbox Log
   | Timestamp | Captured | Filed To | Name | Confidence | Status |
   |-----------|----------|----------|------|------------|--------|
   ```
5. Install "Self-hosted LiveSync" plugin, connect to `http://couchdb:5984`

### Step 4: Set Up n8n Workflows

This is the detailed part. Open `https://n8n.yourdomain.com`:

**Create Credentials:**

1. **Telegram Bot credential:**
   - Settings → Credentials → Add → "Telegram API"
   - Paste your bot token
   - Name it `Telegram Bot`

2. **Anthropic API credential:**
   - Settings → Credentials → Add → "Header Auth"
   - Name: `Anthropic API Key`
   - Header Name: `x-api-key`
   - Header Value: your Anthropic API key

**Import Workflows:**

For each file in `workflows/`:
1. Click **+** (Add Workflow)
2. Click **⋮** menu → **Import from File**
3. Select the JSON file

Import order: `telegram-capture.json`, `bouncer-clarify.json`, `morning-briefing.json`, `weekly-review.json`

**Connect Credentials to Nodes:**

After importing each workflow, you must connect your credentials:

For **telegram-capture**:
- Click each Telegram node → select `Telegram Bot` credential
- Click the `Claude Classify` HTTP node → select `Anthropic API Key`

For **bouncer-clarify**:
- Same pattern: Telegram nodes get `Telegram Bot`, Claude node gets `Anthropic API Key`

For **morning-briefing** and **weekly-review**:
- Claude nodes get `Anthropic API Key`
- Telegram nodes get `Telegram Bot`

**Set Your Chat ID:**

In each workflow, find nodes that reference `$env.TELEGRAM_CHAT_ID` and either:
- Set the environment variable in n8n settings, or
- Replace with your actual chat ID number

**Activate Workflows:**

1. Open each workflow
2. Toggle the **Active** switch (top-right)
3. For Telegram triggers, n8n will register webhooks automatically

### Step 5: Test It

Send a message to your bot:
```
Call Sarah about the Q3 budget by Friday
```

You should receive:
```
Filed as PROJECTS: "Sarah Q3 Budget Call" (87% confident)
Reply "fix: [category]" if wrong.
```

Check your Obsidian vault - a new file should appear in `Projects/`.

## What This Feels Like

After a week of using this:

- **Head is clearer.** When a thought appears, I throw it at Telegram and move on. The system handles the rest.
- **Morning has direction.** The daily briefing tells me exactly what to do first.
- **Open loops close.** The weekly review surfaces things I'd forgotten.
- **Trust builds.** Because I can see what the system did and correct mistakes easily, I actually use it.

The anxiety doesn't magically disappear. But it changes character. It stops being a background hum of untracked commitments and starts being a small set of next actions I can actually take.

## Conclusion

For 500,000 years, we've had the same cognitive architecture. We can hold 4-7 things in working memory. We're terrible at retrieval. We forget what matters.

For the first time, we have systems that work for us while we sleep. That classify without us deciding. That surface without us searching. That nudge without us remembering.

And you don't have to be an engineer to build this. You just have to understand patterns.

The patterns are:
- One capture point, zero decisions
- Four stable buckets, not infinite folders
- Confidence thresholds, not blind trust
- Small outputs, high frequency
- Easy corrections, no friction

That's the whole architecture. Build it yourself in an afternoon.

---

*The full source code (Docker Compose, n8n workflows, and configs) is available in this repo.*

*Questions? Find me on Twitter or drop me a line.*
