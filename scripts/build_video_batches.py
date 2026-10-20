import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

source = json.loads((DATA / "vocabulary_pilot.json").read_text(encoding="utf-8"))
entries = source["entries"]
random.Random(20261020).shuffle(entries)

WORD_SIZE = 7
SENTENCE_SIZE = 4


def make_batches(items, size):
    """Fill batches in randomized order, avoiding duplicate groups when possible."""
    batches = []
    for item in items:
        placed = False

        # Prefer a batch with space that does not already contain this group.
        for batch in batches:
            if len(batch) < size and all(x["group_id"] != item["group_id"] for x in batch):
                batch.append(item)
                placed = True
                break

        # Otherwise use the earliest batch with space.
        if not placed:
            for batch in batches:
                if len(batch) < size:
                    batch.append(item)
                    placed = True
                    break

        # Start a new batch only when every existing batch is full.
        if not placed:
            batches.append([item])

    return batches


words = [e for e in entries if e["type"] == "word"]
sentences = [e for e in entries if e["type"] == "sentence"]

word_batches = make_batches(words, WORD_SIZE)
sentence_batches = make_batches(sentences, SENTENCE_SIZE)

full_word_batches = [b for b in word_batches if len(b) == WORD_SIZE]
full_sentence_batches = [b for b in sentence_batches if len(b) == SENTENCE_SIZE]
word_remainder = [e for b in word_batches if len(b) < WORD_SIZE for e in b]
sentence_remainder = [e for b in sentence_batches if len(b) < SENTENCE_SIZE for e in b]


def pair(e, position):
    return {
        "position": position,
        "entry_id": e["id"],
        "english": e["english"],
        "kinyarwanda": e["kinyarwanda"],
        "group_id": e["group_id"],
        "group_title": e["group_title"],
        "grammar": e["grammar"],
        "verification": e["verification"],
        "sources": e["sources"],
        "notes": e["notes"],
    }


videos = []
for i, batch in enumerate(full_word_batches, 1):
    videos.append({
        "id": f"word_{i:02d}",
        "mode": "word",
        "complete": True,
        "pair_count": len(batch),
        "line_count": len(batch) * 2,
        "pairs": [pair(e, n) for n, e in enumerate(batch, 1)],
    })

for i, batch in enumerate(full_sentence_batches, 1):
    videos.append({
        "id": f"sentence_{i:02d}",
        "mode": "sentence",
        "complete": True,
        "pair_count": len(batch),
        "line_count": len(batch) * 2,
        "pairs": [pair(e, n) for n, e in enumerate(batch, 1)],
    })

payload = {
    "meta": {
        "name": "Menya Icyongereza video-ready pilot batches",
        "version": 1,
        "created": "2026-10-20",
        "source_database": "vocabulary_pilot.json",
        "direction": "english_to_kinyarwanda",
        "language_from": "en",
        "language_to": "rw",
        "word_video_size": WORD_SIZE,
        "sentence_video_size": SENTENCE_SIZE,
        "sentence_lines_per_video": SENTENCE_SIZE * 2,
        "word_count": len(words),
        "sentence_count": len(sentences),
        "full_word_videos": len(full_word_batches),
        "full_sentence_videos": len(full_sentence_batches),
        "word_remainder": len(word_remainder),
        "sentence_remainder": len(sentence_remainder),
        "batch_seed": 20261020,
        "rule": "Only complete batches are in videos: word videos have exactly 7 pairs (14 lines); sentence videos have exactly 4 pairs (8 lines). Leftover entries are in remainder and are not treated as complete videos.",
    },
    "videos": videos,
    "remainder": {
        "note": "Not enough entries for a complete batch in this pilot. These will fill the next videos after the database is expanded.",
        "words": [pair(e, i) for i, e in enumerate(word_remainder, 1)],
        "sentences": [pair(e, i) for i, e in enumerate(sentence_remainder, 1)],
    },
}

# Validate every entry appears exactly once and every complete video obeys its size.
video_entry_ids = [p["entry_id"] for v in videos for p in v["pairs"]]
remainder_ids = [p["entry_id"] for p in payload["remainder"]["words"]] + [
    p["entry_id"] for p in payload["remainder"]["sentences"]
]
all_ids = video_entry_ids + remainder_ids
assert len(all_ids) == 100, len(all_ids)
assert len(set(all_ids)) == 100, "duplicate or missing entries"
assert all(v["pair_count"] == 7 and v["line_count"] == 14 for v in videos if v["mode"] == "word")
assert all(v["pair_count"] == 4 and v["line_count"] == 8 for v in videos if v["mode"] == "sentence")
assert len(full_word_batches) == 10
assert len(full_sentence_batches) == 6
assert len(word_remainder) == 4
assert len(sentence_remainder) == 2

out = DATA / "vocabulary_pilot_videos.json"
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = []
lines.append("# Menya Icyongereza — video-ready pilot batches")
lines.append("")
lines.append(f"- **{len(full_word_batches)} word videos** × 7 pairs (14 lines each)")
lines.append(f"- **{len(full_sentence_batches)} sentence videos** × 4 pairs (8 lines each)")
lines.append(f"- Remainder: **{len(word_remainder)} words** and **{len(sentence_remainder)} sentence pairs** (not complete batches)")
lines.append("- Direction: English → Kinyarwanda")
lines.append("")
lines.append("Only complete batches are listed as videos. The remainder is kept separately so no entry is lost.")
lines.append("")

for video in videos:
    lines.append(f"## {video['id']} — {video['pair_count']} pairs / {video['line_count']} lines")
    lines.append("")
    lines.append("| # | English | Kinyarwanda | Group | Status |")
    lines.append("|---|---|---|---|---|")
    for p in video["pairs"]:
        status = "verified" if p["verification"] == "verified" else "native review"
        lines.append(f"| {p['position']} | {p['english']} | {p['kinyarwanda']} | {p['group_title']} | {status} |")
    lines.append("")

lines.append("## Remainder (not a complete video)")
lines.append("")
if word_remainder:
    lines.append("### Words")
    lines.append("")
    lines.append("| # | English | Kinyarwanda | Group | Status |")
    lines.append("|---|---|---|---|---|")
    for p in payload["remainder"]["words"]:
        status = "verified" if p["verification"] == "verified" else "native review"
        lines.append(f"| {p['position']} | {p['english']} | {p['kinyarwanda']} | {p['group_title']} | {status} |")
    lines.append("")
if sentence_remainder:
    lines.append("### Sentences")
    lines.append("")
    lines.append("| # | English | Kinyarwanda | Group | Status |")
    lines.append("|---|---|---|---|---|")
    for p in payload["remainder"]["sentences"]:
        status = "verified" if p["verification"] == "verified" else "native review"
        lines.append(f"| {p['position']} | {p['english']} | {p['kinyarwanda']} | {p['group_title']} | {status} |")
    lines.append("")

review = DATA / "vocabulary_pilot_videos_review.md"
review.write_text("\n".join(lines), encoding="utf-8")

print(f"wrote {out}")
print(f"wrote {review}")
print(f"word videos: {len(full_word_batches)} (7 pairs each)")
print(f"sentence videos: {len(full_sentence_batches)} (4 pairs each)")
print(f"remainder: {len(word_remainder)} words, {len(sentence_remainder)} sentences")
