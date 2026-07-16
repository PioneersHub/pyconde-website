# Transcripts

Speaker-diarized transcripts are imported from a local directory into each talk's `contents.lr`. Once present, transcripts render in a collapsible section on the talk page and are indexed in full by Pagefind, so a search for a phrase that only appears in the recording surfaces the right talk.

## Source layout

Transcripts arrive from the audio-transcription pipeline as one folder per session, keyed by Pretalx code. The exact folder-name shape varies between batches; the importer accepts all of them.

```text
~/Documents/Claude/{year}-transcripts/
  3VYSMS-Darya Petrashka/
    transcript.md              ← only file the importer reads
    transcript.json            ← machine-readable copy (ignored)
    transcript.txt             ← plain text (ignored)
    transcript.speakers.txt    ← speaker-labelled plain text (ignored)
  7EC3UY/                      ← 2024-style, bare code is fine too
  7EC3UY 2/                    ← duplicate sibling, auto-skipped
  processing_summary.txt       ← batch metadata, ignored
```

Code extraction tolerates `-`, `_`, space, or `.` as the separator after the 6-character Pretalx code.

## Format

The importer reads `transcript.md`, strips the YAML front-matter and the redundant title/metadata block that the pipeline prepends, and keeps only the speaker-labelled body.

Body shape — diarized blocks, no identity attribution:

```markdown
**Speaker 1** _[00:08]_

Let's start this talk with an analogy. It all started as…

**Speaker 2** _[19:05]_

Thank you for the talk and yes, we have some time for Q&A…
```

The speaker labels reflect **diarization order**, not identity. For regular talks this resolves to three implicit phases: chair intro → speaker → audience Q&A. Panel sessions warrant a hand-edited `speaker_map` (open item; not yet implemented in the importer).

The rendered transcript page carries a note explaining the labelling so readers don't misread the diarization as misattribution.

## Import a batch

```bash
uv run python utils/import_transcripts.py \
    --year 2024 \
    --src ~/Documents/Claude/2024-transcripts \
    --status auto                                 # default
```

`--year` accepts a four-digit year or `current` for the in-flight edition. `--status` is the value written to `transcript_status:` — `auto` (default), `reviewed`, `official`, or `none`. `--dry-run` previews without writing.

The importer:

1. Builds a `code → talk-folder` map from each talk's `code:` field (necessary after the slug migration, since folder names are slugs not codes).
2. Walks the source directory, dedupes folders that share a Pretalx code (e.g. `ABC123` and `ABC123 2`), and writes the cleaned transcript body into the matching talk's `contents.lr` under `transcript:`, plus `transcript_status` and `transcript_language`.
3. Reports `imported`, `duplicate`, `no-md`, and `orphans` counts at the end.

Re-running the importer is idempotent — the `transcript:` field is upserted, not appended.

## Rendering

`templates/talk.html` shows the transcript inside a `<details>` block, gated on `talk.transcript and not talk.do_not_record`. JSON-LD adds:

- `Event.subjectOf` pointing to the same page's `#transcript` fragment.
- `VideoObject.transcript` set to the same fragment URL.
- `VideoObject.inLanguage` uses `transcript_language` (default `en`).

Pagefind indexes the rendered transcript text as part of the talk page's body. No special markers are needed — the transcript already lives inside the `data-pagefind-body` article.

## Working with `transcript_status`

| Value | Use when |
|---|---|
| `none` | No transcript imported (default field default; no badge rendered) |
| `auto` | Pipeline-generated, unreviewed — default for fresh imports |
| `reviewed` | Volunteer or speaker has read through and silently fixed obvious errors |
| `official` | Speaker has signed off on the wording |

The talk-page summary line renders the status as a tag next to the "Transcript" heading. Setting `reviewed` or `official` does not regenerate the body — only the badge.
