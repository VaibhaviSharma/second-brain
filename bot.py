"""
bot.py — Telegram bot for Second Brain.

Lets you save URLs and notes directly from Telegram into your brain database.
Supports auto-detection of source type, manual type prefixes, and browse/search
commands.

Usage:
    python bot.py          # run directly
    brain bot              # via CLI

Requires: TELEGRAM_BOT_TOKEN in .env or environment.
Install:   pip install python-telegram-bot python-dotenv
"""

import logging
import os
import sys

# Allow imports from the same directory when called as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from db import get_db, now_iso, normalise_tags

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Type detection maps ───────────────────────────────────────────────────────

URL_TYPE_MAP = [
    # (domain_fragment, type, tags)
    ('linkedin.com/jobs', 'job',      ['linkedin']),
    ('linkedin.com',      'resource', ['linkedin']),
    ('youtube.com',       'link',     ['youtube']),
    ('youtu.be',          'link',     ['youtube']),
    ('instagram.com',     'resource', ['instagram']),
    ('substack.com',      'link',     ['substack']),
    ('github.com',        'skill',    ['github']),
    ('medium.com',        'link',     ['medium']),
    ('twitter.com',       'link',     ['twitter']),
    ('x.com',             'link',     ['twitter']),
    ('reddit.com',        'link',     ['reddit']),
    ('netflix.com',       'resource', ['netflix']),
    ('spotify.com',       'resource', ['spotify']),
]

PREFIX_TYPE_MAP = {
    'recipe':  'resource',
    'recipes': 'resource',
    'job':     'job',
    'skill':   'skill',
    'learn':   'skill',
    'read':    'link',
    'link':    'link',
    'inspo':   'resource',
    'idea':    'idea',
    'note':    'note',
    'notes':   'note',
}

CAT_LABELS = {
    'link': 'Saved Links', 'job': 'Jobs', 'skill': 'Learning',
    'idea': 'Ideas', 'note': 'Notes', 'resource': 'Inspiration',
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_url_type(url: str):
    """Return (type, tags) for a URL based on URL_TYPE_MAP, or ('link', []) as default."""
    for fragment, type_, tags in URL_TYPE_MAP:
        if fragment in url:
            return type_, tags
    return 'link', []


def _is_url(text: str) -> bool:
    return text.startswith(('http://', 'https://'))


def _hostname(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname or url
    except Exception:
        return url


def _save_entry(title: str, url: str, type_: str, tags: list, content: str = '') -> int:
    """Insert an entry into the database and return its ID."""
    db = get_db()
    ts = now_iso()
    tags_str = normalise_tags(','.join(tags))
    try:
        cur = db.execute(
            "INSERT INTO entries"
            " (title, content, url, type, tags, priority, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, 3, 'active', ?, ?)",
            (title, content, url, type_, tags_str, ts, ts),
        )
        db.commit()
        return cur.lastrowid
    finally:
        db.close()

# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start and /help commands."""
    msg = (
        "Second Brain Bot\n\n"
        "Send me anything to save it:\n"
        "  A URL -> auto-detected type & tags\n"
        "  job: <url> -> saves as job\n"
        "  recipe: <url> -> saves as inspiration\n"
        "  idea: <text> -> saves as idea\n"
        "  note: <text> -> saves as note\n\n"
        "Commands:\n"
        "/browse - browse by category\n"
        "/search <query> - search your brain\n"
        "/random - surprise me\n"
        "/stats - see your counts\n"
        "/help - show this message"
    )
    await update.message.reply_text(msg)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command — show counts per type."""
    try:
        db = get_db()
        try:
            total = db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            by_type = db.execute(
                "SELECT type, COUNT(*) AS c FROM entries WHERE status='active' GROUP BY type ORDER BY c DESC"
            ).fetchall()
        finally:
            db.close()

        lines = [f"Second Brain - {total} total entries\n"]
        for row in by_type:
            label = CAT_LABELS.get(row['type'], row['type'].capitalize())
            lines.append(f"  {label}: {row['c']}")

        await update.message.reply_text('\n'.join(lines))
    except RuntimeError as e:
        await update.message.reply_text(f"Error: {e}")


async def cmd_random(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /random command — send a random active entry."""
    try:
        db = get_db()
        try:
            row = db.execute(
                "SELECT * FROM entries WHERE status='active'"
                " AND updated_at <= date('now','-7 days')"
                " ORDER BY RANDOM() LIMIT 1"
            ).fetchone()
            if not row:
                row = db.execute(
                    "SELECT * FROM entries WHERE status='active' ORDER BY RANDOM() LIMIT 1"
                ).fetchone()
        finally:
            db.close()

        if not row:
            await update.message.reply_text("No active entries found.")
            return

        label = CAT_LABELS.get(row['type'], row['type'].capitalize())
        if row['url']:
            msg = f"[{row['title']}]({row['url']})\n_{label}_"
        else:
            msg = f"*{row['title']}*\n_{label}_"
        if row['tags']:
            tags_display = ' '.join(f"#{t.strip()}" for t in row['tags'].split(',') if t.strip())
            msg += f"\n{tags_display}"

        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    except RuntimeError as e:
        await update.message.reply_text(f"Error: {e}")


async def cmd_browse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /browse command — show inline keyboard of categories."""
    try:
        db = get_db()
        try:
            rows = db.execute(
                "SELECT type, COUNT(*) AS c FROM entries WHERE status='active' GROUP BY type ORDER BY c DESC"
            ).fetchall()
        finally:
            db.close()

        if not rows:
            await update.message.reply_text("No entries yet.")
            return

        buttons = []
        for row in rows:
            label = CAT_LABELS.get(row['type'], row['type'].capitalize())
            buttons.append(
                InlineKeyboardButton(f"{label} ({row['c']})", callback_data=f"browse:{row['type']}")
            )

        # Arrange into rows of 2
        keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Browse by category:", reply_markup=reply_markup)
    except RuntimeError as e:
        await update.message.reply_text(f"Error: {e}")


async def callback_browse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle browse category button taps."""
    query = update.callback_query
    await query.answer()

    type_ = query.data.split(':', 1)[1]
    try:
        db = get_db()
        try:
            rows = db.execute(
                "SELECT * FROM entries WHERE type=? AND status='active'"
                " ORDER BY created_at DESC LIMIT 10",
                (type_,),
            ).fetchall()
        finally:
            db.close()

        label = CAT_LABELS.get(type_, type_.capitalize())
        if not rows:
            await query.edit_message_text(f"No entries in {label}.")
            return

        lines = [f"*{label}* - last {len(rows)} entries\n"]
        for row in rows:
            if row['url']:
                lines.append(f"[{row['title']}]({row['url']})")
            else:
                lines.append(f"- {row['title']}")

        await query.edit_message_text('\n'.join(lines), parse_mode=ParseMode.MARKDOWN)
    except RuntimeError as e:
        await query.edit_message_text(f"Error: {e}")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search <query> command."""
    if not context.args:
        await update.message.reply_text("Usage: /search <query>")
        return

    query_str = ' '.join(context.args)
    try:
        from db import fts_search
        db = get_db()
        try:
            ids = fts_search(db, query_str)
            if ids is not None:
                if not ids:
                    await update.message.reply_text(f'No results for "{query_str}".')
                    return
                placeholders = ','.join('?' * len(ids[:10]))
                rows = db.execute(
                    f"SELECT * FROM entries WHERE id IN ({placeholders}) LIMIT 10",
                    ids[:10],
                ).fetchall()
            else:
                like = f"%{query_str}%"
                rows = db.execute(
                    "SELECT * FROM entries WHERE title LIKE ? OR content LIKE ? OR tags LIKE ? LIMIT 10",
                    (like, like, like),
                ).fetchall()
        finally:
            db.close()

        if not rows:
            await update.message.reply_text(f'No results for "{query_str}".')
            return

        lines = [f"*Search: {query_str}* - {len(rows)} results\n"]
        for row in rows:
            if row['url']:
                lines.append(f"[{row['title']}]({row['url']})")
            else:
                lines.append(f"- {row['title']}")

        await update.message.reply_text('\n'.join(lines), parse_mode=ParseMode.MARKDOWN)
    except RuntimeError as e:
        await update.message.reply_text(f"Error: {e}")


# ── Message handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all non-command messages — auto-detect type and save."""
    text = update.message.text.strip()
    if not text:
        return

    type_ = None
    tags = []
    url = ''
    title = ''
    content = ''

    # Check for "prefix: rest" pattern
    if ':' in text:
        prefix, _, rest = text.partition(':')
        prefix_lower = prefix.strip().lower()
        rest = rest.strip()
        if prefix_lower in PREFIX_TYPE_MAP and rest:
            type_ = PREFIX_TYPE_MAP[prefix_lower]
            if _is_url(rest):
                url = rest
                title = _hostname(rest)
                tags = [prefix_lower]
            else:
                title = rest[:100]
                content = rest
                tags = [prefix_lower]

    # If no prefix matched, check if the whole message is a URL
    if type_ is None:
        if _is_url(text):
            url = text
            auto_type, auto_tags = _detect_url_type(text)
            type_ = auto_type
            tags = auto_tags
            title = _hostname(text)
        else:
            # Plain text -> note
            type_ = 'note'
            title = text[:100]
            content = text

    try:
        entry_id = _save_entry(title=title, url=url, type_=type_, tags=tags, content=content)
        label = CAT_LABELS.get(type_, type_.capitalize())
        if tags:
            tags_display = ' '.join(f"#{t}" for t in tags)
            reply = f"Saved under *{label}*, tagged {tags_display}"
        else:
            reply = f"Saved as *{label}*"
        await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
    except RuntimeError as e:
        await update.message.reply_text(f"Error saving: {e}")


# ── Error handler ─────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors."""
    logger.error("Exception while handling an update:", exc_info=context.error)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Start the bot."""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Add it to .env or environment.")
        sys.exit(1)

    app = ApplicationBuilder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("random", cmd_random))
    app.add_handler(CommandHandler("browse", cmd_browse))
    app.add_handler(CommandHandler("search", cmd_search))

    # Inline keyboard callbacks
    app.add_handler(CallbackQueryHandler(callback_browse, pattern=r'^browse:'))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Error handler
    app.add_error_handler(error_handler)

    logger.info("Second Brain bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
