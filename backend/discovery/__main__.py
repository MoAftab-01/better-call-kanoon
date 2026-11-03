"""Read-only discovery/preview; optional explicit packet export into scratch only."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from backend.review.service import Catalog
from .passages import discover, export_packets

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-workspace", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["discover", "preview", "export"]:
        p = commands.add_parser(name)
        p.add_argument("--limit", type=int, default=5)
        if name == "preview":
            p.add_argument("candidate_id")
        if name == "export":
            p.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.synthetic_workspace or ROOT
        if args.synthetic_workspace:
            catalog = Catalog(root)
            if any(catalog.document(k)[1].metadata.source_type != "synthetic" for k in catalog.documents):
                raise ValueError("Demonstration workspace requires synthetic sources only")
        if args.command == "export":
            result = export_packets(root, args.output_dir, args.limit)
        else:
            report, packets = discover(root, args.limit)
            result = report
            if args.command == "preview":
                result = next((p for p in packets if p["candidate_id"] == args.candidate_id), None)
                if result is None:
                    raise ValueError("Candidate not in the current limited discovery result")
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
        return 0
    except ValidationError:
        print(json.dumps({"error": "Stage 2F schema validation failed; no input values echoed"}))
        return 2
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
