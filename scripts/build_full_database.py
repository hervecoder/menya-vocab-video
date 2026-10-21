#!/usr/bin/env python3
"""Build the 1,098-video rotation database from cached internet sources.

The database keeps the 10 already-published, Glosbe-verified word videos and
adds 1,088 generated word videos. Generated videos draw from a common-word pool
built from:

* an English frequency list (internet, cached in ``data/sources``)
* the Menya Icyongereza English -> Kinyarwanda dictionary (cached)
* the app curriculum (high-confidence seed)

Uniqueness rules:

* every video has exactly 7 pairs
* no two videos have the same set of pairs
* no word repeats inside a video
* consecutive videos share no words
* words may repeat across non-adjacent videos, always in different combinations

The output is ``data/vocabulary_all_videos.json``, which is then passed to
``scripts/build_chunks.py``.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCES = DATA / "sources"

DEFAULT_DICTIONARY = SOURCES / "menya_dictionary.json"
DEFAULT_FREQUENCY = SOURCES / "en_frequency_50k.txt"
DEFAULT_CURRICULUM = SOURCES / "curriculum_words.json"
DEFAULT_CORPUS = SOURCES / "en_rw_corpus.tsv"
DEFAULT_PILOT = DATA / "vocabulary_pilot_videos.json"
DEFAULT_OUTPUT = DATA / "vocabulary_all_videos.json"
DEFAULT_REVIEW = DATA / "vocabulary_all_review.md"

WORD_SIZE = 7
TOTAL_VIDEOS = 1098
PILOT_VIDEOS = 10
GENERATED_VIDEOS = TOTAL_VIDEOS - PILOT_VIDEOS
POOL_SIZE = 1500
SEED = 20261021

FREQUENCY_URL = (
    "https://raw.githubusercontent.com/hermitdave/FrequencyWords/"
    "master/content/2018/en/en_50k.txt"
)

# Pure grammar / conversational glue. Curriculum words are kept even if they
# appear here because the app already teaches them.
STOPWORDS = set(
    """
    a an the and or but if of to in on at by for with from as is are was were
    be been being this that these those it its he she they them his her their
    we you i me my your our us not no yes do does did done have has had can
    could will would shall should may might must who whom whose what which
    when where why how than then there here such very too also just only all
    any some each every both few many much more most other another same own so
    because while during before after above below over under again once
    """.split()
)

# A few dictionary headwords whose first gloss is a different sense.  The
# replacement is either another gloss from the same dictionary or a form that
# is attested with the English word in the aligned corpus.
TRANSLATION_OVERRIDES = {
    "after": "nyuma",
    "alien": "umunyamahanga",
    "around": "hafi",
    "bar": "akabari",
    "circumstances": "ibihe",
    "claim": "ikirego",
    "data": "ibyakusanyijwe",
    "down": "hasi",
    "dry": "kuma",
    "effect": "ingaruka",
    "experiment": "igerageza",
    "good": "nziza",
    "great": "komeye",
    "high": "hejuru",
    "home": "urugo",
    "last": "iheruka",
    "plant": "igihingwa",
    "really": "rwose",
    "specific": "byihariye",
    "stop": "guhagarika",
    "time": "igihe",
}

# Words whose dictionary entries are only wrong senses and have no usable
# alternative in the same source.  Leaving them out lets the next common word
# fill the slot.
DROP_WORDS = {
    "attention",
    "bay",
    "estate",
    "ever",
    "exact",
    "freak",
    "gear",
    "guilty",
    "rose",
    "sure",
}

BLOCKLIST = set(
    """
    fuck fucking fucked shit shitty bitch asshole bastard damn hell sex sexual
    penis vagina nigga nigger cunt dick pussy whore slut rape raped naked
    porn suicide kill killed murder murdered ass asses
    """.split()
)

MIXED_LANGUAGE_TOKENS = set(
    """
    the and of to a an is are was were for with from art noun verb adj adv
    prep pron conj interj plural singular literally
    """.split()
)

COMPARATIVE_FORMS = {
    "greater": "great",
    "greatest": "great",
    "larger": "large",
    "largest": "large",
    "smaller": "small",
    "smallest": "small",
    "bigger": "big",
    "biggest": "big",
    "higher": "high",
    "highest": "high",
    "lower": "low",
    "lowest": "low",
    "longer": "long",
    "longest": "long",
    "shorter": "short",
    "shortest": "short",
    "stronger": "strong",
    "strongest": "strong",
    "weaker": "weak",
    "weakest": "weak",
    "easier": "easy",
    "easiest": "easy",
    "harder": "hard",
    "hardest": "hard",
    "faster": "fast",
    "fastest": "fast",
    "slower": "slow",
    "slowest": "slow",
    "richer": "rich",
    "richest": "rich",
    "poorer": "poor",
    "poorest": "poor",
    "earlier": "early",
    "earliest": "early",
    "later": "late",
    "latest": "late",
    "older": "old",
    "oldest": "old",
    "younger": "young",
    "youngest": "young",
    "better": "good",
    "best": "good",
    "worse": "bad",
    "worst": "bad",
    "farther": "far",
    "farthest": "far",
    "further": "far",
    "furthest": "far",
}

# Common -ing nouns that are headwords in their own right, not just gerunds.
ING_NOUNS = set(
    """
    building meeting wedding morning evening painting clothing feeling meaning
    opening saying beginning ending training learning teaching shopping parking
    housing farming fishing cooking banking marketing engineering writing
    reading hearing sightseeing misunderstanding surroundings belongings
    earnings savings findings
    """.split()
)

# Common -ed adjectives that should stay even when the base verb exists.
ED_ADJECTIVES = set(
    """
    married tired bored excited interested worried surprised frightened confused
    dressed prepared advanced aged beloved wicked talented skilled detailed
    limited complicated crowded polluted exhausted satisfied disappointed
    embarrassed depressed stressed experienced qualified retired used located
    named armed developed related
    """.split()
)

IRREGULAR = {
    "gone": "go",
    "went": "go",
    "seen": "see",
    "saw": "see",
    "done": "do",
    "did": "do",
    "made": "make",
    "took": "take",
    "taken": "take",
    "gave": "give",
    "given": "give",
    "came": "come",
    "got": "get",
    "gotten": "get",
    "knew": "know",
    "known": "know",
    "thought": "think",
    "told": "tell",
    "said": "say",
    "found": "find",
    "left": "leave",
    "felt": "feel",
    "kept": "keep",
    "held": "hold",
    "brought": "bring",
    "began": "begin",
    "begun": "begin",
    "wrote": "write",
    "written": "write",
    "spoke": "speak",
    "spoken": "speak",
    "ran": "run",
    "paid": "pay",
    "met": "meet",
    "sent": "send",
    "built": "build",
    "understood": "understand",
    "bought": "buy",
    "caught": "catch",
    "taught": "teach",
    "threw": "throw",
    "thrown": "throw",
    "grew": "grow",
    "grown": "grow",
    "drew": "draw",
    "drawn": "draw",
    "flew": "fly",
    "flown": "fly",
}


def read_json(path: Path) -> Any:
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def load_frequency(path: Path) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split()
        if len(parts) == 2:
            ranks[parts[0].casefold()] = index
    if not ranks:
        raise SystemExit(f"No frequency words found in {path}")
    return ranks


def load_dictionary(path: Path) -> dict[str, list[str]]:
    payload = read_json(path)
    pairs = payload.get("pairs") if isinstance(payload, dict) else payload
    if not pairs:
        raise SystemExit(f"No dictionary pairs found in {path}")
    by_word: dict[str, list[str]] = defaultdict(list)
    for row in pairs:
        english = str(row.get("english", "")).strip()
        kinyarwanda = str(row.get("kinyarwanda", "")).strip()
        if english and kinyarwanda:
            by_word[english].append(kinyarwanda)
    return by_word


def load_curriculum(path: Path) -> dict[str, str]:
    payload = read_json(path)
    pairs = payload.get("pairs") if isinstance(payload, dict) else payload
    result: dict[str, str] = {}
    for row in pairs or []:
        english = str(row.get("english", "")).strip()
        kinyarwanda = str(row.get("kinyarwanda", "")).strip()
        if english and kinyarwanda:
            result.setdefault(english.casefold(), kinyarwanda)
    return result


def load_corpus(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    rows: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            kinyarwanda = " ".join(parts[0].split())
            english = " ".join(parts[1].split())
            if kinyarwanda and english:
                rows.append((english, kinyarwanda))
    return rows


def normalize_rw(text: str) -> str:
    text = text.casefold()
    text = text.replace("’", "'").replace("‘", "'")
    return " ".join(text.split())


def rw_variants(segment: str) -> list[str]:
    """Return the full gloss plus a likely Kinyarwanda stem.

    The corpus is inflected, so an infinitive such as ``gukeneye`` will not
    match ``ukeneye`` literally.  Stripping the common infinitive prefix gives
    the stem the corpus actually uses.
    """
    normalized = normalize_rw(segment)
    variants = [normalized]
    if normalized.startswith(("gu", "ku", "kw")) and len(normalized) > 4:
        variants.append(normalized[2:])
    if normalized.startswith("kwi") and len(normalized) > 5:
        variants.append(normalized[3:])
    return list(dict.fromkeys(variants))


def segment_matches(segment: str, rw_text: str) -> bool:
    for variant in rw_variants(segment):
        if len(variant) >= 4 and variant in rw_text:
            return True
    return False


def score_corpus(
    candidate_data: dict[str, dict[str, Any]],
    corpus_rows: list[tuple[str, str]],
) -> tuple[Counter, defaultdict]:
    """Count English-word/Kinyarwanda-gloss co-occurrences in the corpus."""
    candidate_words = set(candidate_data)
    english_counts: Counter = Counter()
    cooccur: defaultdict[str, Counter] = defaultdict(Counter)

    for english_text, kinyarwanda_text in corpus_rows:
        tokens = set(re.findall(r"[a-z]+", english_text.casefold()))
        present = tokens & candidate_words
        if not present:
            continue
        rw_text = normalize_rw(kinyarwanda_text)
        for word in present:
            english_counts[word] += 1
            for segment in candidate_data[word]["valid"]:
                if segment_matches(segment, rw_text):
                    cooccur[word][segment] += 1
    return english_counts, cooccur


def choose_best_translation(
    word: str,
    valid: list[str],
    curriculum_translation: str | None,
    english_counts: Counter,
    cooccur: defaultdict,
) -> tuple[str, int]:
    """Pick the first dictionary gloss, unless the corpus strongly supports
    a later gloss.  This keeps the dictionary's primary sense and only fixes
    clear sense errors."""
    curriculum_hits = (
        cooccur[word][curriculum_translation]
        if curriculum_translation
        else 0
    )
    if curriculum_translation and curriculum_hits >= 2:
        return curriculum_translation, curriculum_hits

    first = valid[0]
    first_hits = cooccur[word][first]
    best = first
    best_hits = first_hits
    best_index = 0
    for index, segment in enumerate(valid):
        hits = cooccur[word][segment]
        if (hits, -index) > (best_hits, -best_index):
            best = segment
            best_hits = hits
            best_index = index

    # Do not let one lucky sentence override the dictionary. Require at least
    # two corpus hits and a clear lead over the primary gloss.
    if best != first and best_hits >= 2 and best_hits >= first_hits + 2:
        return best, best_hits
    if curriculum_translation:
        return curriculum_translation, curriculum_hits
    return first, first_hits


def split_translation(raw: str) -> Iterable[str]:
    text = re.sub(r"\([^)]*\)", "", str(raw or ""))
    text = re.sub(r"\[[^\]]*\]", "", text)
    for part in re.split(r"[;/,|]", text):
        part = " ".join(part.split())
        # Drop a leading genitive/concord fragment from phrases such as
        # "cyo hagati" -> "hagati" and "cy'igihimbano" -> "igihimbano".
        part = re.sub(
            r"^(?:cyo|cya|bya|bwa|kwa)\s+",
            "",
            part,
            flags=re.IGNORECASE,
        )
        part = re.sub(
            r"^(?:cy'|by'|bw'|kw')",
            "",
            part,
            flags=re.IGNORECASE,
        )
        part = part.strip()
        if part:
            yield part


def translation_ok(segment: str, english: str, frequent_english: set[str]) -> bool:
    if not segment or segment.casefold() == english.casefold():
        return False
    if len(segment) > 55 or len(segment.split()) > 4:
        return False
    if re.search(r"[0-9\[\]{}()\"“”?!:;=]", segment):
        return False
    if segment.startswith("-") or segment in {"-", "—"}:
        return False
    if segment.isupper() or re.search(r"[A-Z]", segment):
        return False
    if re.search(r"\b(cyangwa|na)\b", segment, re.IGNORECASE):
        return False
    tokens = re.findall(r"[A-Za-zÀ-ÿ']+", segment.casefold())
    if not tokens:
        return False
    for token in tokens:
        if token in MIXED_LANGUAGE_TOKENS:
            return False
        # A one-off token that is also a common English word is usually a
        # scraper artifact (e.g. "art ubukorikori").
        if token in frequent_english and len(token) > 2:
            return False
    if all(len(token) <= 2 for token in tokens):
        return False
    return True


def lemma_candidates(word: str, dictionary: dict[str, list[str]]) -> set[str]:
    forms: set[str] = set()
    if word.endswith("ies") and len(word) > 4:
        forms.add(word[:-3] + "y")
    if word.endswith("ied") and len(word) > 4:
        forms.add(word[:-3] + "y")
    if word.endswith("ing") and len(word) > 5:
        base = word[:-3]
        forms.add(base)
        forms.add(base + "e")
        if len(base) > 2 and base[-1] == base[-2]:
            forms.add(base[:-1])
    if word.endswith("ed") and len(word) > 4:
        base = word[:-2]
        forms.add(base)
        forms.add(word[:-1])
        if len(base) > 2 and base[-1] == base[-2]:
            forms.add(base[:-1])
    if word.endswith("es") and len(word) > 4:
        forms.add(word[:-2])
    if word.endswith("s") and len(word) > 3 and not word.endswith("ss"):
        forms.add(word[:-1])
    return {form for form in forms if form in dictionary}


def is_inflected(
    word: str,
    dictionary: dict[str, list[str]],
    ranks: dict[str, int],
) -> bool:
    if word in IRREGULAR:
        base = IRREGULAR[word]
        if base in dictionary and ranks.get(base, 10**9) <= ranks.get(word, 10**9):
            return True

    if word in COMPARATIVE_FORMS:
        return True

    # Regular -ing forms are usually gerunds. Keep the common nouns in
    # ING_NOUNS, but drop forms such as "finding"/"invented" whose base verb is
    # already in the dictionary.
    if word.endswith("ing") and word not in ING_NOUNS and len(word) > 5:
        base = word[:-3]
        candidates = {base, base + "e"}
        if len(base) > 2 and base[-1] == base[-2]:
            candidates.add(base[:-1])
        if any(candidate in dictionary for candidate in candidates):
            return True

    if word.endswith("ed") and word not in ED_ADJECTIVES and len(word) > 4:
        base = word[:-2]
        candidates = {base, word[:-1]}
        if len(base) > 2 and base[-1] == base[-2]:
            candidates.add(base[:-1])
        if any(candidate in dictionary for candidate in candidates):
            return True

    for base in lemma_candidates(word, dictionary):
        if base == word:
            continue
        if ranks.get(base, 10**9) <= ranks.get(word, 10**9):
            return True
    return False


def choose_pool(
    dictionary: dict[str, list[str]],
    curriculum: dict[str, str],
    ranks: dict[str, int],
    pool_size: int,
    corpus_rows: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    # First pass: all valid translation segments per word.
    frequent_english = {word for word, rank in ranks.items() if rank <= 2000}
    candidate_data: dict[str, dict[str, Any]] = {}
    for original, translations in dictionary.items():
        english = original.casefold()
        if original != original.lower():
            continue
        if not re.fullmatch(r"[a-z][a-z-]*", english):
            continue
        if len(english) < 3 or len(english) > 24:
            continue
        if english in BLOCKLIST or english in DROP_WORDS:
            continue
        if english in STOPWORDS and english not in curriculum:
            continue
        if is_inflected(english, dictionary, ranks):
            continue

        raw_segments: list[str] = []
        for translation in translations:
            raw_segments.extend(split_translation(translation))
        valid: list[str] = []
        seen = set()
        for segment in raw_segments:
            key = segment.casefold()
            if key in seen:
                continue
            if translation_ok(segment, english, frequent_english):
                seen.add(key)
                valid.append(segment)
        if not valid:
            continue

        candidate_data[english] = {
            "valid": valid,
            "curriculum": english in curriculum,
        }

    english_counts, cooccur = score_corpus(candidate_data, corpus_rows)
    candidates: list[dict[str, Any]] = []
    for english, data in candidate_data.items():
        curriculum_translation = curriculum.get(english)
        if curriculum_translation and not translation_ok(
            curriculum_translation, english, frequent_english
        ):
            curriculum_translation = None
        chosen, hits = choose_best_translation(
            english,
            data["valid"],
            curriculum_translation,
            english_counts,
            cooccur,
        )
        override = TRANSLATION_OVERRIDES.get(english)
        if override and translation_ok(override, english, frequent_english):
            chosen = override
            hits = max(hits, cooccur[english][override])
        if not chosen:
            continue
        candidates.append(
            {
                "english": english,
                "kinyarwanda": chosen,
                "rank": ranks.get(english, 10**9),
                "curriculum": english in curriculum,
                "corpus_hits": hits,
            }
        )

    if len(candidates) < pool_size:
        raise SystemExit(
            f"Only {len(candidates)} valid candidate words; need {pool_size}. "
            "Lower --pool-size or loosen the filters."
        )

    # Keep every curriculum seed, then fill by frequency. Curriculum first
    # guarantees the app's own high-confidence words are represented.
    curriculum_words = [item for item in candidates if item["curriculum"]]
    other_words = [item for item in candidates if not item["curriculum"]]
    curriculum_words.sort(key=lambda item: (item["rank"], item["english"]))
    other_words.sort(key=lambda item: (item["rank"], item["english"]))

    pool = curriculum_words[:pool_size]
    remaining = pool_size - len(pool)
    if remaining > 0:
        pool.extend(other_words[:remaining])

    # Deduplicate by English while preserving order.
    unique: list[dict[str, Any]] = []
    seen_words = set()
    for item in pool:
        if item["english"] in seen_words:
            continue
        seen_words.add(item["english"])
        unique.append(item)

    if len(unique) < pool_size:
        for item in other_words:
            if item["english"] in seen_words:
                continue
            unique.append(item)
            seen_words.add(item["english"])
            if len(unique) >= pool_size:
                break

    if len(unique) < pool_size:
        raise SystemExit(
            f"Could only build a {len(unique)}-word pool; need {pool_size}."
        )
    return unique[:pool_size]


def pair_signature(pairs: Iterable[dict[str, Any]]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (
                str(pair["english"]).strip().casefold(),
                str(pair["kinyarwanda"]).strip().casefold(),
            )
            for pair in pairs
        )
    )


def load_pilot_videos(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path)
    videos = []
    for video in payload.get("videos") or []:
        if str(video.get("mode")) != "word":
            continue
        pairs = video.get("pairs") or []
        if len(pairs) != WORD_SIZE:
            continue
        if not all(
            str(pair.get("verification", "")).casefold() == "verified"
            for pair in pairs
        ):
            continue
        videos.append(video)
    videos.sort(key=lambda video: str(video.get("id", "")))
    if len(videos) < PILOT_VIDEOS:
        raise SystemExit(
            f"Expected {PILOT_VIDEOS} verified pilot word videos, found {len(videos)}."
        )
    return videos[:PILOT_VIDEOS]


def make_generated_video(
    number: int,
    words: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": f"full_word_{number:04d}",
        "mode": "word",
        "complete": True,
        "pair_count": WORD_SIZE,
        "line_count": WORD_SIZE * 2,
        "pairs": [
            {
                "position": index,
                "entry_id": f"full_{item['english']}",
                "english": item["english"],
                "kinyarwanda": item["kinyarwanda"],
                "group_id": "general-vocabulary",
                "group_title": "General Vocabulary",
                "grammar": "word",
                "verification": (
                    "verified" if item["curriculum"] else "dictionary"
                ),
                "verification_tier": (
                    "curriculum" if item["curriculum"] else "dictionary"
                ),
                "sources": (
                    ["curriculum.json"]
                    if item["curriculum"]
                    else [
                        FREQUENCY_URL,
                        "Menya Icyongereza App dictionary "
                        "(Iriza 2006 / Cox-Adamson-Teusink 1957)",
                    ]
                ),
                "corpus_hits": item.get("corpus_hits", 0),
                "notes": (
                    f"frequency rank {item['rank']}; "
                    f"corpus hits {item.get('corpus_hits', 0)}; "
                    "dictionary-selected common vocabulary"
                ),
            }
            for index, item in enumerate(words, 1)
        ],
    }


def build_schedule(
    pool: list[dict[str, Any]],
    count: int,
    seed: int,
    pilot_videos: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    order = pool[:]
    rng.shuffle(order)
    cursor = 0

    pilot_signatures = {pair_signature(video["pairs"]) for video in pilot_videos}
    first_pilot_words = {
        str(pair["english"]).casefold()
        for pair in pilot_videos[0]["pairs"]
    }
    previous_words = {
        str(pair["english"]).casefold()
        for pair in pilot_videos[-1]["pairs"]
    }

    seen_signatures = set(pilot_signatures)
    videos: list[dict[str, Any]] = []

    while len(videos) < count:
        chosen: list[dict[str, Any]] = []
        guard = 0
        while len(chosen) < WORD_SIZE:
            guard += 1
            if guard > len(pool) * 4:
                raise SystemExit(
                    "Could not build a 7-word video without repeats; "
                    "increase --pool-size."
                )
            if cursor >= len(order):
                rng.shuffle(order)
                cursor = 0
            item = order[cursor]
            cursor += 1
            word = item["english"]
            if word in previous_words:
                continue
            if any(existing["english"] == word for existing in chosen):
                continue
            chosen.append(item)

        signature = pair_signature(
            [
                {
                    "english": item["english"],
                    "kinyarwanda": item["kinyarwanda"],
                }
                for item in chosen
            ]
        )
        if signature in seen_signatures:
            continue

        videos.append(
            make_generated_video(len(videos) + 1, chosen)
        )
        seen_signatures.add(signature)
        previous_words = {item["english"] for item in chosen}

    # Make the wrap back to content_0001 clean too: the last generated video
    # should not share words with the first pilot video.
    if videos:
        last_words = {
            str(pair["english"]).casefold()
            for pair in videos[-1]["pairs"]
        }
        if last_words & first_pilot_words:
            current = {
                str(pair["english"]).casefold()
                for pair in videos[-1]["pairs"]
            }
            for position, pair in enumerate(videos[-1]["pairs"]):
                if str(pair["english"]).casefold() not in first_pilot_words:
                    continue
                replacement = next(
                    (
                        item
                        for item in pool
                        if item["english"] not in current
                        and item["english"] not in first_pilot_words
                    ),
                    None,
                )
                if replacement is None:
                    break
                current.discard(str(pair["english"]).casefold())
                pair.update(
                    {
                        "entry_id": f"full_{replacement['english']}",
                        "english": replacement["english"],
                        "kinyarwanda": replacement["kinyarwanda"],
                        "verification": (
                            "verified"
                            if replacement["curriculum"]
                            else "dictionary"
                        ),
                        "verification_tier": (
                            "curriculum"
                            if replacement["curriculum"]
                            else "dictionary"
                        ),
                        "sources": (
                            ["curriculum.json"]
                            if replacement["curriculum"]
                            else [
                                FREQUENCY_URL,
                                "Menya Icyongereza App dictionary "
                                "(Iriza 2006 / Cox-Adamson-Teusink 1957)",
                            ]
                        ),
                        "corpus_hits": replacement.get("corpus_hits", 0),
                        "notes": (
                            f"frequency rank {replacement['rank']}; "
                            f"corpus hits {replacement.get('corpus_hits', 0)}; "
                            "dictionary-selected common vocabulary"
                        ),
                    }
                )
                current.add(replacement["english"])
                break

    return videos


def validate_database(
    pilot_videos: list[dict[str, Any]],
    generated_videos: list[dict[str, Any]],
    pool: list[dict[str, Any]],
) -> dict[str, Any]:
    videos = pilot_videos + generated_videos
    if len(videos) != TOTAL_VIDEOS:
        raise SystemExit(
            f"Expected {TOTAL_VIDEOS} videos, built {len(videos)}."
        )

    signatures = set()
    for video in videos:
        pairs = video.get("pairs") or []
        if len(pairs) != WORD_SIZE:
            raise SystemExit(f"{video.get('id')} does not have 7 pairs.")
        english = [str(pair["english"]).casefold() for pair in pairs]
        if len(set(english)) != len(english):
            raise SystemExit(f"{video.get('id')} repeats a word inside the video.")
        signature = pair_signature(pairs)
        if signature in signatures:
            raise SystemExit(f"Duplicate video signature: {video.get('id')}")
        signatures.add(signature)

    # Consecutive videos must not share words. The pilot videos are fixed;
    # only check the boundaries involving generated videos.
    for index in range(1, len(videos)):
        left = videos[index - 1]
        right = videos[index]
        if left in pilot_videos and right in pilot_videos:
            continue
        left_words = {str(pair["english"]).casefold() for pair in left["pairs"]}
        right_words = {str(pair["english"]).casefold() for pair in right["pairs"]}
        if left_words & right_words:
            raise SystemExit(
                f"Consecutive videos share words: {left.get('id')} / "
                f"{right.get('id')}"
            )

    pool_words = {item["english"] for item in pool}
    occurrences = Counter()
    for video in generated_videos:
        for pair in video["pairs"]:
            word = str(pair["english"]).casefold()
            if word not in pool_words:
                raise SystemExit(f"Generated word not in pool: {word}")
            occurrences[word] += 1

    return {
        "total_videos": len(videos),
        "pilot_videos": len(pilot_videos),
        "generated_videos": len(generated_videos),
        "unique_video_signatures": len(signatures),
        "pool_size": len(pool),
        "word_slots": len(generated_videos) * WORD_SIZE,
        "min_word_occurrences": min(occurrences.values()) if occurrences else 0,
        "max_word_occurrences": max(occurrences.values()) if occurrences else 0,
        "words_used": len(occurrences),
    }


def write_review(
    path: Path,
    pilot_videos: list[dict[str, Any]],
    generated_videos: list[dict[str, Any]],
    pool: list[dict[str, Any]],
    stats: dict[str, Any],
) -> None:
    lines: list[str] = []
    lines.append("# Menya Vocab — full 1,098-video database review")
    lines.append("")
    lines.append(f"- Videos: **{stats['total_videos']}** "
                 f"({stats['pilot_videos']} verified pilot + "
                 f"{stats['generated_videos']} generated)")
    lines.append(f"- Unique video signatures: **{stats['unique_video_signatures']}**")
    lines.append(f"- Word pool: **{stats['pool_size']}** common words; "
                 f"**{stats['word_slots']}** word slots")
    lines.append(f"- Occurrences per word: {stats['min_word_occurrences']}–"
                 f"{stats['max_word_occurrences']}")
    lines.append("")
    lines.append("Generated words repeat across different videos, but no two "
                 "videos have the same 7-word set and consecutive videos share "
                 "no words.")
    lines.append("")

    lines.append("## Word pool")
    lines.append("")
    lines.append(
        "| # | English | Kinyarwanda | Frequency rank | Corpus hits | Seed |"
    )
    lines.append("|---:|---|---|---:|---:|---|")
    for index, item in enumerate(sorted(pool, key=lambda x: (x["rank"], x["english"])), 1):
        rank = item["rank"] if item["rank"] < 10**9 else "—"
        seed = "curriculum" if item["curriculum"] else "dictionary"
        lines.append(
            f"| {index} | {item['english']} | {item['kinyarwanda']} | "
            f"{rank} | {item.get('corpus_hits', 0)} | {seed} |"
        )
    lines.append("")

    lines.append("## Videos")
    lines.append("")
    lines.append("| # | Source id | Words |")
    lines.append("|---:|---|---|")
    for index, video in enumerate(pilot_videos + generated_videos, 1):
        words = ", ".join(
            f"{pair['english']} = {pair['kinyarwanda']}"
            for pair in video["pairs"]
        )
        lines.append(f"| {index} | {video.get('id', '')} | {words} |")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the 1,098-video vocabulary database."
    )
    parser.add_argument("--dictionary", type=Path, default=DEFAULT_DICTIONARY)
    parser.add_argument("--frequency", type=Path, default=DEFAULT_FREQUENCY)
    parser.add_argument("--curriculum", type=Path, default=DEFAULT_CURRICULUM)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--pilot", type=Path, default=DEFAULT_PILOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--pool-size", type=int, default=POOL_SIZE)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    if args.pool_size < WORD_SIZE * 2:
        raise SystemExit("--pool-size Must be at least 14.")

    dictionary = load_dictionary(args.dictionary)
    curriculum = load_curriculum(args.curriculum)
    ranks = load_frequency(args.frequency)
    corpus_rows = load_corpus(args.corpus)
    pool = choose_pool(
        dictionary, curriculum, ranks, args.pool_size, corpus_rows
    )
    pilot_videos = load_pilot_videos(args.pilot)
    generated_videos = build_schedule(
        pool,
        GENERATED_VIDEOS,
        args.seed,
        pilot_videos,
    )
    stats = validate_database(pilot_videos, generated_videos, pool)

    payload = {
        "meta": {
            "name": "Menya Icyongereza 1,098-video database",
            "version": 1,
            "created": date.today().isoformat(),
            "direction": "english_to_kinyarwanda",
            "word_video_size": WORD_SIZE,
            "total_videos": TOTAL_VIDEOS,
            "pilot_videos": PILOT_VIDEOS,
            "generated_videos": GENERATED_VIDEOS,
            "pool_size": len(pool),
            "word_slots": stats["word_slots"],
            "seed": args.seed,
            "shared_words_allowed": True,
            "unique_videos": True,
            "consecutive_video_overlap": 0,
            "source_frequency": FREQUENCY_URL,
            "source_dictionary": (
                "Menya Icyongereza App dictionary cache "
                "(Iriza 2006 / Cox-Adamson-Teusink 1957)"
            ),
            "source_curriculum": "Menya Icyongereza App curriculum.json",
            "source_corpus": (
                "BIBLE APP kinyarwanda-english-corpus.tsv "
                "(14,411 aligned sentences)"
            ),
            "verification_policy": (
                "10 pilot word videos are Glosbe-verified; generated words "
                "come from the app curriculum and dictionary cache. No "
                "sentence pairs or native-review holdout content are included."
            ),
            "note": (
                "Words repeat across different videos, but every video has a "
                "unique 7-word set and consecutive videos share no words."
            ),
            **stats,
        },
        "videos": pilot_videos + generated_videos,
    }

    write_json(args.out, payload)
    write_review(args.review, pilot_videos, generated_videos, pool, stats)

    print(f"database: {args.out}")
    print(f"review:   {args.review}")
    print(
        f"videos:   {stats['total_videos']} "
        f"({stats['pilot_videos']} pilot + {stats['generated_videos']} generated)"
    )
    print(
        f"pool:     {stats['pool_size']} words, "
        f"{stats['word_slots']} slots, "
        f"{stats['min_word_occurrences']}-{stats['max_word_occurrences']} "
        "uses per word"
    )
    print(f"unique:   {stats['unique_video_signatures']} video signatures")


if __name__ == "__main__":
    main()
