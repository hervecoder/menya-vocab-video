import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

with (DATA / "verification" / "pilot_glosbe_sources.json").open(encoding="utf-8") as f:
    primary = json.load(f)
with (DATA / "verification" / "pilot_glosbe_alternatives.json").open(encoding="utf-8") as f:
    alternatives = json.load(f)

cache = {}
for row in primary + alternatives:
    cache[(row["group"], row["english"], row["kinyarwanda"])] = row

GROUPS = [
    ("common-action-verbs", "Common Action Verbs", "word", "Daily activities", ""),
    ("everyday-foods", "Everyday Foods", "word", "Food and drinks", "Pilot uses rice and milk; other foods are queued for the full expansion."),
    ("describing-words", "Describing Words", "word", "Daily activities", ""),
    ("people-and-roles", "People and Roles", "word", "Family", ""),
    ("question-and-answer", "Question and Answer", "sentence", "Daily activities", ""),
    ("basic-daily-questions", "Basic Daily Questions", "sentence", "Daily activities", ""),
    ("buying-at-a-shop", "Buying at a Shop", "sentence", "Shopping", ""),
    ("household-actions", "Household Actions", "word", "Daily activities", ""),
    ("home-items", "Home Items", "word", "Home", "Door uses urugi (verified); the reference also lists umuryango (gate/door)."),
    ("talking-in-class", "Talking in Class", "sentence", "Education", "Good morning is verified online; the other pair needs native review."),
    ("yes-or-no-questions", "Yes or No Questions", "sentence", "Daily activities", ""),
    ("daily-life-actions", "Daily Life Actions", "sentence", "Daily activities", ""),
    ("common-travel-verbs", "Common Travel Verbs", "word", "Transport", ""),
    ("market-items", "Market Items", "word", "Shopping", ""),
    ("character-words-umuntu", "Character Words (UMUNTU)", "word", "Feelings", "Pilot uses honest and patient, verified through reverse Glosbe entries."),
    ("work-roles", "Work Roles", "word", "Jobs", "Doctor and nurse; farmer is also verified but is outside this 100-entry sample."),
    ("evening-sentences", "Evening Sentences", "sentence", "Home", ""),
    ("home-questions", "Home Questions", "sentence", "Home", ""),
    ("clinic-conversation", "Clinic Conversation", "sentence", "Health", ""),
    ("school-tools", "School Tools", "word", "Education", ""),
    ("repair-verbs", "Repair Verbs", "word", "Daily activities", "Pilot uses to repair (gusana); the reference also lists to fix."),
    ("weather-words", "Weather Words", "word", "Weather", "Pilot uses verified weather nouns (sun, rain, wind); sunny/rainy adjective forms are queued for review."),
    ("village-people", "Village People", "word", "Family", ""),
    ("bus-travel-conversation", "Bus Travel Conversation", "sentence", "Transport", ""),
    ("morning-sentences", "Morning Sentences", "sentence", "Daily activities", ""),
    ("money-questions", "Money Questions", "sentence", "Shopping", ""),
    ("kitchen-verbs", "Kitchen Verbs", "word", "Food and drinks", ""),
    ("garden-nouns", "Garden Nouns", "word", "Home", ""),
    ("body-parts", "Body Parts", "word", "Body parts", ""),
    ("office-people", "Office People", "word", "Jobs", "Accountant uses umucungamari (verified); the reference also lists umubaruramari."),
    ("phone-conversation", "Phone Conversation", "sentence", "Daily activities", ""),
    ("safety-sentences", "Safety Sentences", "sentence", "Daily activities", ""),
    ("quiet-questions", "Quiet Questions", "sentence", "Daily activities", ""),
    ("cleaning-verbs", "Cleaning Verbs", "word", "Daily activities", ""),
    ("farm-animals", "Farm Animals", "word", "Animals", ""),
    ("family-relations", "Family Relations", "word", "Family", "Pilot uses daughter, father and sister; grandparent/uncle forms are queued for native review."),
    ("shop-conversation", "Shop Conversation", "sentence", "Shopping", ""),
    ("reading-sentences", "Reading Sentences", "sentence", "Education", ""),
    ("health-questions", "Health Questions", "sentence", "Health", ""),
    ("sound-adjectives-ijwi", "Sound Adjectives (IJWI)", "word", "Daily activities", "Pilot uses verified sound words (silent, noise); adjective forms are queued for review."),
    ("taxi-conversation", "Taxi Conversation", "sentence", "Transport", ""),
    ("simple-daily-statements", "Simple Daily Statements", "sentence", "Daily activities", ""),
    ("daily-movement-verbs", "Daily Movement Verbs", "word", "Daily activities", ""),
    ("clothing-items", "Clothing Items", "word", "Clothes", "Trousers uses ipantaro (verified spelling); the reference spelling was ipantalo."),
    ("taste-adjectives", "Taste Adjectives", "word", "Food and drinks", "Sour is listed as sharira (verified root); the adjective gisharira needs native confirmation."),
    ("transport-types", "Transport Types", "word", "Transport", ""),
    ("helping-sentences", "Helping Sentences", "sentence", "Daily activities", ""),
    ("direction-questions", "Direction Questions", "sentence", "Places", ""),
    ("restaurant-conversation", "Restaurant Conversation", "sentence", "Food and drinks", ""),
    ("time-words", "Time Words", "word", "Time", ""),
    ("feeling-verbs", "Feeling Verbs", "word", "Feelings", ""),
    ("colors", "Colors", "word", "Colors", ""),
    ("park-conversation", "Park Conversation", "sentence", "Places", ""),
    ("body-actions", "Body Actions", "word", "Body parts", ""),
    ("building-items", "Building Items", "word", "Home", ""),
    ("polite-questions", "Polite Questions", "sentence", "Daily activities", ""),
    ("daily-routine-sentences", "Daily Routine Sentences", "sentence", "Daily activities", ""),
]

# (group_id, english, kinyarwanda, grammar, note, explicit_source)
WORDS = [
    ("common-action-verbs", "to eat", "kurya", "verb", "", None),
    ("common-action-verbs", "to drink", "kunywa", "verb", "", None),
    ("everyday-foods", "rice", "umuceri", "noun", "", None),
    ("everyday-foods", "milk", "amata", "noun", "", None),
    ("describing-words", "big", "nini", "adjective", "", None),
    ("describing-words", "small", "gitoya", "adjective", "Reference lists nto; pilot uses verified gitoya (class 7 adjective).", "https://glosbe.com/en/rw/small"),
    ("people-and-roles", "teacher", "umwarimu", "noun", "", None),
    ("people-and-roles", "student", "umunyeshuri", "noun", "", None),
    ("people-and-roles", "mother", "mama", "noun", "Extra word selected by the seeded random sample.", None),
    ("household-actions", "to open", "gufungura", "verb", "", None),
    ("household-actions", "to close", "gufunga", "verb", "", None),
    ("household-actions", "to clean", "gusukura", "verb", "Extra word selected by the seeded random sample.", None),
    ("home-items", "house", "inzu", "noun", "", None),
    ("home-items", "door", "urugi", "noun", "Reference lists umuryango; verified Glosbe form is urugi.", None),
    ("home-items", "window", "idirishya", "noun", "Extra word selected by the seeded random sample.", None),
    ("common-travel-verbs", "to travel", "gutembera", "verb", "", None),
    ("common-travel-verbs", "to choose", "guhitamo", "verb", "", None),
    ("market-items", "bottle", "icupa", "noun", "", None),
    ("market-items", "key", "urufunguzo", "noun", "", None),
    ("character-words-umuntu", "honest", "inyangamugayo", "adjective", "Glosbe reverse entry lists reliable/trustworthy person; reference form is w'inyangamugayo.", "https://glosbe.com/rw/en/inyangamugayo"),
    ("character-words-umuntu", "patient", "ihangana", "adjective", "Glosbe reverse entry lists patient/endure; reference form is wihangana.", "https://glosbe.com/rw/en/ihangana"),
    ("work-roles", "doctor", "umuganga", "noun", "", None),
    ("work-roles", "nurse", "umuforomo", "noun", "", None),
    ("school-tools", "pencil", "ikaramu", "noun", "", None),
    ("school-tools", "blackboard", "ikibaho", "noun", "", None),
    ("repair-verbs", "to repair", "gusana", "verb", "Reference group lists to fix; Glosbe verifies gusana as repair/mend.", None),
    ("repair-verbs", "to replace", "gusimbura", "verb", "", None),
    ("weather-words", "sun", "izuba", "noun", "Verified noun form; sunny adjective form is queued.", None),
    ("weather-words", "rain", "imvura", "noun", "Verified noun form; rainy adjective form is queued.", None),
    ("weather-words", "wind", "umuyaga", "noun", "Extra word selected by the seeded random sample; verified noun form.", None),
    ("village-people", "elder", "umusaza", "noun", "", None),
    ("village-people", "guest", "umushyitsi", "noun", "", None),
    ("village-people", "twin", "impanga", "noun", "Extra word selected by the seeded random sample.", None),
    ("kitchen-verbs", "to cook", "guteka", "verb", "", None),
    ("kitchen-verbs", "to fry", "gukaranga", "verb", "", None),
    ("kitchen-verbs", "to mix", "kuvanga", "verb", "Extra word selected by the seeded random sample.", None),
    ("garden-nouns", "flower", "ururabyo", "noun", "", None),
    ("garden-nouns", "tree", "igiti", "noun", "", None),
    ("garden-nouns", "leaf", "ikibabi", "noun", "Extra word selected by the seeded random sample.", None),
    ("body-parts", "hand", "ikiganza", "noun", "", None),
    ("body-parts", "foot", "ikirenge", "noun", "", None),
    ("office-people", "secretary", "umunyamabanga", "noun", "", None),
    ("office-people", "accountant", "umucungamari", "noun", "Reference lists umubaruramari; verified Glosbe form is umucungamari.", None),
    ("cleaning-verbs", "to sweep", "gukubura", "verb", "", None),
    ("cleaning-verbs", "to wipe", "guhanagura", "verb", "", None),
    ("farm-animals", "cow", "inka", "noun", "", None),
    ("farm-animals", "goat", "ihene", "noun", "", None),
    ("family-relations", "daughter", "umukobwa", "noun", "", None),
    ("family-relations", "father", "papa", "noun", "", None),
    ("family-relations", "sister", "mushiki", "noun", "Extra word selected by the seeded random sample.", None),
    ("sound-adjectives-ijwi", "silent", "ceceka", "verb", "Glosbe reverse entry: silent, quiet, stop talking; Menya dictionary also lists guceceka.", "https://glosbe.com/rw/en/ceceka"),
    ("sound-adjectives-ijwi", "noise", "urusaku", "noun", "Glosbe reverse entry: noise, sound, clamour.", "https://glosbe.com/rw/en/urusaku"),
    ("daily-movement-verbs", "to jump", "gusimbuka", "verb", "", None),
    ("daily-movement-verbs", "to walk", "kugenda", "verb", "", None),
    ("clothing-items", "shirt", "ishati", "noun", "", None),
    ("clothing-items", "trousers", "ipantaro", "noun", "Spelling corrected from reference ipantalo to verified ipantaro.", None),
    ("taste-adjectives", "bitter", "kirura", "adjective", "", None),
    ("taste-adjectives", "sour", "sharira", "adjective", "Glosbe lists the root sharira; natural adjective form gisharira needs native confirmation.", None),
    ("transport-types", "bus", "bisi", "noun", "", None),
    ("transport-types", "car", "imodoka", "noun", "", None),
    ("transport-types", "bicycle", "igare", "noun", "Extra word selected by the seeded random sample.", None),
    ("time-words", "morning", "igitondo", "noun", "", None),
    ("time-words", "today", "uyu munsi", "adverb", "", None),
    ("time-words", "tomorrow", "ejo", "adverb", "Extra word selected by the seeded random sample.", None),
    ("feeling-verbs", "to smile", "kumwenyura", "verb", "", None),
    ("feeling-verbs", "to cry", "kurira", "verb", "", None),
    ("colors", "red", "umutuku", "adjective", "", None),
    ("colors", "blue", "ubururu", "adjective", "", None),
    ("colors", "green", "icyatsi", "adjective", "Extra word selected by the seeded random sample.", None),
    ("body-actions", "to breathe", "guhumeka", "verb", "", None),
    ("body-actions", "to cough", "gukorora", "verb", "", None),
    ("building-items", "brick", "itafari", "noun", "", None),
    ("building-items", "stone", "ibuye", "noun", "", None),
    ("building-items", "sand", "umucanga", "noun", "Extra word selected by the seeded random sample.", None),
]

# (group_id, english, kinyarwanda, topic, note, source)
SENTENCES = [
    ("question-and-answer", "Do you have any siblings?", "Ugira abavandimwe?", "Daily activities", "", None),
    ("basic-daily-questions", "Where are you?", "Uri he?", "Daily activities", "", None),
    ("buying-at-a-shop", "How much is it?", "Ni angahe?", "Shopping", "", None),
    ("talking-in-class", "Good morning", "Mwaramutse", "Education", "Common phrase confirmed on Glosbe.", "https://glosbe.com/en/rw/good%20morning"),
    ("yes-or-no-questions", "Do you eat rice?", "Urarya umuceri?", "Daily activities", "", None),
    ("daily-life-actions", "He cooks food", "Ateka ibiryo", "Daily activities", "", None),
    ("evening-sentences", "I close the window at night", "Mfunga idirishya nijoro", "Home", "", None),
    ("home-questions", "Where did you put the key?", "Washyize he urufunguzo?", "Home", "", None),
    ("clinic-conversation", "I have a headache.", "Mfite umutwe ubabara.", "Health", "", None),
    ("bus-travel-conversation", "How much is the ride?", "Urugendo ni angahe?", "Transport", "", None),
    ("morning-sentences", "I wake before sunrise", "Mbyuka mbere y'uko izuba rirasa", "Daily activities", "", None),
    ("money-questions", "How much do you need?", "Ukeneye amafaranga angahe?", "Shopping", "", None),
    ("phone-conversation", "Hi there, can you hear me?", "Muraho, uranyumva?", "Daily activities", "", None),
    ("safety-sentences", "Look both ways before crossing", "Reba impande zombi mbere yo kwambuka", "Daily activities", "", None),
    ("quiet-questions", "Is the baby sleeping?", "Umwana arasinziriye?", "Daily activities", "", None),
    ("shop-conversation", "Good afternoon, I need a small bag.", "Mwiriwe neza, nkeneye agapaki gato.", "Shopping", "", None),
    ("reading-sentences", "I read a short story", "Nsoma inkuru ngufi", "Education", "", None),
    ("health-questions", "Where does it hurt?", "Uri kubabara he?", "Health", "", None),
    ("taxi-conversation", "Please, take me to the station.", "Nyamuneka njyana kuri sitasiyo.", "Transport", "", None),
    ("simple-daily-statements", "I eat food", "Ndarya ibiryo", "Daily activities", "", None),
    ("helping-sentences", "I carry your bag", "Nagutwarira igikapu", "Daily activities", "", None),
    ("direction-questions", "Where is the road?", "Umuhanda uri he?", "Places", "", None),
    ("restaurant-conversation", "I would like food.", "Ndashaka ibiryo.", "Food and drinks", "", None),
    ("park-conversation", "Let us walk in the park.", "Reka tugende muri pariki.", "Places", "", None),
    ("polite-questions", "May I come in?", "Ninjire?", "Daily activities", "", None),
    ("daily-routine-sentences", "I brush my teeth", "Noza amenyo", "Daily activities", "", None),
]

groups_by_id = {g[0]: {"id": g[0], "title": g[1], "type": g[2], "topic": g[3], "notes": g[4]} for g in GROUPS}
assert len(groups_by_id) == 57, len(groups_by_id)

entries = []

for group_id, en, rw, grammar, note, explicit_source in WORDS:
    group = groups_by_id[group_id]
    row = cache.get((group["title"], en, rw))
    source = explicit_source or (row["url"] if row else None)
    if not source:
        raise SystemExit(f"Missing source for word: {group['title']} / {en} / {rw}")
    status = "verified"
    entries.append({
        "id": None,
        "group_id": group_id,
        "group_title": group["title"],
        "english": en,
        "kinyarwanda": rw,
        "type": "word",
        "grammar": grammar,
        "topic": group["topic"],
        "origin": "reference_group",
        "verification": status,
        "sources": [source],
        "notes": note,
    })

for group_id, en, rw, topic, note, source in SENTENCES:
    group = groups_by_id[group_id]
    status = "verified" if source else "native_review_required"
    entries.append({
        "id": None,
        "group_id": group_id,
        "group_title": group["title"],
        "english": en,
        "kinyarwanda": rw,
        "type": "sentence",
        "grammar": "sentence",
        "topic": topic,
        "origin": "reference_table",
        "verification": status,
        "sources": [source] if source else [],
        "notes": note or ("Common phrase confirmed on Glosbe." if source else "From the supplied reference table; exact sentence pair not found in online dictionary."),
    })

assert len(entries) == 100, len(entries)
assert sum(1 for e in entries if e["type"] == "word") == 74
assert sum(1 for e in entries if e["type"] == "sentence") == 26

rng = random.Random(20261020)
rng.shuffle(entries)

word_no = 0
sentence_no = 0
for entry in entries:
    if entry["type"] == "word":
        word_no += 1
        entry["id"] = f"w{word_no:03d}"
    else:
        sentence_no += 1
        entry["id"] = f"s{sentence_no:03d}"

# Validate uniqueness and coverage.
assert len({e["id"] for e in entries}) == 100
assert len({(e["type"], e["english"].lower()) for e in entries}) == 100
assert {e["group_id"] for e in entries} == set(groups_by_id)
assert all(e["sources"] for e in entries if e["verification"] == "verified")

verified = sum(1 for e in entries if e["verification"] == "verified")
pending = sum(1 for e in entries if e["verification"] == "native_review_required")

payload = {
    "meta": {
        "name": "Menya Icyongereza vocabulary pilot",
        "version": 1,
        "created": "2026-10-20",
        "direction": "english_to_kinyarwanda",
        "language_from": "en",
        "language_to": "rw",
        "pilot": True,
        "total_entries": len(entries),
        "word_entries": 74,
        "sentence_entries": 26,
        "word_video_batch": 7,
        "sentence_video_batch": 4,
        "selection_seed": 20261020,
        "selection": "Stratified random sample covering all 57 reference groups: two words per word group, twelve extra words chosen by seed, and one sentence pair per sentence group. Entry order was randomized with the same seed.",
        "verification": "Every word was checked against a live Glosbe English-Kinyarwanda page; reverse Glosbe pages were used where the English page did not list the form. Sentence pairs come from the supplied reference table and need native review because exact everyday sentence pairs are not available in the online dictionaries checked.",
        "counts": {
            "verified": verified,
            "native_review_required": pending,
            "words_verified": 74,
            "sentences_verified": 1,
            "sentences_pending": 25,
        },
        "status_values": {
            "verified": "The Kinyarwanda form appears on the cited live Glosbe page.",
            "native_review_required": "Reference-table sentence pair; exact pair not found online; needs native speaker confirmation.",
        },
        "notes": [
            "Word mode remains 7 pairs per video; sentence mode is 4 pairs (8 text lines) per video.",
            "All 57 reference groups are represented once.",
            "Do not expand to the full 1,098 entries until the user reviews this pilot.",
        ],
    },
    "groups": [groups_by_id[g[0]] for g in GROUPS],
    "entries": entries,
}

out = DATA / "vocabulary_pilot.json"
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Human-readable review file, grouped for easier reading.
lines = []
lines.append("# Menya Icyongereza — vocabulary pilot (100 entries)")
lines.append("")
lines.append(f"Generated 2026-10-20. **{verified} verified** and **{pending} pending native review**.")
lines.append("")
lines.append("- Direction: English → Kinyarwanda")
lines.append("- Composition: 74 words + 26 sentence pairs")
lines.append("- Coverage: all 57 reference groups")
lines.append("- Word video batch: 7 pairs; sentence video batch: 4 pairs (8 lines)")
lines.append("- Selection: stratified random sample, seed `20261020`")
lines.append("")
lines.append("Words were checked against live Glosbe pages. Sentence pairs come from the supplied reference table; exact everyday sentence pairs were not available in the online dictionaries checked, so they are marked **native review required**.")
lines.append("")
lines.append("When reviewing, reply with the entry ID and the corrected Kinyarwanda. I will update the JSON and only then continue toward the full database.")
lines.append("")

for group in payload["groups"]:
    group_entries = [e for e in entries if e["group_id"] == group["id"]]
    if not group_entries:
        continue
    lines.append(f"## {group['title']} · {len(group_entries)}")
    if group["notes"]:
        lines.append("")
        lines.append(f"_{group['notes']}_")
    lines.append("")
    lines.append("| ID | English | Kinyarwanda | Type | Grammar | Status | Source | Notes |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for e in group_entries:
        source = e["sources"][0] if e["sources"] else "reference table"
        status = "verified" if e["verification"] == "verified" else "needs native review"
        note = e["notes"] or ""
        if note.startswith("Extra word selected") or note.startswith("From the supplied reference table"):
            note = ""
        lines.append(f"| {e['id']} | {e['english']} | {e['kinyarwanda']} | {e['type']} | {e['grammar']} | {status} | {source} | {note} |")
    lines.append("")

lines.append("## Changes from the supplied reference worth checking")
lines.append("")
lines.append("- `door`: reference `umuryango`; pilot uses verified `urugi`.")
lines.append("- `trousers`: reference `ipantalo`; pilot uses verified `ipantaro`.")
lines.append("- `accountant`: reference `umubaruramari`; pilot uses verified `umucungamari`.")
lines.append("- `honest` / `patient`: pilot uses `inyangamugayo` / `ihangana`, verified through reverse Glosbe entries.")
lines.append("- `sour`: pilot uses the verified root `sharira`; the natural adjective `gisharira` needs confirmation.")
lines.append("- Sound group: pilot uses verified `silent` (`ceceka`) and `noise` (`urusaku`) instead of unverified adjective forms.")
lines.append("- Weather group: pilot uses verified nouns `sun`, `rain`, `wind`; adjective forms `sunny`, `rainy`, `windy` are queued.")
lines.append("- Family group: pilot uses verified `daughter`, `father`, `sister`; grandparent/uncle forms are queued.")
lines.append("- `small`: reference lists `nto`; pilot uses verified `gitoya` (class 7 adjective).")
lines.append("")

lines.append(f"## Pending native review ({pending})")
lines.append("")
lines.append("These are the sentence pairs that need your confirmation. Check the Kinyarwanda wording, tone, and punctuation.")
lines.append("")
lines.append("| ID | Group | English | Kinyarwanda |")
lines.append("|---|---|---|---|")
for e in entries:
    if e["verification"] == "native_review_required":
        lines.append(f"| {e['id']} | {e['group_title']} | {e['english']} | {e['kinyarwanda']} |")
lines.append("")

review = DATA / "vocabulary_pilot_review.md"
review.write_text("\n".join(lines), encoding="utf-8")

print(f"wrote {out}")
print(f"wrote {review}")
print(f"entries={len(entries)} words=74 sentences=26 verified={verified} pending={pending}")
print("groups represented:", len({e['group_id'] for e in entries}))
