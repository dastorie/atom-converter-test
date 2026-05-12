# Finding Aid → AtoM CSV Converter

## Context

The University of Regina Archives & Special Collections has 13 legacy finding aids (PDFs in `finding_aids/`) that need to be ingested into Access to Memory (AtoM). The PDFs share a rough structure — title page, optional biographical note, optional table of contents, then a Series → Sub-Series → File listing with `Box N` markers in the left column — but the formatting is genuinely inconsistent across decades of authorship (compare the 2-page `95_63.pdf` against the 12-box `75_4.pdf`). A Gemini system prompt already produces usable JSON in AI Studio, and one CSV (`example/atom_example.csv`, generated from `example/86_4.pdf`) imports successfully into AtoM.

We want a repeatable Python CLI that takes a PDF in and emits an AtoM-ready CSV, designed so a web UI can be added later. The Claude API replaces the manual AI-Studio copy/paste step. End state: `python -m converter finding_aids/86-4.pdf` produces `output/86-4.csv` plus `output/86-4.report.md`.

## Design decisions (confirmed)

1. **Stack**: Python CLI + Claude API (`anthropic` SDK). Core extraction kept as pure functions so a FastAPI/Flask layer can wrap them later — no Click/CLI imports inside `core/`.
2. **GMD casing**: lowercase per RAD (`textual record`, `graphic material`, etc.). The example CSV uses `Textual records` — we are deliberately diverging from that to be RAD-compliant. Confirm AtoM term-matching behavior on the first import; if AtoM creates duplicate terms, revisit.
3. **Item granularity**: Item records only when the PDF explicitly enumerates pieces under a file (e.g. `Small drawing` and `Slide of small drawing` under `Art` in 86-4). Otherwise stop at File.
4. **Outputs**: per-PDF `output/<accession>.csv` plus `output/<accession>.report.md`. No combined CSV, no intermediate JSON committed by default (a `--save-json` flag is cheap to add for debugging).

## Architecture

```
finding-aid-converter2/
├── finding_aids/                  (existing — input PDFs)
├── example/                       (existing — reference input + expected output)
├── output/                        (generated)
├── src/converter/
│   ├── __init__.py
│   ├── cli.py                     # entry: argparse → core.convert()
│   ├── core.py                    # convert(pdf_path, opts) -> (csv_str, report_str)
│   ├── pdf_extract.py             # pdfplumber → text + light layout hints
│   ├── llm_extract.py             # anthropic SDK call, prompt caching
│   ├── prompts.py                 # system prompt (refined Gemini prompt)
│   ├── schema.py                  # pydantic models: Record, Hierarchy
│   ├── csv_writer.py              # hierarchy → AtoM CSV rows
│   ├── validator.py               # integrity checks → report.md
│   └── defaults.py                # URASC, "en", "Open to Researchers", etc.
├── tests/
│   └── test_against_example.py    # 86-4.pdf → CSV ≈ atom_example.csv
├── pyproject.toml
├── .env.example                   # ANTHROPIC_API_KEY
└── README.md
```

The `core.convert()` function is the single seam a future web UI will call: it accepts a path (or bytes), returns CSV + report strings, and never touches stdout/stderr or `sys.argv`.

## Module responsibilities

### `pdf_extract.py`
- Use `pdfplumber` with `extract_text(layout=True)` to preserve indentation and the left-column `Box N` markers — these are positional, not textual, in several PDFs.
- Return a single text blob with `--- PAGE N ---` markers between pages so the LLM can cite location.
- No structural parsing here — we deliberately let the LLM do the messy interpretation work; trying to detect bold/headings via font metadata is brittle across these PDFs (75_4 and 86-72 don't use bold at all).

### `prompts.py` — refined system prompt
Built on the existing Gemini prompt with these adjustments:

- Begin extraction at the **Series** level; no Fonds/Accession record.
- Hierarchy rules: Series `pid=null`; everything else `pid=` direct parent's `id`. Sequential integer `id` starting at a configurable offset (default `3` — matches the example CSV where IDs 1–2 are reserved for the existing AtoM Fonds record).
- `code` (identifier): `S{n}` for Series, `SB{n}` for Sub-Series, `F{n}` for File, `I{n}` for Item. Counters reset per type per accession (per the example).
- `loc` format: `"Basement, {accession}, Box {n}, File {n}"`. For Series/Sub-Series that span boxes, emit `"Basement, {accession}, Box {a}, Box {b}"` (matches example S2).
- **File numbering**: sequential within each box, starting at 1 each new box, since most PDFs don't print explicit file numbers. Prompt must tell the model this.
- GMD vocabulary: lowercase RAD only — `textual record`, `graphic material`, `cartographic material`, `architectural drawing`, `moving images`, `sound recording`, `technical drawing`, `object`, `multiple media`. Multi-value joined with ` | `.
- Date formats: `YYYY`, `YYYY-YYYY`, `[ca. YYYY]`, `[YYY-]`, `[s.d.]`, or comma-joined inclusive lists (`"1920-21, 1926, 1939-43"`).
- Defaults injected by the prompt: `repository="University of Regina Archives & Special Collections"`, `language="en"`, `accessConditions="Open to Researchers"`, `institutionIdentifier="URASC"`, `descriptionStatus="Draft"`.
- Ambiguous fragments → `generalNote`, never discard.
- **Output contract**: a single flat JSON array of records, each with id/pid set. Enforced via Claude's `tool_use` with a JSON schema (most reliable structured-output path on the Anthropic SDK).

System prompt is cached (`cache_control: {"type": "ephemeral"}`) so the 13 PDFs share one cache entry.

### `llm_extract.py`
- Model: `claude-opus-4-7` (accuracy matters more than speed on a 13-doc batch).
- Sends extracted PDF text as the user message; system prompt does the heavy lifting.
- Uses tool_use with a `submit_records` tool whose input schema matches `schema.Record`. Forces the model to return validated JSON.
- For PDFs whose text exceeds ~150k tokens (none of the current 13 should — the largest is `75_4.pdf` at ~687KB binary, well under context), fall back to a two-pass strategy: first call extracts the Series outline, second call enriches each Series in parallel. Implement the simple path first; add chunking only if a real PDF hits the limit.
- Surfaces token usage so the report can show per-PDF cost.

### `schema.py`
Pydantic `Record` model mirroring the 23 AtoM columns plus the LLM-internal `id`/`pid`/`qubitParentSlug` fields. Validators:
- `code` matches `^(S|SB|F|I)\d+$`
- `levelOfDescription` ∈ {Series, Sub-Series, File, Item}
- `radGeneralMaterialDesignation` tokens ∈ the lowercase RAD set
- `loc` matches the `Basement, ...` pattern

### `csv_writer.py`
- Maps `Record` → the 23 AtoM column names in `example/atom_example.csv` header order.
- Emits `legacyId` from the model's `id`, `parentId` from `pid` (blank for Series), `qubitParentSlug` only on top-level Series (CLI-supplied, e.g. `--parent-slug margaret-messer-2`).
- Uses `csv.writer` with `QUOTE_MINIMAL` to match the example's quoting style.

### `validator.py` → `output/<accession>.report.md`
Per-PDF report listing:
- **Hierarchy integrity**: every non-Series record's `parentId` resolves; no cycles.
- **Identifier sequencing**: S1..Sn / F1..Fn / I1..In are contiguous with no gaps.
- **Box/file coverage**: every record has a Box number; warn on duplicate `(box, file)` pairs.
- **Date sanity**: dates not matching the allowed RAD patterns flagged for review.
- **GMD sanity**: any non-vocabulary terms flagged.
- **`generalNote` digest**: every record where the LLM punted information into `generalNote`, so the archivist can sweep for misclassified fields.
- **API stats**: input/output tokens, cache hits, estimated cost.

### `cli.py`
```
python -m converter <pdf> [--parent-slug SLUG] [--accession N]
                          [--id-offset 3] [--output-dir output/]
                          [--save-json] [--dry-run]
python -m converter --batch finding_aids/   # processes all PDFs
```
`--accession` and `--parent-slug` override what the LLM infers, for the cases where the slug already exists in AtoM and must match exactly.

## Critical files / references

- **Input examples** (read these in the implementation):
  - `/Users/dalestorie/Code/finding-aid-converter2/example/86_4.pdf` — canonical input.
  - `/Users/dalestorie/Code/finding-aid-converter2/example/atom_example.csv` — canonical output (note: this output uses capitalized GMDs; our converter will emit lowercase by design).
- **Format variation samples** to consult when refining the prompt:
  - `finding_aids/95_63.pdf` — small (2 pages, no ToC, no bio).
  - `finding_aids/86-72.pdf` — medium, has ToC, tabular Box layout.
  - `finding_aids/75_4.pdf` — large, deep numeric IDs (e.g. `806.1-1`), photo catalog with metadata columns.
- **External docs** (already researched, no need to re-fetch):
  - AtoM CSV import: https://www.accesstomemory.org/en/docs/2.6/user-manual/import-export/csv-import/
  - AtoM CSV templates: https://wiki.accesstomemory.org/Resources/CSV_templates

## Verification

1. **Reference-PDF test** (`tests/test_against_example.py`): run the converter on `example/86_4.pdf` with `--parent-slug margaret-messer-2 --id-offset 3 --accession 86-4`. Assert that:
   - row count matches `atom_example.csv` ± minor expected differences,
   - every `(code, title, eventDates)` triple from the example appears in our output,
   - every Series has `parentId` blank and the right `qubitParentSlug`,
   - every File has the expected `Box N, File N` in `loc`,
   - GMD terms are lowercase (this is the one expected diff vs. the example).
2. **Validation reports**: run against the 3 sampled PDFs (`95_63`, `86-72`, `75_4`) and confirm each `report.md` shows zero hierarchy errors and a manageable `generalNote` digest.
3. **Dry-run import**: import one generated CSV into a staging AtoM instance, confirm parent linking via `qubitParentSlug` works and GMD terms resolve. If GMD terms fail to match controlled vocabulary on import, decide whether to switch the converter to the capitalized variant.
4. **Batch run**: `python -m converter --batch finding_aids/`. Spot-check 2–3 reports for plausibility; record total API spend.
