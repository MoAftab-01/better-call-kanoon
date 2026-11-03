"""Read-only by default; only submit and record-decision append events."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from .models import Attribution, Candidate, Decision
from .service import Catalog, ReviewStore, preview, read_json, make_span

ROOT = Path(__file__).resolve().parents[2]


def boundaries(value):
    try:
        result = tuple(int(s) for s in value.split(":"))
        if len(result) != 3 or min(result) < 1:
            raise ValueError()
        return result
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use physical_page:start_line:end_line") from exc


def checkpoint(value):
    try:
        number, digest = value.split(":")
        if int(number) < 0 or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError()
        return int(number), digest
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use sequence:64-lowercase-hex-digest") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-workspace", type=Path, help="Isolated demonstration root; requires source_type=synthetic for EVERY document.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("documents", help="Read-only source catalogue and page IDs")
    p = commands.add_parser("preview", help="Read-only deterministic candidate proposal on stdout")
    p.add_argument("--document", required=True)
    p.add_argument("--span", type=boundaries, action="append", required=True)
    p.add_argument("--context", type=boundaries, action="append", required=True)
    p.add_argument("--context-rationale", required=True)
    p.add_argument("--cross-page-context")
    p.add_argument("--printed-label")
    p.add_argument("--label-span", type=boundaries)
    p = commands.add_parser("list", help="Read-only pending candidates; no file creation")
    p.add_argument("--state", choices=["pending", "approved", "rejected", "needs_correction"], default="pending")
    p = commands.add_parser("inspect", help="Read original text, context and QA findings")
    p.add_argument("candidate")
    commands.add_parser("history", help="Read immutable decision history and checkpoint")
    for name in ["verify", "allowlist"]:
        p = commands.add_parser(name, help="Read-only chain verification/live allowlist on stdout")
        p.add_argument("--checkpoint", type=checkpoint)
    for name in ["submit", "record-decision"]:
        p = commands.add_parser(name, help="EXPLICIT WRITE: append one immutable event")
        if name == "submit":
            p.add_argument("--candidate-file", type=Path, required=True)
        else:
            p.add_argument("--candidate", required=True)
        p.add_argument("--decision-file", type=Path, required=True)
        p.add_argument("--confirm-candidate", required=True)
        p.add_argument("--approve-one", action="store_true", help="Required in addition to explicit candidate confirmation for approval")
    args = parser.parse_args(argv)
    try:
        root = args.synthetic_workspace or ROOT
        catalog = Catalog(root)
        if args.synthetic_workspace:
            for identifier in catalog.documents:
                _, doc = catalog.document(identifier)
                if doc.metadata.source_type != "synthetic":
                    raise ValueError("Demonstration workspace cannot contain real-source metadata")
        store = ReviewStore(catalog)
        if args.command == "documents":
            result = {"documents": [dict(document=d["document"], document_id=k,
                       pages=[dict(physical_page=p["pdf_page"], page_id=p["page_id"]) for p in d["pages"]]) for k, d in sorted(catalog.documents.items())]}
        elif args.command == "preview":
            attribution = None
            if bool(args.printed_label) != bool(args.label_span):
                raise ValueError("Printed attribution requires both label and exact anchor")
            if args.printed_label:
                _, doc = catalog.document(args.document)
                attribution = Attribution(kind="printed_label", label=args.printed_label,
                                          anchor=make_span(doc, *args.label_span))
            result = preview(catalog, args.document, args.span, args.context,
                             args.context_rationale, args.cross_page_context, attribution).model_dump(mode="json")
        elif args.command in {"verify", "allowlist"}:
            result = store.allowlist(args.checkpoint)
            if args.command == "verify":
                result = dict(audit_chain="PASS", checkpoint=result["checkpoint"],
                              eligible_count=len(result["entries"]), blocked=result["blocked"])
        else:
            events, states = store.replay()
            if args.command == "list":
                result = {"candidates": []}
                for identifier, state in sorted(states.items()):
                    if state["review"].decision == args.state:
                        try:
                            details = store.inspect(state["candidate"])
                            reasons = details["exclusion_reasons"]
                        except (ValueError, OSError) as exc:
                            reasons = [str(exc)]
                        result["candidates"].append(dict(candidate_id=identifier, decision=args.state, exclusion_reasons=reasons))
            elif args.command == "history":
                result = dict(events=[e.model_dump(mode="json") for e in events])
            elif args.command == "inspect":
                if args.candidate not in states:
                    raise ValueError("Candidate not found")
                result = store.inspect(states[args.candidate]["candidate"])
                result["latest_review"] = states[args.candidate]["review"].model_dump(mode="json")
            else:
                if args.command == "submit":
                    candidate = Candidate.model_validate(read_json(args.candidate_file))
                else:
                    if args.candidate not in states:
                        raise ValueError("Candidate not found")
                    candidate = states[args.candidate]["candidate"]
                decision = Decision.model_validate(read_json(args.decision_file))
                event = store.append(candidate, decision, args.confirm_candidate,
                                     submit=args.command == "submit", approve_one=args.approve_one)
                result = dict(appended=event.model_dump(mode="json"),
                              retain_checkpoint=dict(sequence=event.sequence, event_sha256=event.event_sha256))
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
        return 0
    except ValidationError as exc:
        print(json.dumps({"error": "Invalid review record", "fields": [list(e["loc"]) for e in exc.errors(include_input=False, include_url=False, include_context=False)]}))
        return 2
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
