"""All documents in this module are SYNTHETIC SOFTWARE FIXTURES, NOT REAL LAWS."""

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
import pytest

from backend.app.ingestion.extraction import extract_pages, extract_sections, normalize_text
from backend.app.ingestion.models import LegalDocument, LegalMetadata
from backend.app.ingestion.paths import output_path
from backend.app.ingestion.pipeline import canonical_json, ingest_manifest, load_manifest

FIXTURES = Path(__file__).parent / "fixtures"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXED_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def sample(tmp_path):
    source = tmp_path / "inputs"
    source.mkdir()
    for path in FIXTURES.iterdir():
        shutil.copyfile(path, source / path.name)
    return source / "synthetic-manifest.json", tmp_path / "output"


def manifest_data(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(path, value):
    path.write_bytes(canonical_json(value))


def read_record(result):
    return LegalDocument.model_validate_json(result.output_path.read_bytes())


def synthetic_pdf(path, pages):
    with pymupdf.open() as pdf:
        for body in pages:
            page = pdf.new_page()
            if body:
                page.insert_text((50, 60), body)
        pdf.save(path)


def switch_source(manifest, filename):
    data = manifest_data(manifest)
    data["documents"][0]["file_path"] = filename
    write_manifest(manifest, data)


def directory_link(link, target):
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        # Windows junctions exercise real reparse-point protection without admin privileges.
        safe_link = str(link).replace("'", "''")
        safe_target = str(target).replace("'", "''")
        command = f"New-Item -ItemType Junction -Path '{safe_link}' -Target '{safe_target}' -ErrorAction Stop | Out-Null"
        subprocess.run(["powershell", "-NoProfile", "-Command", command], check=True, capture_output=True)


def test_txt_provenance_unicode_unknown_dates_and_source_immutability(sample):
    manifest, output = sample
    source = manifest.parent / "synthetic-not-law.txt"
    before = source.read_bytes(), source.stat().st_mtime_ns, manifest.read_bytes()
    result = ingest_manifest(manifest, output, ingested_at=FIXED_TIME)[0]
    record = read_record(result)
    assert result.status == "created"
    assert record.source_file.sha256 == hashlib.sha256(before[0]).hexdigest()
    assert record.source_file.size_bytes == len(before[0])
    assert record.verification_status == "not_independently_verified"
    assert record.provenance_status == "user_supplied"
    assert record.metadata.effective_date is None
    assert record.metadata.legal_applicability is None
    assert record.metadata.jurisdiction is None
    assert record.metadata.issuing_authority is None
    assert record.pages[0].page_number is None
    assert "हिन्दी, ₹ १०,०००" in record.pages[0].text
    assert "hyphen-\nremain" in record.pages[0].text
    assert "synthetic_fixture_not_law" in record.warnings
    assert (source.read_bytes(), source.stat().st_mtime_ns, manifest.read_bytes()) == before


def test_repeat_ingestion_is_byte_identical_and_preserves_first_timestamp(sample):
    manifest, output = sample
    first = ingest_manifest(manifest, output, ingested_at=FIXED_TIME)[0]
    before = first.output_path.read_bytes(), first.output_path.stat().st_mtime_ns
    second = ingest_manifest(manifest, output)[0]
    assert second.status == "unchanged"
    assert second.document_id == first.document_id
    assert (second.output_path.read_bytes(), second.output_path.stat().st_mtime_ns) == before
    assert read_record(second).ingested_at == FIXED_TIME
    assert len(list(output.iterdir())) == 1


def test_same_inputs_and_clock_produce_deterministic_json(sample):
    manifest, output = sample
    first = ingest_manifest(manifest, output, ingested_at=FIXED_TIME)[0]
    second = ingest_manifest(manifest, output.parent / "other", ingested_at=FIXED_TIME)[0]
    assert first.output_path.read_bytes() == second.output_path.read_bytes()
    assert first.output_path.read_bytes().endswith(b"\n")


def test_document_ids_do_not_depend_on_local_filename_or_manifest_key_order(sample):
    manifest, output = sample
    first = ingest_manifest(manifest, output)[0]
    shutil.copyfile(manifest.parent / "synthetic-not-law.txt", manifest.parent / "renamed.TXT")
    data = manifest_data(manifest)
    data["documents"][0]["file_path"] = "renamed.TXT"
    data["documents"][0]["metadata"] = dict(reversed(list(data["documents"][0]["metadata"].items())))
    write_manifest(manifest, data)
    second = ingest_manifest(manifest, output)[0]
    assert second.document_id == first.document_id
    assert second.status == "unchanged"


def test_metadata_or_source_change_creates_new_identity(sample):
    manifest, output = sample
    first = ingest_manifest(manifest, output)[0]
    data = manifest_data(manifest)
    data["documents"][0]["metadata"]["amendment_version"] = "Synthetic fixture revision B; not a real amendment"
    write_manifest(manifest, data)
    second = ingest_manifest(manifest, output)[0]
    with (manifest.parent / "synthetic-not-law.txt").open("a", encoding="utf-8") as stream:
        stream.write("\nAdditional synthetic software test text.\n")
    third = ingest_manifest(manifest, output)[0]
    assert len({first.document_id, second.document_id, third.document_id}) == 3


def test_official_domain_and_user_claim_are_never_independent_verification(sample):
    manifest, output = sample
    data = manifest_data(manifest)
    metadata = data["documents"][0]["metadata"]
    url = "https://indiacode.nic.in/SYNTHETIC-NOT-LAW?x=1%2F2#UserReference"
    metadata["source_url"] = url
    metadata["source_type"] = "official_portal"  # Merely a supplied claim, not a real source.
    metadata["provenance"]["verification_claim"] = "user_claimed_verified"
    metadata["provenance"]["verification_evidence"] = "Synthetic test claim only; no independent check."
    write_manifest(manifest, data)
    record = read_record(ingest_manifest(manifest, output)[0])
    assert record.metadata.source_url == url
    assert record.metadata.provenance.verification_claim == "user_claimed_verified"
    assert record.verification_status == "not_independently_verified"


@pytest.mark.parametrize("field,value", [
    ("official_title", "   "), ("instrument_type", "invented_kind"),
    ("source_type", "automatically_verified"), ("language", ""),
    ("publication_date", "2026-02-30"), ("effective_date", "2026"),
    ("retrieval_date", 1735689600), ("enactment_date", True),
    ("source_url", "file:///secret.txt"), ("source_url", "https://"),
    ("source_url", "https://user:synthetic-password@example.invalid/"),
    ("source_url", " https://example.invalid/"),
    ("verification_status", "independently_verified"),
])
def test_invalid_metadata_is_rejected_before_writing(sample, field, value):
    manifest, output = sample
    data = manifest_data(manifest)
    data["documents"][0]["metadata"][field] = value
    write_manifest(manifest, data)
    with pytest.raises(ValueError, match="Invalid metadata manifest"):
        ingest_manifest(manifest, output)
    assert not output.exists()


@pytest.mark.parametrize("field", ["official_title", "instrument_type", "jurisdiction", "issuing_authority", "source_url", "source_type", "language", "provenance"])
def test_required_metadata_is_not_inferred(sample, field):
    manifest, output = sample
    data = manifest_data(manifest)
    del data["documents"][0]["metadata"][field]
    write_manifest(manifest, data)
    with pytest.raises(ValueError, match="Invalid metadata manifest"):
        ingest_manifest(manifest, output)
    assert not output.exists()


def test_dates_and_applicability_are_supplied_not_inferred(sample):
    manifest, output = sample
    data = manifest_data(manifest)
    metadata = data["documents"][0]["metadata"]
    metadata.update({"publication_date": "2026-01-01", "effective_date": "2027-03-04", "state": "Synthetic state label; not real applicability"})
    write_manifest(manifest, data)
    record = read_record(ingest_manifest(manifest, output)[0])
    assert record.metadata.publication_date.isoformat() == "2026-01-01"
    assert record.metadata.effective_date.isoformat() == "2027-03-04"
    assert record.metadata.enactment_date is None
    assert record.metadata.legal_applicability is None


@pytest.mark.parametrize("claim", ["independently_verified", "verified"])
def test_user_cannot_assign_independent_verification_status(sample, claim):
    manifest, output = sample
    data = manifest_data(manifest)
    data["documents"][0]["metadata"]["provenance"]["verification_claim"] = claim
    write_manifest(manifest, data)
    with pytest.raises(ValueError):
        ingest_manifest(manifest, output)


@pytest.mark.parametrize("unsafe", ["../outside.txt", "nested/../../outside.txt", "/outside.txt", "C:/outside.txt", "C:outside.txt", "\\\\host\\share\\outside.txt", "nested\\outside.txt", "nested/./source.txt", "a//b.txt", "NUL.txt", "nested/COM1.txt", "file.txt:stream", "tail./file.txt"])
def test_source_path_traversal_and_windows_device_paths_rejected(sample, unsafe):
    manifest, output = sample
    switch_source(manifest, unsafe)
    with pytest.raises(ValueError):
        ingest_manifest(manifest, output)
    assert not output.exists()


def test_nested_sources_and_configured_source_root(sample, tmp_path):
    manifest, output = sample
    nested = tmp_path / "separate-sources" / "nested"
    nested.mkdir(parents=True)
    shutil.copyfile(manifest.parent / "synthetic-not-law.txt", nested / "sample.txt")
    switch_source(manifest, "nested/sample.txt")
    result = ingest_manifest(manifest, output, source_root=nested.parent)[0]
    assert result.status == "created"


def test_output_traversal_and_git_output_are_rejected(sample):
    manifest, output = sample
    for unsafe in [output / ".." / "escaped", output.parent / ".git" / "records"]:
        with pytest.raises(ValueError):
            ingest_manifest(manifest, unsafe)
    with pytest.raises(ValueError):
        output_path(output, "../../outside")


@pytest.mark.parametrize("kind", ["source", "output", "output_parent"])
def test_directory_symlinks_or_windows_junctions_cannot_escape(sample, tmp_path, kind):
    manifest, output = sample
    external = tmp_path / "external"
    external.mkdir()
    if kind == "source":
        shutil.copyfile(manifest.parent / "synthetic-not-law.txt", external / "sample.txt")
        directory_link(manifest.parent / "linked", external)
        switch_source(manifest, "linked/sample.txt")
    elif kind == "output":
        directory_link(output, external)
    else:
        directory_link(output, external)
        output = output / "nested"
    before = sorted(p.name for p in external.iterdir())
    with pytest.raises(ValueError, match="reparse|Symlinks"):
        ingest_manifest(manifest, output)
    assert sorted(p.name for p in external.iterdir()) == before


def test_existing_output_hardlink_cannot_overwrite_an_external_file(sample, tmp_path):
    manifest, output = sample
    result = ingest_manifest(manifest, output)[0]
    result.output_path.unlink()
    external = tmp_path / "external.json"
    external.write_text("SYNTHETIC SENTINEL — not a legal record", encoding="utf-8")
    os.link(external, result.output_path)
    before = external.read_bytes()
    with pytest.raises(ValueError, match="refusing to overwrite"):
        ingest_manifest(manifest, output)
    assert external.read_bytes() == before


@pytest.mark.parametrize("filename,content", [("empty.txt", b""), ("blank.txt", b" \n \n"), ("bad.txt", b"\xff"), ("nul.txt", b"synthetic\x00text"), ("fixture.docx", b"not supported"), ("bad.pdf", b"not a PDF"), ("corrupt.pdf", b"%PDF-1.7\nSYNTHETIC INVALID PDF")])
def test_unsupported_invalid_and_empty_sources_fail_without_output(sample, filename, content):
    manifest, output = sample
    (manifest.parent / filename).write_bytes(content)
    switch_source(manifest, filename)
    with pytest.raises(ValueError):
        ingest_manifest(manifest, output)
    assert not output.exists()


def test_size_limit_and_expected_hash_checked_before_extraction(sample):
    manifest, output = sample
    with pytest.raises(ValueError, match="size limit"):
        ingest_manifest(manifest, output, max_file_bytes=16)
    data = manifest_data(manifest)
    data["documents"][0]["expected_sha256"] = "0" * 64
    write_manifest(manifest, data)
    with pytest.raises(ValueError, match="SHA-256"):
        ingest_manifest(manifest, output)
    source = manifest.parent / "synthetic-not-law.txt"
    data["documents"][0]["expected_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    write_manifest(manifest, data)
    assert ingest_manifest(manifest, output)[0].status == "created"


def test_pdf_preserves_physical_pages_and_does_not_infer_cross_page_sections(sample):
    manifest, output = sample
    pdf = manifest.parent / "synthetic.pdf"
    synthetic_pdf(pdf, ["SYNTHETIC TEST ONLY - NOT LAW\nSection 7. Practice heading\nPractice content.", "SYNTHETIC TEST ONLY - NOT LAW\nContinuation with no explicit section heading.", ""])
    before = pdf.read_bytes(), pdf.stat().st_mtime_ns
    switch_source(manifest, pdf.name)
    record = read_record(ingest_manifest(manifest, output)[0])
    assert [page.page_number for page in record.pages] == [1, 2, 3]
    assert record.pages[2].text == ""
    assert "empty_or_image_only_page" in record.pages[2].warnings
    assert all("pdf_reading_order_unverified" in page.warnings for page in record.pages)
    assert record.sections[-1].page_number == 2
    assert record.sections[-1].identifier is None
    assert any(section.identifier == "Section 7" for section in record.sections)
    assert (pdf.read_bytes(), pdf.stat().st_mtime_ns) == before


def test_image_only_or_blank_pdf_requires_ocr_instead_of_inventing_text(sample):
    manifest, output = sample
    pdf = manifest.parent / "scan.pdf"
    synthetic_pdf(pdf, [""])
    switch_source(manifest, pdf.name)
    with pytest.raises(ValueError, match="No extractable text"):
        ingest_manifest(manifest, output)
    assert not output.exists()


def test_password_protected_pdf_rejected(sample):
    manifest, output = sample
    pdf_path = manifest.parent / "encrypted.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((50, 60), "SYNTHETIC TEST ONLY - NOT LAW")
        pdf.save(pdf_path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="synthetic-only", owner_pw="synthetic-owner")
    switch_source(manifest, pdf_path.name)
    with pytest.raises(ValueError, match="Encrypted"):
        ingest_manifest(manifest, output)


def test_normalization_preserves_meaningful_spacing_unicode_and_numbering():
    raw = "\r\nSYNTHETIC ONLY  \r\n  १. हिन्दी\u200d  ₹\u00a0100\tX  \r\nword-\r\ncontinuation\r\n\r\n"
    assert normalize_text(raw) == "SYNTHETIC ONLY\n  १. हिन्दी\u200d  ₹\u00a0100\tX\nword-\ncontinuation"


def test_utf8_bom_is_accepted_without_unicode_loss():
    pages, _ = extract_pages(b"\xef\xbb\xbf" + "SYNTHETIC ONLY — हिन्दी".encode(), ".txt", "doc_" + "a" * 64)
    assert pages[0].text == "SYNTHETIC ONLY — हिन्दी"


def test_bare_numbers_cross_references_and_non_english_headings_are_not_guessed():
    text = "SYNTHETIC ONLY\n1. Bare numeric practice text\nSection 12 applies to this synthetic example.\nSee Section 13.\nधारा १ — केवल कृत्रिम परीक्षण"
    pages, _ = extract_pages(text.encode(), ".txt", "doc_" + "a" * 64)
    sections = extract_sections(pages, "doc_" + "a" * 64)
    assert len(sections) == 1
    assert sections[0].identifier is None
    assert sections[0].text == text
    assert sections[0].structure_status == "unidentified"


def test_sections_cover_every_normalized_line_without_losing_uncertain_text(sample):
    manifest, output = sample
    record = read_record(ingest_manifest(manifest, output)[0])
    assert [section.identifier for section in record.sections] == [None, "Section 1", "Section 2"]
    assert "\n".join(section.text for section in record.sections) == record.pages[0].text
    for section in record.sections:
        lines = record.pages[0].text.split("\n")
        assert section.text == "\n".join(lines[section.start_line - 1:section.end_line])
        assert section.page_id == record.pages[0].page_id
        assert section.uncertainties


def test_collection_duplicates_are_idempotent_and_selection_is_explicit(sample):
    manifest, output = sample
    data = manifest_data(manifest)
    duplicate = copy.deepcopy(data["documents"][0])
    other = copy.deepcopy(duplicate)
    shutil.copyfile(manifest.parent / "synthetic-not-law.txt", manifest.parent / "other.txt")
    other["file_path"] = "other.txt"
    other["metadata"]["official_title"] = "SECOND SYNTHETIC FIXTURE — NOT LAW"
    data["documents"] += [duplicate, other]
    write_manifest(manifest, data)
    results = ingest_manifest(manifest, output)
    assert [result.status for result in results] == ["created", "unchanged", "created"]
    assert len(list(output.glob("*.json"))) == 2
    selected = ingest_manifest(manifest, output, document="other.txt")
    assert len(selected) == 1 and selected[0].status == "unchanged"
    with pytest.raises(ValueError, match="not listed"):
        ingest_manifest(manifest, output, document="missing.txt")


def test_collection_preflight_does_not_write_if_later_source_is_invalid(sample):
    manifest, output = sample
    data = manifest_data(manifest)
    later = copy.deepcopy(data["documents"][0])
    later["file_path"] = "missing.pdf"
    data["documents"].append(later)
    write_manifest(manifest, data)
    with pytest.raises((ValueError, OSError)):
        ingest_manifest(manifest, output)
    assert not output.exists()


@pytest.mark.parametrize("tamper", ["invalid_json", "changed_text"])
def test_existing_outputs_are_never_silently_overwritten(sample, tamper):
    manifest, output = sample
    result = ingest_manifest(manifest, output)[0]
    if tamper == "invalid_json":
        result.output_path.write_bytes(b"invalid synthetic JSON")
    else:
        value = json.loads(result.output_path.read_bytes())
        value["pages"][0]["text"] = "Synthetic altered content"
        result.output_path.write_bytes(canonical_json(value))
    before = result.output_path.read_bytes()
    with pytest.raises(ValueError, match="refusing to overwrite"):
        ingest_manifest(manifest, output)
    assert result.output_path.read_bytes() == before


@pytest.mark.parametrize("contents", [b'{"schema_version":1,"schema_version":1,"documents":[]}', b'{"schema_version":NaN}', b'{"schema_version":true,"documents":[]}', b"not-json"])
def test_ambiguous_or_invalid_manifest_json_rejected(tmp_path, contents):
    path = tmp_path / "bad.json"
    path.write_bytes(contents)
    with pytest.raises(ValueError):
        load_manifest(path)


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "backend.app.ingestion", *map(str, args)], cwd=PROJECT_ROOT, capture_output=True, text=True)


def test_cli_created_unchanged_and_document_selection(sample):
    manifest, output = sample
    args = ["--manifest", manifest, "--output-dir", output, "--document", "synthetic-not-law.txt"]
    first = run_cli(*args)
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["created"] == 1
    second = run_cli(*args)
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout)["unchanged"] == 1
    assert json.loads(second.stdout)["verification_status"] == "not_independently_verified"


def test_cli_collection_and_failure_exit_codes(sample):
    manifest, output = sample
    data = manifest_data(manifest)
    other = copy.deepcopy(data["documents"][0])
    other["metadata"]["official_title"] = "SECOND SYNTHETIC RECORD — NOT LAW"
    data["documents"].append(other)
    write_manifest(manifest, data)
    assert json.loads(run_cli("--manifest", manifest, "--output-dir", output).stdout)["created"] == 2
    bad = run_cli("--manifest", manifest, "--output-dir", output, "--document", "../outside.txt")
    assert bad.returncode == 2
    assert bad.stdout == ""
    assert "error" in json.loads(bad.stderr)
    assert "Traceback" not in bad.stderr
    assert run_cli("--manifest", manifest, "--output-dir", output, "--max-file-size-mb", "0").returncode == 2


def test_cli_errors_do_not_echo_credential_values(sample):
    manifest, output = sample
    data = manifest_data(manifest)
    data["documents"][0]["metadata"]["source_url"] = "https://user:synthetic-only-secret@example.invalid/"
    write_manifest(manifest, data)
    result = run_cli("--manifest", manifest, "--output-dir", output)
    assert result.returncode == 2
    assert "synthetic-only-secret" not in result.stderr


def test_no_network_calls_are_needed_for_ingestion(sample, monkeypatch):
    import socket

    def no_network(*args, **kwargs):
        raise AssertionError("Offline ingestion must not open a network connection.")

    monkeypatch.setattr(socket, "socket", no_network)
    manifest, output = sample
    data = manifest_data(manifest)
    metadata = data["documents"][0]["metadata"]
    metadata["source_url"] = "https://egazette.gov.in/SYNTHETIC-NOT-LAW"
    write_manifest(manifest, data)
    assert LegalMetadata.model_validate(metadata).source_type == "synthetic"
    assert ingest_manifest(manifest, output)[0].status == "created"


def test_failed_atomic_publication_leaves_no_partial_json_or_temp_file(sample, monkeypatch):
    manifest, output = sample

    def publication_failure(*args, **kwargs):
        raise OSError("Synthetic publication failure")

    with monkeypatch.context() as patch:
        patch.setattr(os, "link", publication_failure)
        with pytest.raises(OSError, match="Synthetic publication failure"):
            ingest_manifest(manifest, output)
    assert list(output.iterdir()) == []
    assert ingest_manifest(manifest, output)[0].status == "created"


def test_another_writer_publishing_the_same_record_is_safe(sample, monkeypatch):
    manifest, output = sample
    real_link = os.link

    def concurrent_publication(source, target, **kwargs):
        real_link(source, target, **kwargs)
        raise FileExistsError("Synthetic other writer won publication")

    monkeypatch.setattr(os, "link", concurrent_publication)
    result = ingest_manifest(manifest, output)[0]
    assert result.status == "unchanged"
    assert read_record(result).source_file.sha256
    assert len(list(output.iterdir())) == 1


def test_resource_limits_are_enforced_before_any_json_is_written(sample, monkeypatch):
    from backend.app.ingestion import extraction, pipeline

    manifest, output = sample
    with monkeypatch.context() as patch:
        patch.setattr(extraction, "MAX_TEXT_CHARACTERS", 16)
        with pytest.raises(ValueError, match="character limit"):
            ingest_manifest(manifest, output)
    pdf = manifest.parent / "two-pages.pdf"
    synthetic_pdf(pdf, ["SYNTHETIC ONLY - NOT LAW", "SYNTHETIC ONLY - NOT LAW"])
    switch_source(manifest, pdf.name)
    with monkeypatch.context() as patch:
        patch.setattr(extraction, "MAX_PAGES", 1)
        with pytest.raises(ValueError, match="pages"):
            ingest_manifest(manifest, output)
    with monkeypatch.context() as patch:
        patch.setattr(pipeline, "MAX_MANIFEST_BYTES", 16)
        with pytest.raises(ValueError, match="size limit"):
            ingest_manifest(manifest, output)
    assert not output.exists()


def test_bad_later_output_prevents_other_collection_outputs(sample):
    manifest, output = sample
    data = manifest_data(manifest)
    other = copy.deepcopy(data["documents"][0])
    other["metadata"]["official_title"] = "SECOND SYNTHETIC RECORD — NOT LAW"
    data["documents"].append(other)
    write_manifest(manifest, data)
    results = ingest_manifest(manifest, output)
    results[0].output_path.unlink()
    results[1].output_path.write_bytes(b"invalid synthetic output")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        ingest_manifest(manifest, output)
    assert not results[0].output_path.exists()


def test_verification_claim_requires_evidence(sample):
    manifest, output = sample
    data = manifest_data(manifest)
    data["documents"][0]["metadata"]["provenance"]["verification_claim"] = "user_claimed_verified"
    write_manifest(manifest, data)
    with pytest.raises(ValueError, match="requires user-supplied evidence"):
        ingest_manifest(manifest, output)


def test_manifest_title_cannot_control_the_output_path(sample):
    manifest, output = sample
    data = manifest_data(manifest)
    data["documents"][0]["metadata"]["official_title"] = "SYNTHETIC ../../outside — NOT LAW"
    write_manifest(manifest, data)
    result = ingest_manifest(manifest, output)[0]
    assert result.output_path.parent == output.resolve()
    assert result.output_path.name == result.document_id + ".json"
    assert not (output.parent / "outside.json").exists()
