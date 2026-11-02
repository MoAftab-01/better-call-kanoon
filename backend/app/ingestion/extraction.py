"""Page-preserving extraction and deliberately conservative, unverified structure."""

import re
import sys

from .models import ExtractedPage, ExtractedSection, ExtractionInfo

MAX_PAGES = 2000
MAX_TEXT_CHARACTERS = 5_000_000
HEADING = re.compile(
    r"^(?P<identifier>(?:Section|Sec\.|Rule|Regulation|Article)\s+"
    r"[0-9]+[A-Za-z]?(?:\([0-9A-Za-z]+\))*)"
    r"(?:\s*[.:—–-]\s*\S.*)?$", re.IGNORECASE,
)
STRUCTURAL_HEADING = re.compile(
    r"^(?P<identifier>(?:Chapter|Part|Schedule)\s+(?:[0-9]+[A-Za-z]?|[IVXLCDM]+))"
    r"(?:\s*[.:—–-]\s*\S.*)?$", re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """Do not fold Unicode, collapse paragraphs, renumber, join words, or dehyphenate."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip(" \t") for line in text.split("\n")).strip("\n")


def extract_pages(data: bytes, suffix: str, document_id: str) -> tuple[list[ExtractedPage], ExtractionInfo]:
    raw_pages: list[tuple[int | None, str, list[str]]] = []
    if suffix == ".txt":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("TXT sources must be valid UTF-8 (an initial UTF-8 BOM is allowed).") from exc
        if "\x00" in text:
            raise ValueError("TXT sources must not contain NUL bytes.")
        raw_pages.append((None, normalize_text(text), ["txt_page_numbers_unavailable"]))
        info = ExtractionInfo(engine="python-utf8", engine_version=sys.version.split()[0])
    else:
        import pymupdf

        if not data.startswith(b"%PDF-"):
            raise ValueError("PDF source does not have a PDF header.")
        try:
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                if pdf.needs_pass or pdf.is_encrypted:
                    raise ValueError("Encrypted/password-protected PDFs are not supported.")
                if not pdf.is_pdf or not 1 <= len(pdf) <= MAX_PAGES:
                    raise ValueError(f"PDF must have between 1 and {MAX_PAGES} pages.")
                total = 0
                for number, page in enumerate(pdf, 1):
                    text = normalize_text(page.get_text("text", sort=False))
                    total += len(text)
                    if total > MAX_TEXT_CHARACTERS:
                        raise ValueError("Extracted text exceeds the 5,000,000-character limit.")
                    warnings = ["pdf_reading_order_unverified"]
                    if pdf.is_repaired:
                        warnings.append("pdf_repaired_by_parser")
                    if not text.strip():
                        warnings.append("empty_or_image_only_page")
                    if "\ufffd" in text:
                        warnings.append("unicode_replacement_character_present")
                    raw_pages.append((number, text, warnings))
        except (pymupdf.FileDataError, RuntimeError) as exc:
            raise ValueError("PDF could not be read; the file may be corrupt or unsupported.") from exc
        info = ExtractionInfo(engine="pymupdf", engine_version=pymupdf.VersionBind)

    if sum(len(text) for _, text, _ in raw_pages) > MAX_TEXT_CHARACTERS:
        raise ValueError("Extracted text exceeds the 5,000,000-character limit.")
    if not any(text.strip() for _, text, _ in raw_pages):
        raise ValueError("No extractable text found. OCR/scanned-only documents are not supported.")

    pages = [
        ExtractedPage(
            page_id=f"{document_id}:page:{ordinal:06d}", ordinal=ordinal,
            page_number=number, text=text, warnings=warnings,
        )
        for ordinal, (number, text, warnings) in enumerate(raw_pages, 1)
    ]
    return pages, info


def extract_sections(pages: list[ExtractedPage], document_id: str) -> list[ExtractedSection]:
    sections = []
    for page in pages:
        if not page.text:
            continue
        lines = page.text.split("\n")
        headings = {}
        for index, line in enumerate(lines):
            if len(line) > 160:
                continue
            candidate = HEADING.fullmatch(line.strip()) or STRUCTURAL_HEADING.fullmatch(line.strip())
            if candidate:
                headings[index] = candidate.group("identifier")
        starts = sorted({0, *headings})
        for index, start in enumerate(starts):
            end = starts[index + 1] if index + 1 < len(starts) else len(lines)
            identifier = headings.get(start)
            sections.append(ExtractedSection(
                section_id=f"{document_id}:section:{len(sections) + 1:06d}",
                page_id=page.page_id, page_number=page.page_number,
                start_line=start + 1, end_line=end, identifier=identifier,
                heading=lines[start] if identifier else None,
                text="\n".join(lines[start:end]),
                structure_status="candidate" if identifier else "unidentified",
                uncertainties=["heading_detection_unverified" if identifier else "section_identifier_not_identified"],
            ))
    return sections
