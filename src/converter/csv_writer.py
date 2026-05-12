from __future__ import annotations

import csv
import io
from typing import Iterable

from .defaults import (
    ACCESS_CONDITIONS,
    CSV_COLUMNS,
    DESCRIPTION_STATUS,
    INSTITUTION_IDENTIFIER,
    LANGUAGE,
    REPOSITORY,
)
from .schema import Record

GMD_DISPLAY = {
    "textual record": "textual record",
    "graphic material": "graphic material",
    "cartographic material": "cartographic material",
    "architectural drawing": "architectural drawing",
    "moving images": "moving images",
    "sound recording": "sound recording",
    "technical drawing": "technical drawing",
    "object": "object",
    "multiple media": "multiple media",
}


def _gmd_field(gmd: list[str]) -> str:
    return " | ".join(GMD_DISPLAY[t] for t in gmd)


def _row_for(record: Record, parent_slug: str | None) -> dict:
    is_top_series = record.level == "Series" and record.pid is None
    is_file_or_item = record.level in ("File", "Item")
    return {
        "legacyId": record.id,
        "parentId": "" if record.pid is None else record.pid,
        "qubitParentSlug": parent_slug if is_top_series and parent_slug else "",
        "identifier": record.code,
        "accessionNumber": record.accession,
        "title": record.title,
        "radGeneralMaterialDesignation": _gmd_field(record.gmd),
        "levelOfDescription": record.level,
        "repository": REPOSITORY,
        "extentAndMedium": record.extent or ("1 file" if is_file_or_item else ""),
        "archivalHistory": record.archival_history or "",
        "scopeAndContent": record.scope or "",
        "physicalCharacteristics": record.physical_characteristics or "",
        "acquisition": record.acquisition or "",
        "arrangement": record.arrangement or "",
        "language": LANGUAGE,
        "locationOfOriginals": record.loc,
        "accessConditions": ACCESS_CONDITIONS,
        "accruals": record.accruals or "",
        "institutionIdentifier": INSTITUTION_IDENTIFIER,
        "descriptionStatus": DESCRIPTION_STATUS,
        "generalNote": record.note or "",
        "eventDates": record.dates or "",
    }


def to_csv(records: Iterable[Record], parent_slug: str | None) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=list(CSV_COLUMNS),
        quoting=csv.QUOTE_NONNUMERIC,
        lineterminator="\n",
    )
    writer.writeheader()
    for record in records:
        writer.writerow(_row_for(record, parent_slug))
    return buf.getvalue()
