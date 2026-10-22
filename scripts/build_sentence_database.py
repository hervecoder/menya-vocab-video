#!/usr/bin/env python3
"""Build the separate everyday-sentence rotation.

Every source pair is taken from the cached 14,411-row English/Kinyarwanda
aligned corpus.  Pairs are filtered hard before they can enter a video:

- 5-12 English words and 4-16 Kinyarwanda words
- one complete sentence, capitalised, with terminal punctuation
- no digits, quotes, brackets, URLs, or damaged replacement characters
- no proper nouns after the first token, and no blocklisted religious or
  technical/proper terms
- every English token must occur in the 50k frequency list
- at least one common verb
- at least 0.80 dictionary-gloss alignment coverage
- no duplicate English or Kinyarwanda sentence

The final 72 pairs are a deliberately curated subset (not every candidate the
filters accept).  A small orthographic fix table inserts missing apostrophes and
word spaces such as ``yubukwe -> y'ubukwe`` and ``mugihe -> mu gihe``; it does
not change the translation.  The source pair still carries
``verification: "corpus"`` so the build cannot claim native review.

A sentence video contains 5 or 6 pairs (10-12 text lines): English sentence,
then its Kinyarwanda translation.  The split is chosen by a layout planner,
not a fixed pair count: six cards are preferred when they still keep readable
type and breathing room; otherwise the planner uses five.  A remainder is
dropped rather than published as a partial video.

Usage:

    python scripts/build_sentence_database.py

Outputs:

    data/vocabulary_sentences.json
    data/vocabulary_sentences_review.md
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_full_database as base  # noqa: E402
from sentence_planner import plan_sentence_groups, summary as plan_summary  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "sources" / "en_rw_corpus.tsv"
DICTIONARY = ROOT / "data" / "sources" / "menya_dictionary.json"
FREQUENCY = ROOT / "data" / "sources" / "en_frequency_50k.txt"
OUTPUT = ROOT / "data" / "vocabulary_sentences.json"
REVIEW = ROOT / "data" / "vocabulary_sentences_review.md"

MIN_PAIRS_PER_VIDEO = 5
MAX_PAIRS_PER_VIDEO = 6
MIN_EN_WORDS = 5
MAX_EN_WORDS = 12
MIN_RW_WORDS = 4
MAX_RW_WORDS = 16
MIN_ALIGNMENT = 0.80

# Words that make a sentence religious, technical, or name-heavy rather than a
# clean everyday example.  The corpus is a Bible-app corpus, so this blocklist
# is necessary to keep the sentence rotation general-purpose.
BLOCKED = set(
    """
    god lord jesus christ bible church pray prayer sin sins apostle disciples
    holy heaven kingdom israel jew jews gentile gentiles scripture prophet
    moses david abraham isaac jacob solomon saul paul peter john matthew mark
    luke samaria corinth ephesus galilee sinai testament christians christian
    muslim islam quran allah religion temple statue artemis theo keza
    bweranyange slave cannabis arms
    """.split()
)

GRAMMAR_BAD = re.compile(
    r"\b(advices|informations|peoples|childrens|womens|mens|didnt|doesnt|"
    r"dont|cant|wont|isnt|arent|wasnt|werent|hasnt|havent|couldnt|wouldnt|"
    r"shouldnt|im|ive|id|youre|theyre|weve|thats|whats)\b",
    re.I,
)
BAD_CHARS = re.compile(r'[0-9\[\]{}()"“”<>|_=*#@/\\;:]')
FIRST_BAD = set(
    "to and but so because that which who whom whose if when while after "
    "before although though unless until since as".split()
)
VERBS = set(
    """
    am is are was were be been being have has had do does did can could will
    would shall should may might must want wants wanted need needs needed like
    likes liked love loves loved eat eats ate go goes went come comes came see
    sees saw know knows knew think thinks thought say says said tell tells told
    ask asks asked give gives gave take takes took make makes made work works
    worked live lives lived play plays played read reads write writes wrote
    speak speaks spoke learn learns learned buy buys sells sold help helps
    helped find finds found look looks looked feel feels felt put puts keep
    keeps kept leave leaves left start starts started stop stops stopped try
    tries tried use uses used get gets got become becomes became
    """.split()
)

# Curated order.  Every English sentence below was found in the aligned corpus,
# passed the hard gates, and was manually scanned for an obvious mistranslation
# or fragment.  The final 12 items were added in a second review pass.
CURATED = [
    "There is something I want you to know.",
    "Do you think this is a good idea?",
    "I want to hear you say that again.",
    "How many people do you think will be there?",
    "I think you might want to hear this.",
    "All you have to do is wait for his answer.",
    "This is going to take some time to explain.",
    "You have to live well while you are alive.",
    "Go and ask a child who is playing there.",
    "Many times people do not want to die.",
    "I want to say a few words.",
    "Yet they did not want to spend too much time.",
    "I never wanted to lose my job.",
    "I want to ask you a few questions.",
    "For some reason he is going to write.",
    "There are few children in the school.",
    "He says there is something under the bed.",
    "The girl running there is my sister.",
    "We will pay you according to the work you do.",
    "You have a dog that can run fast.",
    "We say he is very rich.",
    "You have less time to read these days.",
    "There is a lot of money in the account.",
    "Were you present at the time of the accident?",
    "They do not set a date for their wedding.",
    "We never got there when it started to rain.",
    "Look at the boy and the dogs running there.",
    "I will have to correct them for my mistake.",
    "Do you think it will rain in the afternoon?",
    "Have you decided whether to sell your house or not?",
    "There may have been a road accident.",
    "There was a train accident early in the morning.",
    "There is a lot of rain all year round.",
    "The hotel I am in does not have parking.",
    "I have to take photos for my school project.",
    "Is there a reason why I should obey him?",
    "In the south there are many enemies.",
    "Time passes when we do something we love.",
    "There is sand on the bottom of the sea.",
    "The hotel has five other guests.",
    "He drank a cup of tea and asked for more.",
    "The employee himself would not do so.",
    "The working man must be paid according to his skill.",
    "There was a lot of fear after the earthquake.",
    "I wrote an article for a school magazine.",
    "Using the ability to think helps.",
    "From the tenth minute I had a chance to win.",
    "The concert was packed with people.",
    "Behind our house is a cottage.",
    "A lot of money goes into the pockets of individuals.",
    "At the top of the pillar was a flag.",
    "Do you have information on old music concerts?",
    "It will take time to finish unloading this truck.",
    "There must be a way to achieve diplomatic solutions.",
    "He is not accustomed to urban life.",
    "Mom loves tulips and so does my sister.",
    "Instead they are motivated to fulfill their responsibilities.",
    "He grew up to be a good man.",
    "There is a market building near my house.",
    "This is a photo of my wife on the sand.",
    "It is not a problem for me to quit my job.",
    "The teacher told me that I would not be late for school.",
    "People say that I am the same age as my sister.",
    "We could not bear to hear the cry of the sick child.",
    "There are a lot of people on both sides of the road.",
    "You should not be afraid to make mistakes while learning a language.",
    "There was so much noise that the speaker could not hear.",
    "The game would not be suspended if it did not rain heavily.",
    "You should not be discouraged because you are not an expert.",
    "The midterm exam will start next week.",
    "Some people do not like to get up early in the morning.",
    "Inside the refrigerator is a bottle of white wine.",
]

# Orthographic cleanup only.  These are the common corpus joins that make
# otherwise-correct Kinyarwanda look unpolished.  No translation sense changes.
TEXT_FIXES = {
    "You have to live well while you are alive.": (
        "Ugomba kubaho neza mu gihe ukiriho."
    ),
    "He says there is something under the bed.": (
        "Avuga ko hari ikintu munsi y'igitanda."
    ),
    "You have less time to read these days.": (
        "Mufite umwanya muto wo gusoma muri iyi minsi."
    ),
    "They do not set a date for their wedding.": (
        "Ntabwo barashiraho itariki y'ubukwe bwabo."
    ),
    "Look at the boy and the dogs running there.": (
        "Reba umuhungu n'imbwa ziruka hariya."
    ),
    "I will have to correct them for my mistake.": (
        "Nzagomba kubakosora ku bw'ikosa ryanjye."
    ),
    "There may have been a road accident.": (
        "Birashoboka ko habaye impanuka yo mu muhanda."
    ),
    "There was a train accident early in the morning.": (
        "Habaye impanuka ya gari ya moshi kare mu gitondo."
    ),
    "I have to take photos for my school project.": (
        "Ngomba gufata amafoto ku mushinga wanjye w'ishuri."
    ),
    "There is sand on the bottom of the sea.": (
        "Hasi y'inyanja hari umusenyi."
    ),
    "I wrote an article for a school magazine.": (
        "Nanditse ingingo y'ikinyamakuru cy'ishuri."
    ),
    "From the tenth minute I had a chance to win.": (
        "Kuva ku munota wa cumi narimfite amahirwe yo gutsinda."
    ),
    "Behind our house is a cottage.": (
        "Inyuma y'inzu yacu hari akazu."
    ),
    "At the top of the pillar was a flag.": (
        "Hejuru y'inkingi hari ibendera."
    ),
    "Do you have information on old music concerts?": (
        "Waba ufite amakuru ku bitaramo bya muzika bya kera?"
    ),
    "It will take time to finish unloading this truck.": (
        "Bizatwara igihe cyo kurangiza gupakurura iyi kamyo."
    ),
    "There must be a way to achieve diplomatic solutions.": (
        "Hagomba kubaho inzira yo kugera ku bisubizo bya diplomasi."
    ),
    "He is not accustomed to urban life.": (
        "Ntabwo aramenyera ubuzima bw'umujyi."
    ),
    "He grew up to be a good man.": (
        "Yarakuze aba umugabo mwiza."
    ),
    "There is a market building near my house.": (
        "Hano hari isoko hafi y'inzu yanjye."
    ),
    "This is a photo of my wife on the sand.": (
        "Iyi ni ifoto y'umugore wanjye ku musenyi."
    ),
    "People say that I am the same age as my sister.": (
        "Abantu bavuga ko mfite imyaka ingana n'iya mushiki wanjye."
    ),
    "We could not bear to hear the cry of the sick child.": (
        "Ntabwo twashoboye kwihanganira kumva gutaka k'umwana urwaye."
    ),
    "You should not be afraid to make mistakes while learning a language.": (
        "Ntugomba gutinya gukora amakosa mu gihe wiga ururimi."
    ),
    "There was so much noise that the speaker could not hear.": (
        "Hariho urusaku rwinshi ku buryo uwatanze disikuru atashoboraga kumva."
    ),
    "Some people do not like to get up early in the morning.": (
        "Abantu bamwe ntibakunda kubyuka kare mu gitondo."
    ),
}


def now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def clean(text: str) -> str:
    # The corpus occasionally uses U+FFFD where an apostrophe was lost.  It is
    # safe to restore it between letters; validation rejects anything left over.
    text = str(text or "").replace("\ufffd", "'")
    return " ".join(text.split()).strip()


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÿ']+", text)


def english_key(text: str) -> str:
    return " ".join(tokens(text)).casefold()


def capitalise(text: str) -> str:
    return text[:1].upper() + text[1:] if text and text[0].islower() else text


def valid_candidate(english: str, kinyarwanda: str) -> tuple[str, str] | None:
    english = clean(english)
    kinyarwanda = clean(kinyarwanda)
    et = tokens(english)
    rt = tokens(kinyarwanda)

    if not (MIN_EN_WORDS <= len(et) <= MAX_EN_WORDS):
        return None
    if not (MIN_RW_WORDS <= len(rt) <= MAX_RW_WORDS):
        return None
    if BAD_CHARS.search(english) or BAD_CHARS.search(kinyarwanda):
        return None
    if "\ufffd" in english or "\ufffd" in kinyarwanda:
        return None
    if english.isupper() or kinyarwanda.isupper():
        return None
    if english.count(".") + english.count("?") + english.count("!") != 1:
        return None
    if not re.search(r"[.?!]$", english) or not re.search(r"[.?!]$", kinyarwanda):
        return None
    if not english[0].isalpha() or not kinyarwanda[0].isalpha():
        return None

    # A capital in the middle of the English sentence usually means a name or a
    # place; those are not useful general-vocabulary examples.
    for word in et[1:]:
        if word[0].isupper() and word != "I":
            return None

    if et[0].casefold() in FIRST_BAD:
        return None
    if GRAMMAR_BAD.search(english):
        return None
    if any(word.casefold() in BLOCKED for word in et):
        return None
    if not any(word.casefold() in VERBS for word in et):
        return None

    return capitalise(english), capitalise(kinyarwanda)


def alignment(english: str, kinyarwanda: str, dictionary: dict[str, list[str]]) -> tuple[float, list[str]]:
    known: list[str] = []
    for word in tokens(english):
        word = word.casefold().strip("'")
        if len(word) < 3 or word in base.STOPWORDS:
            continue
        if word not in dictionary:
            continue
        known.append(word)
    known = list(dict.fromkeys(known))
    if len(known) < 2:
        return 0.0, known

    rw_text = base.normalize_rw(kinyarwanda)
    matched = 0
    for word in known:
        ok = False
        for gloss in dictionary[word]:
            for segment in base.split_translation(gloss):
                if len(segment) >= 4 and base.segment_matches(segment, rw_text):
                    ok = True
                    break
            if ok:
                break
        if ok:
            matched += 1
    return matched / len(known), known


def validate_final(english: str, kinyarwanda: str) -> None:
    if not english or not kinyarwanda:
        raise SystemExit("A curated sentence is empty.")
    if BAD_CHARS.search(english) or BAD_CHARS.search(kinyarwanda):
        raise SystemExit(f"Unsafe characters in sentence {english!r}")
    if "\ufffd" in english or "\ufffd" in kinyarwanda:
        raise SystemExit(f"Damaged characters in sentence {english!r}")
    if not re.search(r"[.?!]$", english) or not re.search(r"[.?!]$", kinyarwanda):
        raise SystemExit(f"Missing terminal punctuation in {english!r}")
    if not english[0].isupper() or not kinyarwanda[0].isupper():
        raise SystemExit(f"Sentence not capitalised: {english!r}")
    if not (MIN_EN_WORDS <= len(tokens(english)) <= MAX_EN_WORDS):
        raise SystemExit(f"English length out of range: {english!r}")
    if not (MIN_RW_WORDS <= len(tokens(kinyarwanda)) <= MAX_RW_WORDS):
        raise SystemExit(f"Kinyarwanda length out of range: {english!r}")


def build_candidates(
    corpus: list[tuple[str, str]],
    dictionary: dict[str, list[str]],
    frequency: dict[str, int],
) -> tuple[dict[str, dict[str, Any]], Counter]:
    stats: Counter = Counter()
    candidates: dict[str, dict[str, Any]] = {}
    seen_rw: set[str] = set()
    frequency_set = set(frequency)

    for raw_english, raw_kinyarwanda in corpus:
        stats["rows"] += 1
        pair = valid_candidate(raw_english, raw_kinyarwanda)
        if pair is None:
            stats["filtered"] += 1
            continue
        english, kinyarwanda = pair

        # Every English token must be a real common word.  This catches joined
        # corpus typos such as "lateand" and name-heavy sentences.
        if any(
            word.casefold() not in frequency_set and word.casefold() != "i"
            for word in tokens(english)
        ):
            stats["unknown_english"] += 1
            continue

        key = english_key(english)
        rw_key = " ".join(tokens(kinyarwanda)).casefold()
        if key in candidates or rw_key in seen_rw:
            stats["duplicate"] += 1
            continue

        coverage, known = alignment(english, kinyarwanda, dictionary)
        if len(known) < 2 or coverage < MIN_ALIGNMENT:
            stats["low_alignment"] += 1
            continue

        ranks = [frequency.get(word.casefold(), 50_000) for word in tokens(english)]
        candidates[key] = {
            "english": english,
            "kinyarwanda": kinyarwanda,
            "coverage": round(coverage, 3),
            "known": known,
            "avg_rank": round(sum(ranks) / len(ranks), 1),
        }
        seen_rw.add(rw_key)
        stats["candidates"] += 1

    return candidates, stats


def write_review(videos: list[dict[str, Any]], stats: Counter) -> None:
    pair_total = sum(len(video["pairs"]) for video in videos)
    lines = [
        "# Sentence rotation review",
        "",
        f"Generated: {now_iso()}",
        "",
        "Source: `data/sources/en_rw_corpus.tsv` (14,411 aligned pairs).",
        "Policy: 5 or 6 sentence pairs per video (10-12 text lines), chosen by "
        "layout analysis; English first, Kinyarwanda second.",
        "",
        f"These {pair_total} pairs passed the hard alignment/length/grammar filters and a "
        "manual scan. Orthographic fixes only add missing apostrophes/spaces; "
        "the translation itself is still corpus-sourced. They are **not** "
        "native-reviewed yet, so the source tier is `corpus`, not `native`.",
        "",
        "## Video layout decisions",
        "",
        "| Video | Pairs | Text lines | Avg font | Min font | Wrapped cards | Gap | Used / available |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for video in videos:
        layout = video["layout"]
        lines.append(
            f"| `{video['id']}` | {video['pair_count']} | "
            f"{video['line_count']} | {layout['average_font_px']} px | "
            f"{layout['min_font_px']} px | {layout['wrapped_cards']} | "
            f"{layout['gap_px']} px | {layout['used_height_px']} / "
            f"{layout['available_height_px']} px |"
        )
    lines += [
        "",
        "| # | Video | English sentence | Kinyarwanda translation | Alignment | Notes |",
        "|---:|---|---|---|---:|---|",
    ]
    number = 0
    for video in videos:
        for pair in video["pairs"]:
            number += 1
            notes = pair.get("notes", "")
            lines.append(
                f"| {number} | `{video['id']}` | {pair['english']} | "
                f"{pair['kinyarwanda']} | {pair.get('corpus_alignment', 0):.2f} | "
                f"{notes} |"
            )
    lines += [
        "",
        "## Build counts",
        "",
        f"- corpus rows: {stats['rows']}",
        f"- hard-filtered out: {stats['filtered']}",
        f"- unknown English tokens: {stats['unknown_english']}",
        f"- duplicates: {stats['duplicate']}",
        f"- alignment below {MIN_ALIGNMENT:.2f}: {stats['low_alignment']}",
        f"- candidates before curation: {stats['candidates']}",
        f"- curated pairs: {number}",
        f"- videos: {len(videos)}",
        "",
    ]
    REVIEW.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if not CORPUS.exists():
        raise SystemExit(f"Missing corpus: {CORPUS}")
    if not DICTIONARY.exists():
        raise SystemExit(f"Missing dictionary: {DICTIONARY}")
    if not FREQUENCY.exists():
        raise SystemExit(f"Missing frequency list: {FREQUENCY}")

    corpus = base.load_corpus(CORPUS)
    dictionary = base.load_dictionary(DICTIONARY)
    frequency = base.load_frequency(FREQUENCY)
    candidates, stats = build_candidates(corpus, dictionary, frequency)

    if len(candidates) < len(CURATED):
        raise SystemExit(
            f"Only {len(candidates)} candidates passed; need {len(CURATED)}."
        )

    selected: list[dict[str, Any]] = []
    seen_english: set[str] = set()
    seen_kinyarwanda: set[str] = set()
    for english in CURATED:
        key = english_key(english)
        candidate = candidates.get(key)
        if candidate is None:
            raise SystemExit(
                f"Curated sentence did not pass the source filter: {english!r}"
            )
        if key in seen_english:
            raise SystemExit(f"Duplicate curated English sentence: {english!r}")
        kinyarwanda = TEXT_FIXES.get(english, candidate["kinyarwanda"])
        kinyarwanda = clean(kinyarwanda)
        validate_final(candidate["english"], kinyarwanda)
        rw_key = " ".join(tokens(kinyarwanda)).casefold()
        if rw_key in seen_kinyarwanda:
            raise SystemExit(f"Duplicate curated Kinyarwanda sentence: {kinyarwanda!r}")
        seen_english.add(key)
        seen_kinyarwanda.add(rw_key)
        selected.append(
            {
                "english": candidate["english"],
                "kinyarwanda": kinyarwanda,
                "coverage": candidate["coverage"],
                "avg_rank": candidate["avg_rank"],
                "fixed": english in TEXT_FIXES,
            }
        )

    selected_pairs = [
        (item["english"], item["kinyarwanda"]) for item in selected
    ]
    groups = None
    for usable in range(len(selected), MIN_PAIRS_PER_VIDEO - 1, -1):
        try:
            groups = plan_sentence_groups(selected_pairs[:usable])
        except ValueError:
            continue
        if usable != len(selected):
            print(
                f"dropping {len(selected) - usable} lowest-priority pair(s) so "
                "every video is a complete layout-checked job"
            )
            selected = selected[:usable]
        break
    if groups is None:
        raise SystemExit(
            "Could not split the curated sentences into complete "
            f"{MIN_PAIRS_PER_VIDEO}- or {MAX_PAIRS_PER_VIDEO}-pair videos."
        )

    videos: list[dict[str, Any]] = []
    number = 0
    for video_number, group in enumerate(groups, start=1):
        batch = selected[group.start : group.end]
        video_id = f"sentence_{video_number:04d}"
        pairs = []
        for position, item in enumerate(batch, start=1):
            number += 1
            note = (
                "Corpus-aligned; orthography normalized; native review "
                "recommended."
                if item["fixed"]
                else "Corpus-aligned; native review recommended."
            )
            pairs.append(
                {
                    "position": position,
                    "entry_id": f"sentence_entry_{number:04d}",
                    "english": item["english"],
                    "kinyarwanda": item["kinyarwanda"],
                    "group_id": "daily-sentences",
                    "group_title": "Everyday Sentences",
                    "grammar": "sentence",
                    "verification": "corpus",
                    "verification_tier": "corpus",
                    "corpus_alignment": item["coverage"],
                    "sources": [
                        "data/sources/en_rw_corpus.tsv",
                        "Aligned English/Kinyarwanda corpus",
                    ],
                    "notes": note,
                }
            )
        videos.append(
            {
                "id": video_id,
                "source_id": video_id,
                "mode": "sentence",
                "complete": True,
                "pair_count": group.pair_count,
                "line_count": group.line_count,
                "layout": {
                    "average_font_px": round(group.avg_font, 1),
                    "min_font_px": group.min_font,
                    "max_font_px": group.max_font,
                    "wrapped_cards": group.wrapped_cards,
                    "gap_px": group.gap,
                    "used_height_px": group.used_height,
                    "available_height_px": group.available_height,
                },
                "selection_note": (
                    f"{group.pair_count} pairs chosen by layout analysis: "
                    f"average {group.avg_font:.1f}px, "
                    f"{group.wrapped_cards} wrapped card(s), "
                    f"{group.gap}px gap."
                ),
                "pairs": pairs,
            }
        )

    if len(videos) < 1:
        raise SystemExit("No sentence videos were produced.")
    if number != len(selected):
        raise SystemExit("Internal error: a partial sentence video was produced.")
    if sum(group.pair_count for group in groups) != len(selected):
        raise SystemExit("Internal error: the sentence plan left pairs uncovered.")

    payload = {
        "meta": {
            "generated_at": now_iso(),
            "source": "data/sources/en_rw_corpus.tsv",
            "source_kind": "sentence_rotation",
            "total_pairs": number,
            "total_entries": number,
            "total_videos": len(videos),
            "min_pairs_per_video": MIN_PAIRS_PER_VIDEO,
            "max_pairs_per_video": MAX_PAIRS_PER_VIDEO,
            "pair_counts": dict(
                Counter(video["pair_count"] for video in videos)
            ),
            "verification_tier": "corpus",
            "native_review_required": True,
            "filter_policy": (
                f"{MIN_EN_WORDS}-{MAX_EN_WORDS} English words; "
                f"{MIN_RW_WORDS}-{MAX_RW_WORDS} Kinyarwanda words; "
                f"alignment >= {MIN_ALIGNMENT:.2f}; no names/religious terms; "
                "orthography normalized; curated"
            ),
            "layout_policy": (
                "5-6 pairs per video, chosen by measuring the rendered card "
                "stack; six pairs only when type stays readable"
            ),
            "orthography_fixes": len(TEXT_FIXES),
            "notes": [
                "English first, Kinyarwanda second on every card.",
                "5-6 pairs = 10-12 text lines per video, chosen by layout.",
                "Corpus-sourced, not individually native-reviewed.",
            ],
        },
        "videos": videos,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_review(videos, stats)

    print(
        f"wrote {OUTPUT.relative_to(ROOT)}: {number} pairs, {len(videos)} videos "
        f"({plan_summary(groups)}), 10-12 lines per video"
    )
    print(f"wrote {REVIEW.relative_to(ROOT)}")
    print(
        f"filter counts: {stats['rows']} rows -> {stats['candidates']} candidates "
        f"-> {number} curated"
    )


if __name__ == "__main__":
    main()
