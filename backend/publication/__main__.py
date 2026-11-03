"""Read-only V2 metadata, real-corpus and audit verification. Never approves."""
import argparse
import json
from pathlib import Path
from backend.review.models import Candidate
from backend.review.service import validate_candidate
from .bindings import ReadOnlyReview, proposals, verify_metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["metadata", "verify", "list", "history", "allowlist", "preview"])
    parser.add_argument("candidate_id", nargs="?")
    parser.add_argument("--checkpoint", help="Independently retained latest sequence:hash")
    args = parser.parse_args(argv)
    try:
        catalog, saved = verify_metadata(Path(__file__).resolve().parents[2])
        if args.command == "metadata":
            result = dict(metadata_bindings="PASS", evidence_version="v2", catalogue_sha256=catalog.digest,
                packets=len(saved), source_bytes_verified=False, human_approval=False, legal_currentness="unknown")
        else:
            for identifier in catalog.documents:
                catalog.document(identifier)
            for packet in saved:
                validate_candidate(catalog, Candidate.model_validate(packet["candidate"]))
            if proposals(catalog) != saved:
                raise ValueError("Real-source V2 regeneration differs")
            review = ReadOnlyReview(catalog)
            checkpoint = None
            if args.checkpoint:
                number, digest = args.checkpoint.split(":")
                if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                    raise ValueError("Invalid checkpoint")
                checkpoint = (int(number), digest)
            events, states = review.replay(checkpoint)
            if args.command == "preview":
                actual = proposals(catalog)
                if actual != saved:
                    raise ValueError("Regenerated V2 proposals differ")
                result = next((p for p in actual if p["candidate_id"] == args.candidate_id), None)
                if result is None:
                    raise ValueError("Candidate absent from V2; versions are not interchangeable")
            elif args.command == "history":
                result = dict(events=[e.model_dump(mode="json") for e in events])
            elif args.command == "list":
                result = dict(candidates=[dict(candidate_id=k, decision=v["review"].decision) for k,v in states.items()])
            elif args.command == "allowlist":
                result = review.allowlist(checkpoint)
            else:
                allowed = review.allowlist(checkpoint)
                result = dict(audit_chain="PASS", evidence_version="v2", source_documents=len(catalog.documents),
                    eligible_count=len(allowed["entries"]), checkpoint=allowed["checkpoint"], blocked=allowed["blocked"])
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps(dict(error=str(exc), evidence_version="v2", verified=False,
            note="Real-corpus commands require the separately acquired exact source/processed bundle; no approvals are created."), ensure_ascii=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
