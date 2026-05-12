from __future__ import annotations

from pathlib import Path

import pdfplumber


def extract_text(pdf_path: str | Path) -> str:
    """Extract text from a finding-aid PDF, preserving layout.

    The `Box N` markers in the left column of these PDFs are positional, not
    inline, so we keep `layout=True` to retain the column structure. Each page
    is delimited by a marker so the LLM can cite location.
    """
    pdf_path = Path(pdf_path)
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(layout=True) or ""
            pages.append(f"--- PAGE {i} ---\n{text.rstrip()}")
    return "\n\n".join(pages)
