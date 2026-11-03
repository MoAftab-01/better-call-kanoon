"""V2 read-only verification using the immutable Stage 2F identity/policy core.

No submit/approve operation is exposed. Migration is never a human review.
"""
from pathlib import Path

from backend.app.ingestion.paths import checked_path, source_path
from backend.app.ingestion.pipeline import canonical_json, read_bounded
from backend.review.models import Candidate
from backend.review.service import (
    Catalog as V1Catalog, ReviewStore, exclusion_reasons, model_hash, read_json,
    sha, validate_candidate, preview,
)
from backend.discovery.passages import LABEL, RATIONALE, CHECKLIST, LIMITATIONS, profile_boundary

VERSION = "publication-v2-1"
PREFIX = "docs/evidence/v2/"
SPEC = PREFIX + "legal-passage-review-stage2f.json"
QA = PREFIX + "legal-text-quality-stage2e.json"
MANIFEST = PREFIX + "migration.json"
V1_MANIFEST = "docs/evidence/v1-preservation.json"
LEDGER = "backend/data/reviews/stage2f/v2"
POLICY = "stage2f-publication-v2"


class Catalog(V1Catalog):
    """Only storage/configuration is versioned; source and candidate rules are V1."""
    def __init__(self, root):
        self.root = checked_path(Path(root))
        self.config = read_json(source_path(self.root, SPEC))["catalog"]
        if self.config["policy_version"] != POLICY:
            raise ValueError("Unsupported V2 catalogue policy")
        self.digest = sha(canonical_json(self.config))
        self.verify_pins()
        self.qa_hash = sha(read_bounded(source_path(self.root, QA), 8 * 1024 * 1024))
        self.qa = read_json(source_path(self.root, QA))
        if not self.qa.get("documents") or not all(self.qa["ledger_checks"].values()):
            raise ValueError("V2 QA ledger failed")
        self.documents = {d["document_id"]: d for d in self.qa["documents"]}
        if len(self.documents) != len(self.qa["documents"]):
            raise ValueError("Duplicate V2 document identities")

    def verify_pins(self):
        if sha(canonical_json(read_json(source_path(self.root, SPEC))["catalog"])) != self.digest:
            raise ValueError("V2 catalogue changed during verification")
        for name, expected in self.config["input_pins"].items():
            if sha(read_bounded(source_path(self.root, name), 8 * 1024 * 1024)) != expected:
                raise ValueError("Stale V2 catalogue input: " + name)


class ReadOnlyReview:
    """Separate ledger namespace, same chain checks, explicit V2 approval checks.

    This release deliberately provides no event writer. Future human write actions
    require separate authorization/workflow work, never a migration shortcut.
    """
    def __init__(self, catalog):
        self.catalog = catalog
        self.store = ReviewStore(catalog)
        self.store.path = checked_path(catalog.root / LEDGER)

    def replay(self, checkpoint=None):
        events, states = self.store.replay(checkpoint)
        for state in states.values():
            validate_candidate(self.catalog, state["candidate"])
        return events, states

    def allowlist(self, checkpoint=None):
        events, states = self.replay(checkpoint)
        entries, blocked = [], []
        for identifier, state in sorted(states.items()):
            if state["review"].decision != "approved":
                continue
            try:
                if checkpoint is None:
                    raise ValueError("Retained trusted latest checkpoint required")
                c, decision = state["candidate"], state["review"]
                item, _ = validate_candidate(self.catalog, c)
                if exclusion_reasons(item, c):
                    raise ValueError("Unresolved V2 exclusion")
                pages = {s.physical_page for s in [*c.spans, *c.context_spans]}
                rendered, qa_pages = set(), set()
                for ref in decision.evidence:
                    if sha(read_bounded(source_path(self.catalog.root, ref.file_path), 25*1024*1024)) != ref.sha256:
                        raise ValueError("Stale V2 decision evidence")
                    if ref.kind == "rendered_pdf_page" and ref.file_path == c.raw_path and ref.sha256 == c.raw_sha256:
                        rendered.update(ref.physical_pages)
                    if ref.kind == "qa_report" and ref.file_path == QA and ref.sha256 == c.qa_sha256:
                        qa_pages.update(ref.physical_pages)
                a = decision.attestations
                if not (pages <= rendered and pages <= qa_pages and a.visual_comparison_performed
                        and a.boundaries_and_attribution_verified and a.qualifiers_and_exceptions_preserved
                        and a.archival_scope_only and (len(c.spans) == 1 or a.cross_page_context_verified)):
                    raise ValueError("Missing V2 human evidence/attestations")
                entries.append(dict(candidate=c.model_dump(mode="json"), approval=decision.model_dump(mode="json")))
            except (ValueError, OSError) as exc:
                blocked.append(dict(candidate_id=identifier, reason=str(exc)))
        return dict(entries=entries, blocked=blocked, checkpoint=dict(sequence=len(events),
                    event_sha256=events[-1].event_sha256 if events else "0"*64),
                    evidence_version="v2", legal_currentness="unknown")


def proposals(catalog):
    """Reuse the original conservative notification profile and hard exclusions."""
    review = ReadOnlyReview(catalog)
    if review.replay() != ([], {}) or review.allowlist()["entries"]:
        raise ValueError("V2 generation requires empty review state; never reset it")
    packets = []
    for identifier, item in sorted(catalog.documents.items(), key=lambda x: (x[1]["metadata_for_citations"]["source_url"] or "", x[0])):
        _, doc = catalog.document(identifier)  # All six sources, including skipped Acts.
        boundary, _ = profile_boundary(item, doc)
        if boundary is None:
            continue
        if len(packets) == 5:
            break
        page, _, _ = boundary
        c = preview(catalog, identifier, [boundary], [(page, 1, len(doc.pages[page-1].text.split("\n")))], RATIONALE)
        details = review.store.inspect(c)
        if details["exclusion_reasons"]:
            continue
        packets.append(dict(packet_schema_version=1, binding_version="v2", kind="discovery_review_packet",
            label=LABEL, submitted=False, approved=False, eligible=False, document=item["document"],
            candidate_id=c.candidate_id, candidate=c.model_dump(mode="json"),
            exact_passage=details["selected"], surrounding_context=details["context"],
            source_pdf=dict(path=c.raw_path, sha256=c.raw_sha256, physical_pages=[s.physical_page for s in c.spans]),
            qa_pages=details["qa_pages"], gate_checks=dict(stage2f_candidate_validation="PASS", exclusion_reasons=[],
                full_english_operative_paragraph=True, full_same_page_context=True),
            commencement_context=item["notification_exception_check"], citation_kind="document_and_physical_page_only",
            human_review_checklist=list(CHECKLIST), limitations=list(LIMITATIONS)))
    return packets


def validate_mapping(old_manifest, catalog, mapping, packets):
    """Public metadata consistency proof; PDF/processed proof is a separate check."""
    catalog.verify_pins()
    if mapping["migration_version"] != VERSION or mapping["human_approval"] is not False:
        raise ValueError("Invalid migration version/approval claim")
    old_digest = sha(canonical_json(old_manifest["catalog"]))
    if old_digest != old_manifest["catalogue_sha256"]:
        raise ValueError("Invalid V1 catalogue preservation digest")
    if old_digest == catalog.digest or mapping["v2_catalogue_sha256"] != catalog.digest:
        raise ValueError("Migration catalogue versions are not distinct/matching")
    if (mapping.get("v1_catalogue_sha256", old_digest) != old_digest
            or mapping.get("v1_qa_sha256", old_manifest["qa_sha256"]) != old_manifest["qa_sha256"]
            or mapping.get("v2_qa_sha256", catalog.qa_hash) != catalog.qa_hash):
        raise ValueError("Mapping header bindings differ")
    old = {c["candidate_id"]: Candidate.model_validate(c) for c in old_manifest["candidates"]}
    new = {p["candidate_id"]: p for p in packets}
    rows = mapping["mappings"]
    if len(rows) != len(old) or len(rows) != len(new) or len({r["v1_candidate_id"] for r in rows}) != len(rows) or len({r["v2_candidate_id"] for r in rows}) != len(rows):
        raise ValueError("Missing, duplicate or unexpected migration row")
    for row in rows:
        a = old[row["v1_candidate_id"]]
        packet = new[row["v2_candidate_id"]]
        b = Candidate.model_validate(packet["candidate"])
        for candidate in [a, b]:
            if candidate.candidate_id != "passage_" + model_hash(candidate, {"candidate_id"}):
                raise ValueError("Tampered migration candidate identity")
        if (a.catalog_sha256 != old_digest or a.qa_sha256 != old_manifest["qa_sha256"]
                or b.catalog_sha256 != catalog.digest or b.qa_sha256 != catalog.qa_hash):
            raise ValueError("Migration QA/catalogue binding mismatch")
        excluded = {"candidate_id", "catalog_sha256", "qa_sha256"}
        if a.model_dump(exclude=excluded) != b.model_dump(exclude=excluded):
            raise ValueError("Unexplained candidate change outside QA/catalogue bindings")
        expected = dict(document_id=b.document_id, raw_sha256=b.raw_sha256,
            processed_sha256=b.processed_sha256, passage_sha256=b.passage_sha256, context_sha256=b.context_sha256,
            source_identity=dict(document_id=b.document_id,official_title=b.source_metadata.official_title,
                source_url=b.source_metadata.source_url,original_identifiers=b.original_identifiers),
            passage_identity=dict(spans=[s.model_dump() for s in b.spans],context_spans=[s.model_dump() for s in b.context_spans],attribution=b.attribution.model_dump()),
            exact_text_hashes=[s.text_sha256 for s in b.spans], v1_catalogue_sha256=old_digest,
            v2_catalogue_sha256=catalog.digest, migration_version=VERSION,
            reason="Publication metadata and versioned QA/catalogue pins only; no legal text or review change")
        if {k: row.get(k) for k in expected} != expected:
            raise ValueError("Invalid migration identity mapping")
        if packet["label"] != LABEL or any(packet[k] for k in ["submitted", "approved", "eligible"]):
            raise ValueError("Migration packet must remain unapproved")
        item = catalog.documents[b.document_id]
        for span in [*b.spans, *b.context_spans]:
            if (not 1 <= span.physical_page <= len(item["pages"])
                    or item["pages"][span.physical_page-1]["page_id"] != span.page_id):
                raise ValueError("Ambiguous public page binding")
        if exclusion_reasons(item, b):
            raise ValueError("Excluded migration passage")
        expected_qa = [item["pages"][s.physical_page-1] for s in b.spans]
        if packet.get("qa_pages") != expected_qa:
            raise ValueError("Packet QA findings differ")
        for key, spans in [("exact_passage", b.spans), ("surrounding_context", b.context_spans)]:
            values = packet[key]
            if len(values) != len(spans):
                raise ValueError("Missing packet text/context")
            for value, span in zip(values, spans, strict=True):
                if {k: value[k] for k in span.model_dump()} != span.model_dump() or sha(value["text"].encode("utf-8")) != span.text_sha256:
                    raise ValueError("Packet exact text/boundary differs")
            digest = sha(canonical_json({"spans": values}))
            if digest != (b.passage_sha256 if key == "exact_passage" else b.context_sha256):
                raise ValueError("Packet selection/context hash differs")
    return True


def verify_metadata(root):
    catalog = Catalog(root)
    manifest = read_json(source_path(catalog.root, MANIFEST))
    old = read_json(source_path(catalog.root, V1_MANIFEST))
    packets = []
    for entry in manifest["packets"]:
        p = source_path(catalog.root, entry["path"])
        if sha(p.read_bytes()) != entry["sha256"]:
            raise ValueError("Stale public V2 proposal packet")
        packets.append(read_json(p))
    validate_mapping(old, catalog, manifest, packets)
    return catalog, packets
