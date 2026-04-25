#!/usr/bin/env python3
"""
make_icons.py — Generate PWA icons for Second Brain.

Uses only Python stdlib (struct + zlib) — no Pillow needed.
Run once from the project directory:

    python3 make_icons.py

Produces:
    static/icon-192.png   (used by manifest + Android home screen)
    static/icon-512.png   (used by manifest splash screen)
    static/icon-apple.png (180×180, used by iOS "Add to Home Screen")
"""
import math, pathlib, struct, zlib

OUT = pathlib.Path(__file__).parent / "static"

# ── Palette ─────────────────────────────────────────────────────────────────────
BG = (13,  17,  23)   # --bg  dark canvas
AC = (88,  166, 255)  # --ac  blue brain
SH = (31,  111, 235)  # slightly darker blue for shading


# ── Minimal PNG encoder ─────────────────────────────────────────────────────────

def _chunk(tag: bytes, data: bytes) -> bytes:
    payload = tag + data
    return (
        struct.pack(">I", len(data))
        + payload
        + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
    )


def _png(rows) -> bytes:
    """rows: list[list[(r,g,b)]]"""
    h, w = len(rows), len(rows[0])
    raw  = bytearray()
    for row in rows:
        raw += b"\x00"                        # filter: None
        for r, g, b in row:
            raw += bytes([r, g, b])
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


# ── Icon renderer ───────────────────────────────────────────────────────────────

def _brain(size: int) -> bytes:
    """
    Two overlapping circles (brain hemispheres) in AC on BG.
    A narrow vertical groove separates them (corpus callosum).
    Small notches at the crown of each lobe add a bit of texture.
    """
    cx  = size / 2.0
    cy  = size / 2.0

    r   = size * 0.285           # hemisphere radius
    ox  = size * 0.100           # horizontal offset from centre
    oy  = size * 0.015           # slight upward offset
    lx  = cx - ox                # left lobe centre x
    rx  = cx + ox                # right lobe centre x
    hcy = cy - oy                # shared lobe centre y

    gap = size * 0.030           # half-width of centre groove
    groove_top = hcy - r * 0.50  # groove only covers lower portion

    notch_r = r * 0.21
    notches = [                  # small indentations at crown of each lobe
        (lx - r * 0.28, hcy - r * 0.58),
        (rx + r * 0.28, hcy - r * 0.58),
    ]

    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            dl = math.hypot(x - lx, y - hcy)
            dr = math.hypot(x - rx, y - hcy)

            in_brain  = dl <= r or dr <= r
            in_groove = abs(x - cx) < gap and y > groove_top
            in_notch  = any(math.hypot(x - nx, y - ny) < notch_r
                            for nx, ny in notches)

            if in_brain and not in_groove and not in_notch:
                # Subtle shading: right lobe slightly darker where it doesn't
                # overlap with left lobe
                if dr <= r and not (dl <= r):
                    row.append(SH)
                else:
                    row.append(AC)
            else:
                row.append(BG)
        rows.append(row)

    return _png(rows)


# ── Main ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for size, name in [(192, "icon-192.png"), (512, "icon-512.png"), (180, "icon-apple.png")]:
        data = _brain(size)
        path = OUT / name
        path.write_bytes(data)
        print(f"  ✓  static/{name}  ({len(data):,} bytes)")
    print("Done.")
