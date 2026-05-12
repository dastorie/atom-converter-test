from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Iterable

from .defaults import RAD_GMD_TERMS
from .llm_extract import Usage
from .schema import Record

_MONTH = (
    r"(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)"
)
_YEAR_ATOM = (
    r"(?:"
    r"\d{4}(?:-\d{2,4})?"            # 1939 or 1920-21 or 1920-1945
    r"|\[\d{4}\](?:-\d{4})?"         # [1969] or [1969]-1985
    r"|\[ca\.\s*\d{4}\](?:-\d{4})?"  # [ca. 1950] or [ca. 1950]-2002
    r"|\[\d{3}-\]"                   # [194-]
    r"|\[s\.d\.\]"                   # [s.d.]
    r"|n\.d\."                       # n.d.
    rf"|{_MONTH}\s+\d{{1,2}},\s+\d{{4}}"  # May 29, 2014
    rf"|{_MONTH}\s+\d{{4}}"          # September 2014
    r")"
)
DATE_PATTERNS = [re.compile(rf"^{_YEAR_ATOM}(?:,\s*{_YEAR_ATOM})*$")]

BOX_RE = re.compile(r"Box\s+(\d+)")
FILE_RE = re.compile(r"File\s+(\d+)")

# Pricing per 1M tokens for claude-sonnet-4-6 (approximate; update as needed).
PRICE_INPUT_PER_M = 3.0
PRICE_OUTPUT_PER_M = 15.0
PRICE_CACHE_WRITE_PER_M = 3.75
PRICE_CACHE_READ_PER_M = 0.30


def _is_date_ok(d: str) -> bool:
    if not d:
        return True
    return any(p.match(d.strip()) for p in DATE_PATTERNS)


def _hierarchy_issues(records: list[Record]) -> list[str]:
    ids = {r.id for r in records}
    issues: list[str] = []
    for r in records:
        if r.level == "Series" and r.pid is not None:
            issues.append(f"{r.code} ({r.title}): Series must have null parent, got pid={r.pid}")
        if r.level != "Series" and r.pid is None:
            issues.append(f"{r.code} ({r.title}): non-Series record missing parent")
        if r.pid is not None and r.pid not in ids:
            issues.append(f"{r.code} ({r.title}): parent id {r.pid} not found")
        if r.pid == r.id:
            issues.append(f"{r.code}: self-referential parent")
    return issues


def _sequencing_issues(records: list[Record]) -> list[str]:
    by_prefix: dict[str, list[int]] = defaultdict(list)
    for r in records:
        prefix = "SB" if r.code.startswith("SB") else r.code[0]
        n = int(r.code[len(prefix):])
        by_prefix[prefix].append(n)
    issues: list[str] = []
    for prefix, nums in by_prefix.items():
        nums_sorted = sorted(nums)
        expected = list(range(1, len(nums_sorted) + 1))
        if nums_sorted != expected:
            issues.append(
                f"{prefix} identifiers not contiguous 1..{len(nums_sorted)}: {nums_sorted}"
            )
        dupes = [n for n, c in Counter(nums).items() if c > 1]
        if dupes:
            issues.append(f"{prefix} identifiers duplicated: {dupes}")
    return issues


def _box_file_issues(records: list[Record]) -> list[str]:
    issues: list[str] = []
    seen: dict[tuple[str, str], str] = {}
    for r in records:
        if r.level not in ("File", "Item"):
            continue
        box = BOX_RE.search(r.loc)
        file_num = FILE_RE.search(r.loc)
        if not box:
            issues.append(f"{r.code} ({r.title}): no Box in loc {r.loc!r}")
            continue
        if r.level == "File" and not file_num:
            issues.append(f"{r.code} ({r.title}): no File in loc {r.loc!r}")
            continue
        if r.level == "File" and file_num:
            key = (box.group(1), file_num.group(1))
            if key in seen:
                issues.append(
                    f"{r.code}: duplicate (Box {key[0]}, File {key[1]}) "
                    f"shared with {seen[key]}"
                )
            else:
                seen[key] = r.code
    return issues


def _date_issues(records: list[Record]) -> list[str]:
    issues: list[str] = []
    for r in records:
        if r.dates and not _is_date_ok(r.dates):
            issues.append(f"{r.code} ({r.title}): unusual date {r.dates!r}")
    return issues


def _gmd_issues(records: list[Record]) -> list[str]:
    issues: list[str] = []
    for r in records:
        bad = [t for t in r.gmd if t not in RAD_GMD_TERMS]
        if bad:
            issues.append(f"{r.code} ({r.title}): non-RAD GMD {bad}")
    return issues


def _notes_digest(records: list[Record]) -> list[str]:
    return [
        f"- **{r.code}** ({r.title}): {r.note}"
        for r in records
        if r.note
    ]


def _cost(usage: Usage) -> float:
    return (
        usage.input_tokens * PRICE_INPUT_PER_M
        + usage.output_tokens * PRICE_OUTPUT_PER_M
        + usage.cache_creation_input_tokens * PRICE_CACHE_WRITE_PER_M
        + usage.cache_read_input_tokens * PRICE_CACHE_READ_PER_M
    ) / 1_000_000


def _section(title: str, items: Iterable[str]) -> str:
    items = list(items)
    if not items:
        return f"## {title}\n\nNo issues.\n"
    body = "\n".join(f"- {x}" for x in items)
    return f"## {title}\n\n{body}\n"


def build_report(
    accession: str,
    records: list[Record],
    usage: Usage,
) -> str:
    parts = [f"# Validation report — accession {accession}\n"]
    parts.append(f"Records emitted: **{len(records)}**\n")

    parts.append(_section("Hierarchy integrity", _hierarchy_issues(records)))
    parts.append(_section("Identifier sequencing", _sequencing_issues(records)))
    parts.append(_section("Box / file coverage", _box_file_issues(records)))
    parts.append(_section("Date sanity", _date_issues(records)))
    parts.append(_section("GMD sanity", _gmd_issues(records)))

    notes = _notes_digest(records)
    if notes:
        parts.append("## generalNote digest\n\n" + "\n".join(notes) + "\n")
    else:
        parts.append("## generalNote digest\n\nNo records used generalNote.\n")

    parts.append(
        "## API usage\n\n"
        f"- input tokens: {usage.input_tokens}\n"
        f"- output tokens: {usage.output_tokens}\n"
        f"- cache creation: {usage.cache_creation_input_tokens}\n"
        f"- cache read: {usage.cache_read_input_tokens}\n"
        f"- estimated cost: ${_cost(usage):.4f}\n"
    )
    return "\n".join(parts)
