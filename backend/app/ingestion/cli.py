"""Run from the repository root: python -m backend.app.ingestion --help."""

import argparse
import json
import sys
from pathlib import Path

from .pipeline import ingest_manifest


def _positive_mebibytes(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("File size must be an integer between 1 and 100 MiB.") from exc
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError("File size must be between 1 and 100 MiB.")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest local legal documents with user-supplied metadata. No network access or authenticity verification.")
    parser.add_argument("--manifest", required=True, type=Path, help="UTF-8 JSON metadata manifest.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for generated, non-overwriting JSON records.")
    parser.add_argument("--source-root", type=Path, help="Allowed source directory; defaults to the manifest directory.")
    parser.add_argument("--document", help="Ingest only this manifest file_path; otherwise ingest the full collection.")
    parser.add_argument("--max-file-size-mb", type=_positive_mebibytes, default=25, help="Per-source limit in MiB (1-100; default 25).")
    args = parser.parse_args(argv)
    try:
        results = ingest_manifest(
            args.manifest, args.output_dir, source_root=args.source_root,
            document=args.document, max_file_bytes=args.max_file_size_mb * 1024 * 1024,
        )
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2
    print(json.dumps({
        "created": sum(result.status == "created" for result in results),
        "unchanged": sum(result.status == "unchanged" for result in results),
        "documents": [
            {"document_id": result.document_id, "status": result.status, "output_path": str(result.output_path)}
            for result in results
        ],
        "verification_status": "not_independently_verified",
    }, ensure_ascii=True, sort_keys=True))
    return 0
