from __future__ import annotations

import sys
from dataclasses import dataclass

import anthropic

from .prompts import SYSTEM_PROMPT, user_message
from .schema import Record, to_tool_input_schema

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 64000

TOOL = {
    "name": "submit_records",
    "description": (
        "Submit the full hierarchical list of archival records extracted "
        "from the finding-aid PDF, in document order."
    ),
    "input_schema": to_tool_input_schema(),
}


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


def extract_records(
    pdf_text: str,
    accession: str,
    id_offset: int = 3,
    client: anthropic.Anthropic | None = None,
    progress: bool = True,
) -> tuple[list[Record], Usage]:
    client = client or anthropic.Anthropic()
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "submit_records"},
        messages=[
            {
                "role": "user",
                "content": user_message(pdf_text, accession, id_offset),
            }
        ],
    ) as stream:
        ticks = 0
        for event in stream:
            if not progress:
                continue
            if event.type == "content_block_delta":
                ticks += 1
                if ticks % 50 == 0:
                    sys.stderr.write(".")
                    sys.stderr.flush()
        if progress:
            sys.stderr.write("\n")
        resp = stream.get_final_message()

    if resp.stop_reason == "max_tokens":
        raise RuntimeError(
            "Model output was truncated at max_tokens "
            f"({MAX_TOKENS}). The tool call is incomplete and cannot be "
            "trusted. Raise MAX_TOKENS in llm_extract.py or split the PDF."
        )

    tool_blocks = [b for b in resp.content if b.type == "tool_use"]
    if not tool_blocks:
        raise RuntimeError(
            "Model did not call submit_records. Stop reason: "
            f"{resp.stop_reason}"
        )
    payload = tool_blocks[0].input
    raw_records = payload.get("records", [])
    if not raw_records:
        raise RuntimeError(
            "Model returned zero records. Stop reason: "
            f"{resp.stop_reason}. Tool input keys: {list(payload.keys())}"
        )
    records = [Record(**r) for r in raw_records]

    usage = Usage(
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
        cache_creation_input_tokens=getattr(
            resp.usage, "cache_creation_input_tokens", 0
        ) or 0,
        cache_read_input_tokens=getattr(
            resp.usage, "cache_read_input_tokens", 0
        ) or 0,
    )
    return records, usage
