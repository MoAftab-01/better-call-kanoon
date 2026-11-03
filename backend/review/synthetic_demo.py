"""Create isolated SYNTHETIC fixtures and unsigned requests, NEVER decisions.

This fixture is not Indian law and contains no real reviewer or approval record.
"""

import argparse
import json
from pathlib import Path

import pymupdf

from backend.app.ingestion.paths import checked_path
from backend.app.ingestion.pipeline import canonical_json, ingest_manifest, load_manifest
from backend.qa.legal_text import check_document
from .models import Attestations, Decision, EvidenceReference
from .service import Catalog, POLICY, QA, SPEC, preview, sha


def create_demo(destination):
    root = checked_path(Path(destination))
    if root.exists():
        raise ValueError("Synthetic destination already exists; refusing overwrite")
    root.mkdir(parents=True)
    (root / "docs").mkdir()
    source = root / "backend/data/raw/synthetic-not-law.pdf"
    source.parent.mkdir(parents=True)
    with pymupdf.open() as pdf:
        for text in [
            "SYNTHETIC SOFTWARE FIXTURE - NOT LAW\nSection 1. Practice heading\nPractice paragraph continues here.\nNo real legal effect is asserted.",
            "SYNTHETIC SOFTWARE FIXTURE - NOT LAW\nPractice continuation on another physical page.\nEnd of the synthetic example.",
        ]:
            pdf.new_page().insert_text((50, 60), text)
        pdf.save(source)
    digest = sha(source.read_bytes())
    metadata = dict(official_title="SYNTHETIC REVIEW FIXTURE - NOT LAW", instrument_type="other",
        jurisdiction=None, issuing_authority="SYNTHETIC TEST LABEL - NOT GOVERNMENT",
        source_url="https://example.invalid/synthetic-not-law", source_type="synthetic",
        language="en", amendment_version="SYNTHETIC SOFTWARE TEST DATA ONLY",
        provenance=dict(supplied_by="Synthetic fixture generator", verification_claim="unverified",
                        notes="Not a real Act, notification, reviewer approval or legal authority."))
    manifest = root / "docs/synthetic-manifest.json"
    manifest.write_bytes(canonical_json(dict(schema_version=1, documents=[dict(file_path=source.name, metadata=metadata, expected_sha256=digest)])))
    result = ingest_manifest(manifest, root / "backend/data/processed/synthetic/v1", source_root=source.parent)[0]
    source.chmod(0o444)
    previous = dict(document="SYNTHETIC QA FIXTURE - NOT LAW", raw_path=source.relative_to(root).as_posix(),
        output_path=result.output_path.relative_to(root).as_posix(), source_sha256=digest,
        output_sha256=sha(result.output_path.read_bytes()), original_identifiers={"fixture": "SYNTHETIC ONLY"})
    acquired = dict(sha256=digest, byte_size=source.stat().st_size, page_count=2, commencement_review=None)
    entry = load_manifest(manifest).documents[0]
    doc_qa = check_document(root, previous, acquired, entry, [])
    (root / QA).write_bytes(canonical_json(dict(ledger_checks={"synthetic_fixture": True}, documents=[doc_qa])))
    (root / SPEC).write_bytes(canonical_json(dict(schema_version=1, catalog=dict(policy_version=POLICY,
        input_pins={QA: sha((root / QA).read_bytes()), "docs/synthetic-manifest.json": sha(manifest.read_bytes())}))))
    catalog = Catalog(root)
    candidate = preview(catalog, result.document_id, [(1, 2, 4)], [(1, 1, 4)],
                        "SYNTHETIC practice context; no legal attribution.")
    (root / "candidate.json").write_bytes(canonical_json(candidate.model_dump(mode="json")))
    evidence = [EvidenceReference(kind="rendered_pdf_page", file_path=candidate.raw_path,
        sha256=candidate.raw_sha256, physical_pages=[1], note="SYNTHETIC template: user must actually inspect the fixture."),
        EvidenceReference(kind="qa_report", file_path=QA, sha256=candidate.qa_sha256,
                          physical_pages=[1], note="SYNTHETIC QA reference; not legal verification.")]
    for name, state, clock in [("pending-request.json", "pending", "2026-01-01T00:00:00Z"),
                               ("approval-request.json", "approved", "2026-01-02T00:00:00Z")]:
        request = Decision(decision=state, reviewer_id="SYNTHETIC EXAMPLE ACTOR - NOT A REAL REVIEWER",
            decision_time=clock, rationale="SYNTHETIC unsigned request template only; no real approval.",
            evidence=evidence, attestations=Attestations())
        (root / name).write_bytes(canonical_json(request.model_dump(mode="json")))
    return dict(synthetic_workspace=str(root), candidate_id=candidate.candidate_id,
                events_created=0, approvals_created=0,
                warning="Templates have false attestations. Only a user's explicit single-candidate action can record a reviewed synthetic decision.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(create_demo(args.output_dir), sort_keys=True))
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    main()
