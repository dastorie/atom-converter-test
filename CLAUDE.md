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
