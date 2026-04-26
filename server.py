"""
server.py — Flask web server and REST API for the Second Brain app.

Run standalone:  python server.py
Via CLI:         brain web
"""

import os
import sys
import logging

# Allow running as `python server.py` from any directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, send_from_directory  # type: ignore

from db import (
    DB_PATH, VALID_STATUSES,
    get_db, now_iso, normalise_tags, fts_search,
)

# ── Paths ───────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR    = os.path.join(BASE_DIR, "static")

# ── Safe sort columns (prevent SQL injection) ───────────────────────────────────
_SAFE_SORT = {"id", "title", "type", "priority", "status", "created_at", "updated_at"}


def create_app() -> Flask:
    app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
    app.config["JSON_SORT_KEYS"] = False

    # Silence werkzeug request logs; errors still surface
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    # ── Frontend ─────────────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return send_from_directory(TEMPLATES_DIR, "index.html")

    # ── /api/stats ───────────────────────────────────────────────────────────────

    @app.route("/api/stats")
    def api_stats():
        db = get_db()
        try:
            total       = db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            by_status   = dict(db.execute(
                "SELECT status, COUNT(*) FROM entries GROUP BY status"
            ).fetchall())
            by_type     = dict(db.execute(
                "SELECT type, COUNT(*) FROM entries GROUP BY type"
            ).fetchall())
            by_priority = {
                str(r[0]): r[1]
                for r in db.execute(
                    "SELECT priority, COUNT(*) FROM entries GROUP BY priority"
                ).fetchall()
            }
        finally:
            db.close()
        return jsonify({
            "total":       total,
            "by_status":   by_status,
            "by_type":     by_type,
            "by_priority": by_priority,
        })

    # ── /api/entries  GET ─────────────────────────────────────────────────────────

    @app.route("/api/entries", methods=["GET"])
    def api_list():
        q      = request.args.get("q",      "").strip()
        type_  = request.args.get("type",   "").strip()
        tag    = request.args.get("tag",    "").strip()
        status = request.args.get("status", "").strip()
        sort   = request.args.get("sort",   "created_at").strip()
        order  = request.args.get("order",  "desc").strip().upper()
        limit  = min(int(request.args.get("limit",  25)), 200)
        offset = max(int(request.args.get("offset",  0)),  0)

        if sort  not in _SAFE_SORT:       sort  = "created_at"
        if order not in ("ASC", "DESC"):  order = "DESC"

        db       = get_db()
        clauses: list = []
        params:  list = []

        if q:
            ids = fts_search(db, q)
            if ids is not None:
                if not ids:
                    db.close()
                    return jsonify({"entries": [], "total": 0,
                                    "limit": limit, "offset": offset})
                clauses.append(f"id IN ({','.join('?' * len(ids))})")
                params.extend(ids)
            else:
                like = f"%{q}%"
                clauses.append("(title LIKE ? OR content LIKE ? OR tags LIKE ?)")
                params.extend([like, like, like])

        if type_:
            clauses.append("type = ?");  params.append(type_)
        if tag:
            clauses.append("(',' || tags || ',') LIKE ?")
            params.append(f"%,{tag},%")
        if status:
            clauses.append("status = ?"); params.append(status)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        try:
            total = db.execute(
                f"SELECT COUNT(*) FROM entries {where}", params
            ).fetchone()[0]
            rows  = db.execute(
                f"SELECT * FROM entries {where}"
                f" ORDER BY {sort} {order} LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
        finally:
            db.close()

        return jsonify({
            "entries": [dict(r) for r in rows],
            "total":   total,
            "limit":   limit,
            "offset":  offset,
        })

    # ── /api/entries  POST ────────────────────────────────────────────────────────

    @app.route("/api/entries", methods=["POST"])
    def api_create():
        data     = request.get_json(force=True) or {}
        title    = str(data.get("title",   "")).strip()
        if not title:
            return jsonify({"error": "title required"}), 400

        type_    = str(data.get("type",    "note")).strip().lower()
        content  = str(data.get("content", "")).strip()
        url      = str(data.get("url",     "")).strip()
        tags     = normalise_tags(str(data.get("tags", "")))
        priority = int(data.get("priority", 3))
        status   = str(data.get("status",  "active"))

        if not 1 <= priority <= 5:
            return jsonify({"error": "priority must be 1-5"}), 400
        if status not in VALID_STATUSES:
            return jsonify({"error": "invalid status"}), 400

        ts = now_iso()
        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO entries"
                " (title, content, url, type, tags, priority, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (title, content, url, type_, tags, priority, status, ts, ts),
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM entries WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        finally:
            db.close()
        return jsonify(dict(row)), 201

    # ── /api/entries/<id>  GET ────────────────────────────────────────────────────

    @app.route("/api/entries/<int:eid>", methods=["GET"])
    def api_get(eid):
        db = get_db()
        try:
            row = db.execute(
                "SELECT * FROM entries WHERE id = ?", (eid,)
            ).fetchone()
        finally:
            db.close()
        if not row:
            return jsonify({"error": "not found"}), 404
        return jsonify(dict(row))

    # ── /api/entries/<id>  PUT ────────────────────────────────────────────────────

    @app.route("/api/entries/<int:eid>", methods=["PUT"])
    def api_update(eid):
        db = get_db()
        try:
            row = db.execute(
                "SELECT * FROM entries WHERE id = ?", (eid,)
            ).fetchone()
            if not row:
                return jsonify({"error": "not found"}), 404

            data     = request.get_json(force=True) or {}
            title    = str(data.get("title",    row["title"])).strip()
            type_    = str(data.get("type",     row["type"])).strip().lower()
            content  = str(data.get("content",  row["content"])).strip()
            url      = str(data.get("url",      row["url"])).strip()
            tags     = normalise_tags(str(data.get("tags",  row["tags"])))
            priority = int(data.get("priority", row["priority"]))
            status   = str(data.get("status",   row["status"]))

            if not title:
                return jsonify({"error": "title required"}), 400
            if not 1 <= priority <= 5:
                return jsonify({"error": "priority must be 1-5"}), 400
            if status not in VALID_STATUSES:
                return jsonify({"error": "invalid status"}), 400

            db.execute(
                "UPDATE entries"
                " SET title=?, type=?, content=?, url=?, tags=?,"
                " priority=?, status=?, updated_at=?"
                " WHERE id=?",
                (title, type_, content, url, tags, priority, status, now_iso(), eid),
            )
            db.commit()
            updated = db.execute(
                "SELECT * FROM entries WHERE id = ?", (eid,)
            ).fetchone()
        finally:
            db.close()
        return jsonify(dict(updated))

    # ── /api/entries/<id>  DELETE ─────────────────────────────────────────────────

    @app.route("/api/entries/<int:eid>", methods=["DELETE"])
    def api_delete(eid):
        db = get_db()
        try:
            if not db.execute(
                "SELECT id FROM entries WHERE id = ?", (eid,)
            ).fetchone():
                return jsonify({"error": "not found"}), 404
            db.execute("DELETE FROM entries WHERE id = ?", (eid,))
            db.commit()
        finally:
            db.close()
        return jsonify({"deleted": eid})

    # ── /api/tags ─────────────────────────────────────────────────────────────────

    @app.route("/api/tags")
    def api_tags():
        db = get_db()
        try:
            rows = db.execute(
                "SELECT tags FROM entries WHERE tags != ''"
            ).fetchall()
        finally:
            db.close()
        counts: dict = {}
        for r in rows:
            for t in r["tags"].split(","):
                t = t.strip()
                if t:
                    counts[t] = counts.get(t, 0) + 1
        return jsonify(sorted(
            [{"tag": k, "count": v} for k, v in counts.items()],
            key=lambda x: -x["count"],
        ))

    # ── /api/types ────────────────────────────────────────────────────────────────

    @app.route("/api/types")
    def api_types():
        db = get_db()
        try:
            rows = db.execute(
                "SELECT type, COUNT(*) AS count FROM entries"
                " GROUP BY type ORDER BY count DESC"
            ).fetchall()
        finally:
            db.close()
        return jsonify([dict(r) for r in rows])

    # ── /api/random ───────────────────────────────────────────────────────────────

    @app.route("/api/random")
    def api_random():
        db = get_db()
        try:
            # Prefer entries not touched in 7+ days
            row = db.execute(
                "SELECT * FROM entries WHERE status='active'"
                " AND updated_at <= date('now','-7 days')"
                " ORDER BY RANDOM() LIMIT 1"
            ).fetchone()
            if not row:
                row = db.execute(
                    "SELECT * FROM entries WHERE status='active'"
                    " ORDER BY RANDOM() LIMIT 1"
                ).fetchone()
        finally:
            db.close()
        if not row:
            return jsonify({"error": "no active entries"}), 404
        return jsonify(dict(row))

    return app


# ── Run directly ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import webbrowser, threading
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}. Run 'brain init' first.")
        sys.exit(1)
    port = int(os.environ.get("BRAIN_PORT", 8787))
    url  = f"http://127.0.0.1:{port}"
    print(f"Brain Web UI -> {url}  (Ctrl+C to stop)")
    threading.Timer(0.9, lambda: webbrowser.open(url)).start()
    create_app().run(host="127.0.0.1", port=port, debug=False,
                     threaded=True, use_reloader=False)
