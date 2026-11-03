"""Deterministic, read-only Stage 2E checks. Findings are signals, not corrections.

Run from the repository root: python -m backend.qa.legal_text
No network, OCR, text repair, chunking, indexing, or ingestion is performed.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import stat
import unicodedata

import pymupdf

from backend.app.ingestion.extraction import normalize_text
from backend.app.ingestion.models import LegalDocument
from backend.app.ingestion.pipeline import canonical_json, load_manifest

VERSION = "stage2e-qa-v1"
ROOT = Path(__file__).resolve().parents[2]
AUDIT_D = "docs/legal-document-ingestion-stage2d.json"
AUDIT_C = "docs/legal-source-acquisition-stage2c.json"
VISUAL = Path(__file__).with_name("stage2e_visual_review.json")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def finding(code, start, end, evidence, method="automatic_heuristic"):
    return dict(code=code, start_line=start, end_line=end,
                evidence=evidence, method=method)


def text_findings(text: str) -> list[dict]:
    """Line-local signals with preserved evidence. No text transformation."""
    result = []
    for number, line in enumerate(text.split("\n"), 1):
        codes = set()
        if "\ufffd" in line:
            codes.add("replacement_character")
        if any(unicodedata.category(c) == "Cc" and c not in "\t" for c in line):
            codes.add("unexpected_control")
        if any(unicodedata.category(c) in {"Co", "Cs", "Cn"} for c in line):
            codes.add("private_surrogate_or_unassigned_unicode")
        if any(unicodedata.category(c) == "Cf" for c in line):
            codes.add("invisible_or_directional_format_character")
        if re.search(r"Ã.|Â.|â€|ï¿½", line):
            codes.add("possible_mojibake")
        if re.search(r"\t| {3,}|[^\S \n]", line):
            codes.add("unusual_whitespace_candidate")
        if any("\u0900" <= c <= "\u097f" for c in line):
            codes.add("devanagari_mapping_unverified")
        if any(token in line for token in ("vlk/kkj.k", "Hkkx", "izkf/kdkj")):
            codes.add("legacy_hindi_glyph_codes")
        if re.fullmatch(r"\s*\d+\s+of\s+\d{4}\.?\s*", line):
            codes.add("marginal_citation_association_unverified")
        for code in sorted(codes):
            result.append(finding(code, number, number, line))
    for left, right in (("(", ")"), ("[", "]")):
        if text.count(left) != text.count(right):
            result.append(finding("unbalanced_delimiters_candidate", 1,
                                  len(text.split("\n")),
                                  {left: text.count(left), right: text.count(right)}))
    lines = text.split("\n")
    body = [(n, s) for n, s in enumerate(lines, 1)
            if len(s.strip()) >= 45 and sum(c.isalpha() for c in s) >= 20
            and not re.search(r"GAZETTE|____|PUBLISHED BY|UPLOADED BY", s)]
    if body and not re.search(r"[.!?;:।)\]\"'’”]$", body[-1][1].rstrip()):
        n, line = body[-1]
        result.append(finding("possible_page_boundary_continuation", n, n, line))
    return result


def duplicate_groups(texts: list[str]) -> list[list[int]]:
    groups = defaultdict(list)
    for number, text in enumerate(texts, 1):
        if text.strip():
            groups[sha(text.encode("utf-8"))].append(number)
    return [group for group in groups.values() if len(group) > 1]


def section_coverage(page, sections) -> bool:
    parts = [s for s in sections if s.page_id == page.page_id]
    lines, cursor = page.text.split("\n"), 1
    for part in parts:
        if (part.page_number != page.page_number or part.start_line != cursor
                or not part.start_line <= part.end_line <= len(lines)
                or part.text != "\n".join(lines[part.start_line - 1:part.end_line])):
            return False
        cursor = part.end_line + 1
    return "\n".join(s.text for s in parts) == page.text and (not page.text or cursor == len(lines) + 1)


def paragraph_location(text, paragraph):
    match = re.search(r"\s+".join(re.escape(t) for t in paragraph.split()), text)
    if match is None:
        return None
    return dict(start_line=text[:match.start()].count("\n") + 1,
                end_line=text[:match.end()].count("\n") + 1,
                text=text[match.start():match.end()])


def check_document(root, previous, acquired, entry, visual):
    source = root / previous["raw_path"]
    output = root / previous["output_path"]
    raw, payload = source.read_bytes(), output.read_bytes()
    doc = LegalDocument.model_validate_json(payload)
    identity = dict(schema_version=1, pipeline_version="stage2a-v1",
                    metadata=doc.metadata.model_dump(mode="json"),
                    source_file=doc.source_file.model_dump(mode="json"))
    invariants = dict(
        raw_hash=sha(raw) == acquired["sha256"] == previous["source_sha256"] == entry.expected_sha256 == doc.source_file.sha256,
        processed_hash=sha(payload) == previous["output_sha256"],
        raw_size=len(raw) == acquired["byte_size"] == doc.source_file.size_bytes,
        raw_read_only=not bool(source.stat().st_mode & stat.S_IWRITE),
        metadata=doc.metadata == entry.metadata,
        document_id=doc.document_id == "doc_" + sha(canonical_json(identity)),
        provenance=doc.verification_status == "not_independently_verified" and doc.provenance_status == "user_supplied" and doc.metadata.provenance.verification_claim == "unverified",
        unknown_applicability=doc.metadata.legal_applicability is None,
    )
    if previous["document"] in {"BNS act", "BNSS act", "BNS notification", "BNSS notification"}:
        invariants["qualified_effective_date_not_flattened"] = doc.metadata.effective_date is None
    page_reports = []
    lines_by_page = [p.text.split("\n") for p in doc.pages]
    line_occurrences = defaultdict(list)
    for n, lines in enumerate(lines_by_page, 1):
        for k, line in enumerate(lines, 1):
            if len(line.strip()) >= 24:
                line_occurrences[line.strip()].append((n, k))
    schedule = None
    with pymupdf.open(stream=raw, filetype="pdf") as pdf:
        invariants["page_count"] = len(pdf) == len(doc.pages) == acquired["page_count"]
        for number, page in enumerate(doc.pages, 1):
            source_page = pdf[number - 1]
            text = page.text
            lines = text.split("\n")
            checks = dict(
                physical_order=page.ordinal == page.page_number == number and page.page_id == f"{doc.document_id}:page:{number:06d}",
                extracted_text_match=text == normalize_text(source_page.get_text("text", sort=False)),
                section_line_coverage=section_coverage(page, doc.sections),
            )
            signals = text_findings(text)
            for k, line in enumerate(lines, 1):
                locations = line_occurrences.get(line.strip(), [])
                if len({p for p, _ in locations}) >= 3:
                    signals.append(finding("repeated_line_candidate", k, k, line))
            if not text.strip():
                signals.append(finding("empty_page", 1, len(lines), ""))
            if "THE FIRST SCHEDULE" in text:
                schedule = "first_schedule"
            if "THE SECOND SCHEDULE" in text:
                schedule = "second_schedule"
            if "THE SCHEDULE" in text:
                schedule = "schedule"
            if schedule or re.search(r"FORM\s+No\.?\s*\d|PART [AB]\b", text):
                signals.append(finding("table_or_form_layout_unverified", 1, len(lines), schedule or "form"))
            if normalize_text(source_page.get_text("text", sort=True)) != text:
                signals.append(finding("sorted_extraction_differs", 1, len(lines), "Alternative ordering differs; neither ordering is certified visually correct."))
            # Margin folios are clues only: do not confuse schedule column numbers with page numbers.
            folios = sorted({int(w[4]) for w in source_page.get_text("words")
                             if w[4].isdigit() and 0 < int(w[4]) <= 2000
                             and (w[1] < 65 or w[3] > source_page.rect.height - 65)})
            if folios and number not in folios:
                signals.append(finding("possible_printed_page_order_mismatch", 1, len(lines), folios))
            # Candidate section starts are observations, not assigned legal identifiers.
            starts = [dict(line=k, printed_number=int(m.group(1)))
                      for k, line in enumerate(lines, 1)
                      if (m := re.match(r"^(\d{1,3})\.\s+\S", line))]
            counts = Counter(lines)
            repeats = [dict(line=line, occurrences=count) for line, count in sorted(counts.items())
                       if count >= 3 and sum(c.isalpha() for c in line) >= 5]
            if repeats:
                signals.append(finding("within_page_repetition_candidate", 1, len(lines), repeats))
            selected = [r for r in visual if r["document"] == previous["document"] and r["pdf_page"] == number]
            for r in selected:
                if r["source_sha256"] != sha(raw):
                    raise ValueError("Visual review belongs to different source bytes")
            page_reports.append(dict(pdf_page=number, page_id=page.page_id,
                automatic_checks=checks, characters=len(text), nonempty=bool(text.strip()),
                text_sha256=sha(text.encode("utf-8")), non_ascii=sum(ord(c) > 127 for c in text),
                margin_folio_candidates=folios, printed_number_candidates=starts,
                findings=signals, visual_reviews=selected,
                verified_evidence_eligible=False,
                eligibility_reason="No approved passage-level visual/semantic review ledger; automatic equality does not prove visual fidelity or current law."))
    duplicate = duplicate_groups([p.text for p in doc.pages])
    for group in duplicate:
        for number in group:
            p = page_reports[number - 1]
            p["findings"].append(finding("duplicate_page_text", 1, len(doc.pages[number-1].text.split("\n")), group))
    notification = None
    if acquired["commencement_review"]:
        review = acquired["commencement_review"]
        paragraph = paragraph_location(doc.pages[review["evidence_pdf_page"] - 1].text, review["exact_operative_english_text"])
        invariants["commencement_operative_paragraph"] = paragraph is not None
        notification = dict(pdf_page=review["evidence_pdf_page"], location=paragraph,
                            exact_exception=review["exact_exception_text"],
                            subsequent_status="unverified")
    integrity_ok = all(invariants.values()) and all(all(p["automatic_checks"].values()) for p in page_reports)
    codes = sorted({f["code"] for p in page_reports for f in p["findings"]})
    return dict(document=previous["document"], document_id=doc.document_id,
        raw_path=previous["raw_path"], processed_path=previous["output_path"],
        raw_sha256=sha(raw), processed_sha256=sha(payload),
        readiness="PARTIAL" if integrity_ok else "BLOCKED", invariants=invariants,
        metadata_for_citations=dict(title=doc.metadata.official_title,
            original_identifiers=previous["original_identifiers"], source_url=doc.metadata.source_url,
            version=doc.metadata.amendment_version, provenance=doc.verification_status,
            archive_page_citations="PASS with document ID, raw hash and physical page; notifications need the companion catalogue number, not NOTIFICATION alone.",
            provision_citations="BLOCKED until section/row/subsection boundaries are manually validated; currentness remains unknown."),
        pdf_pages=len(page_reports), nonempty_pages=sum(p["nonempty"] for p in page_reports),
        characters=sum(p["characters"] for p in page_reports), duplicate_page_groups=duplicate,
        finding_page_counts={code: sum(any(f["code"] == code for f in p["findings"]) for p in page_reports) for code in codes},
        notification_exception_check=notification, pages=page_reports)


def build_report(root=ROOT):
    root = Path(root)
    previous = json.loads((root / AUDIT_D).read_text(encoding="utf-8"))
    acquired = json.loads((root / AUDIT_C).read_text(encoding="utf-8"))
    manifest = load_manifest(root / previous["manifest_path"])
    visual = json.loads(VISUAL.read_text(encoding="utf-8")) if VISUAL.exists() else []
    ledger_checks = dict(
        six_sources=len(previous["documents"]) == len(acquired["records"]) == len(manifest.documents) == 6,
        acquisition_audit_hash=sha((root / AUDIT_C).read_bytes()) == previous["acquisition_audit_sha256"],
        manifest_hash=sha((root / previous["manifest_path"]).read_bytes()) == previous["manifest_sha256"],
    )
    documents = []
    for d, c, entry in zip(previous["documents"], acquired["records"], manifest.documents, strict=True):
        try:
            documents.append(check_document(root, d, c, entry, visual))
        except (ValueError, OSError, RuntimeError, IndexError) as exc:
            documents.append(dict(document=d["document"], readiness="BLOCKED", error=type(exc).__name__ + ": " + str(exc), pages=[]))
    return dict(schema_version=1, checker_version=VERSION, deterministic=True,
        ledger_checks=ledger_checks,
        runtime=dict(pymupdf=pymupdf.VersionBind, unicode=unicodedata.unidata_version),
        inputs={name: sha((root / name).read_bytes()) for name in (AUDIT_C, AUDIT_D, previous["manifest_path"], "backend/qa/legal_text.py", "backend/qa/stage2e_visual_review.json")},
        limitations=["Same-engine text comparison is a consistency check, not independent visual verification.",
                     "Heuristics have false positives and false negatives; no automatic text corrections.",
                     "No exhaustive semantic, translation, page continuity, legal-currentness or signature certification."],
        readiness="BLOCKED" if not all(ledger_checks.values()) or any(d["readiness"] == "BLOCKED" for d in documents) else "PARTIAL",
        verified_evidence_readiness="BLOCKED pending approved passage review and legal-status controls",
        proposed_retrieval_rules=dict(
            default="Deny promotion to verified evidence without an approved, hash-bound passage review. No retrieval is implemented.",
            include_only_after_approval=["English passage visually compared to the original at exact PDF page and normalized line range; include all qualifications and adjacent continuation context.", "Pin document ID, raw hash, processed hash, physical page, source URL, original edition and provenance limitations.", "Keep Acts, commencement notifications and later editions separate; link commencement statements to exact notification evidence."],
            exclude_until_resolved=["Unreviewed Hindi/glyph mappings, suspicious Unicode, OCR or purported repaired text.", "Schedule table rows/columns, form checkboxes or fields without validated layout associations.", "Fragments without verified subsection boundaries, marginal-note associations or cross-page continuation context.", "Headers, footers, colophons and signature appearances as substantive legal authority; never delete repeated legal text by a repetition heuristic.", "Any claim that BNS 106(2) or its BNSS First Schedule entry is commenced solely from the original Acts or a scalar date.", "Any legally-current or case-applicable assertion without separately reviewed amendment/commencement/applicability evidence."],
        ),
        documents=documents)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare generated report with saved report, writing nothing.")
    args = parser.parse_args()
    target = ROOT / "docs/legal-text-quality-stage2e.json"
    payload = canonical_json(build_report())
    if args.check:
        if target.read_bytes() != payload:
            raise SystemExit("Saved report differs from deterministic checks.")
    else:
        target.write_bytes(payload)
    print(json.dumps(dict(report=str(target), deterministic_match=True, document_count=6)))


if __name__ == "__main__":
    main()
