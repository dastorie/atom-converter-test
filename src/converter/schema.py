from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .defaults import LEVELS_OF_DESCRIPTION, RAD_GMD_TERMS

CODE_PATTERN = re.compile(r"^(S|SB|F|I)\d+$")
LOC_PATTERN = re.compile(r"^(Basement|Vault), .+")


class Record(BaseModel):
    """One row in the AtoM hierarchy. The LLM emits these in a flat list."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(description="Sequential integer id, unique within this PDF.")
    pid: Optional[int] = Field(
        default=None,
        description="Parent record id. null for top-level Series.",
    )
    code: str = Field(description="Identifier: S{n}, SB{n}, F{n}, or I{n}.")
    level: Literal["Series", "Sub-Series", "File", "Item"] = Field(
        description="Level of description."
    )
    title: str
    accession: str = Field(description="Accession number, e.g. '86-4'.")
    gmd: list[str] = Field(
        default_factory=lambda: ["textual record"],
        description="Lowercase RAD general material designations.",
    )
    extent: Optional[str] = Field(default=None, description="extentAndMedium")
    scope: Optional[str] = Field(default=None, description="scopeAndContent")
    arrangement: Optional[str] = None
    archival_history: Optional[str] = None
    physical_characteristics: Optional[str] = None
    acquisition: Optional[str] = None
    accruals: Optional[str] = None
    loc: str = Field(
        description="Basement, {accession}, Box {n}[, File {n}] location string."
    )
    dates: Optional[str] = Field(default=None, description="eventDates per RAD.")
    note: Optional[str] = Field(default=None, description="generalNote.")

    @field_validator("code")
    @classmethod
    def _code_pattern(cls, v: str) -> str:
        if not CODE_PATTERN.match(v):
            raise ValueError(f"code {v!r} must match ^(S|SB|F|I)\\d+$")
        return v

    @field_validator("gmd")
    @classmethod
    def _gmd_terms(cls, v: list[str]) -> list[str]:
        if not v:
            return ["textual record"]
        bad = [t for t in v if t not in RAD_GMD_TERMS]
        if bad:
            raise ValueError(f"non-RAD GMD terms: {bad}")
        return v

    @field_validator("loc")
    @classmethod
    def _loc_pattern(cls, v: str) -> str:
        if not LOC_PATTERN.match(v):
            raise ValueError(
                f"loc {v!r} must start with 'Basement, ' or 'Vault, '"
            )
        return v

    @field_validator("level")
    @classmethod
    def _level_matches_code(cls, v: str, info) -> str:
        code = info.data.get("code")
        if code:
            prefix = {
                "S": "Series",
                "SB": "Sub-Series",
                "F": "File",
                "I": "Item",
            }
            expected_prefix = {
                "Series": "S",
                "Sub-Series": "SB",
                "File": "F",
                "Item": "I",
            }[v]
            actual_prefix = "SB" if code.startswith("SB") else code[0]
            if actual_prefix != expected_prefix:
                raise ValueError(
                    f"code prefix {actual_prefix!r} does not match level {v!r}"
                )
            _ = prefix  # silence unused-name warning
        return v


def to_tool_input_schema() -> dict:
    """JSON schema for the submit_records tool call."""
    return {
        "type": "object",
        "properties": {
            "records": {
                "type": "array",
                "description": (
                    "Flat list of archival records in document order, each "
                    "with id/pid linking children to parents."
                ),
                "items": {
                    "type": "object",
                    "required": [
                        "id", "code", "level", "title", "accession", "loc"
                    ],
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "integer"},
                        "pid": {"type": ["integer", "null"]},
                        "code": {
                            "type": "string",
                            "pattern": "^(S|SB|F|I)\\d+$",
                        },
                        "level": {
                            "type": "string",
                            "enum": list(LEVELS_OF_DESCRIPTION),
                        },
                        "title": {"type": "string"},
                        "accession": {"type": "string"},
                        "gmd": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": sorted(RAD_GMD_TERMS),
                            },
                        },
                        "extent": {"type": ["string", "null"]},
                        "scope": {"type": ["string", "null"]},
                        "arrangement": {"type": ["string", "null"]},
                        "archival_history": {"type": ["string", "null"]},
                        "physical_characteristics": {"type": ["string", "null"]},
                        "acquisition": {"type": ["string", "null"]},
                        "accruals": {"type": ["string", "null"]},
                        "loc": {"type": "string"},
                        "dates": {"type": ["string", "null"]},
                        "note": {"type": ["string", "null"]},
                    },
                },
            }
        },
        "required": ["records"],
    }
