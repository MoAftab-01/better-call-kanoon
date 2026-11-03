"""Small, deterministic discovery profile: complete QA-located notifications only.

Stage 2F remains the sole candidate validator and exclusion-policy owner.
This module has no call to ReviewStore.append, decision creation or approval.
"""

from pathlib import Path
import stat
import unicodedata

from backend.app.ingestion.paths import checked_path
from backend.app.ingestion.pipeline import canonical_json
from backend.review.models import Candidate
from backend.review.service import (
    Catalog, HARD_EXCLUSIONS, ReviewStore, SPEC, exclusion_reasons,
    preview, sha, validate_candidate,
)

VERSION = "stage2g-notification-discovery-v1"
MAX_PROPOSALS = 5
SCRATCH = "backend/data/qa/stage2g"
LABEL = "PROPOSED / NOT SUBMITTED / NOT APPROVED"
RATIONALE = (
    "Stage 2G proposal: complete QA-located English operative paragraph; the entire "
    "same physical PDF page is retained as context, including heading, date, reference "
    "and publication/signature furniture. No visual approval, submission, legal "
    "currentness or applicability determination is asserted."
)
LIMITATIONS = [
    "This is an unsubmitted proposal for human inspection, not approved evidence.",
    "An original enactment or commencement instrument does not establish present legal applicability.",
    "Later commencement, amendments, corrigenda, jurisdictional scope and applicability remain unknown.",
    "Existing QA findings and reading-order uncertainty remain; text-layer equality is not visual verification.",
    "Hindi page 1 is outside this English single-page profile and remains unverified; no translation or bilingual comparison is claimed.",
]
CHECKLIST = [
    "Recheck raw PDF, processed JSON, catalogue and QA hashes against this candidate.",
    "Open the ORIGINAL PDF at the physical page shown; compare every selected character and line with the rendering.",
    "Compare the complete operative paragraph and its qualifications/exceptions; do not treat an appointed date alone as evidence.",
    "Check instrument number, heading, issuing authority, date and reference against the full unchanged context.",
    "Inspect every retained QA finding, including reading order and publication/signature furniture; never silently remove lines.",
    "Distinguish BNS section 106(2) from the BNSS First Schedule entry concerning that BNS subsection.",
    "Use only document/physical-page attribution; no verified legal provision identifier or current-status claim is supplied.",
    "Do not submit, approve or promote through this packet; any later review requires separate explicit authorization.",
]


def review_state(store):
    events, states = store.replay()
    allowed = store.allowlist()
    return dict(events=len(events), pending=sum(s["review"].decision == "pending" for s in states.values()),
                states=len(states), eligible_entries=len(allowed["entries"]),
                ledger_exists=store.path.exists(), checkpoint=allowed["checkpoint"])


def profile_boundary(item, doc):
    """Use only existing QA anchors, not heuristic section/heading detection."""
    if doc.metadata.instrument_type != "notification":
        return None, "outside_notification_paragraph_scope"
    info = item.get("notification_exception_check")
    if not isinstance(info, dict) or not isinstance(info.get("location"), dict):
        return None, "no_complete_qa_operative_paragraph"
    location = info["location"]
    if (set(location) != {"start_line", "end_line", "text"}
            or set(info) != {"pdf_page", "location", "exact_exception", "subsequent_status"}):
        return None, "cross_page_or_ambiguous_qa_boundaries"
    page, start, end = info.get("pdf_page"), location["start_line"], location["end_line"]
    if any(type(n) is not int for n in (page, start, end)) or not 1 <= page <= len(doc.pages):
        return None, "invalid_physical_page_or_lines"
    lines = doc.pages[page - 1].text.split("\n")
    if not 1 <= start <= end <= len(lines):
        return None, "cross_page_or_out_of_range_lines"
    text = "\n".join(lines[start - 1:end])
    if not text.strip() or text != location["text"]:
        return None, "qa_paragraph_text_or_boundary_mismatch"
    # This is a script sanity check, not independent language/translation verification.
    letters = [c for c in text if c.isalpha()]
    if not letters or any(not unicodedata.name(c, "").startswith("LATIN ") for c in letters):
        return None, "not_latin_script_english_profile"
    return (page, start, end), None


def discover(root, limit=MAX_PROPOSALS):
    if type(limit) is not int or not 1 <= limit <= MAX_PROPOSALS:
        raise ValueError("Discovery limit must be an integer from 1 to 5")
    catalog = Catalog(root)
    store = ReviewStore(catalog)
    before = review_state(store)
    if before["events"] or before["states"] or before["eligible_entries"]:
        raise ValueError("Stage 2G requires an empty review history and allowlist; nothing was changed")
    # Validate ALL source hashes before constructing or exporting any proposal.
    sources = [(item, catalog.document(identifier)[1])
               for identifier, item in sorted(catalog.documents.items(),
                   key=lambda pair: (pair[1]["metadata_for_citations"]["source_url"] or "", pair[0]))]
    packets, skipped, checks = [], [], []
    examined = 0
    for item, doc in sources:
        # Inventory only; final gating always calls the unmodified Stage 2F policy.
        inventory = [dict(physical_page=p["pdf_page"],
                          reasons=sorted({f["code"] for f in p["findings"] if f["code"] in HARD_EXCLUSIONS}))
                     for p in item["pages"] if any(f["code"] in HARD_EXCLUSIONS for f in p["findings"])]
        checks.append(dict(document=item["document"], document_id=doc.document_id,
            raw_path=item["raw_path"], raw_sha256=item["raw_sha256"],
            processed_path=item["processed_path"], processed_sha256=item["processed_sha256"],
            hash_validation="PASS", qa_hard_signal_inventory=inventory))
        boundary, reason = profile_boundary(item, doc)
        if reason:
            skipped.append(dict(document=item["document"], document_id=doc.document_id,
                                reason=reason, proposed_candidate_created=False))
            continue
        if len(packets) >= limit or examined >= MAX_PROPOSALS:
            skipped.append(dict(document=item["document"], document_id=doc.document_id,
                                reason="discovery_limit_reached", proposed_candidate_created=False))
            continue
        examined += 1
        page, start, end = boundary
        try:
            candidate = preview(catalog, doc.document_id, [boundary],
                [(page, 1, len(doc.pages[page - 1].text.split("\n")))], RATIONALE)
            reasons = exclusion_reasons(item, candidate)
            if reasons:
                skipped.append(dict(document=item["document"], document_id=doc.document_id,
                    physical_page=page, start_line=start, end_line=end,
                    reason="stage2f_hard_exclusion", exclusion_reasons=reasons,
                    proposed_candidate_created=False))
                continue
            inspection = store.inspect(candidate)  # Read-only; no submission/event.
            if inspection["exclusion_reasons"]:
                raise ValueError("Stage 2F inspection rejected a proposed passage")
            packets.append(dict(packet_schema_version=1, kind="discovery_review_packet",
                label=LABEL, submitted=False, approved=False, eligible=False,
                document=item["document"], candidate_id=candidate.candidate_id,
                candidate=candidate.model_dump(mode="json"),
                exact_passage=inspection["selected"], surrounding_context=inspection["context"],
                source_pdf=dict(path=candidate.raw_path, sha256=candidate.raw_sha256,
                                physical_pages=[s.physical_page for s in candidate.spans]),
                qa_pages=inspection["qa_pages"],
                gate_checks=dict(stage2f_candidate_validation="PASS", exclusion_reasons=[],
                                 full_english_operative_paragraph=True, full_same_page_context=True),
                commencement_context=item["notification_exception_check"],
                citation_kind="document_and_physical_page_only",
                human_review_checklist=list(CHECKLIST), limitations=list(LIMITATIONS)))
        except ValueError as exc:
            # Hash/pin checks are repeated below. They must abort the entire run,
            # never be silently downgraded to a harmless no-candidate result.
            skipped.append(dict(document=item["document"], document_id=doc.document_id,
                                reason="stage2f_candidate_validation_failed", detail=str(exc),
                                proposed_candidate_created=False))
    for item, _ in sources:
        catalog.document(item["document_id"])
    after = review_state(store)
    if after != before:
        raise ValueError("Review state changed during read-only discovery; stop")
    report = dict(schema_version=1, stage="2G", discovery_version=VERSION,
        label=LABEL, scope="archival_text_only", candidate_limit=limit,
        selection_profile="Single-page complete English operative paragraphs already located by QA; no Act-section or cross-page discovery.",
        catalog_sha256=catalog.digest, qa_sha256=catalog.qa_hash,
        stage2f_specification_sha256=sha((catalog.root / SPEC).read_bytes()),
        proposed_count=len(packets), examined_operative_paragraphs=examined,
        proposals=[dict(candidate_id=p["candidate_id"], document=p["document"],
            document_id=p["candidate"]["document_id"], spans=p["candidate"]["spans"],
            passage_sha256=p["candidate"]["passage_sha256"], context_sha256=p["candidate"]["context_sha256"],
            status=LABEL, eligible=False) for p in packets],
        source_checks=checks, skipped=skipped, review_before=before, review_after=after,
        limitations=list(LIMITATIONS))
    return report, packets


def export_packets(root, output_dir, limit=MAX_PROPOSALS):
    """Explicit export ONLY into a new Stage 2G scratch child; no overwrites."""
    root = checked_path(Path(root))
    target = checked_path(Path(output_dir) if Path(output_dir).is_absolute() else root / output_dir)
    base = checked_path(root / SCRATCH)
    if target == base or not target.is_relative_to(base):
        raise ValueError("Exports must use a new child of backend/data/qa/stage2g")
    if target.exists():
        raise ValueError("Export destination already exists; refusing overwrite")
    report, packets = discover(root, limit)
    catalog = Catalog(root)
    for packet in packets:
        candidate = Candidate.model_validate(packet["candidate"])
        item, _ = validate_candidate(catalog, candidate)
        if exclusion_reasons(item, candidate):
            raise ValueError("Source QA exclusion changed before export")
    # Nothing is written until the whole discovery and source revalidation pass.
    checked_path(target.parent).mkdir(parents=True, exist_ok=True)
    target.mkdir(exist_ok=False)
    exported = []
    for packet in packets:
        path = checked_path(target / ("proposal_" + packet["candidate_id"] + ".json"))
        data = canonical_json(packet)
        with path.open("xb") as stream:
            stream.write(data)
        path.chmod(stat.S_IREAD)
        exported.append(dict(candidate_id=packet["candidate_id"], path=path.relative_to(root).as_posix(),
                             sha256=sha(data), bytes=len(data)))
    if review_state(ReviewStore(catalog)) != report["review_before"]:
        raise ValueError("Review state changed during export; packets remain unapproved scratch data")
    return dict(discovery=report, packet_export=dict(directory=target.relative_to(root).as_posix(), files=exported))
