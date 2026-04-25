# TODO / Future Ideas

Rough roadmap of things to build next. No priority order.

## Capture

- **Safari bookmarklet** — one-click save from any desktop browser without the Shortcuts app; POST directly to the local server
- **Telegram bot** — send a message to a personal bot and it lands in the brain; useful when not on Apple devices
- **Browser extension** — Chrome/Firefox extension that saves the current page with title, URL, and selected text
- **Import from browser bookmarks** — parse Chrome/Safari/Firefox HTML bookmark exports and bulk-import as link entries
- **Email-to-brain** — forward an email to a dedicated address and have it parsed into an entry

## Organisation

- **Markdown support** — render content field as Markdown in the web UI (use marked.js, keep storage as plain text)
- **Due dates and reminders** — optional `due_date` field; CLI `brain due` command lists upcoming items; local notification via `osascript`
- **Linked entries** — relate two entries (e.g. a job entry linked to a skill entry); show links in the detail view
- **Collections / notebooks** — group entries into named collections beyond the type system
- **Bulk tag / type edit** — select multiple entries in the web UI and change tags or type at once

## Discovery

- **`brain random` nudge** — a cron job or launchd agent that sends a macOS notification once a day with a random entry you haven't touched in a while
- **"On this day"** — surface entries created on the same date in previous years (show in dashboard)
- **Related entries** — simple TF-IDF or tag overlap to show "you might also want to revisit…" suggestions

## Export & Sync

- **Obsidian export** — write each entry as a `.md` file with YAML front-matter into an Obsidian vault folder
- **Notion import** — pull pages from a Notion database via the API and bulk-import them
- **JSON / CSV scheduled backup** — auto-export to a dated file in the iCloud folder nightly

## Web UI

- **Drag-and-drop priority** — reorder entries in the category view by dragging
- **Keyboard shortcuts** — `n` for new, `/` to focus search, `e` to edit focused entry
- **PWA / home screen icon** — add a web app manifest so the web UI can be added to the iPhone home screen
