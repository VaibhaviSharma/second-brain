# Second Brain

> A local-first personal knowledge base — capture notes, links, jobs, ideas, and inspiration from your terminal, browser, or iPhone. Everything syncs through iCloud.

---

## Features

- **CLI** — add, search, edit, tag, archive, and export entries from the terminal with a clean rich interface
- **Web UI** — dark-mode dashboard with category cards, live search, quick-add form, and inline edit/delete
- **Category cards** — To Read, Jobs, Skills, Ideas, Notes, Inspiration — each with counts and drill-down view
- **Apple Shortcut** — share any URL or text from iOS/Mac directly into your inbox with one tap from the share sheet
- **iCloud sync** — database and inbox live in iCloud Drive, sync automatically to all your Apple devices
- **Full-text search** — SQLite FTS5 with Porter stemming; falls back to LIKE for fuzzy queries
- **Random pick** — surfaces an entry you haven't revisited in a while
- **Inbox system** — items captured on iPhone queue in `inbox.txt`; one command imports them all

---

## Screenshots

> *Add screenshots here once hosted*

---

## Quick Start

**Prerequisites:** Python 3.8+, pip

```bash
git clone https://github.com/VaibhaviSharma/second-brain
cd second-brain
pip3 install -r requirements.txt --user
python3 brain.py init
```

That's it. Your database is created at `~/Library/Mobile Documents/com~apple~CloudDocs/brain/brain.db` and syncs via iCloud automatically.

---

## CLI Usage

```bash
# First time
python3 brain.py init

# Adding entries
python3 brain.py add                          # interactive prompts
python3 brain.py quick "great idea"           # instant one-liner note
python3 brain.py quick "idea" -T idea         # specify type
python3 brain.py quick "apply here" -T job    # job entry

# Finding entries
python3 brain.py list                         # list active entries
python3 brain.py list --type job              # filter by type
python3 brain.py list --tag python            # filter by tag
python3 brain.py list --all                   # include archived + done
python3 brain.py search "rust async"          # full-text search

# Managing entries
python3 brain.py show 5                       # show full entry #5
python3 brain.py edit 5                       # edit interactively
python3 brain.py tag 5 rust,backend           # add tags
python3 brain.py done 5                       # mark as done
python3 brain.py archive 5                    # archive
python3 brain.py delete 5                     # delete (asks for confirmation)

# Inbox (from Apple Shortcut)
python3 brain.py import-inbox                 # import pending inbox items

# Stats & export
python3 brain.py stats                        # overview
python3 brain.py tags                         # all tags + counts
python3 brain.py types                        # all types + counts
python3 brain.py export backup.json           # export everything to JSON

# Web UI
python3 brain.py web                          # opens http://localhost:8787
python3 brain.py web --port 9000              # custom port
```

---

## Web UI

```bash
python3 brain.py web
```

Opens `http://localhost:8787` in your browser.

**Dashboard**

- **Category cards** — To Read, Jobs, Skills, Ideas, Notes, Inspiration with live entry counts. Click any card to drill into that category, sorted by priority.
- **Search bar** — type to search across all entries; navigates to filtered browse view.
- **Quick Add form** — add an entry without leaving the dashboard.
- **🎲 Pick something for me** — surfaces a random entry not touched in 7+ days.
- **Inbox badge** — blue banner appears when iCloud inbox has items waiting; one-click import.
- **Recently Added** — last 10 entries at a glance.

**Browse view** — filter by type, tag, status, sort order; paginated; full inline edit.

**Tags / Types views** — tag cloud and type breakdown with click-through filtering.

---

## Apple Shortcut — Save to Brain

Save anything from your iPhone or Mac's share sheet into your brain inbox.
The inbox file is in iCloud Drive so it syncs automatically — no server needed on your phone.

### How the inbox parser works

Each line in `inbox.txt` becomes one entry:

| Line | Saved as |
|---|---|
| `https://example.com` | type **link**, URL and title both set |
| `read: https://…` | type **link** |
| `job: Senior Engineer at Stripe` | type **job** |
| `skill: learn Rust` | type **skill** |
| `idea: build a habit tracker` | type **idea** |
| `inspo: constraints breed creativity` | type **resource** (Inspiration) |
| `note: call dentist tomorrow` | type **note** |
| Any plain text | type **note** |

### Building the shortcut

> Takes ~3 minutes. Works on iPhone, iPad, and Mac.

**Step 1 — Create the shortcut**

1. Open the **Shortcuts** app → tap **+**.
2. Tap the title and rename it **Save to Brain**.

**Step 2 — Accept share sheet input**

1. Tap **Add Action** → search **Receive input** → select **"Receive [Any] from Share Sheet"**.
2. Enable input types: **URLs**, **Text**, **Web Pages**, **Articles**, **Safari web pages**.
3. Set *"If there's no input"* → **Continue**.

**Step 3 — Append to inbox.txt**

1. Add action → search **"Append to File"**.
2. Set the fields:
   - **Storage**: iCloud Drive
   - **File Path**: `brain/inbox.txt`
   - **Input**: tap the token field → select **Shortcut Input**
   - Check **"New Line"** ✓
   - Leave *"Create if not exists"* on.

**Step 4 — Confirmation notification (optional)**

1. Add action → **Show Notification** → set body to `Saved to Brain ✓`.

**Step 5 — Enable in share sheet**

1. Tap **ⓘ** → toggle **"Show in Share Sheet"** → on → **Done**.

**Step 6 — Test**

1. Open Safari → share any page → tap **Save to Brain**.
2. On your Mac, run `python3 brain.py import-inbox` or click **Import now** in the web UI.

### Power tip — type-specific shortcuts

Make a second shortcut called "Save Job to Brain" with a **Text** action before "Append to File":

```
job: [Shortcut Input]
```

Repeat for `idea:`, `skill:`, etc. Each one routes directly to the right category.

### Troubleshooting

| Problem | Fix |
|---|---|
| `inbox.txt` not appearing on Mac | Open Files app on iPhone to force a sync |
| "Append to File" can't find the file | Settings → Apple ID → iCloud → iCloud Drive → enable |
| Import shows 0 items | `cat "$HOME/Library/Mobile Documents/com~apple~CloudDocs/brain/inbox.txt"` |

---

## Data & Backup

| File | Location |
|---|---|
| Database | `~/Library/Mobile Documents/com~apple~CloudDocs/brain/brain.db` |
| Inbox | `~/Library/Mobile Documents/com~apple~CloudDocs/brain/inbox.txt` |

Both files sync automatically via iCloud. Manual backup:

```bash
BRAIN="$HOME/Library/Mobile Documents/com~apple~CloudDocs/brain"
cp "$BRAIN/brain.db" "$BRAIN/brain-backup-$(date +%Y%m%d).db"
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Database | SQLite + FTS5 (full-text search, Porter stemming) |
| CLI | Python 3 · [click](https://click.palletsprojects.com) · [rich](https://github.com/Textualize/rich) |
| Web server | [Flask](https://flask.palletsprojects.com) |
| Frontend | Vanilla JS · CSS custom properties · no build step |
| Storage & sync | iCloud Drive |
| Mobile capture | Apple Shortcuts (share sheet) |

---

## Project Structure

```
second-brain/
├── brain.py          # CLI entry point (click commands)
├── server.py         # Flask app factory + all REST API routes
├── db.py             # Database layer: schema, FTS, inbox parser, helpers
├── templates/
│   └── index.html    # SPA shell (no inline JS/CSS)
├── static/
│   ├── style.css     # All styles, dark + light themes
│   └── app.js        # SPA logic, hash router, API calls
├── requirements.txt
├── TODO.md
└── LICENSE
```

---

## License

MIT — see [LICENSE](LICENSE).
