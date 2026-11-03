"""Human-workflow regressions. ALL writes/actors/events are SYNTHETIC, NOT LAW.

The real catalogue is never used for a write-path test. No reviewer identity or
human visual attestation is created for any real source by these tests.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.ingestion.pipeline import canonical_json, ingest_manifest, load_manifest
from backend.discovery.__main__ import main as discovery_cli
from backend.discovery.passages import discover, LABEL
from backend.qa.legal_text import check_document
from backend.review.__main__ import main as review_cli
from backend.review.models import Candidate, Decision
from backend.review.service import Catalog, QA, SPEC, ReviewStore, sha
from backend.review.synthetic_demo import create_demo

PROJECT = Path(__file__).resolve().parents[2]


@pytest.fixture
def exercise(tmp_path):
    root = tmp_path / "SYNTHETIC-HUMAN-WORKFLOW-NOT-LAW"
    create_demo(root)  # Creates unsigned templates, NEVER audit events.
    raw = root / "backend/data/raw/synthetic-not-law.pdf"
    data = json.loads((root / "docs/synthetic-manifest.json").read_bytes())
    data["documents"][0]["metadata"].update(instrument_type="notification",
        official_title="SYNTHETIC OPERATOR EXERCISE - NOT LAW")
    manifest_path = root / "docs/operator-fixture-manifest.json"
    manifest_path.write_bytes(canonical_json(data))
    result = ingest_manifest(manifest_path, root / "backend/data/processed/operator-fixture/v1", source_root=raw.parent)[0]
    record = json.loads(result.output_path.read_bytes())
    previous = dict(document="SYNTHETIC OPERATOR EXERCISE - NOT LAW",
        raw_path=raw.relative_to(root).as_posix(), output_path=result.output_path.relative_to(root).as_posix(),
        source_sha256=sha(raw.read_bytes()), output_sha256=sha(result.output_path.read_bytes()),
        original_identifiers={"fixture": "SYNTHETIC SOFTWARE DATA ONLY"})
    acquired = dict(sha256=previous["source_sha256"], byte_size=raw.stat().st_size,
                    page_count=2, commencement_review=None)
    qa = check_document(root, previous, acquired, load_manifest(manifest_path).documents[0], [])
    qa["notification_exception_check"] = dict(pdf_page=1,
        location=dict(start_line=2, end_line=4, text="\n".join(record["pages"][0]["text"].split("\n")[1:4])),
        exact_exception="No real legal effect is asserted.", subsequent_status="unverified")
    (root / QA).write_bytes(canonical_json(dict(ledger_checks={"synthetic_fixture": True}, documents=[qa])))
    (root / SPEC).write_bytes(canonical_json(dict(schema_version=1, catalog=dict(policy_version="stage2f-v1",
        input_pins={QA: sha((root / QA).read_bytes()), manifest_path.relative_to(root).as_posix(): sha(manifest_path.read_bytes())}))))
    _, packets = discover(root)
    packet = packets[0]
    candidate = Candidate.model_validate(packet["candidate"])
    assert root.is_relative_to(tmp_path) and candidate.source_metadata.source_type == "synthetic"
    (root / "operator-candidate.json").write_bytes(canonical_json(candidate.model_dump(mode="json")))
    return root, packet, candidate, ReviewStore(Catalog(root))


def decision(root, state="pending", day=1, attested=False):
    value = json.loads((root / "pending-request.json").read_bytes())
    value.update(decision=state, reviewer_id="SYNTHETIC TEST ACTOR - NOT A HUMAN LEGAL APPROVAL",
        decision_time=datetime(2026, 1, day, tzinfo=timezone.utc).isoformat(),
        rationale="SYNTHETIC workflow simulation only; no real source has been reviewed or approved.")
    for ref in value["evidence"]:
        ref["sha256"] = sha((root / ref["file_path"]).read_bytes())
    if attested:
        value["attestations"].update(visual_comparison_performed=True,
            boundaries_and_attribution_verified=True, qualifiers_and_exceptions_preserved=True,
            archival_scope_only=True)
    return Decision.model_validate(value)


def pending(exercise):
    root, _, candidate, store = exercise
    return store.append(candidate, decision(root), candidate.candidate_id, submit=True)


def approve_synthetic(exercise):
    root, _, candidate, store = exercise
    pending(exercise)
    return store.append(candidate, decision(root, "approved", 2, True), candidate.candidate_id, approve_one=True)


def pointer(value, path):
    for key in path.split("/")[1:]:
        value = value[int(key)] if isinstance(value, list) else value[key.replace("~1", "/").replace("~0", "~")]
    return value


def test_one_packet_presentation_covers_runbook_fields_without_approval(exercise, capsys):
    root, packet, c, store = exercise
    spec = json.loads((PROJECT / "docs/review-presentation-contract.json").read_bytes())
    for path in spec["presentation_json_pointers"]:
        pointer(packet, path)  # Unknown applicability is deliberately present as null.
    assert discovery_cli(["--synthetic-workspace", str(root), "preview", c.candidate_id]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown == packet and shown["label"] == LABEL
    assert shown["candidate"]["legal_currentness"] == "unknown"
    assert shown["candidate"]["source_metadata"]["legal_applicability"] is None
    assert shown["exact_passage"] and shown["surrounding_context"] and shown["qa_pages"]
    assert not any(shown[k] for k in ["submitted", "approved", "eligible"])
    assert store.replay() == ([], {}) and not store.path.exists()


def test_binding_tampering_cannot_be_presented_as_original_evidence(exercise):
    _, _, c, store = exercise
    changed = c.model_copy(update={"processed_sha256": "0" * 64})
    with pytest.raises(ValueError, match="Tampered"):
        store.inspect(changed)
    assert store.replay() == ([], {})


@pytest.mark.parametrize("missing", ["reviewer_id", "decision_time", "rationale", "evidence"])
def test_operator_information_cannot_be_omitted(exercise, missing):
    root, _, _, store = exercise
    value = decision(root, "approved", 2, True).model_dump(mode="json")
    del value[missing]
    with pytest.raises(ValidationError):
        Decision.model_validate(value)
    assert store.replay() == ([], {})


@pytest.mark.parametrize("false_field", ["visual_comparison_performed", "boundaries_and_attribution_verified",
    "qualifiers_and_exceptions_preserved", "archival_scope_only", "ALL_MISSING"])
def test_false_or_missing_human_attestations_never_approve(exercise, false_field):
    root, _, c, store = exercise
    pending(exercise)
    value = decision(root, "approved", 2, True).model_dump(mode="json")
    if false_field == "ALL_MISSING":
        del value["attestations"]
    else:
        value["attestations"][false_field] = False
    with pytest.raises(ValueError, match="attestations"):
        store.append(c, Decision.model_validate(value), c.candidate_id, approve_one=True)
    assert len(store.replay()[0]) == 1 and not store.allowlist()["entries"]


@pytest.mark.parametrize("failure", ["wrong_candidate", "missing_explicit_action"])
def test_operator_must_confirm_one_candidate_and_explicit_approval(exercise, failure):
    root, _, c, store = exercise
    pending(exercise)
    identifier = "passage_" + "0" * 64 if failure == "wrong_candidate" else c.candidate_id
    with pytest.raises(ValueError):
        store.append(c, decision(root, "approved", 2, True), identifier,
                     approve_one=failure != "missing_explicit_action")
    assert len(store.replay()[0]) == 1


@pytest.mark.parametrize("withdrawal", ["rejected", "needs_correction"])
def test_withdrawal_is_a_new_event_and_removes_export_eligibility(exercise, withdrawal):
    root, _, c, store = exercise
    approved = approve_synthetic(exercise)
    assert len(store.allowlist((approved.sequence, approved.event_sha256))["entries"]) == 1
    before = {p.name: p.read_bytes() for p in store.path.iterdir()}
    latest = store.append(c, decision(root, withdrawal, 3), c.candidate_id)
    assert all((store.path / name).read_bytes() == data for name, data in before.items())
    assert len(store.replay()[0]) == 3
    assert store.allowlist((latest.sequence, latest.event_sha256))["entries"] == []
    with pytest.raises(ValueError, match="checkpoint"):
        store.allowlist((approved.sequence, approved.event_sha256))


def test_export_requires_a_retained_matching_checkpoint(exercise):
    _, _, _, store = exercise
    approved = approve_synthetic(exercise)
    assert store.allowlist()["entries"] == []
    with pytest.raises(ValueError, match="checkpoint"):
        store.allowlist((approved.sequence, "0" * 64))
    assert len(store.allowlist((approved.sequence, approved.event_sha256))["entries"]) == 1


@pytest.mark.parametrize("tamper", ["raw", "processed", "evidence"])
def test_source_or_evidence_changes_fail_closed(exercise, tamper):
    root, _, c, store = exercise
    extra = root / "synthetic-visual-note.txt"
    extra.write_text("SYNTHETIC evidence note, not real inspection", encoding="utf-8")
    pending(exercise)
    value = decision(root, "approved", 2, True).model_dump(mode="json")
    value["evidence"].append(dict(kind="context_review", file_path=extra.name,
        sha256=sha(extra.read_bytes()), physical_pages=[1], note="SYNTHETIC TEST EVIDENCE ONLY"))
    approved = store.append(c, Decision.model_validate(value), c.candidate_id, approve_one=True)
    target = {"raw": root / c.raw_path, "processed": root / c.processed_path, "evidence": extra}[tamper]
    target.chmod(0o600)  # Synthetic fixtures ONLY; no real source is ever edited.
    target.write_bytes(target.read_bytes() + b" ")
    exported = store.allowlist((approved.sequence, approved.event_sha256))
    assert not exported["entries"] and exported["blocked"]


def test_read_only_inspection_keeps_source_bytes_and_review_history_unchanged(exercise):
    root, _, c, store = exercise
    sources = [root / c.raw_path, root / c.processed_path, root / QA, root / SPEC]
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns, p.stat().st_mode) for p in sources}
    for _ in range(2):
        inspected = store.inspect(c)
        assert inspected["eligible"] is False and inspected["exclusion_reasons"] == []
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns, p.stat().st_mode) for p in sources}
    assert store.replay() == ([], {}) and store.allowlist()["entries"] == []


def test_operator_read_only_commands_never_call_the_event_writer(exercise, monkeypatch, capsys):
    root, _, c, store = exercise

    def prohibited(*args, **kwargs):
        raise AssertionError("Read-only human presentation must never append a review event")

    monkeypatch.setattr(ReviewStore, "append", prohibited)
    prefix = ["--synthetic-workspace", str(root)]
    for command in ["list", "verify", "allowlist", "history"]:
        assert review_cli(prefix + [command]) == 0
        capsys.readouterr()
    assert discovery_cli(prefix + ["preview", c.candidate_id]) == 0
    capsys.readouterr()
    assert store.replay() == ([], {}) and not store.path.exists()


def test_synthetic_cli_decision_requires_separate_action_and_truthful_fields(exercise, capsys):
    root, _, c, store = exercise
    request_file = root / "explicit-synthetic-request.json"
    request_file.write_bytes(canonical_json(decision(root).model_dump(mode="json")))
    prefix = ["--synthetic-workspace", str(root)]
    assert review_cli(prefix + ["submit", "--candidate-file", str(root / "operator-candidate.json"),
        "--decision-file", str(request_file), "--confirm-candidate", c.candidate_id]) == 0
    capsys.readouterr()
    request_file.write_bytes(canonical_json(decision(root, "approved", 2, True).model_dump(mode="json")))
    args = prefix + ["record-decision", "--candidate", c.candidate_id,
                    "--decision-file", str(request_file), "--confirm-candidate", c.candidate_id]
    assert review_cli(args) == 2
    capsys.readouterr()
    assert review_cli(args + ["--approve-one"]) == 0
    receipt = json.loads(capsys.readouterr().out)["retain_checkpoint"]
    assert len(store.allowlist((receipt["sequence"], receipt["event_sha256"]))["entries"]) == 1
    assert c.source_metadata.source_type == "synthetic"
