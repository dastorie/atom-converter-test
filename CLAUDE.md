# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

Convert legacy University of Regina archival finding-aid PDFs into Access to
Memory (AtoM) Information Object CSVs. The conversion delegates structural
interpretation to the Claude API — these PDFs were authored over decades by
different people and are too inconsistent for pure parsing.

## Commands

```bash
# Setup
python -m venv .venv && .venv/bin/pip install -e .
cp .env.example .env       # add ANTHROPIC_API_KEY

# Single PDF (the typical path — set --parent-slug to the existing AtoM Fonds slug)
.venv/bin/python -m converter example/86_4.pdf --parent-slug margaret-messer-2

# Batch every *.pdf in a directory
.venv/bin/python -m converter finding_aids/ --batch

# Reference test (calls the live API, ~$0.40)
.venv/bin/pytest -q tests/test_against_example.py
```

Useful flags: `--save-json` (writes the raw record list so CSV generation can
be redone without another API call), `--id-offset N` (default 3),
`--accession N` (override the accession inferred from filename).

## Architecture

`core.convert(pdf_path, opts) -> ConvertResult` is the only seam intended for
reuse. A future web UI wraps that function without re-implementing anything;
`cli.py` does the same wrapping for the terminal.

Pipeline:

1. **`pdf_extract.extract_text()`** — `pdfplumber.extract_text(layout=True)`.
   The left-column `Box N` markers in these PDFs are positional, not inline
   text. Layout mode is required to keep them visible to the model.
2. **`llm_extract.extract_records()`** — streamed call to Sonnet 4.6 with
   prompt caching on the system prompt. The model is forced to call a
   `submit_records` tool whose JSON schema mirrors `schema.Record`, so the
   output is validated structured data, not free text. Raises on
   `stop_reason == "max_tokens"` and on empty record arrays.
3. **`csv_writer.to_csv()`** — flattens records to the 23-column AtoM
   Information Objects schema using `csv.QUOTE_NONNUMERIC`.
4. **`validator.build_report()`** — per-PDF report covering hierarchy
   integrity, identifier sequencing, box/file coverage, date sanity, GMD
   vocabulary, a `generalNote` digest, and token cost.

## Non-obvious decisions to preserve

- **Model is Sonnet 4.6, not Opus.** This is a structured-extraction task;
  Opus was ~5× the cost with no quality gain. If you switch models, update
  the `PRICE_*` constants in `validator.py` too.
- **`MAX_TOKENS = 64000` requires streaming.** The Anthropic SDK refuses
  non-streaming calls that could exceed 10 minutes. Don't move back to
  `client.messages.create()` without dropping max_tokens below ~30k. The
  smallest PDFs work fine at 32k, the largest two (`75_4.pdf`,
  `2022-31.pdf`, `86-72.pdf`) need the 64k headroom.
- **Lowercase RAD GMDs.** The converter emits `"textual record"`, not
  `"Textual records"`. `example/atom_example.csv` uses the capitalized form;
  this is a deliberate divergence to follow RAD spec. If AtoM creates
  duplicate controlled terms on import, swap the values in `GMD_DISPLAY`
  inside `csv_writer.py`.
- **`id_offset=3` by default.** The example CSV starts at legacyId=3 because
  IDs 1–2 are reserved for the existing AtoM Fonds record.
- **`qubitParentSlug` is set only on top-level Series.** It links each Series
  to an existing AtoM Fonds. In `--batch` mode the slug falls back to the
  accession number (e.g. `"86-4"`), which usually will not match the real
  AtoM slug (`"margaret-messer-2"`) — those columns need correcting before
  import.
- **Items are created only when the PDF explicitly enumerates named pieces
  beneath a file heading.** The prompt has worked JSON examples for this.
  Note: `example/atom_example.csv` contains Items (`Small drawing`,
  `Slide of small drawing`) that the human curator added from physical
  inspection of the file — those titles are *not* in the source PDF, so the
  converter should not be expected to reproduce them. Treat the example CSV
  as a format reference, not a per-row ground truth.
- **Date regex in `validator.py` is intentionally permissive.** It composes
  one pattern that accepts comma-joined combinations of RAD-style atoms
  (`1939`, `1920-21`, `[ca. 1950]-2002`, `[1969]`, `[s.d.]`, `n.d.`,
  `September 2014`, `May 29, 2014`). Add new atoms there rather than adding
  parallel patterns.

## Current state (as of initial commit)

The code is complete and tested end-to-end. A full `--batch` run was executed
against all 13 PDFs in `finding_aids/` for ~$2.63 total, producing 1,132
records in `output/` (git-ignored).

**Important:** the prompt and validator were patched *after* that batch run
to make Sonnet less conservative about Item-level records and to accept more
RAD date forms. Only `output/86-4.csv` reflects the patches; the other 12
CSVs were generated with the older prompt and have **zero Items** even where
the PDFs explicitly enumerate named pieces.

Open work for the next session:

1. **Required before AtoM import — `qubitParentSlug` fix.** `--batch` mode
   fell back to inferring the slug from each accession (e.g. `"86-4"`), but
   AtoM Fonds slugs are donor-name-based (e.g. `"margaret-messer-2"`). Every
   top-level Series row in every CSV needs its slug column corrected to
   match the existing AtoM Fonds record. The user needs to gather the real
   slugs from their AtoM instance first; then either re-run each PDF with
   `--parent-slug <slug>` or find/replace the column.
2. **Optional — re-run remaining 12 PDFs with the patched prompt.** Cost
   ~$2.50. Items will likely appear in `86-72.pdf` and the other PDFs that
   have indented named-piece lists under file headings.
3. **Known structural ambiguity (do not "fix" without confirming with the
   user).** Sonnet sometimes interprets a thematic grouping (e.g.
   "Commissions") as `File + Items` where a human curator would prefer
   `Sub-Series + Files`. Both are valid RAD; resolving requires either a
   prompt refinement with examples or post-conversion editing.
4. **Known structural ambiguity (small PDFs).** When a PDF has no Series
   headings (e.g. `95_63.pdf`, parts of `89-32.pdf`), Sonnet promotes each
   top-level item to its own Series rather than synthesizing a "General"
   Series. Either pattern imports fine into AtoM.

## Reference materials

- `example/86_4.pdf` + `example/atom_example.csv` — canonical input/output
  pair. The CSV is partial (~25 of ~75 records) and contains curator
  additions; use it for format reference, not record-count comparison.
- `finding_aids/` — 13 PDFs to convert, ranging from `95_63.pdf` (2 pages,
  ~3 records) to `86-72.pdf` (~349 records).
- `output/` — generated artefacts (`<accession>.csv`, `<accession>.report.md`,
  optional `<accession>.json`). Git-ignored.
- `docs/original-prompt.md` — the brief that kicked off this project,
  including the Gemini system prompt that was used previously in AI Studio.
- `docs/initial-plan.md` — the design plan for this project.
