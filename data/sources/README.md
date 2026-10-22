# Source cache

These files let the video database be generated deterministically without
re-downloading large data on every workflow run.

## English frequency list

- File: `en_frequency_50k.txt`
- Source: `https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/en/en_50k.txt`
- Retrieved: 2026-10-21
- Size: 622,749 bytes (50,000 ranked English words)
- Use: rank candidate words so the videos teach common, useful vocabulary first.

## English → Kinyarwanda dictionary

- File: `menya_dictionary.json`
- Source: the local `Menya Icyongereza App` assets
  (`app/src/main/assets/dict/*.json`).
- Provenance: digitized Iriza 2006 and Cox–Adamson–Teusink 1957 word pairs,
  as audited by the app's `translation-review` track. Only bare word pairs are
  cached here; the reference books are not included.
- Retrieved: 2026-10-21
- Size: 19,849 unique pairs (12,677 unique English headwords).
- Use: translation cache for the generated videos. Generated pairs are marked
  `verification: "dictionary"` and carry this provenance; they are not claimed
  as individually live-checked Glosbe entries.

## Bilingual sentence corpus

- File: `en_rw_corpus.tsv`
- Source: the local `BIBLE APP` assets
  (`D:\kinyarwnda\BIBLE APP\Assets\kinyarwanda-english-corpus.tsv`).
- Size: 1,181,550 bytes, 14,411 English/Kinyarwanda sentence pairs.
- Use: score dictionary translation candidates by whether the English word and
  the Kinyarwanda candidate actually co-occur in a sentence. This corrects
  common dictionary sense errors (for example *capital* -> *umurwa mukuru*
  instead of *ubukungu*) without adding new downloads.
- Sentence track: the same corpus supplies the 72 curated pairs behind the
  separate 12-video sentence rotation (5 or 6 pairs per video, chosen by the
  layout planner). Candidate pairs are length/grammar/alignment filtered,
  orthography-normalized, and marked `verification: "corpus"` (not
  native-reviewed). See `data/vocabulary_sentences_review.md` for the full list
  and alignment scores.

## Curriculum seed

- File: `curriculum_words.json`
- Source: the local `Menya Icyongereza App` asset
  (`app/src/main/assets/curriculum.json`).
- The app owner confirmed the curriculum is OK; its word pairs are used as the
  high-confidence seed for the generated database.

## Data budget

The full cache is about 4.2 MB on disk. No dictionary is downloaded per workflow run.
The workflow only renders from the committed database, so GitHub Actions needs
no content-download step.
