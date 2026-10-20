#!/usr/bin/env python3
"""
Menya Icyongereza - vocabulary video generator.

Renders a 1080x1920 video frame that looks like the Menya Icyongereza app
screen (phone mockup background), with 5 English word / Kinyarwanda
translation rows and a yellow promo box.

Everything is drawn at 1.5x the source mockup so text stays sharp.

Usage:
    python generate.py                         # built-in test content
    python generate.py --pairs "Book=Igitabo,Water=Amazi"
    python generate.py --note "Some text" --duration 6
    python generate.py --video                 # also encode the mp4
"""

import argparse
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- paths / canvas
ROOT = Path(__file__).resolve().parent
BG_PATH = ROOT / "assets" / "img" / "background.png"
FONT_DIR = ROOT / "assets" / "fonts"
OUT_DIR = ROOT / "output"
PREVIEW_DIR = ROOT / "preview"

SCALE = 1.5
W, H = 1080, 1920

# Phone screen body measured from the 720x1280 mockup (x 32..685, y 183..1115)
BODY = (
    round(32 * SCALE),      # left
    round(183 * SCALE),     # top
    round(685 * SCALE),     # right
    round(1115 * SCALE),    # bottom
)

# ---------------------------------------------------------------- design tokens
GREEN = "#58CC02"
GREEN_DARK = "#46A302"
GREEN_LIGHT = "#D7FFB8"
TEXT = "#3C3C3C"
MUTED = "#8A8A8A"
BORDER = "#E5E5E5"
YELLOW = "#FFF9C4"
INK = "#1E1E1E"
WHITE = "#FFFFFF"

SIDE_PAD = 36
ROW_GAP = 20
ROW_MAX_H = 184
PROMO_PAD = 30

# ---------------------------------------------------------------- defaults
DEFAULT_PAIRS = "Book=Igitabo,Water=Amazi,House=Inzu,Friend=Inshuti,School=Ishuri"
DEFAULT_NOTE = (
    "Ushaka kwiga icyongereza wakoresha iyi app yitwa Menya Icyongereza App"
)
DEFAULT_BRAND = "Menya Icyongereza App"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


def tracked_text(draw, xy, text, fnt, fill, tracking=0.0, anchor="la"):
    """Draw text with letter-spacing (Pillow has no native tracking)."""
    x, y = xy
    if tracking == 0:
        draw.text((x, y), text, font=fnt, fill=fill, anchor=anchor)
        return
    widths = [fnt.getlength(ch) for ch in text]
    total = sum(widths) + tracking * max(0, len(text) - 1)
    if anchor[0] == "m":
        x -= total / 2
    elif anchor[0] == "r":
        x -= total
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=fnt, fill=fill, anchor=anchor)
        x += w + tracking


def parse_pairs(raw: str):
    chunks = [c.strip() for c in raw.replace("\r", "").split(";")]
    chunks = [c for chunk in chunks for c in chunk.split("\n")]
    chunks = [c.strip() for c in chunks if c.strip()]
    if len(chunks) == 1 and "," in chunks[0]:
        chunks = [c.strip() for c in chunks[0].split(",") if c.strip()]

    pairs = []
    for chunk in chunks:
        for sep in ("=", "|"):
            if sep in chunk:
                eng, kin = chunk.split(sep, 1)
                break
        else:
            raise SystemExit(f"Bad pair (use English=Kinyarwanda): {chunk!r}")
        eng, kin = eng.strip(), kin.strip()
        if eng and kin:
            pairs.append((eng, kin))
    if not pairs:
        raise SystemExit("No word pairs given.")
    return pairs[:6]


def fit_font(text, font_name, start, minimum, max_width):
    size = start
    while size > minimum:
        f = font(font_name, size)
        if f.getlength(text) <= max_width:
            return f
        size -= 1
    return font(font_name, minimum)


def wrap_to_width(text, fnt, max_width):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if fnt.getlength(trial) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def wrap_balanced(text, fnt, max_width):
    """Wrap lines so they look even instead of leaving one orphan word.

    Minimises the sum of squared empty space on every line. Explicit
    newlines in the input are respected.
    """
    if "\n" in text:
        out = []
        for part in text.split("\n"):
            part = part.strip()
            if part:
                out.extend(wrap_balanced(part, fnt, max_width))
        return out or [""]

    words = text.split()
    if not words:
        return [""]

    widths = [fnt.getlength(w) for w in words]
    space = fnt.getlength(" ")
    n = len(words)

    # cost of putting words i..j on one line (None if it does not fit)
    def line_cost(i, j):
        w = sum(widths[i : j + 1]) + space * (j - i)
        if w > max_width:
            return None, w
        return (max_width - w) ** 2, w

    best = [float("inf")] * (n + 1)
    best[0] = 0
    prev = [0] * (n + 1)
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            cost, w = line_cost(i, j - 1)
            if cost is None:
                break
            cand = best[i] + cost
            if cand < best[j]:
                best[j] = cand
                prev[j] = i

    # reconstruct
    lines = []
    j = n
    while j > 0:
        i = prev[j]
        lines.append(" ".join(words[i:j]))
        j = i
    return list(reversed(lines))


def rounded_shadow(base, box, radius, offset=6, alpha=26):
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(shadow)
    x0, y0, x1, y1 = box
    d.rounded_rectangle(
        (x0, y0 + offset, x1, y1 + offset), radius=radius, fill=(20, 20, 20, alpha)
    )
    return Image.alpha_composite(base, shadow)


def draw_row(canvas, box, index, english, kinyarwanda):
    x0, y0, x1, y1 = box
    h = y1 - y0
    radius = 24
    canvas = rounded_shadow(canvas, box, radius)
    d = ImageDraw.Draw(canvas)

    # card
    d.rounded_rectangle(box, radius=radius, fill=WHITE, outline=BORDER, width=2)

    # number badge (3D: darker edge under the green face)
    badge = 64
    bx = x0 + 26
    by = y0 + (h - badge) // 2
    d.rounded_rectangle(
        (bx, by + 4, bx + badge, by + badge + 4), radius=18, fill=GREEN_DARK
    )
    d.rounded_rectangle((bx, by, bx + badge, by + badge), radius=18, fill=GREEN)
    num = font("Poppins-ExtraBold.ttf", 30)
    d.text(
        (bx + badge / 2, by + badge / 2 + 1),
        str(index),
        font=num,
        fill=WHITE,
        anchor="mm",
    )

    # English (left) and Kinyarwanda (right), baseline aligned
    text_left = bx + badge + 26
    text_right = x1 - 30
    available = text_right - text_left

    f_eng = fit_font(english, "Poppins-ExtraBold.ttf", 46, 26, available * 0.62)
    f_kin = fit_font(kinyarwanda, "Poppins-Bold.ttf", 42, 24, available * 0.55)

    eng_w = f_eng.getlength(english)
    kin_w = f_kin.getlength(kinyarwanda)

    baseline = y0 + h / 2 + 0.35 * f_eng.size

    d.text((text_left, baseline), english, font=f_eng, fill=TEXT, anchor="ls")
    d.text((text_right, baseline), kinyarwanda, font=f_kin, fill=GREEN_DARK, anchor="rs")

    # dotted leader between the two columns
    dot_start = text_left + eng_w + 22
    dot_end = text_right - kin_w - 22
    if dot_end - dot_start >= 40:
        dot_y = y0 + h / 2 + 12
        r = 3
        step = 15
        x = dot_start
        while x <= dot_end:
            d.ellipse((x - r, dot_y - r, x + r, dot_y + r), fill="#D5D5D5")
            x += step

    return canvas


def draw_promo(canvas, box, lines, brand):
    x0, y0, x1, y1 = box
    radius = 24
    canvas = rounded_shadow(canvas, box, radius, offset=6, alpha=24)
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle(box, radius=radius, fill=YELLOW, outline=INK, width=2)

    inner_w = (x1 - x0) - PROMO_PAD * 2

    f_line = font("Poppins-Bold.ttf", 40)
    line_h = 54
    pill_h = 76
    gap = 14
    text_h = len(lines) * line_h
    content_h = text_h + (gap + pill_h if brand else 0)
    cy = y0 + ((y1 - y0) - content_h) / 2

    for line in lines:
        d.text(((x0 + x1) / 2, cy), line, font=f_line, fill=INK, anchor="ma")
        cy += line_h

    if brand:
        cy += gap
        f_brand = fit_font(brand, "Poppins-ExtraBold.ttf", 34, 22, inner_w - 110)
        text_w = f_brand.getlength(brand)
        pw = text_w + 104
        px0 = (x0 + x1) / 2 - pw / 2
        py0 = cy
        d.rounded_rectangle(
            (px0, py0 + 4, px0 + pw, py0 + pill_h + 4),
            radius=pill_h / 2,
            fill=GREEN_DARK,
        )
        d.rounded_rectangle(
            (px0, py0, px0 + pw, py0 + pill_h), radius=pill_h / 2, fill=GREEN
        )
        d.text(
            (px0 + pw / 2, py0 + pill_h / 2 + 1),
            brand,
            font=f_brand,
            fill=WHITE,
            anchor="mm",
        )

    return canvas


def render(pairs, note, brand, out_path: Path):
    if not BG_PATH.exists():
        raise SystemExit(f"Missing background: {BG_PATH}")

    bg = Image.open(BG_PATH).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)
    canvas = bg.copy()

    left, top, right, bottom = BODY
    content_left = left + SIDE_PAD
    content_right = right - SIDE_PAD
    content_w = content_right - content_left

    # section label
    label = f"AMAGAMBO {len(pairs)} Y'ICYONGEREZA"
    d = ImageDraw.Draw(canvas)
    f_label = font("Poppins-SemiBold.ttf", 24)
    tracked_text(
        d, (content_left + 3, top + 34), label, f_label, MUTED, tracking=3.2
    )

    # promo block height first (so rows can use the rest of the screen)
    f_line = font("Poppins-Bold.ttf", 40)
    note_clean = note.strip()
    show_brand = False
    if brand and brand.lower() in note_clean.lower():
        idx = note_clean.lower().rfind(brand.lower())
        note_clean = note_clean[:idx].rstrip(" ,.-")
        show_brand = True
    note_lines = wrap_balanced(note_clean, f_line, content_w - PROMO_PAD * 2)
    promo_h = (
        PROMO_PAD * 2
        + len(note_lines) * 54
        + (14 + 76 if show_brand else 0)
    )

    promo_bottom = bottom - 30
    promo_top = promo_bottom - promo_h

    rows_top = top + 34 + 40 + 28
    rows_bottom_limit = promo_top - 42
    n = len(pairs)
    row_h = min(ROW_MAX_H, int((rows_bottom_limit - rows_top - (n - 1) * ROW_GAP) / n))
    row_h = max(row_h, 96)

    y = rows_top
    for i, (eng, kin) in enumerate(pairs, start=1):
        canvas = draw_row(
            canvas, (content_left, y, content_right, y + row_h), i, eng, kin
        )
        y += row_h + ROW_GAP

    canvas = draw_promo(
        canvas,
        (content_left, promo_top, content_right, promo_bottom),
        note_lines,
        brand if show_brand else "",
    )

    out = canvas.convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, "PNG", optimize=True)
    return out


def encode_video(frame_path: Path, out_path: Path, duration: float, song: Path | None):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg not found on PATH.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", "-framerate", "30", "-loop", "1", "-i", str(frame_path)]
    if song:
        cmd += ["-stream_loop", "-1", "-i", str(song)]
        cmd += [
            "-af",
            "loudnorm=I=-15:TP=-1.5:LRA=11",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
        ]
    cmd += [
        "-t",
        str(duration),
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "19",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return out_path


def pick_song(explicit: str):
    if explicit:
        song = Path(explicit)
        if not song.exists():
            raise SystemExit(f"Song not found: {song}")
        return song

    song_dir = ROOT / "assets" / "song"
    if not song_dir.exists():
        return None
    tracks = [
        p
        for p in sorted(song_dir.iterdir())
        if p.suffix.lower() in {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg"}
    ]
    return random.choice(tracks) if tracks else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=DEFAULT_PAIRS)
    ap.add_argument("--note", default=DEFAULT_NOTE)
    ap.add_argument("--brand", default=DEFAULT_BRAND)
    ap.add_argument("--duration", type=float, default=6.0)
    ap.add_argument("--song", default="")
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--preview", default="")
    args = ap.parse_args()

    pairs = parse_pairs(args.pairs)
    preview_path = Path(args.preview) if args.preview else PREVIEW_DIR / "preview.png"
    render(pairs, args.note, args.brand, preview_path)
    print(f"preview: {preview_path}")

    if args.video:
        if args.out:
            video_path = Path(args.out)
        else:
            stamp = int(time.time() * 1000)
            video_path = OUT_DIR / f"menya_vocab_{stamp}.mp4"
        song = pick_song(args.song)
        if song:
            print(f"song:    {song}")
        encode_video(preview_path, video_path, args.duration, song)
        print(f"video:   {video_path}")


if __name__ == "__main__":
    main()
