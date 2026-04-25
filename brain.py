#!/usr/bin/env python3
"""
brain.py — CLI entry point for the Second Brain knowledge base.

Usage:
    python brain.py <command> [options]

Commands:
    init                  Set up the database (run once)
    add                   Add a new entry interactively
    quick "text"          One-liner save (auto-type: note)
    list                  List entries (supports --type, --tag, --status, --all)
    search "query"        Full-text search
    show <id>             Show full entry details
    edit <id>             Edit an entry
    tag <id> "a,b"        Add tags to an entry
    archive <id>          Mark as archived
    done <id>             Mark as done
    delete <id>           Delete (with confirmation)
    types                 List all types + counts
    tags                  List all tags + counts
    stats                 Overall stats
    export                Export to JSON
    web                   Launch the web UI

Install deps:  pip install click rich flask
Make a shortcut: chmod +x brain.py && ln -s $(pwd)/brain.py /usr/local/bin/brain
"""

import json
import os
import sys
from pathlib import Path

# Allow imports from the same directory when called as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from db import (
    DB_PATH, BRAIN_DIR, INBOX_PATH, VALID_STATUSES, DEFAULT_TYPES,
    get_db, init_db, now_iso, normalise_tags, fts_search, import_inbox,
)

# ── Console + display constants ─────────────────────────────────────────────────
console = Console()

PRIORITY_LABELS = {
    1: "[bold red]1 Critical[/bold red]",
    2: "[red]2 High[/red]",
    3: "[yellow]3 Medium[/yellow]",
    4: "[green]4 Low[/green]",
    5: "[dim]5 Minimal[/dim]",
}
PRIORITY_SHORT = {
    1: "[bold red]1[/bold red]",
    2: "[red]2[/red]",
    3: "[yellow]3[/yellow]",
    4: "[green]4[/green]",
    5: "[dim]5[/dim]",
}
STATUS_STYLE = {"active": "green", "archived": "dim", "done": "blue"}
TYPE_STYLE   = {
    "note": "cyan", "link": "bright_blue", "skill": "magenta",
    "job": "yellow", "idea": "bright_green", "resource": "white",
}

# ── DB helper with nice CLI error ───────────────────────────────────────────────

def _get_db():
    try:
        return get_db()
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

# ── Rendering helpers ────────────────────────────────────────────────────────────

def _type_style(t: str) -> str:   return TYPE_STYLE.get(t, "white")
def _status_style(s: str) -> str: return STATUS_STYLE.get(s, "white")

def _fmt_tags(tags: str) -> str:
    if not tags or not tags.strip():
        return "[dim]—[/dim]"
    return " ".join(f"[dim cyan]#{t.strip()}[/dim cyan]"
                    for t in tags.split(",") if t.strip())

def _fmt_tags_plain(tags: str) -> str:
    if not tags or not tags.strip():
        return ""
    return ", ".join(f"#{t.strip()}" for t in tags.split(",") if t.strip())

def _build_list_table(title: str = "") -> Table:
    t = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan",
              title=title or None, title_style="bold", show_lines=False)
    t.add_column("ID",      style="dim bold", width=5, justify="right")
    t.add_column("Type",    width=10)
    t.add_column("Title",   min_width=28)
    t.add_column("Tags",    min_width=16)
    t.add_column("P",       width=3, justify="center")
    t.add_column("Status",  width=10)
    t.add_column("Created", width=11)
    return t

def _add_row(table: Table, row) -> None:
    tc = _type_style(row["type"])
    sc = _status_style(row["status"])
    table.add_row(
        str(row["id"]),
        f"[{tc}]{row['type']}[/{tc}]",
        row["title"],
        _fmt_tags_plain(row["tags"]),
        PRIORITY_SHORT.get(row["priority"], str(row["priority"])),
        f"[{sc}]{row['status']}[/{sc}]",
        row["created_at"][:10],
    )

# ── CLI ──────────────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """
    \b
    brain — your local second brain knowledge base
    ───────────────────────────────────────────────
    Store notes, links, skills, jobs, ideas, and more.
    Everything lives in iCloud Drive → brain/brain.db (SQLite).
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ── init ─────────────────────────────────────────────────────────────────────────

@cli.command()
def init() -> None:
    """Initialize the brain database (run once)."""
    if DB_PATH.exists():
        console.print(f"[yellow]Already initialized:[/yellow] {DB_PATH}")
        return
    init_db()
    console.print(f"[green]✓ Brain initialized[/green] → [dim]{DB_PATH}[/dim]")
    console.print(
        '[dim]Next: [bold]brain add[/bold]  or  '
        '[bold]brain quick "first thought"[/bold][/dim]'
    )


# ── add ──────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--title",    "-t", default=None, help="Entry title")
@click.option("--type",     "-T", "etype", default=None, help="Entry type")
@click.option("--content",  "-c", default=None, help="Body / notes")
@click.option("--url",      "-u", default=None, help="URL")
@click.option("--tags",     "-g", default=None, help="Comma-separated tags")
@click.option("--priority", "-p", default=None, type=int, help="Priority 1–5")
def add(title, etype, content, url, tags, priority) -> None:
    """Add a new entry (interactive prompts)."""
    db = _get_db()
    console.print("\n[bold cyan]✦ New entry[/bold cyan]\n")

    title = title or Prompt.ask("[bold]Title[/bold]")
    if not title.strip():
        console.print("[red]Title cannot be empty.[/red]"); db.close(); return

    if not etype:
        console.print(f"  [dim]Suggestions: {', '.join(DEFAULT_TYPES)}[/dim]")
        etype = Prompt.ask("[bold]Type[/bold]", default="note")

    if content  is None: content  = Prompt.ask("[bold]Content[/bold] [dim](notes, details)[/dim]", default="")
    if url      is None: url      = Prompt.ask("[bold]URL[/bold]     [dim](optional)[/dim]", default="")
    if tags     is None: tags     = Prompt.ask("[bold]Tags[/bold]    [dim](comma-separated)[/dim]", default="")
    if priority is None: priority = IntPrompt.ask("[bold]Priority[/bold] [dim](1=critical … 5=minimal)[/dim]", default=3)

    if not 1 <= priority <= 5:
        console.print("[red]Priority must be 1–5.[/red]"); db.close(); return

    ts  = now_iso()
    cur = db.execute(
        "INSERT INTO entries (title, content, url, type, tags, priority, status, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)",
        (title.strip(), content.strip(), url.strip(),
         etype.strip().lower(), normalise_tags(tags), priority, ts, ts),
    )
    db.commit()
    eid = cur.lastrowid
    db.close()
    console.print(f"\n[green]✓ Entry [bold]#{eid}[/bold] added.[/green]")


# ── quick ─────────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("text")
@click.option("--type", "-T", "etype", default="note", show_default=True)
@click.option("--tags", "-g", default="", help="Comma-separated tags")
@click.option("--priority", "-p", default=3, show_default=True, type=int)
def quick(text: str, etype: str, tags: str, priority: int) -> None:
    """Quickly save a note: brain quick 'some text'"""
    if not 1 <= priority <= 5:
        console.print("[red]Priority must be 1–5.[/red]"); return
    db  = _get_db()
    ts  = now_iso()
    cur = db.execute(
        "INSERT INTO entries (title, content, url, type, tags, priority, status, created_at, updated_at)"
        " VALUES (?, '', '', ?, ?, ?, 'active', ?, ?)",
        (text.strip(), etype.strip().lower(), normalise_tags(tags), priority, ts, ts),
    )
    db.commit()
    eid = cur.lastrowid
    db.close()
    console.print(f"[green]✓ Saved [bold]#{eid}[/bold][/green] [dim]({etype})[/dim]")


# ── list ──────────────────────────────────────────────────────────────────────────

@cli.command("list")
@click.option("--type",    "-T", "etype",    default=None)
@click.option("--tag",     "-g",             default=None)
@click.option("--status",  "-s",             default=None)
@click.option("--priority","-p",             default=None, type=int)
@click.option("--limit",   "-n",             default=25, show_default=True)
@click.option("--all",     "-a", "show_all", is_flag=True, help="Show all statuses")
def list_entries(etype, tag, status, priority, limit, show_all) -> None:
    """List entries with optional filters."""
    db = _get_db()
    clauses, params = [], []

    if not show_all:
        clauses.append("status = ?"); params.append(status or "active")
    elif status:
        clauses.append("status = ?"); params.append(status)

    if etype:    clauses.append("type = ?");                      params.append(etype.lower())
    if tag:      clauses.append("(',' || tags || ',') LIKE ?");   params.append(f"%,{tag.strip()},%")
    if priority: clauses.append("priority = ?");                  params.append(priority)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows  = db.execute(
        f"SELECT * FROM entries {where} ORDER BY priority ASC, created_at DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    db.close()

    if not rows:
        console.print("[dim]No entries found.[/dim]"); return

    filters_desc = []
    if not show_all: filters_desc.append(f"status={status or 'active'}")
    if etype:        filters_desc.append(f"type={etype}")
    if tag:          filters_desc.append(f"tag=#{tag}")
    if priority:     filters_desc.append(f"priority={priority}")

    table = _build_list_table("  ".join(filters_desc))
    for row in rows:
        _add_row(table, row)

    console.print(table)
    console.print(f"[dim]{len(rows)} entr{'y' if len(rows)==1 else 'ies'}.[/dim]")


# ── search ────────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("query")
@click.option("--type", "-T", "etype", default=None)
@click.option("--limit", "-n", default=25, show_default=True)
def search(query: str, etype: str, limit: int) -> None:
    """Full-text search across title, content, and tags."""
    db    = _get_db()
    words = [w.strip() for w in query.split() if w.strip()]
    if not words:
        console.print("[red]Empty query.[/red]"); db.close(); return

    ids = fts_search(db, query)

    if ids is not None:
        if not ids:
            console.print(f'[dim]No results for "[bold]{query}[/bold]".[/dim]')
            db.close(); return
        placeholders = ",".join("?" * len(ids))
        sql    = f"SELECT * FROM entries WHERE id IN ({placeholders})"
        params: list = list(ids)
        if etype:
            sql += " AND type = ?"; params.append(etype.lower())
        sql += " LIMIT ?"
        params.append(limit)
    else:
        like   = f"%{query}%"
        sql    = "SELECT * FROM entries WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?"
        params = [like, like, like]
        if etype:
            sql += " AND type = ?"; params.append(etype.lower())
        sql += " LIMIT ?"
        params.append(limit)

    rows = db.execute(sql, params).fetchall()
    db.close()

    if not rows:
        console.print(f'[dim]No results for "[bold]{query}[/bold]".[/dim]'); return

    table = _build_list_table(f'Search: "{query}"')
    for row in rows:
        _add_row(table, row)
    console.print(table)
    console.print(f"[dim]{len(rows)} result{'s' if len(rows)!=1 else ''}.[/dim]")


# ── show ──────────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("entry_id", type=int)
def show(entry_id: int) -> None:
    """Show full details of an entry."""
    db  = _get_db()
    row = db.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    db.close()

    if not row:
        console.print(f"[red]Entry #{entry_id} not found.[/red]"); return

    tc = _type_style(row["type"])
    sc = _status_style(row["status"])
    lines = [
        f"  [dim]ID[/dim]        {row['id']}",
        f"  [dim]Type[/dim]      [{tc}]{row['type']}[/{tc}]",
        f"  [dim]Status[/dim]    [{sc}]{row['status']}[/{sc}]",
        f"  [dim]Priority[/dim]  {PRIORITY_LABELS.get(row['priority'], str(row['priority']))}",
        f"  [dim]Tags[/dim]      {_fmt_tags(row['tags'])}",
        f"  [dim]URL[/dim]       {row['url'] or '[dim]—[/dim]'}",
        f"  [dim]Created[/dim]   {row['created_at']}",
        f"  [dim]Updated[/dim]   {row['updated_at']}",
    ]
    if row["content"]:
        lines += ["", "  [dim]──── Content ────[/dim]", f"  {row['content']}"]
    console.print(Panel("\n".join(lines), title=f"[bold]{row['title']}[/bold]",
                        border_style=tc, expand=False, padding=(0, 1)))


# ── edit ──────────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("entry_id", type=int)
@click.option("--title",    "-t", default=None)
@click.option("--type",     "-T", "etype", default=None)
@click.option("--content",  "-c", default=None)
@click.option("--url",      "-u", default=None)
@click.option("--tags",     "-g", default=None)
@click.option("--priority", "-p", default=None, type=int)
@click.option("--status",   "-s", default=None, type=click.Choice(VALID_STATUSES))
def edit(entry_id, title, etype, content, url, tags, priority, status) -> None:
    """Edit an entry. Interactive if no flags supplied."""
    db  = _get_db()
    row = db.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        console.print(f"[red]Entry #{entry_id} not found.[/red]"); db.close(); return

    if any(v is not None for v in [title, etype, content, url, tags, priority, status]):
        new_title    = title    if title    is not None else row["title"]
        new_type     = etype    if etype    is not None else row["type"]
        new_content  = content  if content  is not None else row["content"]
        new_url      = url      if url      is not None else row["url"]
        new_tags     = normalise_tags(tags) if tags is not None else row["tags"]
        new_priority = priority if priority is not None else row["priority"]
        new_status   = status   if status   is not None else row["status"]
    else:
        console.print(
            f"\n[bold cyan]Editing [bold]#{entry_id}[/bold][/bold cyan]"
            " [dim](Enter to keep current value)[/dim]\n"
        )
        new_title    = Prompt.ask("[bold]Title[/bold]",    default=row["title"])
        new_type     = Prompt.ask("[bold]Type[/bold]",     default=row["type"])
        new_content  = Prompt.ask("[bold]Content[/bold]",  default=row["content"] or "")
        new_url      = Prompt.ask("[bold]URL[/bold]",      default=row["url"] or "")
        new_tags     = normalise_tags(Prompt.ask("[bold]Tags[/bold]", default=row["tags"] or ""))
        new_priority = IntPrompt.ask("[bold]Priority[/bold]", default=row["priority"])
        console.print(f"[dim]Statuses: {', '.join(VALID_STATUSES)}[/dim]")
        new_status   = Prompt.ask("[bold]Status[/bold]",   default=row["status"])

    if not new_title.strip():
        console.print("[red]Title cannot be empty.[/red]"); db.close(); return
    if new_status not in VALID_STATUSES:
        console.print(f"[red]Invalid status. Choose: {', '.join(VALID_STATUSES)}[/red]")
        db.close(); return
    if not 1 <= new_priority <= 5:
        console.print("[red]Priority must be 1–5.[/red]"); db.close(); return

    db.execute(
        "UPDATE entries SET title=?, type=?, content=?, url=?, tags=?,"
        " priority=?, status=?, updated_at=? WHERE id=?",
        (new_title.strip(), new_type.strip().lower(), new_content.strip(),
         new_url.strip(), new_tags, new_priority, new_status, now_iso(), entry_id),
    )
    db.commit()
    db.close()
    console.print(f"[green]✓ Entry [bold]#{entry_id}[/bold] updated.[/green]")


# ── tag ───────────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("entry_id", type=int)
@click.argument("new_tags")
def tag(entry_id: int, new_tags: str) -> None:
    """Add tags to an entry: brain tag 42 'python,ml'"""
    db  = _get_db()
    row = db.execute("SELECT tags FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        console.print(f"[red]Entry #{entry_id} not found.[/red]"); db.close(); return

    existing = {t.strip() for t in row["tags"].split(",") if t.strip()}
    incoming = {t.strip() for t in new_tags.split(",") if t.strip()}
    merged   = sorted(existing | incoming)

    db.execute("UPDATE entries SET tags=?, updated_at=? WHERE id=?",
               (",".join(merged), now_iso(), entry_id))
    db.commit()
    db.close()
    console.print(
        f"[green]✓[/green] Tags on [bold]#{entry_id}[/bold]: "
        + " ".join(f"[cyan]#{t}[/cyan]" for t in merged)
    )


# ── archive / done ────────────────────────────────────────────────────────────────

def _set_status(entry_id: int, new_status: str) -> None:
    db  = _get_db()
    row = db.execute("SELECT id, title FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        console.print(f"[red]Entry #{entry_id} not found.[/red]"); db.close(); return
    db.execute("UPDATE entries SET status=?, updated_at=? WHERE id=?",
               (new_status, now_iso(), entry_id))
    db.commit()
    db.close()
    sc = _status_style(new_status)
    console.print(
        f"[green]✓[/green] [bold]#{entry_id}[/bold] [dim]{row['title'][:50]}[/dim]"
        f" → [{sc}]{new_status}[/{sc}]"
    )

@cli.command()
@click.argument("entry_id", type=int)
def archive(entry_id: int) -> None:
    """Archive an entry."""
    _set_status(entry_id, "archived")

@cli.command()
@click.argument("entry_id", type=int)
def done(entry_id: int) -> None:
    """Mark an entry as done."""
    _set_status(entry_id, "done")


# ── delete ────────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("entry_id", type=int)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def delete(entry_id: int, yes: bool) -> None:
    """Delete an entry (prompts for confirmation)."""
    db  = _get_db()
    row = db.execute("SELECT id, title FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        console.print(f"[red]Entry #{entry_id} not found.[/red]"); db.close(); return

    console.print(f"[yellow]Delete[/yellow] [bold]#{row['id']}[/bold] — {row['title']}")
    if not yes and not Confirm.ask("[red]Confirm delete?[/red]", default=False):
        console.print("[dim]Cancelled.[/dim]"); db.close(); return

    db.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    db.commit()
    db.close()
    console.print(f"[green]✓ Entry #{entry_id} deleted.[/green]")


# ── types ─────────────────────────────────────────────────────────────────────────

@cli.command()
def types() -> None:
    """List all entry types and their counts."""
    db   = _get_db()
    rows = db.execute(
        "SELECT type, COUNT(*) AS cnt FROM entries GROUP BY type ORDER BY cnt DESC"
    ).fetchall()
    db.close()
    if not rows:
        console.print("[dim]No entries yet.[/dim]"); return
    table = Table(box=box.SIMPLE, header_style="bold cyan", show_edge=False)
    table.add_column("Type", min_width=14)
    table.add_column("Entries", justify="right")
    for row in rows:
        tc = _type_style(row["type"])
        table.add_row(f"[{tc}]{row['type']}[/{tc}]", str(row["cnt"]))
    console.print(table)


# ── tags ──────────────────────────────────────────────────────────────────────────

@cli.command("tags")
def list_tags() -> None:
    """List all tags and their entry counts."""
    db   = _get_db()
    rows = db.execute("SELECT tags FROM entries WHERE tags != ''").fetchall()
    db.close()
    counts: dict = {}
    for row in rows:
        for t in row["tags"].split(","):
            t = t.strip()
            if t: counts[t] = counts.get(t, 0) + 1
    if not counts:
        console.print("[dim]No tags yet.[/dim]"); return
    table = Table(box=box.SIMPLE, header_style="bold cyan", show_edge=False)
    table.add_column("Tag", min_width=18)
    table.add_column("Entries", justify="right")
    for name, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        table.add_row(f"[dim cyan]#{name}[/dim cyan]", str(cnt))
    console.print(table)


# ── stats ─────────────────────────────────────────────────────────────────────────

@cli.command()
def stats() -> None:
    """Show overall knowledge base statistics."""
    db = _get_db()
    total     = db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    by_status = db.execute("SELECT status, COUNT(*) AS c FROM entries GROUP BY status ORDER BY c DESC").fetchall()
    by_type   = db.execute("SELECT type,   COUNT(*) AS c FROM entries GROUP BY type   ORDER BY c DESC").fetchall()
    by_pri    = db.execute("SELECT priority, COUNT(*) AS c FROM entries GROUP BY priority ORDER BY priority").fetchall()
    oldest    = db.execute("SELECT created_at FROM entries ORDER BY created_at ASC  LIMIT 1").fetchone()
    newest    = db.execute("SELECT title, created_at FROM entries ORDER BY created_at DESC LIMIT 1").fetchone()
    tag_count = db.execute("SELECT COUNT(*) FROM entries WHERE tags != ''").fetchone()[0]
    db.close()

    console.print(Panel(f"[bold cyan]{total}[/bold cyan] total entries",
                        title="[bold]Brain Stats[/bold]", border_style="cyan", expand=False))

    for label, rows, col_key, style_fn in [
        ("By status",   by_status, "status",   _status_style),
        ("By type",     by_type,   "type",     _type_style),
    ]:
        t = Table(box=box.SIMPLE, show_header=False, show_edge=False, padding=(0, 2))
        t.add_column("", min_width=12); t.add_column("", justify="right")
        for r in rows:
            s = style_fn(r[col_key])
            t.add_row(f"[{s}]{r[col_key]}[/{s}]", str(r["c"]))
        console.print(f"[bold]{label}[/bold]"); console.print(t)

    pt = Table(box=box.SIMPLE, show_header=False, show_edge=False, padding=(0, 2))
    pt.add_column("", min_width=20); pt.add_column("", justify="right")
    for r in by_pri:
        pt.add_row(PRIORITY_LABELS.get(r["priority"], str(r["priority"])), str(r["c"]))
    console.print("[bold]By priority[/bold]"); console.print(pt)

    if oldest: console.print(f"\n[dim]Oldest entry:  {oldest[0][:10]}[/dim]")
    if newest: console.print(f"[dim]Latest entry:  [bold]{newest['title'][:50]}[/bold] ({newest['created_at'][:10]})[/dim]")
    console.print(f"[dim]Tagged entries: {tag_count} / {total}[/dim]")


# ── export ────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--output",  "-o", default=None,  help="Output file (default: stdout)")
@click.option("--status",  "-s", default=None,  help="Filter by status")
@click.option("--type",    "-T", "etype", default=None, help="Filter by type")
@click.option("--pretty/--compact", default=True, help="Pretty-print JSON")
def export(output, status, etype, pretty) -> None:
    """Export entries to JSON."""
    db = _get_db()
    clauses, params = [], []
    if status: clauses.append("status = ?"); params.append(status)
    if etype:  clauses.append("type = ?");   params.append(etype.lower())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows  = db.execute(
        f"SELECT * FROM entries {where} ORDER BY created_at DESC", params
    ).fetchall()
    db.close()
    data    = [dict(r) for r in rows]
    payload = json.dumps({"exported_at": now_iso(), "count": len(data), "entries": data},
                         indent=2 if pretty else None, ensure_ascii=False)
    if output:
        Path(output).write_text(payload, encoding="utf-8")
        console.print(f"[green]✓ Exported {len(data)} entries → {output}[/green]")
    else:
        print(payload)


# ── import-inbox ─────────────────────────────────────────────────────────────────

@cli.command("import-inbox")
def import_inbox_cmd() -> None:
    """Import pending items from the iCloud inbox.txt file."""
    if not INBOX_PATH.exists():
        console.print("[dim]Inbox file doesn't exist yet — nothing to import.[/dim]")
        console.print(f"[dim]Expected: {INBOX_PATH}[/dim]")
        return

    raw = INBOX_PATH.read_text(encoding="utf-8")
    pending = [l.strip() for l in raw.splitlines() if l.strip()]
    if not pending:
        console.print("[dim]Inbox is empty. Nothing to import.[/dim]")
        return

    console.print(f"\n[bold cyan]📥 Inbox:[/bold cyan] {len(pending)} item{'s' if len(pending) != 1 else ''} pending\n")

    db      = _get_db()
    result  = import_inbox(db)
    db.close()

    if result["imported"] == 0:
        console.print("[dim]No items imported.[/dim]")
        return

    skipped_note = f" [dim]({result['skipped']} blank line{'s' if result['skipped']!=1 else ''} skipped)[/dim]" \
                   if result["skipped"] else ""
    console.print(
        f"[green]✓ Imported {result['imported']} item{'s' if result['imported']!=1 else ''}[/green]"
        + skipped_note
    )

    table = Table(box=box.SIMPLE, header_style="bold cyan", show_edge=False)
    table.add_column("ID",    style="dim", width=5, justify="right")
    table.add_column("Type",  width=10)
    table.add_column("Title")
    for item in result["items"]:
        col = _type_style(item["type"])
        table.add_row(
            str(item["id"]),
            f"[{col}]{item['type']}[/{col}]",
            item["title"][:72] + ("…" if len(item["title"]) > 72 else ""),
        )
    console.print(table)


# ── SSL cert helper ───────────────────────────────────────────────────────────────

def _ensure_cert(lan_ip: str):
    """
    Generate a self-signed cert for the LAN IP using macOS's built-in openssl.
    Stored in BRAIN_DIR (iCloud) so it syncs to iPhone Files app for easy install.
    Returns (cert_path, key_path).
    """
    import subprocess, tempfile, os

    cert_path = BRAIN_DIR / "brain-ssl.crt"
    key_path  = BRAIN_DIR / "brain-ssl.key"

    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    console.print("[dim]Generating SSL certificate…[/dim]")

    # Config file approach — works with both OpenSSL and macOS LibreSSL
    conf = f"""[req]
distinguished_name = dn
x509_extensions    = v3
prompt             = no

[dn]
CN = Second Brain Local

[v3]
subjectAltName     = @san
basicConstraints   = CA:TRUE

[san]
IP.1  = {lan_ip}
IP.2  = 127.0.0.1
DNS.1 = localhost
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".cnf", delete=False) as f:
        f.write(conf)
        conf_file = f.name

    try:
        subprocess.run(
            [
                "openssl", "req", "-x509",
                "-newkey", "rsa:2048",
                "-keyout", str(key_path),
                "-out",    str(cert_path),
                "-days",   "825",       # iOS max allowed validity
                "-nodes",               # no passphrase
                "-config", conf_file,
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        console.print(f"[red]openssl failed:[/red] {e.stderr.decode()}")
        sys.exit(1)
    finally:
        os.unlink(conf_file)

    console.print(f"[green]✓ Certificate created[/green] → [dim]{cert_path}[/dim]")
    return cert_path, key_path


# ── web ───────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--port",       "-p", default=8787, show_default=True, help="Port to listen on")
@click.option("--no-browser", is_flag=True, help="Don't open the browser automatically")
@click.option("--https",      is_flag=True, help="Serve over HTTPS (required for PWA on iPhone)")
def web(port: int, no_browser: bool, https: bool) -> None:
    """Launch the web UI — accessible on local network for iPhone."""
    try:
        import flask  # noqa: F401
    except ImportError:
        console.print("[red]Flask is required.[/red]  pip install flask"); sys.exit(1)

    if not DB_PATH.exists():
        console.print("[red]Database not found.[/red] Run [bold cyan]brain init[/bold cyan] first.")
        sys.exit(1)

    import socket, threading, webbrowser
    from server import create_app

    # Resolve LAN IP
    lan_ip = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    scheme     = "https" if https else "http"
    local_url  = f"{scheme}://localhost:{port}"
    phone_url  = f"{scheme}://{lan_ip}:{port}" if lan_ip else None
    ssl_ctx    = None

    if https:
        if not lan_ip:
            console.print("[red]Could not detect LAN IP — are you on WiFi?[/red]")
            sys.exit(1)
        cert, key = _ensure_cert(lan_ip)
        ssl_ctx   = (str(cert), str(key))

        console.print(f"\n[bold]🧠 Brain Web UI[/bold]  [dim](HTTPS)[/dim]")
        console.print(f"   Mac:   [cyan]{local_url}[/cyan]")
        console.print(f"   Phone: [cyan]{phone_url}[/cyan]  [dim](open in Safari)[/dim]")
        console.print(f"\n[bold yellow]One-time iPhone setup[/bold yellow] [dim](skip if already done)[/dim]")
        console.print( "   1. Open [bold]Files[/bold] app → iCloud Drive → brain → [bold]brain-ssl.crt[/bold] → tap it → Install")
        console.print( "   2. [bold]Settings → General → About → Certificate Trust Settings[/bold]")
        console.print( "      → [bold]Second Brain Local[/bold] → toggle [bold]on[/bold]")
        console.print( "   3. Refresh the page in Safari\n")
    else:
        console.print(f"\n[bold]🧠 Brain Web UI[/bold]")
        console.print(f"   Mac:   [cyan]{local_url}[/cyan]")
        if phone_url:
            console.print(f"   Phone: [cyan]{phone_url}[/cyan]  [dim](same WiFi)[/dim]")
            console.print(f"   [dim]Tip: use --https for full PWA support (Add to Home Screen + offline)[/dim]")

    console.print(f"   [dim]DB → {DB_PATH}[/dim]")
    console.print("[dim]   Ctrl+C to stop\n[/dim]")

    if not no_browser:
        threading.Timer(0.9, lambda: webbrowser.open(local_url)).start()

    try:
        app = create_app()
        app.run(host="0.0.0.0", port=port, debug=False,
                threaded=True, use_reloader=False,
                ssl_context=ssl_ctx)
    except OSError as e:
        if "Address already in use" in str(e):
            console.print(f"[red]Port {port} in use.[/red]  Try: brain web --port {port+1}")
        else:
            console.print(f"[red]{e}[/red]")
        sys.exit(1)


# ── main ──────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
