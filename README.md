# Menya Vocab Video

Generates a 1080x1920 (9:16) Facebook/Reels-ready video that looks like the
**Menya Icyongereza App** screen:

- the app's phone mockup as the full-frame background
- **word mode:** 7 English words with their Kinyarwanda translations
- **sentence mode:** 4 English/Kinyarwanda sentence pairs (8 text lines)
- the app's chunky white cards, green number badges and dotted leaders
- an edge-to-edge yellow promo banner: *Iyi app yitwa* **"Menya Icyongereza
  App"** *wayisanga kuri Play Store yigisha icyongereza* (the app name is
  highlighted in green)

| Word mode | Sentence mode |
|---|---|
| ![word preview](preview/word_01.png) | ![sentence preview](preview/sentence_01.png) |

Output: `output/<content_id>.mp4` — H.264, yuv420p, 30 fps, AAC stereo
audio, `+faststart`. One of the four tracks in `assets/song/` is picked at
random per run (same behaviour as the perime.rw videos). Local samples:
[`output/word_01.mp4`](output/word_01.mp4) and
[`output/sentence_01.mp4`](output/sentence_01.mp4).

The current data set is the **100-entry pilot**:

- `data/vocabulary_pilot.json` — 100 flat entries (74 words + 26 sentence pairs)
- `data/vocabulary_pilot_videos.json` — 10 complete word videos, 6 complete
  sentence videos, plus a 6-entry remainder bucket
- `data/chunks/vocabulary_chunk_01.json` — the 16 complete videos as one
  rotation chunk (94 video entries)
- `data/rotation_manifest.json` — ordered `content_0001`…`content_0016` jobs
  and the chunk map
- `data/rotation_state.json` — remembers the next content and the cycle
- `data/vocabulary_pilot_review.md` and
  `data/vocabulary_pilot_videos_review.md` — human-readable review tables

The pilot's 4 leftover words and 2 leftover sentence pairs are kept in
`remainder`; they do not fill a complete 7-word or 4-pair video. The full
1,098 build should use counts that divide evenly (for example 854 words +
244 sentence pairs) so every entry lands in a complete video.

**Verification status:** 75 entries are checked against live Glosbe pages.
The other 25 sentence pairs are marked `native_review_required`; they are not
claimed as online-verified until a native speaker reviews them.

## Rotation (one video per run)

Every workflow run picks exactly one content item and advances the state:
`content_0001` → `content_0002` → … → `content_0016` → `content_0001` again
(in a new cycle). The state is committed only after the video renders
successfully, so a failed run repeats the same content instead of skipping it.

- `scripts/rotation.py next` peeks at the next job and writes a one-job batch
  for `generate.py`; it does not change the state.
- `scripts/rotation.py advance` runs after encoding and moves to the next job.
- `scripts/rotation.py select --content-id content_0005` replays one specific
  content without touching the state.
- `scripts/rotation.py reset` starts again at `content_0001`, cycle 1.
- `scripts/rotation.py status` shows the remembered position.

## Run it on GitHub

1. Open the repo's **Actions** tab → **Menya Vocab Video** → **Run workflow**.
2. Leave every field as-is.
3. Press **Run workflow**.

The run automatically renders the next `content_XXXX`, commits the mp4, its
preview frame and the updated `data/rotation_state.json`, and attaches them as
the `menya-vocab-video` artifact. The next run starts with the following
content. No typing is needed.

To replay one specific video, set `content_id` to an id from
`data/rotation_manifest.json` (for example `content_0001`). A replay does not
advance the rotation state.

## Inputs

| Input | Meaning | Default |
|---|---|---|
| `content_id` | Optional replay id. Empty = automatically pick the next content | empty |
| `note` | Yellow banner text. The `brand` text is highlighted in green | the Play Store hook |
| `brand` | Text to highlight green inside `note` | `Menya Icyongereza App` |
| `duration` | Video length in seconds | `6` |

## Chunk files and the manifest

The full database is split into small chunk files so no single file has to hold
all 1,098 entries. The builder targets **300 entries per chunk** by default:

```powershell
python scripts/build_chunks.py `
  --input data/vocabulary_all.json `
  --out-dir data/chunks `
  --manifest data/rotation_manifest.json `
  --state data/rotation_state.json `
  --chunk-size 300
```

A chunk file holds complete video jobs only, so the chunks stay near the 300
entry target rather than splitting a 7-word or 4-pair video across files. The
manifest lists every `content_0001`… job and points back to its chunk file and
job index.

Each job looks like this:

```json
{
  "id": "content_0001",
  "content_number": 1,
  "mode": "word",
  "pair_count": 7,
  "entry_start": 1,
  "entry_end": 7,
  "pairs": [
    {
      "english": "secretary",
      "kinyarwanda": "umunyamabanga",
      "verification": "verified"
    }
  ]
}
```

- Word jobs: `mode: "word"`, 7 pairs.
- Sentence jobs: `mode: "sentence"`, 4 pairs.
- A final partial job is allowed only when a database does not divide evenly;
  it is labelled with its real pair count and its cards are centred. The
  conversion command above keeps leftovers in `remainder` unless
  `--allow-partial` is passed.
- Directions are always English → Kinyarwanda.
- `generate.py` accepts 1–7 word pairs or 1–4 sentence pairs, so a short final
  job still renders instead of being dropped.

## Run locally

Requires Python 3.10+, Pillow and ffmpeg.

```powershell
pip install -r requirements.txt

# Pick the next content (writes a temporary one-job batch)
python scripts/rotation.py next `
  --out data/.current_job.json `
  --pending data/.rotation_pending.json

# Render its preview and mp4
python generate.py --batch-json data/.current_job.json --video

# Advance only after the render succeeded
python scripts/rotation.py advance --pending data/.rotation_pending.json
```

You can still render one of the approved pilot batches directly:

```powershell
# word mode (7 pairs)
python generate.py --batch-json data/vocabulary_pilot_videos.json --video-id word_01 --video

# sentence mode (4 pairs / 8 lines)
python generate.py --batch-json data/vocabulary_pilot_videos.json --video-id sentence_01 --video
```

Custom content without the batch JSON still works:

```powershell
# word mode, up to 7 pairs
python generate.py --pairs "Book=Igitabo; Water=Amazi"

# sentence mode, up to 4 pairs
python generate.py --mode sentence --pairs "Where does it hurt?=Uri kubabara he?; He cooks food.=Ateka ibiryo; I drink tea.=Nnywa icyayi; Good morning.=Mwaramutse"
```

## How the layout works

The background is 720x1280, so everything is drawn on a 1080x1920 canvas
(1.5x) to keep text sharp. The usable app body was measured from the mockup:
x 32–685, y 183–1115. The rows use that area with 36 px side padding; the
promo banner runs edge-to-edge and sits on the tab bar divider.

### Word mode

- Section label: `AMAGAMBO 7 Y'ICYONGEREZA`, uppercase, tracked, muted.
- 7 rows: white card, 2 px `#E5E5E5` border, hard offset shadow, 3D green
  number badge, English in Poppins ExtraBold, Kinyarwanda in Poppins Bold
  green, dotted leader between them.
- Long words shrink automatically (46→26 px English, 42→24 px Kinyarwanda)
  so a pair can never overflow the card.
- A short final job with fewer than 7 words is centred vertically instead of
  leaving all the empty space at the bottom.

### Sentence mode

- Section label: `INTERURO 4 Z'ICYONGEREZA`, uppercase, tracked, muted.
- 4 cards, one per pair. Each card stacks the English sentence above the
  Kinyarwanda sentence, so one pair always reads as two lines.
- English is Poppins ExtraBold dark; Kinyarwanda is Poppins Bold green.
- Text wraps and shrinks (46→22 px) until both languages fit inside the card.
- Number badges, borders and shadows match the word cards.
- A short final job with fewer than 4 pairs is centred vertically.

### Promo banner

- Edge-to-edge `#FFF9C4` banner with square corners, no side or top border,
  a single black rule along the bottom, and the text set on two lines at the
  largest size that fits (8 px side padding), brand name highlighted in green.
- Rows are sized from the space left above the promo banner, so the layout
  stays balanced without manual tweaking.

## Customizing

| What | Where |
|---|---|
| Colors | token block at the top of `generate.py` (`GREEN`, `BORDER`, `YELLOW`, …) |
| Fonts | `assets/fonts/` (Poppins, OFL — see `OFL.txt`) |
| Background | `assets/img/background.png` (keep the same 720x1280 screen position, or update `BODY`) |
| Music | drop `.mp3/.m4a/.wav` files into `assets/song/`; one is picked at random. Empty = silent |
| Video length | `--duration` / the `duration` input |
| Video content | edit `data/vocabulary_pilot_videos.json` or `data/vocabulary_all.json`, then rebuild chunks with `scripts/build_chunks.py` |
| Rotation order | `data/rotation_manifest.json` (generated); reset with `scripts/rotation.py reset` |

## Files

```
generate.py                     renderer + ffmpeg encoder
scripts/build_chunks.py         splits entries into video-job chunk files
scripts/rotation.py             next/advance/select/status/reset state machine
data/vocabulary_pilot.json      flat 100-entry database
data/vocabulary_pilot_videos.json   video-ready word/sentence batches
data/chunks/*.json              rotation chunk files (complete videos only)
data/rotation_manifest.json     ordered content ids + chunk map
data/rotation_state.json        remembered next content and cycle
data/*_review.md                human-readable review tables
scripts/build_pilot.py          builds the flat pilot
scripts/build_video_batches.py  builds the video batches
assets/img/background.png       phone mockup background
assets/fonts/Poppins-*.ttf      bundled fonts (OFL)
assets/song/                    optional music
preview/*.png                   rendered frames
output/*.mp4                    generated videos
.github/workflows/menyavocab.yml
```

## Notes

- 9:16 — ready for Facebook Reels, Stories and feed.
- A track from `assets/song/` is mixed automatically; if the folder is empty,
  the video is silent.
- Poppins is licensed under the SIL Open Font License 1.1
  (`assets/fonts/OFL.txt`).
- The workflow is serialized with a concurrency group, so two runs cannot pick
  the same content. The state is committed only after a successful render.
- The full 1,098-entry database is the next build step; this repo currently
  ships the reviewed 100-entry pilot. The chunk builder defaults to 300 entries
  per file. A clean split of 854 words + 244 sentence pairs gives 122 word
  videos + 61 sentence videos = 183 contents in roughly four chunk files.
