#!/usr/bin/env python3
"""Build chunk files and a rotation manifest from a vocabulary database.

Two input shapes are supported:

1. A flat database with an ``entries`` list (or a bare list). Each entry has
   ``type`` = ``word`` or ``sentence``. Words are grouped 7 per video and
   sentences 4 per video. Leftover entries are kept in a ``remainder`` bucket
   unless ``--allow-partial`` is passed.
2. A video-batch file with a ``videos`` list (the pilot format). Every video
   must already be a complete 7-word or 4-pair job.

By default only items marked ``verification: "verified"`` enter the rotation.
Unverified entries/videos are recorded in the manifest meta and excluded.
``--include-unverified`` is for review/layout builds only, never publishing.
``--trust-dictionary`` promotes cached-dictionary pairs; ``--trust-corpus``
does the same for the separately sourced sentence track. Duplicate entries and
duplicate videos are rejected; ``--allow-shared-entries`` relaxes that to unique
video signatures only. ``--chunk-size`` is a soft target: a chunk may go over it
so a video is never split. ``--start-content content_0003`` migrates a rotation
without replaying finished videos. ``--id-prefix sentence_`` keeps a separate
sentence rotation from colliding with the word-track ids.

Outputs:

    data/chunks/vocabulary_chunk_01.json ...
    data/rotation_manifest.json
    data/rotation_state.json

Usage:

    python scripts/build_chunks.py \
        --input data/vocabulary_pilot_videos.json \
        --chunk-size 300

    python scripts/build_chunks.py \
        --input data/vocabulary_all.json \
        --chunk-size 300

The second command is the one to run after the full 1,098-entry database is
ready. The builder refuses to silently drop entries: leftovers and excluded
unverified items are recorded in the manifest and printed in the summary.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "vocabulary_pilot_videos.json"
DEFAULT_OUT_DIR = ROOT / "data" / "chunks"
DEFAULT_MANIFEST = ROOT / "data" / "rotation_manifest.json"
DEFAULT_STATE = ROOT / "data" / "rotation_state.json"


def now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def rel_to_root(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def rel_to_manifest(path: Path, manifest: Path) -> str:
    try:
        return path.resolve().relative_to(manifest.parent.resolve()).as_posix()
    except ValueError:
        return str(path)


def entry_mode(entry: dict[str, Any]) -> str:
    raw = str(entry.get("type") or entry.get("mode") or "").strip().lower()
    if raw in {"word", "words"}:
        return "word"
    if raw in {"sentence", "sentences"}:
        return "sentence"
    raise SystemExit(
        f"Entry has no usable type/mode (expected word or sentence): "
        f"{entry.get('english')!r}"
    )


def entry_is_verified(entry: dict[str, Any]) -> bool:
    return str(entry.get("verification") or "").strip().lower() == "verified"


def pair_is_verified(pair: dict[str, Any]) -> bool:
    return str(pair.get("verification") or "").strip().lower() == "verified"


def promote_verification(data: Any, source_tier: str) -> int:
    """Promote a named source tier to the publishing gate.

    The source database keeps the original tier visible (``dictionary`` for the
    generated word videos, ``corpus`` for the sentence track). The opt-in flags
    promote those pairs to ``verified`` for a build while ``verification_tier``
    preserves where they came from. This is deliberate: a promoted pair is
    publishable, not claimed as individually native-reviewed.
    """
    changed = 0
    wanted = source_tier.strip().lower()

    def promote(pair: dict[str, Any]) -> None:
        nonlocal changed
        if str(pair.get("verification") or "").strip().lower() != wanted:
            return
        pair["verification"] = "verified"
        pair.setdefault("verification_tier", wanted)
        changed += 1

    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                promote(entry)
    elif isinstance(data, dict):
        for entry in data.get("entries", []) or []:
            if isinstance(entry, dict):
                promote(entry)
        for video in data.get("videos", []) or []:
            if not isinstance(video, dict):
                continue
            for pair in video.get("pairs", []) or []:
                if isinstance(pair, dict):
                    promote(pair)
    return changed


def promote_dictionary_verification(data: Any) -> int:
    """Backward-compatible wrapper for the word-track build."""
    return promote_verification(data, "dictionary")


def promote_corpus_verification(data: Any) -> int:
    """Promote corpus-aligned sentence pairs for the separate sentence track."""
    return promote_verification(data, "corpus")


def pair_from_entry(entry: dict[str, Any], index: int) -> dict[str, Any]:
    english = str(entry.get("english") or "").strip()
    kinyarwanda = str(entry.get("kinyarwanda") or "").strip()
    if not english or not kinyarwanda:
        raise SystemExit(f"Entry {index + 1} is missing english or kinyarwanda.")
    return {
        "english": english,
        "kinyarwanda": kinyarwanda,
        "entry_id": entry.get("id") or f"entry_{index + 1:04d}",
        "group_id": entry.get("group_id", ""),
        "group_title": entry.get("group_title", ""),
        "grammar": entry.get("grammar", ""),
        "verification": entry.get("verification", ""),
        "verification_tier": entry.get("verification_tier", ""),
        "corpus_hits": entry.get("corpus_hits", 0),
        "sources": entry.get("sources", []),
        "notes": entry.get("notes", ""),
    }


def mode_jobs(
    items: list[tuple[int, dict[str, Any]]],
    mode: str,
    size: int,
    allow_partial: bool,
) -> tuple[list[dict[str, Any]], list[tuple[int, dict[str, Any]]]]:
    jobs: list[dict[str, Any]] = []
    remainder: list[tuple[int, dict[str, Any]]] = []

    for start in range(0, len(items), size):
        batch = items[start : start + size]
        if len(batch) < size and not allow_partial:
            remainder.extend(batch)
            continue
        pairs = [pair_from_entry(entry, index) for index, entry in batch]
        jobs.append(
            {
                "mode": mode,
                "pair_count": len(pairs),
                "line_count": len(pairs) * 2 if mode == "sentence" else len(pairs),
                "source_indices": [index for index, _ in batch],
                "source_entry_ids": [pair["entry_id"] for pair in pairs],
                "first_source_index": min(index for index, _ in batch),
                "pairs": pairs,
            }
        )

    return jobs, remainder


def merge_jobs(
    word_jobs: list[dict[str, Any]],
    sentence_jobs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge word/sentence jobs by the position of their first source entry."""
    jobs: list[dict[str, Any]] = []
    wi = si = 0
    while wi < len(word_jobs) or si < len(sentence_jobs):
        if si >= len(sentence_jobs):
            jobs.append(word_jobs[wi])
            wi += 1
        elif wi >= len(word_jobs):
            jobs.append(sentence_jobs[si])
            si += 1
        elif (
            word_jobs[wi]["first_source_index"]
            <= sentence_jobs[si]["first_source_index"]
        ):
            jobs.append(word_jobs[wi])
            wi += 1
        else:
            jobs.append(sentence_jobs[si])
            si += 1
    return jobs


def jobs_from_entries(
    entries: list[dict[str, Any]],
    allow_partial: bool,
) -> tuple[
    list[dict[str, Any]],
    list[tuple[int, dict[str, Any]]],
    list[tuple[int, dict[str, Any]]],
    int,
    int,
]:
    words = [(i, e) for i, e in enumerate(entries) if entry_mode(e) == "word"]
    sentences = [
        (i, e) for i, e in enumerate(entries) if entry_mode(e) == "sentence"
    ]

    word_jobs, word_remainder = mode_jobs(words, "word", 7, allow_partial)
    sentence_jobs, sentence_remainder = mode_jobs(
        sentences, "sentence", 4, allow_partial
    )
    jobs = merge_jobs(word_jobs, sentence_jobs)
    return jobs, word_remainder, sentence_remainder, len(words), len(sentences)


def jobs_from_videos(
    data: dict[str, Any],
    include_unverified: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    videos = data.get("videos") or []
    if not videos:
        raise SystemExit("Input has no videos.")

    jobs: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, video in enumerate(videos):
        mode = str(video.get("mode") or "").strip().lower()
        if mode not in {"word", "sentence"}:
            raise SystemExit(f"Video {video.get('id')!r} has no valid mode.")
        expected = 7 if mode == "word" else 4
        pairs = video.get("pairs") or []
        if len(pairs) != expected:
            raise SystemExit(
                f"Video {video.get('id')!r} has {len(pairs)} pairs; "
                f"{mode} needs {expected}."
            )

        if not include_unverified and not all(
            pair_is_verified(pair) for pair in pairs
        ):
            skipped.append(
                {
                    "source_id": video.get("id", f"video_{index + 1:02d}"),
                    "mode": mode,
                    "pair_count": len(pairs),
                    "entry_ids": [
                        pair.get("entry_id", "") for pair in pairs
                    ],
                    "statuses": sorted(
                        {
                            str(pair.get("verification") or "missing")
                            for pair in pairs
                        }
                    ),
                    "reason": "unverified",
                }
            )
            continue

        clean_pairs = []
        for pair in pairs:
            english = str(pair.get("english") or "").strip()
            kinyarwanda = str(pair.get("kinyarwanda") or "").strip()
            if not english or not kinyarwanda:
                raise SystemExit(
                    f"Video {video.get('id')!r} has a pair without text."
                )
            clean_pairs.append(
                {
                    "english": english,
                    "kinyarwanda": kinyarwanda,
                    "entry_id": pair.get("entry_id", ""),
                    "group_id": pair.get("group_id", ""),
                    "group_title": pair.get("group_title", ""),
                    "grammar": pair.get("grammar", ""),
                    "verification": pair.get("verification", ""),
                    "verification_tier": pair.get("verification_tier", ""),
                    "corpus_hits": pair.get("corpus_hits", 0),
                    "sources": pair.get("sources", []),
                    "notes": pair.get("notes", ""),
                }
            )

        jobs.append(
            {
                "source_id": video.get("id", f"video_{index + 1:02d}"),
                "mode": mode,
                "pair_count": len(clean_pairs),
                "line_count": int(
                    video.get(
                        "line_count",
                        len(clean_pairs) * 2 if mode == "sentence" else len(clean_pairs),
                    )
                ),
                "source_indices": [],
                "source_entry_ids": [
                    pair["entry_id"] for pair in clean_pairs if pair["entry_id"]
                ],
                "first_source_index": index,
                "pairs": clean_pairs,
            }
        )

    return jobs, skipped


def split_verified_entries(
    entries: list[dict[str, Any]],
    include_unverified: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if include_unverified:
        return entries, []
    eligible = [entry for entry in entries if entry_is_verified(entry)]
    excluded = [entry for entry in entries if not entry_is_verified(entry)]
    return eligible, excluded


def excluded_entry_summary(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry_id": entry.get("id", ""),
        "english": entry.get("english", ""),
        "kinyarwanda": entry.get("kinyarwanda", ""),
        "type": entry_mode(entry),
        "verification": entry.get("verification", ""),
    }


def entry_source_jobs(
    entries: list[dict[str, Any]],
    allow_partial: bool,
    include_unverified: bool,
) -> tuple[
    list[dict[str, Any]],
    list[tuple[int, dict[str, Any]]],
    list[tuple[int, dict[str, Any]]],
    int,
    int,
    list[dict[str, Any]],
]:
    eligible, excluded = split_verified_entries(entries, include_unverified)
    (
        jobs,
        word_remainder,
        sentence_remainder,
        eligible_words,
        eligible_sentences,
    ) = jobs_from_entries(eligible, allow_partial)
    return (
        jobs,
        word_remainder,
        sentence_remainder,
        eligible_words,
        eligible_sentences,
        excluded,
    )


def assign_content_numbers(
    jobs: list[dict[str, Any]], id_prefix: str = "content_"
) -> None:
    cursor = 1
    for number, job in enumerate(jobs, start=1):
        job["content_number"] = number
        job["id"] = f"{id_prefix}{number:04d}"
        job["entry_start"] = cursor
        job["entry_end"] = cursor + job["pair_count"] - 1
        cursor += job["pair_count"]


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def validate_unique_jobs(
    jobs: list[dict[str, Any]],
    allow_shared_entries: bool,
) -> tuple[int, int]:
    """Reject duplicate entries and duplicate videos.

    Strict mode (the default) also rejects the same word/sentence appearing in
    more than one video. ``--allow-shared-entries`` relaxes that to unique
    video signatures only.
    """
    errors: list[str] = []
    seen_entries: dict[tuple[str, str], str] = {}
    seen_entry_ids: dict[str, str] = {}
    seen_videos: dict[tuple[tuple[str, str], ...], str] = {}
    total_pairs = 0

    for job in jobs:
        label = str(job.get("source_id") or job.get("id") or job["mode"])
        pairs = job.get("pairs") or []
        total_pairs += len(pairs)
        signature = tuple(
            sorted(
                (
                    normalize_text(pair.get("english")),
                    normalize_text(pair.get("kinyarwanda")),
                )
                for pair in pairs
            )
        )
        if signature in seen_videos:
            errors.append(
                f"{label}: duplicate video content "
                f"(same pairs as {seen_videos[signature]})"
            )
        else:
            seen_videos[signature] = label

        for pair in pairs:
            key = (job["mode"], normalize_text(pair.get("english")))
            owner = seen_entries.get(key)
            if owner is not None:
                if not allow_shared_entries:
                    errors.append(
                        f"{label}: duplicate {job['mode']} entry "
                        f"{pair.get('english')!r} (also in {owner})"
                    )
            else:
                seen_entries[key] = label

            entry_id = str(pair.get("entry_id") or "").strip()
            if entry_id:
                id_owner = seen_entry_ids.get(entry_id)
                if id_owner is not None and not allow_shared_entries:
                    errors.append(
                        f"{label}: duplicate entry_id {entry_id!r} "
                        f"(also in {id_owner})"
                    )
                else:
                    seen_entry_ids[entry_id] = label

    if errors:
        shown = errors[:25]
        more = len(errors) - len(shown)
        detail = "\n".join(f"  - {error}" for error in shown)
        if more > 0:
            detail += f"\n  ... and {more} more"
        raise SystemExit(
            "Duplicate content detected. Remove duplicates or pass "
            "--allow-shared-entries for unique-video-only mode:\n"
            f"{detail}"
        )

    return len(seen_videos), len(seen_entries)


def chunk_jobs(
    jobs: list[dict[str, Any]],
    chunk_size: int,
) -> list[list[dict[str, Any]]]:
    """Split jobs into chunks using a soft target.

    A chunk is closed only after it has reached the target, so it may go
    slightly over (by at most one video's worth of pairs). A video is never
    split across chunk files.
    """
    if chunk_size < 1:
        raise SystemExit("--chunk-size must be at least 1.")
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_entries = 0

    for job in jobs:
        if current and current_entries >= chunk_size:
            chunks.append(current)
            current = []
            current_entries = 0
        current.append(job)
        current_entries += job["pair_count"]

    if current:
        chunks.append(current)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split vocabulary videos into chunk files and a rotation manifest."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=300,
        help=(
            "Soft target entries per chunk. A chunk may go over the target so "
            "a 7-word or 4-pair video is never split."
        ),
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Include a final short video when entries do not divide evenly.",
    )
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help=(
            "Include entries/videos that are not marked verification=verified. "
            "Use only for review or layout previews, never for publishing."
        ),
    )
    parser.add_argument(
        "--allow-shared-entries",
        action="store_true",
        help=(
            "Allow the same word/sentence to appear in multiple videos; "
            "video signatures must still be unique. Default is no duplicates "
            "at all."
        ),
    )
    parser.add_argument(
        "--trust-dictionary",
        action="store_true",
        help=(
            "Promote pairs marked verification=dictionary to verified for this "
            "build. Used by the 1,098-video database (curriculum/dictionary "
            "sourced); review builds should omit it."
        ),
    )
    parser.add_argument(
        "--trust-corpus",
        action="store_true",
        help=(
            "Promote pairs marked verification=corpus to verified for this "
            "build. Used by the separate sentence track; the original "
            "verification_tier stays 'corpus'."
        ),
    )
    parser.add_argument(
        "--id-prefix",
        default="content_",
        help=(
            "Prefix for generated job ids (default: content_). Use sentence_ "
            "for a separate sentence rotation so outputs and state cannot "
            "collide with the word track."
        ),
    )
    parser.add_argument(
        "--chunk-prefix",
        default="vocabulary_chunk_",
        help=(
            "Filename prefix for chunk files (default: vocabulary_chunk_). "
            "Use sentence_chunk_ for the sentence track."
        ),
    )
    parser.add_argument(
        "--keep-state",
        action="store_true",
        help="Keep the existing rotation state if total_jobs still matches.",
    )
    parser.add_argument(
        "--start-content",
        default="",
        help=(
            "Start the new state at this content id instead of content_0001. "
            "Useful when migrating a rotation without replaying finished videos."
        ),
    )
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.id_prefix):
        raise SystemExit(
            f"--id-prefix must be lowercase letters/digits/underscore: "
            f"{args.id_prefix!r}"
        )
    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.chunk_prefix):
        raise SystemExit(
            f"--chunk-prefix must be lowercase letters/digits/underscore: "
            f"{args.chunk_prefix!r}"
        )

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")
    data = read_json(args.input)
    if args.trust_dictionary:
        promoted = promote_dictionary_verification(data)
        print(f"trusted dictionary pairs promoted: {promoted}")
    if args.trust_corpus:
        promoted = promote_corpus_verification(data)
        print(f"trusted corpus pairs promoted: {promoted}")

    source_kind: str
    word_remainder: list[tuple[int, dict[str, Any]]] = []
    sentence_remainder: list[tuple[int, dict[str, Any]]] = []
    input_entries = 0
    input_word_entries = 0
    input_sentence_entries = 0
    eligible_word_entries = 0
    eligible_sentence_entries = 0
    excluded_unverified_entries = 0
    excluded_unverified_word_entries = 0
    excluded_unverified_sentence_entries = 0
    skipped_videos: list[dict[str, Any]] = []
    excluded_remainder: list[dict[str, Any]] = []
    excluded_entries: list[dict[str, Any]] = []
    remainder_words: list[dict[str, Any]] = []
    remainder_sentences: list[dict[str, Any]] = []

    if isinstance(data, list):
        source_kind = "entries"
        entries_all = data
        input_entries = len(entries_all)
        input_word_entries = sum(
            1 for entry in entries_all if entry_mode(entry) == "word"
        )
        input_sentence_entries = sum(
            1 for entry in entries_all if entry_mode(entry) == "sentence"
        )
        (
            jobs,
            word_remainder,
            sentence_remainder,
            eligible_word_entries,
            eligible_sentence_entries,
            excluded_entries,
        ) = entry_source_jobs(
            entries_all, args.allow_partial, args.include_unverified
        )
    elif isinstance(data, dict) and "videos" in data:
        source_kind = "videos"
        jobs, skipped_videos = jobs_from_videos(data, args.include_unverified)
        meta = data.get("meta", {}) or {}
        input_entries = int(meta.get("total_entries", 0))
        input_word_entries = int(
            meta.get(
                "word_entries",
                meta.get(
                    "word_count",
                    sum(
                        1
                        for v in data.get("videos", [])
                        if v.get("mode") == "word"
                    )
                    * 7,
                ),
            )
        )
        input_sentence_entries = int(
            meta.get(
                "sentence_entries",
                meta.get(
                    "sentence_count",
                    sum(
                        1
                        for v in data.get("videos", [])
                        if v.get("mode") == "sentence"
                    )
                    * 4,
                ),
            )
        )
        if not input_entries:
            input_entries = input_word_entries + input_sentence_entries

        raw_remainder = data.get("remainder", {}) or {}
        for item in raw_remainder.get("words", []) or []:
            summary = {
                "english": item.get("english", ""),
                "kinyarwanda": item.get("kinyarwanda", ""),
                "entry_id": item.get("entry_id") or item.get("id", ""),
                "type": "word",
                "verification": item.get("verification", ""),
            }
            if args.include_unverified or entry_is_verified(item):
                remainder_words.append(summary)
            else:
                excluded_remainder.append(summary)
        for item in raw_remainder.get("sentences", []) or []:
            summary = {
                "english": item.get("english", ""),
                "kinyarwanda": item.get("kinyarwanda", ""),
                "entry_id": item.get("entry_id") or item.get("id", ""),
                "type": "sentence",
                "verification": item.get("verification", ""),
            }
            if args.include_unverified or entry_is_verified(item):
                remainder_sentences.append(summary)
            else:
                excluded_remainder.append(summary)

        video_word_entries = sum(
            job["pair_count"] for job in jobs if job["mode"] == "word"
        )
        video_sentence_entries = sum(
            job["pair_count"] for job in jobs if job["mode"] == "sentence"
        )
        eligible_word_entries = video_word_entries + len(remainder_words)
        eligible_sentence_entries = video_sentence_entries + len(remainder_sentences)
        excluded_unverified_entries = sum(
            int(video.get("pair_count", 0)) for video in skipped_videos
        ) + len(excluded_remainder)
        excluded_unverified_word_entries = sum(
            int(video.get("pair_count", 0))
            for video in skipped_videos
            if video.get("mode") == "word"
        ) + sum(1 for item in excluded_remainder if item["type"] == "word")
        excluded_unverified_sentence_entries = sum(
            int(video.get("pair_count", 0))
            for video in skipped_videos
            if video.get("mode") == "sentence"
        ) + sum(1 for item in excluded_remainder if item["type"] == "sentence")
    elif isinstance(data, dict) and "entries" in data:
        source_kind = "entries"
        entries_all = data["entries"]
        input_entries = len(entries_all)
        input_word_entries = sum(
            1 for entry in entries_all if entry_mode(entry) == "word"
        )
        input_sentence_entries = sum(
            1 for entry in entries_all if entry_mode(entry) == "sentence"
        )
        (
            jobs,
            word_remainder,
            sentence_remainder,
            eligible_word_entries,
            eligible_sentence_entries,
            excluded_entries,
        ) = entry_source_jobs(
            entries_all, args.allow_partial, args.include_unverified
        )
    else:
        raise SystemExit(
            "Input must be a list, an object with 'entries', or an object with 'videos'."
        )

    if source_kind == "entries":
        excluded_unverified_entries = len(excluded_entries)
        excluded_unverified_word_entries = sum(
            1 for entry in excluded_entries if entry_mode(entry) == "word"
        )
        excluded_unverified_sentence_entries = sum(
            1 for entry in excluded_entries if entry_mode(entry) == "sentence"
        )

    if not jobs:
        hint = (
            ""
            if args.include_unverified
            else " No verified complete videos were found; pass "
            "--include-unverified only for a review build."
        )
        raise SystemExit(f"No complete video jobs were produced.{hint}")

    unique_videos, unique_entries = validate_unique_jobs(
        jobs, args.allow_shared_entries
    )
    assign_content_numbers(jobs, args.id_prefix)
    total_video_entries = sum(job["pair_count"] for job in jobs)
    total_jobs = len(jobs)
    chunks = chunk_jobs(jobs, args.chunk_size)

    # Write the new chunks first; stale chunk files are removed only after a
    # complete rebuild succeeds, so a failed run cannot destroy a working set.
    args.out_dir.mkdir(parents=True, exist_ok=True)
    written_chunk_names: set[str] = set()

    chunk_meta: list[dict[str, Any]] = []
    manifest_jobs: list[dict[str, Any]] = []

    for chunk_id, chunk in enumerate(chunks, start=1):
        filename = f"{args.chunk_prefix}{chunk_id:02d}.json"
        payload = {
            "chunk_id": chunk_id,
            "entry_start": chunk[0]["entry_start"],
            "entry_end": chunk[-1]["entry_end"],
            "entry_count": sum(job["pair_count"] for job in chunk),
            "content_start": chunk[0]["content_number"],
            "content_end": chunk[-1]["content_number"],
            "jobs": chunk,
        }
        write_json(args.out_dir / filename, payload)
        written_chunk_names.add(filename)

        chunk_meta.append(
            {
                "chunk_id": chunk_id,
                "file": rel_to_manifest(
                    args.out_dir / filename, args.manifest
                ),
                "entry_start": payload["entry_start"],
                "entry_end": payload["entry_end"],
                "entry_count": payload["entry_count"],
                "content_start": payload["content_start"],
                "content_end": payload["content_end"],
            }
        )

        for job_index, job in enumerate(chunk):
            manifest_jobs.append(
                {
                    "id": job["id"],
                    "content_number": job["content_number"],
                    "source_id": job.get("source_id", ""),
                    "chunk_id": chunk_id,
                    "job_index": job_index,
                    "mode": job["mode"],
                    "pair_count": job["pair_count"],
                    "line_count": job.get("line_count", 0),
                    "entry_start": job["entry_start"],
                    "entry_end": job["entry_end"],
                    "source_entry_ids": job.get("source_entry_ids", []),
                }
            )

    if source_kind == "entries":
        remainder_words = [
            {
                "english": entry.get("english", ""),
                "kinyarwanda": entry.get("kinyarwanda", ""),
                "entry_id": entry.get("id", ""),
                "type": "word",
                "verification": entry.get("verification", ""),
            }
            for _, entry in word_remainder
        ]
        remainder_sentences = [
            {
                "english": entry.get("english", ""),
                "kinyarwanda": entry.get("kinyarwanda", ""),
                "entry_id": entry.get("id", ""),
                "type": "sentence",
                "verification": entry.get("verification", ""),
            }
            for _, entry in sentence_remainder
        ]
    remainder_count = len(remainder_words) + len(remainder_sentences)

    video_word_entries = sum(
        job["pair_count"] for job in jobs if job["mode"] == "word"
    )
    video_sentence_entries = sum(
        job["pair_count"] for job in jobs if job["mode"] == "sentence"
    )

    manifest = {
        "meta": {
            "generated_at": now_iso(),
            "source": rel_to_root(args.input),
            "source_kind": source_kind,
            "chunk_size_target": args.chunk_size,
            "chunk_count": len(chunk_meta),
            "total_jobs": total_jobs,
            "video_entries": total_video_entries,
            "input_entries": input_entries,
            "word_entries": input_word_entries,
            "sentence_entries": input_sentence_entries,
            "video_word_entries": video_word_entries,
            "video_sentence_entries": video_sentence_entries,
            "eligible_word_entries": eligible_word_entries,
            "eligible_sentence_entries": eligible_sentence_entries,
            "remainder_entries": remainder_count,
            "excluded_unverified_entries": excluded_unverified_entries,
            "excluded_unverified_word_entries": excluded_unverified_word_entries,
            "excluded_unverified_sentence_entries": excluded_unverified_sentence_entries,
            "verified_only": not args.include_unverified,
            "trusted_dictionary": bool(args.trust_dictionary),
            "trusted_corpus": bool(args.trust_corpus),
            "id_prefix": args.id_prefix,
            "chunk_prefix": args.chunk_prefix,
            "unique_videos": unique_videos,
            "unique_entries": unique_entries,
            "strict_unique_entries": not args.allow_shared_entries,
            "skipped_videos": skipped_videos,
            "excluded_remainder": excluded_remainder,
            "excluded_entries": [
                excluded_entry_summary(entry) for entry in excluded_entries
            ],
            "allow_partial": bool(args.allow_partial),
            "word_video_size": 7,
            "sentence_video_size": 4,
        },
        "chunks": chunk_meta,
        "jobs": manifest_jobs,
        "remainder": {
            "words": remainder_words,
            "sentences": remainder_sentences,
        },
    }
    write_json(args.manifest, manifest)
    for old in args.out_dir.glob(f"{args.chunk_prefix}*.json"):
        if old.name not in written_chunk_names:
            old.unlink()

    if args.keep_state and args.state.exists():
        state = read_json(args.state)
        if int(state.get("total_jobs", -1)) != total_jobs:
            raise SystemExit(
                "Existing state has a different total_jobs; remove it or rerun "
                "without --keep-state."
            )
        state.setdefault("input_entries", input_entries)
        state.setdefault("remainder_entries", remainder_count)
        state.setdefault(
            "excluded_unverified_entries", excluded_unverified_entries
        )
        write_json(args.state, state)
    else:
        start_index = 0
        if args.start_content:
            start_index = next(
                (
                    index
                    for index, job in enumerate(manifest_jobs)
                    if job["id"] == args.start_content
                ),
                -1,
            )
            if start_index < 0:
                raise SystemExit(
                    f"--start-content {args.start_content!r} is not in the new "
                    "manifest."
                )
        state = {
            "cycle": 1,
            "next_job_index": start_index,
            "jobs_done_in_cycle": start_index,
            "total_jobs": total_jobs,
            "total_entries": total_video_entries,
            "input_entries": input_entries,
            "remainder_entries": remainder_count,
            "excluded_unverified_entries": excluded_unverified_entries,
            "last_content_id": (
                manifest_jobs[start_index - 1]["id"] if start_index else None
            ),
            "next_content_id": manifest_jobs[start_index]["id"],
            "updated_at": now_iso(),
        }
        write_json(args.state, state)

    print(
        f"source: {rel_to_root(args.input)} ({source_kind})"
    )
    scope = "all" if args.include_unverified else "verified"
    print(
        f"entries: {input_entries} input, {total_video_entries} in {scope} "
        f"video jobs, {remainder_count} remainder"
    )
    if excluded_unverified_entries:
        print(
            f"excluded: {excluded_unverified_entries} entries held out of "
            f"rotation ({excluded_unverified_word_entries} words + "
            f"{excluded_unverified_sentence_entries} sentences)"
        )
    print(
        f"videos: {total_jobs} jobs "
        f"({sum(1 for j in manifest_jobs if j['mode'] == 'word')} word, "
        f"{sum(1 for j in manifest_jobs if j['mode'] == 'sentence')} sentence)"
    )
    print(
        f"unique: {unique_videos} video signatures, {unique_entries} entries "
        f"({'strict' if not args.allow_shared_entries else 'shared entries allowed'})"
    )
    print(
        f"chunks: {len(chunk_meta)} files (target {args.chunk_size} entries each)"
    )
    for chunk in chunk_meta:
        print(
            f"  {chunk['file']}: entries {chunk['entry_start']}-"
            f"{chunk['entry_end']}, contents {chunk['content_start']}-"
            f"{chunk['content_end']}"
        )
    if remainder_count:
        print(
            f"remainder: {len(remainder_words)} words + "
            f"{len(remainder_sentences)} sentences not in a full video"
        )
    print(f"manifest: {rel_to_root(args.manifest)}")
    print(
        f"state: {rel_to_root(args.state)} "
        f"(next {state['next_content_id']}, cycle {state['cycle']})"
    )


if __name__ == "__main__":
    main()
