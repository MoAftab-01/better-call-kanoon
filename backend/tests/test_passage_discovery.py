"""Discovery fixtures are SYNTHETIC SOFTWARE DATA, NOT real law or approvals."""

import copy
import json
from pathlib import Path
import stat

import pytest
from pydantic import ValidationError

from backend.app.ingestion.pipeline import canonical_json, ingest_manifest, load_manifest
from backend.discovery.__main__ import main
from backend.discovery.passages import LABEL, SCRATCH, discover, export_packets
from backend.qa.legal_text import check_document
from backend.review.models import Candidate, Decision
from backend.review.service import Catalog, QA, SPEC, ReviewStore, sha
from backend.review.synthetic_demo import create_demo


def configure(root, count=1, *, notification=True, revision="v1"):
    """Reuse the Stage 2F synthetic raw PDF; rebuild only synthetic fixture versions."""
    source = root / "backend/data/raw/synthetic-not-law.pdf"
    original = json.loads((root / "docs/synthetic-manifest.json").read_bytes())
    entries = []
    for n in range(count):
        entry = copy.deepcopy(original["documents"][0])
        entry["metadata"].update(instrument_type="notification" if notification else "other",
            official_title=f"SYNTHETIC FIXTURE {n} - NOT LAW",
            source_url=f"https://example.invalid/synthetic-{n}",
            amendment_version=f"SYNTHETIC revision {revision} - NOT LAW")
        entries.append(entry)
    path = root / "docs/discovery-fixture-manifest.json"
    path.write_bytes(canonical_json(dict(schema_version=1, documents=entries)))
    manifest = load_manifest(path)
    results = ingest_manifest(path, root / f"backend/data/processed/discovery-fixture/{revision}", source_root=source.parent)
    docs = []
    for n, (result, entry) in enumerate(zip(results, manifest.documents, strict=True)):
        previous = dict(document=f"SYNTHETIC FIXTURE {n} - NOT LAW",
            raw_path=source.relative_to(root).as_posix(),
            output_path=result.output_path.relative_to(root).as_posix(),
            source_sha256=sha(source.read_bytes()), output_sha256=sha(result.output_path.read_bytes()),
            original_identifiers={"fixture": f"SYNTHETIC {n} - NOT LAW"})
        acquired = dict(sha256=previous["source_sha256"], byte_size=source.stat().st_size,
                        page_count=2, commencement_review=None)
        qa = check_document(root, previous, acquired, entry, [])
        record = json.loads(result.output_path.read_bytes())
        text = "\n".join(record["pages"][0]["text"].split("\n")[1:4])
        qa["notification_exception_check"] = dict(pdf_page=1,
            location=dict(start_line=2, end_line=4, text=text),
            exact_exception="No real legal effect is asserted.", subsequent_status="unverified") if notification else None
        docs.append(qa)
    (root / QA).write_bytes(canonical_json(dict(ledger_checks={"synthetic_fixture": True}, documents=docs)))
    (root / SPEC).write_bytes(canonical_json(dict(schema_version=1, catalog=dict(policy_version="stage2f-v1",
        input_pins={QA: sha((root / QA).read_bytes()), path.relative_to(root).as_posix(): sha(path.read_bytes())}))))


@pytest.fixture
def fixture_root(tmp_path):
    root = tmp_path / "SYNTHETIC-NOT-LAW"
    create_demo(root)  # Unsigned templates only; no submission or approval events.
    configure(root)
    return root


def edit_qa(root, edit):
    data = json.loads((root / QA).read_bytes())
    edit(data)
    (root / QA).write_bytes(canonical_json(data))
    spec = json.loads((root / SPEC).read_bytes())
    spec["catalog"]["input_pins"][QA] = sha((root / QA).read_bytes())
    (root / SPEC).write_bytes(canonical_json(spec))


def inventory(root):
    return {p.relative_to(root).as_posix(): (sha(p.read_bytes()), p.stat().st_mtime_ns, p.stat().st_mode)
            for p in root.rglob("*") if p.is_file()}


def test_discovery_is_deterministic_and_preserves_all_inputs(fixture_root):
    before = inventory(fixture_root)
    first = discover(fixture_root)
    assert first == discover(fixture_root)
    assert inventory(fixture_root) == before
    report, packets = first
    assert report["proposed_count"] == len(packets) == 1
    assert report["review_before"] == report["review_after"]
    assert packets[0]["label"] == LABEL
    assert not packets[0]["submitted"] and not packets[0]["approved"] and not packets[0]["eligible"]
    assert packets[0]["candidate"]["attribution"]["kind"] == "document_only"


def test_zero_suitable_candidates_does_not_force_quota(fixture_root):
    configure(fixture_root, notification=False, revision="other")
    report, packets = discover(fixture_root)
    assert packets == [] and report["proposed_count"] == 0
    assert report["skipped"][0]["reason"] == "outside_notification_paragraph_scope"


@pytest.mark.parametrize("field", ["raw_path", "processed_path"])
def test_hash_mismatch_aborts_before_export(fixture_root, field):
    qa = json.loads((fixture_root / QA).read_bytes())
    p = fixture_root / qa["documents"][0][field]
    p.chmod(0o600)
    p.write_bytes(p.read_bytes() + b" ")
    target = fixture_root / SCRATCH / "must-not-exist"
    with pytest.raises(ValueError, match="Stale"):
        export_packets(fixture_root, target)
    assert not target.exists()


def test_stale_qa_pin_is_not_silently_treated_as_zero_candidates(fixture_root):
    (fixture_root / QA).write_bytes((fixture_root / QA).read_bytes() + b" ")
    with pytest.raises(ValueError, match="Stale"):
        discover(fixture_root)


def test_source_revision_changes_proposal_and_catalogue_bindings(fixture_root):
    old_report, old_packets = discover(fixture_root)
    old = old_packets[0]["candidate"]
    configure(fixture_root, revision="v2")
    new_report, new_packets = discover(fixture_root)
    new = new_packets[0]["candidate"]
    assert old["raw_sha256"] == new["raw_sha256"]
    assert old["processed_sha256"] != new["processed_sha256"]
    assert old["candidate_id"] != new["candidate_id"]
    assert old_report["catalog_sha256"] != new_report["catalog_sha256"]


@pytest.mark.parametrize("code", ["legacy_hindi_glyph_codes", "marginal_citation_association_unverified",
    "table_or_form_layout_unverified", "replacement_character"])
def test_required_context_page_exclusion_cannot_be_trimmed_away(fixture_root, code):
    # Signal lies outside selected lines 2-4, but in required whole-page context.
    edit_qa(fixture_root, lambda qa: qa["documents"][0]["pages"][0]["findings"].append(
        dict(code=code, start_line=1, end_line=1)))
    report, packets = discover(fixture_root)
    assert packets == []
    assert report["skipped"][0]["reason"] == "stage2f_hard_exclusion"
    assert code in report["skipped"][0]["exclusion_reasons"]


@pytest.mark.parametrize("change", ["text", "line", "cross_page", "extra_context"])
def test_ambiguous_or_cross_page_profiles_are_not_invented(fixture_root, change):
    def edit(qa):
        info = qa["documents"][0]["notification_exception_check"]
        if change == "text":
            info["location"]["text"] += " SYNTHETIC invented extra text"
        elif change == "line":
            info["location"]["end_line"] = 10000
        elif change == "cross_page":
            info["end_pdf_page"] = 2
        else:
            info["required_context_pages"] = [1, 2]
    edit_qa(fixture_root, edit)
    report, packets = discover(fixture_root)
    assert not packets and report["skipped"]
    assert report["skipped"][0]["reason"] in {"qa_paragraph_text_or_boundary_mismatch",
        "cross_page_or_out_of_range_lines", "cross_page_or_ambiguous_qa_boundaries"}


def test_complete_paragraph_qualifiers_and_furniture_are_preserved(fixture_root):
    _, packets = discover(fixture_root)
    packet = packets[0]
    original = json.loads((fixture_root / packet["candidate"]["processed_path"]).read_bytes())
    assert packet["exact_passage"][0]["text"] == "\n".join(original["pages"][0]["text"].split("\n")[1:4])
    assert "No real legal effect is asserted." in packet["exact_passage"][0]["text"]
    assert packet["surrounding_context"][0]["text"] == original["pages"][0]["text"]


def test_no_automatic_submission_or_approval(fixture_root, monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("Discovery must never append a review event")
    monkeypatch.setattr(ReviewStore, "append", prohibited)
    store = ReviewStore(Catalog(fixture_root))
    assert store.allowlist()["entries"] == []
    discover(fixture_root)
    assert store.replay() == ([], {}) and store.allowlist()["entries"] == []
    assert not store.path.exists()


def test_export_packets_are_separate_read_only_and_not_submission_records(fixture_root):
    before = inventory(fixture_root)
    target = fixture_root / SCRATCH / "packets"
    result = export_packets(fixture_root, target)
    assert len(result["packet_export"]["files"]) == 1
    file = result["packet_export"]["files"][0]
    path = fixture_root / file["path"]
    packet = json.loads(path.read_bytes())
    assert sha(path.read_bytes()) == file["sha256"]
    assert not path.stat().st_mode & stat.S_IWRITE
    Candidate.model_validate(packet["candidate"])
    with pytest.raises(ValidationError):
        Candidate.model_validate(packet)  # Packet wrapper is not a Stage 2F submission.
    after = inventory(fixture_root)
    assert all(after[name] == state for name, state in before.items())
    assert all(name.startswith(SCRATCH + "/") for name in after.keys() - before.keys())
    assert not ReviewStore(Catalog(fixture_root)).path.exists()
    with pytest.raises(ValueError, match="already exists"):
        export_packets(fixture_root, target)


@pytest.mark.parametrize("relative", ["backend/data/raw/unsafe", "backend/data/reviews/unsafe", ".git/unsafe", "docs/unsafe"])
def test_export_cannot_write_to_protected_or_audit_directories(fixture_root, relative):
    target = fixture_root / relative
    with pytest.raises(ValueError, match="Exports must"):
        export_packets(fixture_root, target)
    assert not target.exists()


def test_limit_is_five_total_not_per_document_and_order_is_stable(fixture_root):
    configure(fixture_root, count=7, revision="many")
    report, packets = discover(fixture_root)
    assert len(packets) == report["examined_operative_paragraphs"] == 5
    assert sum(s["reason"] == "discovery_limit_reached" for s in report["skipped"]) == 2
    assert len(discover(fixture_root, limit=2)[1]) == 2
    for bad in [0, 6, True]:
        with pytest.raises(ValueError, match="1 to 5"):
            discover(fixture_root, bad)


def test_read_only_cli_preview_and_empty_history(fixture_root, capsys):
    prefix = ["--synthetic-workspace", str(fixture_root)]
    before = inventory(fixture_root)
    assert main(prefix + ["discover"]) == 0
    report = json.loads(capsys.readouterr().out)
    identifier = report["proposals"][0]["candidate_id"]
    assert main(prefix + ["preview", identifier]) == 0
    assert json.loads(capsys.readouterr().out)["label"] == LABEL
    assert inventory(fixture_root) == before
    assert main(prefix + ["discover", "--limit", "6"]) == 2
    capsys.readouterr()


def test_nonempty_review_history_is_not_reset_or_hidden(fixture_root):
    _, packets = discover(fixture_root)
    c = Candidate.model_validate(packets[0]["candidate"])
    decision = json.loads((fixture_root / "pending-request.json").read_bytes())
    for ref in decision["evidence"]:
        ref["sha256"] = sha((fixture_root / ref["file_path"]).read_bytes())
    store = ReviewStore(Catalog(fixture_root))
    store.append(c, Decision.model_validate(decision), c.candidate_id, submit=True)
    before = inventory(fixture_root)
    with pytest.raises(ValueError, match="empty review history"):
        discover(fixture_root)
    assert inventory(fixture_root) == before
