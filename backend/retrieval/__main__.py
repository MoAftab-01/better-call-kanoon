"""Build/inspect the local in-memory index; optional hash-only manifest export."""
import argparse
import json
from pathlib import Path

from backend.app.ingestion.paths import checked_path
from backend.app.ingestion.pipeline import canonical_json
from .engine import ArchivalIndex, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "check"])
    parser.add_argument("--output", type=Path, help="NEW manifest under ignored backend/data/chat-index; no text exported")
    args = parser.parse_args()
    index = ArchivalIndex()
    result = dict(**index.status(), sources=[dict(candidate_id=p.candidate.candidate_id,
        raw_sha256=p.candidate.raw_sha256, processed_sha256=p.candidate.processed_sha256,
        passage_sha256=p.candidate.passage_sha256) for p in index.passages])
    if args.output:
        target = checked_path(args.output)
        if not target.is_relative_to(checked_path(ROOT / "backend/data/chat-index")):
            parser.error("Output must be a new file under backend/data/chat-index")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(canonical_json(result))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if index.passages else 2


if __name__ == "__main__":
    raise SystemExit(main())
