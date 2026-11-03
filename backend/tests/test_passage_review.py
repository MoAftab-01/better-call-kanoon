"""All generated sources, actors and review events are SYNTHETIC, NOT LAW."""

from datetime import datetime, timezone
import json
from pathlib import Path
import stat

import pytest
from pydantic import ValidationError

from backend.app.ingestion.pipeline import canonical_json
from backend.review.__main__ import main
from backend.review.models import Attribution, Attestations, Candidate, Decision
from backend.review.service import Catalog, ReviewStore, QA, SPEC, ZERO, make_span, model_hash, preview, sha
from backend.review.synthetic_demo import create_demo


@pytest.fixture
def demo(tmp_path):
    root = tmp_path / "synthetic-workspace"
    create_demo(root)
    catalog = Catalog(root)
    candidate = Candidate.model_validate_json((root / "candidate.json").read_bytes())
    return root, catalog, candidate, ReviewStore(catalog)


def request(root, state="pending", day=1, approved=False):
    value = json.loads((root / "pending-request.json").read_bytes())
    value.update(decision=state, decision_time=datetime(2026, 1, day, tzinfo=timezone.utc).isoformat())
    for ref in value["evidence"]:
        ref["sha256"] = sha((root / ref["file_path"]).read_bytes())
    if approved:
        value["attestations"] = dict(visual_comparison_performed=True,
            boundaries_and_attribution_verified=True, qualifiers_and_exceptions_preserved=True,
            archival_scope_only=True, cross_page_context_verified=True)
    return Decision.model_validate(value)


def submit(demo):
    root, catalog, candidate, store = demo
    return store.append(candidate, request(root), candidate.candidate_id, submit=True)


def repin(root):
    spec = json.loads((root / SPEC).read_bytes())
    for name in spec["catalog"]["input_pins"]:
        spec["catalog"]["input_pins"][name] = sha((root / name).read_bytes())
    (root / SPEC).write_bytes(canonical_json(spec))


def test_read_only_defaults_do_not_create_storage_or_approve(demo, capsys):
    root, _, _, store = demo
    assert store.allowlist()["entries"] == [] and not store.path.exists()
    for command in ["list", "verify", "allowlist", "documents", "history"]:
        assert main(["--synthetic-workspace", str(root), command]) == 0
    assert not store.path.exists()
    assert '"candidates": []' in capsys.readouterr().out


def test_preview_is_deterministic_and_does_not_create_pending(demo):
    _, catalog, c, store = demo
    other = preview(catalog, c.document_id, [(1, 2, 4)], [(1, 1, 4)], c.context_rationale)
    assert c == other and store.replay() == ([], {})


def test_only_explicit_single_review_promotes_and_preserves_history(demo):
    root, _, c, store = demo
    first = submit(demo)
    assert store.allowlist()["entries"] == []
    approved = store.append(c, request(root, "approved", 2, True), c.candidate_id, approve_one=True)
    assert not store.allowlist()["entries"]
    assert len(store.allowlist((approved.sequence, approved.event_sha256))["entries"]) == 1
    assert len(store.replay()[0]) == 2
    assert first.event_sha256 != approved.event_sha256
    for p in store.path.iterdir():
        assert not p.stat().st_mode & stat.S_IWRITE
    store.append(c, request(root, "rejected", 3), c.candidate_id)
    assert store.allowlist()["entries"] == [] and len(store.replay()[0]) == 3


@pytest.mark.parametrize("field", ["reviewer_id", "decision_time", "rationale", "evidence"])
def test_missing_review_identity_time_rationale_or_evidence_is_rejected(demo, field):
    root, _, _, _ = demo
    data = request(root).model_dump(mode="json")
    del data[field]
    with pytest.raises(ValidationError):
        Decision.model_validate(data)


def test_no_implicit_or_direct_initial_approval(demo):
    root, _, c, store = demo
    with pytest.raises(ValueError, match="approve-one"):
        store.append(c, request(root, "approved", 2, True), c.candidate_id)
    with pytest.raises(ValueError, match="start pending"):
        store.append(c, request(root, "approved", 2, True), c.candidate_id, submit=True, approve_one=True)
    assert not store.path.exists()


def test_approval_requires_attestations_and_exact_confirmation(demo):
    root, _, c, store = demo
    submit(demo)
    with pytest.raises(ValueError, match="confirmation"):
        store.append(c, request(root, "approved", 2, True), "all", approve_one=True)
    with pytest.raises(ValueError, match="attestations"):
        store.append(c, request(root, "approved", 2), c.candidate_id, approve_one=True)
    assert len(store.replay()[0]) == 1


def test_invalid_state_transitions_and_backdated_review(demo):
    root, _, c, store = demo
    submit(demo)
    with pytest.raises(ValueError, match="transition"):
        store.append(c, request(root, "pending", 2), c.candidate_id)
    store.append(c, request(root, "needs_correction", 2), c.candidate_id)
    with pytest.raises(ValueError, match="transition"):
        store.append(c, request(root, "approved", 3, True), c.candidate_id, approve_one=True)
    with pytest.raises(ValueError, match="precedes"):
        store.append(c, request(root, "pending", 1), c.candidate_id)
    store.append(c, request(root, "pending", 3), c.candidate_id)
    assert store.allowlist()["entries"] == []


@pytest.mark.parametrize("which", ["raw_path", "processed_path"])
def test_stale_source_hash_with_already_loaded_catalogue_denies_export(demo, which):
    root, _, c, store = demo
    submit(demo)
    approved = store.append(c, request(root, "approved", 2, True), c.candidate_id, approve_one=True)
    p = root / getattr(c, which)
    p.chmod(0o600)
    p.write_bytes(p.read_bytes() + b" ")
    output = store.allowlist((approved.sequence, approved.event_sha256))
    assert not output["entries"] and len(output["blocked"]) == 1


def test_catalogue_and_qa_version_changes_invalidate_old_candidate(demo):
    root, catalog, c, store = demo
    submit(demo)
    (root / QA).write_bytes((root / QA).read_bytes() + b" ")
    with pytest.raises(ValueError, match="Stale"):
        store.inspect(c)
    repin(root)
    new = Catalog(root)
    with pytest.raises(ValueError, match="Stale review"):
        ReviewStore(new).inspect(c)


def test_text_hash_or_provenance_tampering_is_rejected(demo):
    root, _, c, store = demo
    changed = c.model_copy(update={"passage_sha256": ZERO})
    with pytest.raises(ValueError, match="Tampered"):
        store.inspect(changed)
    changed = changed.model_copy(update={"candidate_id": "passage_" + model_hash(changed, {"candidate_id"})})
    with pytest.raises(ValueError, match="binding"):
        store.inspect(changed)
    changed = c.model_copy(update={"original_identifiers": {"fiction": "changed"}})
    changed = changed.model_copy(update={"candidate_id": "passage_" + model_hash(changed, {"candidate_id"})})
    with pytest.raises(ValueError, match="provenance"):
        store.inspect(changed)


def test_tampered_event_and_tail_deletion_checkpoint(demo):
    root, _, c, store = demo
    submit(demo)
    last = store.append(c, request(root, "approved", 2, True), c.candidate_id, approve_one=True)
    checkpoint = (last.sequence, last.event_sha256)
    path = sorted(store.path.iterdir())[-1]
    original = path.read_bytes()
    path.chmod(0o600)
    value = json.loads(original)
    value["review"]["rationale"] = "SYNTHETIC tampering"
    path.write_bytes(canonical_json(value))
    with pytest.raises(ValueError, match="tampering"):
        store.allowlist()
    path.write_bytes(original)
    path.unlink()
    with pytest.raises(ValueError, match="checkpoint"):
        store.allowlist(checkpoint)


@pytest.mark.parametrize("code", ["legacy_hindi_glyph_codes", "devanagari_mapping_unverified",
    "table_or_form_layout_unverified", "marginal_citation_association_unverified",
    "unexpected_control", "replacement_character"])
def test_unresolved_exclusions_cannot_be_overridden_by_approval(demo, code):
    root, _, old, _ = demo
    qa = json.loads((root / QA).read_bytes())
    qa["documents"][0]["pages"][0]["findings"].append(dict(code=code, start_line=1, end_line=1))
    (root / QA).write_bytes(canonical_json(qa))
    repin(root)
    catalog = Catalog(root)
    c = preview(catalog, old.document_id, [(1, 2, 4)], [(1, 1, 4)], "SYNTHETIC context")
    store = ReviewStore(catalog)
    store.append(c, request(root), c.candidate_id, submit=True)
    with pytest.raises(ValueError, match="Excluded"):
        store.append(c, request(root, "approved", 2, True), c.candidate_id, approve_one=True)
    assert not store.allowlist()["entries"]


def test_explicit_cross_page_context_required_and_gaps_rejected(demo):
    _, catalog, c, _ = demo
    with pytest.raises(ValueError, match="Cross-page"):
        preview(catalog, c.document_id, [(1, 3, 4), (2, 1, 2)], [(1, 1, 4), (2, 1, 3)], "SYNTHETIC context")
    with pytest.raises(ValueError, match="gap"):
        preview(catalog, c.document_id, [(1, 2, 3), (2, 1, 2)], [(1, 1, 4), (2, 1, 3)], "SYNTHETIC context", "Explicit fictional continuation")
    valid = preview(catalog, c.document_id, [(1, 3, 4), (2, 1, 2)], [(1, 1, 4), (2, 1, 3)], "SYNTHETIC context", "Explicit fictional continuation")
    assert len(valid.spans) == 2


def test_ambiguous_subsection_and_prose_reference_are_not_attribution(demo):
    _, catalog, c, _ = demo
    _, doc = catalog.document(c.document_id)
    for label in ["(2)", "Section 106(2)"]:
        with pytest.raises(ValueError, match="attribution"):
            preview(catalog, c.document_id, [(1, 2, 4)], [(1, 1, 4)], "SYNTHETIC context",
                attribution=Attribution(kind="printed_label", label=label, anchor=make_span(doc, 1, 2, 2)))
    good = preview(catalog, c.document_id, [(1, 2, 4)], [(1, 1, 4)], "SYNTHETIC context",
        attribution=Attribution(kind="printed_label", label="Section 1", anchor=make_span(doc, 1, 2, 2)))
    assert good.attribution.kind == "printed_label"


def test_partial_notification_paragraph_cannot_drop_qualifiers(demo):
    root, _, old, _ = demo
    qa = json.loads((root / QA).read_bytes())
    qa["documents"][0]["notification_exception_check"] = dict(pdf_page=1, location=dict(start_line=2, end_line=4), exact_exception="SYNTHETIC condition")
    (root / QA).write_bytes(canonical_json(qa))
    repin(root)
    catalog = Catalog(root)
    c = preview(catalog, old.document_id, [(1, 2, 3)], [(1, 1, 4)], "SYNTHETIC notification context")
    store = ReviewStore(catalog)
    store.append(c, request(root), c.candidate_id, submit=True)
    with pytest.raises(ValueError, match="incomplete_notification"):
        store.append(c, request(root, "approved", 2, True), c.candidate_id, approve_one=True)


def test_unsafe_bulk_requests_are_not_accepted(demo, capsys):
    root, _, c, _ = demo
    array = root / "bulk.json"
    array.write_text(json.dumps([request(root).model_dump(mode="json")]*2), encoding="utf-8")
    assert main(["--synthetic-workspace", str(root), "submit", "--candidate-file", str(root/"candidate.json"),
                 "--decision-file", str(array), "--confirm-candidate", c.candidate_id]) == 2
    with pytest.raises(SystemExit):
        main(["--synthetic-workspace", str(root), "record-decision", "--all"])


def test_unsafe_paths_and_current_applicability_scope_are_rejected(demo):
    _, _, c, _ = demo
    value = c.model_dump(mode="json")
    value["raw_path"] = "../outside.pdf"
    with pytest.raises(ValidationError):
        Candidate.model_validate(value)
    value = c.model_dump(mode="json")
    value["scope"] = "current_law"
    with pytest.raises(ValidationError):
        Candidate.model_validate(value)


def test_cross_page_approval_requires_all_context_pages_and_attestation(demo):
    root, catalog, old, _ = demo
    c = preview(catalog, old.document_id, [(1, 3, 4), (2, 1, 2)], [(1, 1, 4), (2, 1, 3)],
                "SYNTHETIC context", "Explicit fictional continuation")
    store = ReviewStore(catalog)
    store.append(c, request(root), c.candidate_id, submit=True)
    value = request(root, "approved", 2, True).model_dump(mode="json")
    with pytest.raises(ValueError, match="attestations"):
        store.append(c, Decision.model_validate(value), c.candidate_id, approve_one=True)
    for ref in value["evidence"]:
        ref["physical_pages"] = [1, 2]
    value["attestations"]["cross_page_context_verified"] = False
    with pytest.raises(ValueError, match="attestations"):
        store.append(c, Decision.model_validate(value), c.candidate_id, approve_one=True)
    value["attestations"]["cross_page_context_verified"] = True
    final = store.append(c, Decision.model_validate(value), c.candidate_id, approve_one=True)
    assert len(store.allowlist((final.sequence, final.event_sha256))["entries"]) == 1


def test_changed_external_evidence_invalidates_approval(demo):
    root, _, c, store = demo
    extra = root / "docs/synthetic-context.txt"
    extra.write_text("SYNTHETIC context evidence", encoding="utf-8")
    submit(demo)
    data = request(root, "approved", 2, True).model_dump(mode="json")
    data["evidence"].append(dict(kind="context_review", file_path="docs/synthetic-context.txt",
        sha256=sha(extra.read_bytes()), physical_pages=[1], note="SYNTHETIC evidence reference"))
    final = store.append(c, Decision.model_validate(data), c.candidate_id, approve_one=True)
    assert store.allowlist((final.sequence, final.event_sha256))["entries"]
    extra.write_text("SYNTHETIC changed", encoding="utf-8")
    assert not store.allowlist((final.sequence, final.event_sha256))["entries"]


def test_newer_or_wrong_checkpoint_fails_closed(demo):
    root, _, c, store = demo
    first = submit(demo)
    store.append(c, request(root, "needs_correction", 2), c.candidate_id)
    with pytest.raises(ValueError, match="checkpoint"):
        store.allowlist((first.sequence, first.event_sha256))
    with pytest.raises(ValueError, match="checkpoint"):
        store.allowlist((99, ZERO))


def test_explicit_synthetic_cli_workflow_and_checkpoint_export(demo, capsys):
    root, _, c, _ = demo
    prefix = ["--synthetic-workspace", str(root)]
    assert main(prefix + ["submit", "--candidate-file", str(root/"candidate.json"),
        "--decision-file", str(root/"pending-request.json"), "--confirm-candidate", c.candidate_id]) == 0
    capsys.readouterr()
    request_path = root / "explicit-synthetic-approval.json"
    request_path.write_bytes(canonical_json(request(root, "approved", 2, True).model_dump(mode="json")))
    command = prefix + ["record-decision", "--candidate", c.candidate_id,
        "--decision-file", str(request_path), "--confirm-candidate", c.candidate_id]
    assert main(command) == 2  # No accidental approval without the explicit action.
    capsys.readouterr()
    assert main(command + ["--approve-one"]) == 0
    receipt = json.loads(capsys.readouterr().out)["retain_checkpoint"]
    assert main(prefix + ["allowlist"]) == 0
    assert json.loads(capsys.readouterr().out)["entries"] == []
    token = f"{receipt['sequence']}:{receipt['event_sha256']}"
    assert main(prefix + ["allowlist", "--checkpoint", token]) == 0
    exported = json.loads(capsys.readouterr().out)
    assert len(exported["entries"]) == 1
    assert exported["entries"][0]["candidate"]["source_metadata"]["source_type"] == "synthetic"
