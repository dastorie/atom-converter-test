from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .csv_writer import to_csv
from .llm_extract import extract_records
from .pdf_extract import extract_text
from .validator import build_report


@dataclass
class ConvertOptions:
    parent_slug: str | None = None
    accession: str | None = None
    id_offset: int = 3
    pdf_text: str | None = field(default=None, repr=False)


@dataclass
class ConvertResult:
    accession: str
    csv: str
    report: str
    raw_records: list


def _infer_accession_from_path(pdf_path: Path) -> str:
    """Infer the accession number from filename like 86-4.pdf, 2022-31.pdf, 86_4.pdf."""
    stem = pdf_path.stem
    return stem.replace("_", "-")


def _infer_slug(accession: str) -> str:
    """Best-effort slug from accession: '86-4' -> '86-4'. Caller can override."""
    return re.sub(r"[^a-z0-9-]+", "-", accession.lower()).strip("-")


def convert(pdf_path: str | Path, opts: ConvertOptions | None = None) -> ConvertResult:
    """Convert a finding-aid PDF to an AtoM CSV + validation report.

    This is the single seam a future web UI will wrap; it never touches stdout.
    """
    opts = opts or ConvertOptions()
    pdf_path = Path(pdf_path)
    accession = opts.accession or _infer_accession_from_path(pdf_path)
    parent_slug = opts.parent_slug or _infer_slug(accession)

    pdf_text = opts.pdf_text if opts.pdf_text is not None else extract_text(pdf_path)

    records, usage = extract_records(
        pdf_text=pdf_text,
        accession=accession,
        id_offset=opts.id_offset,
    )

    csv_str = to_csv(records, parent_slug=parent_slug)
    report = build_report(accession=accession, records=records, usage=usage)

    return ConvertResult(
        accession=accession,
        csv=csv_str,
        report=report,
        raw_records=records,
    )
