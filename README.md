# Second Brain

> A local-first personal knowledge base with a visual web UI and Telegram bot. Capture anything — links, jobs, ideas, notes, inspiration — from the terminal or Telegram. Browse visually on the web.

## Features

- Visual web UI with category cards, images, and recent links at a glance
- Telegram bot — share URLs or text directly into your brain from anywhere
- Full CLI for power users
- Full-text search with SQLite FTS5
- Dark/light mode
- Everything stored in iCloud Drive — syncs across your Macs automatically

## Setup

### 1. Install dependencies

```bash
pip3 install -r requirements.txt --user
```

### 2. Initialize the database

```bash
python3 brain.py init
```

### 3. Start the web UI

```bash
python3 brain.py web
```

Opens http://localhost:8787

### 4. Set up the Telegram bot (optional)

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`, follow the prompts, copy the token
3. Copy `.env.example` to `.env` and paste your token:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   ```
4. Start the bot:
   ```bash
   python3 brain.py bot
   ```
5. Find your bot on Telegram and send it a URL or message

## CLI Usage

```bash
# First time
python3 brain.py init

# Adding entries
python3 brain.py add                          # interactive prompts
python3 brain.py quick "great idea"           # instant one-liner note
python3 brain.py quick "apply here" -T job    # specify type

# Finding entries
python3 brain.py list                         # list active entries
python3 brain.py list --type job              # filter by type
python3 brain.py list --tag python            # filter by tag
python3 brain.py list --all                   # include archived + done
python3 brain.py search "machine learning"    # full-text search

# Managing entries
python3 brain.py show 5                       # show full entry #5
python3 brain.py edit 5                       # edit interactively
python3 brain.py tag 5 rust,backend           # add tags
python3 brain.py done 5                       # mark as done
python3 brain.py archive 5                    # archive
python3 brain.py delete 5                     # delete (asks for confirmation)

# Stats & export
python3 brain.py stats                        # overview
python3 brain.py tags                         # all tags + counts
python3 brain.py types                        # all types + counts
python3 brain.py export backup.json           # export everything to JSON

# Web UI
python3 brain.py web                          # opens http://localhost:8787
python3 brain.py web --port 9000              # custom port
python3 brain.py web --no-browser             # don't auto-open browser

# Telegram bot
python3 brain.py bot                          # start the bot
```

## Telegram Bot Usage

- Send any URL — auto-saved with detected type and tags
- `job: <url>` — saves as job
- `recipe: <url>` — saves as inspiration
- `idea: your idea` — saves as idea
- `note: reminder text` — saves as note
- `/browse` — browse categories with inline buttons
- `/search <query>` — search your brain
- `/random` — get a random entry
- `/stats` — see your counts
- `/help` — show help

## Tech Stack

| Layer | Technology |
|---|---|
| Database | SQLite + FTS5 |
| CLI | Python · click · rich |
| Web | Flask + vanilla JS |
| Bot | python-telegram-bot v20 |
| Storage | iCloud Drive |

## Project Structure

```
second-brain/
├── brain.py          # CLI entry point (click commands)
├── server.py         # Flask app factory + all REST API routes
├── db.py             # Database layer: schema, FTS, helpers
├── bot.py            # Telegram bot
├── templates/
│   └── index.html    # SPA shell
├── static/
│   ├── style.css     # All styles, dark + light themes
│   └── app.js        # SPA logic, hash router, API calls
├── requirements.txt
├── .env.example      # Copy to .env and add your Telegram token
├── LICENSE
└── README.md
```

## License

MIT — see [LICENSE](LICENSE).
