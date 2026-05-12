from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .core import ConvertOptions, convert


def _write_outputs(result, out_dir: Path, save_json: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{result.accession}.csv"
    report_path = out_dir / f"{result.accession}.report.md"
    csv_path.write_text(result.csv, encoding="utf-8")
    report_path.write_text(result.report, encoding="utf-8")
    print(f"wrote {csv_path}")
    print(f"wrote {report_path}")
    if save_json:
        json_path = out_dir / f"{result.accession}.json"
        json_path.write_text(
            json.dumps([r.model_dump() for r in result.raw_records], indent=2),
            encoding="utf-8",
        )
        print(f"wrote {json_path}")


def _convert_one(pdf: Path, args: argparse.Namespace) -> None:
    opts = ConvertOptions(
        parent_slug=args.parent_slug,
        accession=args.accession,
        id_offset=args.id_offset,
    )
    print(f"converting {pdf} ...")
    result = convert(pdf, opts)
    _write_outputs(result, Path(args.output_dir), args.save_json)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="finding-aid-convert",
        description="Convert legacy finding-aid PDFs to AtoM-ready CSVs.",
    )
    parser.add_argument("input", help="PDF path, or directory when used with --batch")
    parser.add_argument("--batch", action="store_true",
                        help="Process every *.pdf under the input directory")
    parser.add_argument("--parent-slug", default=None,
                        help="qubitParentSlug for top-level Series records")
    parser.add_argument("--accession", default=None,
                        help="Override the accession number inferred from filename")
    parser.add_argument("--id-offset", type=int, default=3,
                        help="Starting integer id (default 3 to match example CSV)")
    parser.add_argument("--output-dir", default="output",
                        help="Directory for CSV and report outputs")
    parser.add_argument("--save-json", action="store_true",
                        help="Also write the raw record list as JSON")

    args = parser.parse_args(argv)
    target = Path(args.input)

    if args.batch:
        if not target.is_dir():
            parser.error(f"--batch requires a directory; got {target}")
        pdfs = sorted(target.glob("*.pdf"))
        if not pdfs:
            parser.error(f"no PDFs found under {target}")
        if args.accession or args.parent_slug:
            parser.error(
                "--accession/--parent-slug cannot be set in --batch mode; "
                "they are per-PDF."
            )
        for pdf in pdfs:
            try:
                _convert_one(pdf, args)
            except Exception as e:
                print(f"  FAILED {pdf}: {e}", file=sys.stderr)
        return 0

    if not target.is_file():
        parser.error(f"input file not found: {target}")
    _convert_one(target, args)
    return 0
