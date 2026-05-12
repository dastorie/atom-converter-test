"""End-to-end check: run the converter against example/86_4.pdf and compare
the output against the known-good example/atom_example.csv.

This test calls the real Claude API and is skipped without ANTHROPIC_API_KEY.
Run with:    pytest -q tests/test_against_example.py
"""
from __future__ import annotations

import csv
import io
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from converter.core import ConvertOptions, convert

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_PDF = REPO_ROOT / "example" / "86_4.pdf"
EXAMPLE_CSV = REPO_ROOT / "example" / "atom_example.csv"


def _parse_csv(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


@pytest.fixture(scope="module")
def result():
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    return convert(
        EXAMPLE_PDF,
        ConvertOptions(
            accession="86-4",
            parent_slug="margaret-messer-2",
            id_offset=3,
        ),
    )


def test_hierarchy_is_sound(result):
    rows = _parse_csv(result.csv)
    ids = {r["legacyId"] for r in rows}
    for r in rows:
        if r["levelOfDescription"] == "Series":
            assert r["parentId"] == "", f"{r['identifier']} should have empty parentId"
            assert r["qubitParentSlug"] == "margaret-messer-2"
        else:
            assert r["parentId"] in ids, f"{r['identifier']} parent {r['parentId']!r} not found"
            assert r["qubitParentSlug"] == ""


def test_first_record_is_series(result):
    rows = _parse_csv(result.csv)
    assert rows[0]["levelOfDescription"] == "Series"
    assert rows[0]["identifier"].startswith("S")


def test_loc_format(result):
    rows = _parse_csv(result.csv)
    for r in rows:
        assert r["locationOfOriginals"].startswith("Basement, 86-4"), r


def test_gmd_lowercase(result):
    rows = _parse_csv(result.csv)
    for r in rows:
        gmd = r["radGeneralMaterialDesignation"]
        for term in gmd.split(" | "):
            assert term == term.lower(), f"{r['identifier']}: GMD {term!r} not lowercase"


def test_known_titles_present(result):
    """A handful of titles from atom_example.csv that we expect to also appear."""
    expected_titles = {
        "Education",
        "School Commencement Programs",
        "School Reports and Teachers Diplomas",
        "Commissions",
        "Correspondence",
    }
    rows = _parse_csv(result.csv)
    got_titles = {r["title"] for r in rows}
    missing = expected_titles - got_titles
    assert not missing, f"missing expected titles: {missing}"
