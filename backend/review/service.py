"""Default-deny validation and append-only, tamper-evident local decision events.

This is cooperative local storage, not WORM storage, identity authentication or
a digital signature service. A trusted external checkpoint detects tail removal.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from backend.app.ingestion.models import LegalDocument
from backend.app.ingestion.paths import checked_path, source_path
from backend.app.ingestion.pipeline import canonical_json, read_bounded, _unique_object, _reject_constant
from .models import Attribution, Candidate, Decision, Event, Span

ZERO = "0" * 64
POLICY = "stage2f-v1"
SPEC = "docs/legal-passage-review-stage2f.json"
QA = "docs/legal-text-quality-stage2e.json"
LEDGER = "backend/data/reviews/stage2f/v1"
TRANSITIONS = {
    "pending": {"approved", "rejected", "needs_correction"},
    "approved": {"rejected", "needs_correction"},
    "needs_correction": {"pending", "rejected"},
    "rejected": set(),
}
HARD_EXCLUSIONS = {
    "devanagari_mapping_unverified", "legacy_hindi_glyph_codes",
    "table_or_form_layout_unverified", "marginal_citation_association_unverified",
    "replacement_character", "unexpected_control", "possible_mojibake",
    "private_surrogate_or_unassigned_unicode", "invisible_or_directional_format_character",
    "duplicate_page_text", "empty_page",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(read_bounded(Path(path), 8 * 1024 * 1024).decode("utf-8-sig"),
                      object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def model_hash(model, excluded):
    return sha(canonical_json(model.model_dump(mode="json", exclude=excluded)))


class Catalog:
    def __init__(self, root):
        self.root = checked_path(Path(root))
        spec = read_json(source_path(self.root, SPEC))
        self.config = spec["catalog"]
        if self.config["policy_version"] != POLICY:
            raise ValueError("Unsupported review policy")
        self.digest = sha(canonical_json(self.config))
        self.verify_pins()
        self.qa_hash = sha(read_bounded(source_path(self.root, QA), 8 * 1024 * 1024))
        self.qa = read_json(source_path(self.root, QA))
        if not self.qa.get("documents") or not all(self.qa["ledger_checks"].values()):
            raise ValueError("QA catalogue failed its ledger checks")
        self.documents = {d["document_id"]: d for d in self.qa["documents"]}
        if len(self.documents) != len(self.qa["documents"]):
            raise ValueError("Duplicate document identities")

    def verify_pins(self):
        if sha(canonical_json(read_json(source_path(self.root, SPEC))["catalog"])) != self.digest:
            raise ValueError("Review catalogue changed during session")
        for name, expected in self.config["input_pins"].items():
            if sha(read_bounded(source_path(self.root, name), 8 * 1024 * 1024)) != expected:
                raise ValueError("Stale source catalogue or QA input: " + name)

    def document(self, document_id):
        self.verify_pins()
        item = self.documents.get(document_id)
        if item is None or item["readiness"] == "BLOCKED" or not all(item["invariants"].values()):
            raise ValueError("Document absent from approved QA catalogue or blocked")
        raw = read_bounded(source_path(self.root, item["raw_path"]), 25 * 1024 * 1024)
        payload = read_bounded(source_path(self.root, item["processed_path"]), 128 * 1024 * 1024)
        doc = LegalDocument.model_validate_json(payload)
        if sha(raw) != item["raw_sha256"] or sha(raw) != doc.source_file.sha256:
            raise ValueError("Stale raw PDF hash")
        if sha(payload) != item["processed_sha256"] or doc.document_id != document_id:
            raise ValueError("Stale processed source version")
        if not len(doc.pages) == item["pdf_pages"] == len(item["pages"]):
            raise ValueError("Source/QA page count mismatch")
        if doc.verification_status != "not_independently_verified" or doc.metadata.legal_applicability is not None:
            raise ValueError("Unexpected provenance/applicability contract")
        return item, doc


def span_text(doc, span):
    if not 1 <= span.physical_page <= len(doc.pages):
        raise ValueError("Physical page outside source")
    page = doc.pages[span.physical_page - 1]
    lines = page.text.split("\n")
    if (page.page_id != span.page_id or page.ordinal != span.physical_page
            or page.page_number != span.physical_page or span.end_line > len(lines)):
        raise ValueError("Ambiguous page/line boundary")
    text = "\n".join(lines[span.start_line - 1:span.end_line])
    if not text.strip() or sha(text.encode("utf-8")) != span.text_sha256:
        raise ValueError("Exact passage text hash mismatch")
    return text


def make_span(doc, page, start, end):
    if type(page) is not int or not 1 <= page <= len(doc.pages):
        raise ValueError("Invalid physical page")
    p = doc.pages[page - 1]
    lines = p.text.split("\n")
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        raise ValueError("Invalid line boundaries")
    return Span(page_id=p.page_id, physical_page=page, start_line=start, end_line=end,
                text_sha256=sha("\n".join(lines[start - 1:end]).encode("utf-8")))


def selection_hash(doc, spans):
    # Hash the exact UTF-8 text plus explicit page/line boundaries, never a silently
    # joined cross-page string. Each individual span also has its plain-text hash.
    return sha(canonical_json({"spans": [dict(**s.model_dump(), text=span_text(doc, s)) for s in spans]}))


def preview(catalog, document_id, boundaries, contexts, rationale, cross_page_context=None, attribution=None):
    item, doc = catalog.document(document_id)
    spans = [make_span(doc, *b) for b in boundaries]
    context = [make_span(doc, *b) for b in contexts]
    candidate = Candidate(candidate_id="passage_" + ZERO, catalog_sha256=catalog.digest,
        qa_sha256=catalog.qa_hash, document_id=document_id,
        raw_path=item["raw_path"], raw_sha256=item["raw_sha256"],
        processed_path=item["processed_path"], processed_sha256=item["processed_sha256"],
        source_metadata=doc.metadata, original_identifiers=item["metadata_for_citations"]["original_identifiers"],
        spans=spans, context_spans=context, passage_sha256=selection_hash(doc, spans),
        context_sha256=selection_hash(doc, context), context_rationale=rationale,
        cross_page_context=cross_page_context,
        attribution=attribution or Attribution(kind="document_only"))
    candidate = candidate.model_copy(update={"candidate_id": "passage_" + model_hash(candidate, {"candidate_id"})})
    validate_candidate(catalog, candidate)
    return candidate


def validate_candidate(catalog, candidate):
    item, doc = catalog.document(candidate.document_id)
    if candidate.catalog_sha256 != catalog.digest or candidate.qa_sha256 != catalog.qa_hash:
        raise ValueError("Stale review catalogue or QA version")
    if candidate.candidate_id != "passage_" + model_hash(candidate, {"candidate_id"}):
        raise ValueError("Tampered candidate identity")
    actual = (item["raw_path"], item["raw_sha256"], item["processed_path"], item["processed_sha256"],
              doc.metadata, item["metadata_for_citations"]["original_identifiers"])
    supplied = (candidate.raw_path, candidate.raw_sha256, candidate.processed_path,
                candidate.processed_sha256, candidate.source_metadata, candidate.original_identifiers)
    if actual != supplied:
        raise ValueError("Candidate source identity/provenance differs")
    if selection_hash(doc, candidate.spans) != candidate.passage_sha256 or selection_hash(doc, candidate.context_spans) != candidate.context_sha256:
        raise ValueError("Passage or context binding differs")
    numbers = [s.physical_page for s in candidate.spans]
    if numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        raise ValueError("Ambiguous, overlapping or skipped passage pages")
    if len(set(s.physical_page for s in candidate.context_spans)) != len(candidate.context_spans):
        raise ValueError("Duplicate context page boundaries")
    if sum(len(span_text(doc, s)) for s in candidate.spans) > 12000:
        raise ValueError("Passage exceeds narrow 12,000-character limit")
    for span in candidate.spans:
        if not any(c.physical_page == span.physical_page and c.start_line <= span.start_line and c.end_line >= span.end_line for c in candidate.context_spans):
            raise ValueError("Selected text must have enclosing explicit context")
    if len(candidate.spans) > 1:
        if not candidate.cross_page_context:
            raise ValueError("Cross-page association requires explicit context rationale")
        for left, right in zip(candidate.spans, candidate.spans[1:]):
            if left.end_line != len(doc.pages[left.physical_page - 1].text.split("\n")) or right.start_line != 1:
                raise ValueError("Cross-page passage has an ambiguous gap at page boundary")
    elif candidate.cross_page_context is not None:
        raise ValueError("Single-page selection must not assert a cross-page association")
    a = candidate.attribution
    if a.kind == "printed_label":
        text = span_text(doc, a.anchor)
        if (a.label not in text or not re.fullmatch(r"(?:S\.O\.\s*\d+\(E\)\.?|(?:Section|Sec\.|Rule|Article)\s+\d+[A-Za-z]?(?:\([0-9A-Za-z]+\))*|\d+\.)", a.label)
                or a.anchor.start_line != a.anchor.end_line
                or a.anchor.physical_page != candidate.spans[0].physical_page
                or a.anchor.start_line != candidate.spans[0].start_line
                or not re.match(r"^" + re.escape(a.label) + r"(?:$|\s*[:.\u2014\u2013-]|\s+\()", text.strip())):
            raise ValueError("Ambiguous section/subsection attribution; use document_only")
    return item, doc


def exclusion_reasons(item, candidate):
    # Conservative page-wide quarantine also covers detached marginal associations
    # and graphics which may have no extracted characters/precise line location.
    reasons = set()
    for span in [*candidate.spans, *candidate.context_spans]:
        page = item["pages"][span.physical_page - 1]
        if not all(page["automatic_checks"].values()):
            reasons.add("failed_page_invariant")
        reasons.update(f["code"] for f in page["findings"] if f["code"] in HARD_EXCLUSIONS)
    notification = item.get("notification_exception_check")
    if notification and notification.get("location"):
        location = notification["location"]
        for span in candidate.spans:
            if (span.physical_page == notification["pdf_page"]
                    and span.start_line <= location["end_line"] and span.end_line >= location["start_line"]
                    and not (span.start_line <= location["start_line"] and span.end_line >= location["end_line"])):
                reasons.add("incomplete_notification_operative_paragraph")
    return sorted(reasons)


def validate_evidence(catalog, candidate, decision):
    for evidence in decision.evidence:
        if sha(read_bounded(source_path(catalog.root, evidence.file_path), 25 * 1024 * 1024)) != evidence.sha256:
            raise ValueError("Stale decision evidence reference")
    if decision.decision != "approved":
        return
    pages = {s.physical_page for s in [*candidate.spans, *candidate.context_spans]}
    rendered = set()
    qa_seen = False
    for ref in decision.evidence:
        if ref.kind == "rendered_pdf_page" and ref.file_path == candidate.raw_path and ref.sha256 == candidate.raw_sha256:
            rendered.update(ref.physical_pages)
        if ref.kind == "qa_report" and ref.file_path == QA and ref.sha256 == candidate.qa_sha256:
            qa_seen = pages.issubset(set(ref.physical_pages)) or qa_seen
    att = decision.attestations
    if not (pages.issubset(rendered) and qa_seen and att.visual_comparison_performed
            and att.boundaries_and_attribution_verified and att.qualifiers_and_exceptions_preserved
            and att.archival_scope_only and (len(candidate.spans) == 1 or att.cross_page_context_verified)):
        raise ValueError("Missing explicit reviewer approval evidence/attestations")


def validate_approval(catalog, candidate, decision):
    item, _ = validate_candidate(catalog, candidate)
    reasons = exclusion_reasons(item, candidate)
    if reasons:
        raise ValueError("Excluded unresolved source passages: " + ", ".join(reasons))
    validate_evidence(catalog, candidate, decision)


class ReviewStore:
    def __init__(self, catalog):
        self.catalog = catalog
        self.path = checked_path(catalog.root / LEDGER)

    def replay(self, checkpoint=None):
        if not self.path.exists():
            events = []
        else:
            paths = sorted(self.path.iterdir())
            if any(not p.is_file() or not re.fullmatch(r"\d{8}_[0-9a-f]{64}\.json", p.name) for p in paths):
                raise ValueError("Unrecognized audit entry or unfinished write; fail closed")
            events = [Event.model_validate(read_json(checked_path(p))) for p in paths]
        states, previous = {}, ZERO
        for number, event in enumerate(events, 1):
            expected = model_hash(event, {"event_sha256"})
            if event.sequence != number or event.previous_sha256 != previous or event.event_sha256 != expected:
                raise ValueError("Audit hash chain/sequence tampering")
            if self.path.joinpath(f"{number:08d}_{expected}.json").is_file() is False:
                raise ValueError("Audit filename differs from event digest")
            state = states.get(event.candidate_id)
            if state is None:
                if event.review.decision != "pending" or event.candidate is None or event.candidate_id != event.candidate.candidate_id:
                    raise ValueError("Missing pending submission or candidate")
                if event.candidate.candidate_id != "passage_" + model_hash(event.candidate, {"candidate_id"}):
                    raise ValueError("Tampered submitted candidate")
                state = dict(candidate=event.candidate, review=event.review, event_sha256=expected)
                states[event.candidate_id] = state
            else:
                if event.candidate is not None or event.review.decision not in TRANSITIONS[state["review"].decision]:
                    raise ValueError("Invalid audit state transition")
                if event.review.decision_time < state["review"].decision_time:
                    raise ValueError("Decision time precedes previous decision")
                state.update(review=event.review, event_sha256=expected)
            previous = expected
        if checkpoint:
            count, digest = checkpoint
            if len(events) != count or (count and events[-1].event_sha256 != digest) or (not count and digest != ZERO):
                raise ValueError("Audit checkpoint mismatch; possible tail deletion/rewrite")
        return events, states

    def append(self, candidate, review, confirm_candidate, *, submit=False, approve_one=False):
        if confirm_candidate != candidate.candidate_id:
            raise ValueError("Explicit single-candidate confirmation required")
        if (review.decision == "approved") != approve_one:
            raise ValueError("Approval requires the explicit approve-one action")
        # Validate everything before creating storage, and again under write lock.
        if submit:
            if review.decision != "pending":
                raise ValueError("New candidates must start pending; no direct approval")
            validate_candidate(self.catalog, candidate)
        if review.decision == "approved":
            validate_approval(self.catalog, candidate, review)
        else:
            validate_evidence(self.catalog, candidate, review)
        checked_path(self.path.parent).mkdir(parents=True, exist_ok=True)
        lock = checked_path(self.path.parent / ".stage2f-write.lock")
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        temporary = None
        try:
            events, states = self.replay()
            state = states.get(candidate.candidate_id)
            if submit:
                if state is not None:
                    raise ValueError("Candidate already submitted")
            elif state is None or state["candidate"] != candidate or review.decision not in TRANSITIONS[state["review"].decision]:
                raise ValueError("Invalid state transition or missing pending review")
            if state and review.decision_time < state["review"].decision_time:
                raise ValueError("Decision time precedes previous decision")
            if review.decision == "approved":
                validate_approval(self.catalog, candidate, review)
            event = Event(sequence=len(events) + 1, previous_sha256=events[-1].event_sha256 if events else ZERO,
                candidate_id=candidate.candidate_id, candidate=candidate if submit else None,
                review=review, event_sha256=ZERO)
            event = event.model_copy(update={"event_sha256": model_hash(event, {"event_sha256"})})
            self.path.mkdir(exist_ok=True)
            checked_path(self.path)
            with tempfile.NamedTemporaryFile(prefix=".event-", dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(canonical_json(event.model_dump(mode="json")))
                stream.flush()
                os.fsync(stream.fileno())
            target = checked_path(self.path / f"{event.sequence:08d}_{event.event_sha256}.json")
            os.link(temporary, target, follow_symlinks=False)
            temporary.unlink()
            temporary = None
            target.chmod(stat.S_IREAD)
            return event
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            os.close(handle)
            lock.unlink()

    def inspect(self, candidate):
        item, doc = validate_candidate(self.catalog, candidate)
        return dict(candidate=candidate.model_dump(mode="json"),
            selected=[dict(**s.model_dump(), text=span_text(doc, s)) for s in candidate.spans],
            context=[dict(**s.model_dump(), text=span_text(doc, s)) for s in candidate.context_spans],
            qa_pages=[item["pages"][s.physical_page - 1] for s in candidate.spans],
            exclusion_reasons=exclusion_reasons(item, candidate),
            eligible=False, reason="Inspection is not an approval")

    def allowlist(self, checkpoint=None):
        events, states = self.replay(checkpoint)
        entries, blocked = [], []
        for identifier, state in sorted(states.items()):
            if state["review"].decision != "approved":
                continue
            try:
                if checkpoint is None:
                    raise ValueError("Retained trusted latest checkpoint required for approval export")
                validate_approval(self.catalog, state["candidate"], state["review"])
                entries.append(dict(candidate=state["candidate"].model_dump(mode="json"),
                    approval=state["review"].model_dump(mode="json"), approval_event_sha256=state["event_sha256"]))
            except (ValueError, OSError) as exc:
                blocked.append(dict(candidate_id=identifier, reason=str(exc)))
        return dict(schema_version=1, policy_version=POLICY, scope="archival_text_only",
            entries=entries, blocked=blocked,
            checkpoint=dict(sequence=len(events), event_sha256=events[-1].event_sha256 if events else ZERO),
            legal_currentness="unknown; no approval here certifies current commencement or applicability")
