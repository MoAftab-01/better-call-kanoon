"""QA-only tests. All generated content is SYNTHETIC SOFTWARE DATA, NOT LAW."""

import json
from pathlib import Path

import pymupdf
import pytest

from backend.app.ingestion.models import LegalDocument
from backend.app.ingestion.pipeline import ingest_manifest, load_manifest
from backend.qa.legal_text import (
    check_document, duplicate_groups, paragraph_location, section_coverage,
    sha, text_findings,
)


@pytest.mark.parametrize("text,code", [
    ("SYNTHETIC \ufffd", "replacement_character"),
    ("SYNTHETIC \x00", "unexpected_control"),
    ("SYNTHETIC \ue000", "private_surrogate_or_unassigned_unicode"),
    ("SYNTHETIC \u202e", "invisible_or_directional_format_character"),
    ("SYNTHETIC Ã©", "possible_mojibake"),
    ("SYNTHETIC\t  label", "unusual_whitespace_candidate"),
    ("SYNTHETIC हिन्दी", "devanagari_mapping_unverified"),
    ("SYNTHETIC vlk/kkj.k", "legacy_hindi_glyph_codes"),
])
def test_suspicious_text_is_located_and_preserved(text, code):
    before = text.encode()
    signals = text_findings("SYNTHETIC HEADER\n" + text)
    signal = next(f for f in signals if f["code"] == code)
    assert signal["start_line"] == signal["end_line"] == 2
    assert signal["evidence"] == text
    assert text.encode() == before


def test_legitimate_unicode_and_numbering_are_not_called_corrupt():
    codes = {f["code"] for f in text_findings("SYNTHETIC ONLY\n1. ₹ १०० — practice.")}
    assert "devanagari_mapping_unverified" in codes
    assert not codes & {"unexpected_control", "replacement_character", "possible_mojibake"}


def test_duplicate_pages_are_distinct_from_repeated_headers():
    a = "SYNTHETIC HEADER\nFirst practice page."
    b = "SYNTHETIC HEADER\nDifferent practice page."
    assert duplicate_groups([a, b, a, ""]) == [[1, 3]]
    assert duplicate_groups([a, b]) == []


def test_boundary_signal_does_not_assert_actual_truncation():
    text = "SYNTHETIC practice content that continues beyond this physical page without a period"
    result = text_findings(text)
    assert any(f["code"] == "possible_page_boundary_continuation" and f["method"] == "automatic_heuristic" for f in result)


def test_paragraph_matching_keeps_original_line_breaks_and_qualifications():
    text = "SYNTHETIC\nAppointed date, except\nthe practice exception.\nFOOTER"
    location = paragraph_location(text, "Appointed date, except the practice exception.")
    assert location == dict(start_line=2, end_line=3, text="Appointed date, except\nthe practice exception.")
    assert paragraph_location(text, "Invented practice sentence.") is None


@pytest.fixture
def synthetic_qa(tmp_path):
    raw = tmp_path / "raw.pdf"
    with pymupdf.open() as pdf:
        for text in ["SYNTHETIC ONLY - NOT LAW\nSection 7. Practice label\nPractice text.", "SYNTHETIC ONLY - NOT LAW\nContinuation without a guessed identifier."]:
            pdf.new_page().insert_text((50, 60), text)
        pdf.save(raw)
    data = json.loads((Path(__file__).parent / "fixtures/synthetic-manifest.json").read_text(encoding="utf-8"))
    data["documents"][0]["file_path"] = raw.name
    data["documents"][0]["expected_sha256"] = sha(raw.read_bytes())
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    result = ingest_manifest(manifest, tmp_path / "output")[0]
    raw.chmod(0o444)
    entry = load_manifest(manifest).documents[0]
    previous = dict(document="SYNTHETIC QA FIXTURE - NOT LAW", raw_path=raw.name,
                    output_path=result.output_path.relative_to(tmp_path).as_posix(),
                    source_sha256=entry.expected_sha256,
                    output_sha256=sha(result.output_path.read_bytes()),
                    original_identifiers={"label": "SYNTHETIC ONLY"})
    acquired = dict(sha256=entry.expected_sha256, byte_size=raw.stat().st_size,
                    page_count=2, commencement_review=None)
    return tmp_path, previous, acquired, entry


def test_qa_determinism_and_automatic_match_never_grants_visual_approval(synthetic_qa):
    first = check_document(*synthetic_qa, [])
    assert first == check_document(*synthetic_qa, [])
    assert all(all(p["automatic_checks"].values()) for p in first["pages"])
    assert all(not p["visual_reviews"] and not p["verified_evidence_eligible"] for p in first["pages"])


def test_bad_recorded_hash_blocks_document(synthetic_qa):
    root, previous, acquired, entry = synthetic_qa
    acquired["sha256"] = "0" * 64
    report = check_document(root, previous, acquired, entry, [])
    assert report["readiness"] == "BLOCKED" and not report["invariants"]["raw_hash"]


def test_swapped_processed_pages_are_detected(synthetic_qa):
    root, previous, acquired, entry = synthetic_qa
    path = root / previous["output_path"]
    data = json.loads(path.read_bytes())
    data["pages"].reverse()
    path.write_text(json.dumps(data), encoding="utf-8")
    previous["output_sha256"] = sha(path.read_bytes())
    report = check_document(root, previous, acquired, entry, [])
    assert report["readiness"] == "BLOCKED"
    assert not report["pages"][0]["automatic_checks"]["physical_order"]
    assert not report["pages"][0]["automatic_checks"]["extracted_text_match"]


def test_section_gap_is_detected(synthetic_qa):
    root, previous, _, _ = synthetic_qa
    record = LegalDocument.model_validate_json((root / previous["output_path"]).read_bytes())
    assert section_coverage(record.pages[0], record.sections)
    assert not section_coverage(record.pages[0], record.sections[1:])


def test_visual_review_cannot_be_reused_for_different_bytes(synthetic_qa):
    root, previous, acquired, entry = synthetic_qa
    visual = [dict(document=previous["document"], pdf_page=1, source_sha256="0" * 64)]
    with pytest.raises(ValueError, match="different source bytes"):
        check_document(root, previous, acquired, entry, visual)
