# Finding-Aid → AtoM CSV Converter

Converts University of Regina Archives & Special Collections legacy finding-aid
PDFs into CSVs ready for import into [Access to Memory](https://www.accesstomemory.org/)
(AtoM). Uses the Claude API to do the messy interpretation work.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

## Use

Single PDF:

```bash
python -m converter finding_aids/86-4.pdf --parent-slug margaret-messer-2
```

Produces:

- `output/86-4.csv` — AtoM-ready CSV
- `output/86-4.report.md` — validation report (hierarchy integrity, sequencing,
  box/file coverage, date sanity, GMD sanity, generalNote digest, API cost)

Batch (every `*.pdf` in a directory):

```bash
python -m converter finding_aids/ --batch
```

Options:

- `--parent-slug` — `qubitParentSlug` for top-level Series (existing AtoM Fonds slug)
- `--accession` — override accession inferred from filename
- `--id-offset N` — starting integer `legacyId` (default 3; matches the example CSV
  where 1–2 are reserved for the existing Fonds record)
- `--output-dir DIR` — defaults to `output/`
- `--save-json` — also write the raw hierarchical records for debugging

## Design

- **Layout-aware PDF extraction** (`pdfplumber` with `layout=True`) preserves
  the left-column `Box N` markers and indentation.
- **Strict structured output**: the model is forced to call a `submit_records`
  tool whose JSON schema mirrors the `Record` Pydantic model. No free-text
  parsing.
- **Prompt caching** is on for the system prompt, so the per-PDF cost drops
  significantly across a batch.
- **Lowercase RAD GMDs** (`textual record`, `graphic material`, etc.) per RAD,
  diverging from the example CSV's `Textual records` casing.
- `core.convert(pdf_path, opts) -> ConvertResult` is the one entry point — a
  future FastAPI/Flask web UI wraps it without re-implementing anything.

## Background

See [`docs/original-prompt.md`](docs/original-prompt.md) for the original
brief (including the Gemini system prompt previously used in AI Studio) and
[`docs/initial-plan.md`](docs/initial-plan.md) for the design plan.

## Project layout

```
src/converter/
├── cli.py           # argparse → core.convert()
├── core.py          # pure conversion function (web-UI seam)
├── pdf_extract.py   # pdfplumber wrapper
├── prompts.py       # refined system prompt
├── llm_extract.py   # Anthropic SDK call (tool_use + prompt caching)
├── schema.py        # Pydantic Record model + JSON schema for tool_use
├── csv_writer.py    # Record → AtoM CSV
├── validator.py     # Record list → report.md
└── defaults.py      # URASC defaults + RAD vocabulary
```
