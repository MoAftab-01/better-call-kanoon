"""Contract tests for Stage 2 — local statute-PDF ingestion and chunking.

Every PDF in this file is generated on the fly into pytest's ``tmp_path`` and
every word in it is invented non-legal filler. That is not fastidiousness, it
is the project's first hard rule: this repository must never contain a
fabricated section number, act name or legal sentence, not even inside a test
fixture. The number 420 appears below purely as an arbitrary integer fed to a
regex-style detector, always beside placeholder prose.

The suite pins three things beyond ordinary "does it work":

* **Honesty.** ``knowledge_base_ready`` must stay ``False`` after a Stage 2
  build, because no embeddings exist yet. A test that let this slip would let
  the app advertise a searchable knowledge base it cannot search.
* **Purity of provenance.** Every detected section label must be a verbatim
  substring of the extracted text. If a label could be synthesised, the system
  would be inventing citations.
* **Neutral failure text.** No failure reason may leak a traceback, an absolute
  path or a library location, because those reasons are printed to an operator
  and, eventually, shown to a user.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pymupdf
import pytest

# Imported as modules rather than names so the tests below can reach private
# helpers. Module-attribute access keeps every collaborator patchable, and the
# private names under test here (_alpha_runs, _is_alpha_char,
# _summarise_page_numbers, _open_document, _dump_json) are private precisely
# because they are implementation detail whose *behaviour* still has to be
# pinned.
from app.config import get_settings
from app.rag import extraction as extraction_module
from app.rag import pipeline as pipeline_module
from app.rag.chunking import Chunk, ChunkingConfig, chunk_document, detect_section_labels
from app.rag.documents import (
    MIN_ALPHA_RUN_CHARS,
    MIN_TEXT_CHARS_THRESHOLD,
    ExtractionResult,
    PageText,
    SourceDocument,
)
from app.rag.extraction import (
    REASON_OPEN_FAILED,
    REASON_TEXT_READ_FAILED,
    ExtractionError,
    extract_document,
    normalise_law_id,
    scan_law_pdfs,
)
from app.rag.pipeline import (
    CHUNKS_FILENAME,
    METADATA_FILENAME,
    IndexNotWrittenError,
    IngestionFailure,
    IngestionReport,
    build_index,
    neutral_reason,
    write_index,
)

# ---------------------------------------------------------------------------
# Invented filler. None of this is law; it is lorem-shaped prose that exists
# only so PyMuPDF has glyphs to lay out and the extractor has a text layer.
# ---------------------------------------------------------------------------

FILLER_SENTENCES: tuple[str, ...] = (
    "Alpha clause records a sample obligation for the widget ledger.",
    "Beta clause notes that the sample gadget count is reported each quarter.",
    "Gamma clause describes a routine drill for the tin valve assembly.",
    "Delta clause sets out a sample checklist for the velvet hinge crate.",
    "Epsilon clause mentions nothing binding and is purely illustrative.",
    "Zeta clause closes the sample paragraph set with a filler closing note.",
)

#: Distinct, extractable tokens used to prove which page a chunk came from.
PAGE_MARKERS: tuple[str, ...] = (
    "ZEBRAFILLERMARKERONE",
    "ZEBRAFILLERMARKERTWO",
    "ZEBRAFILLERMARKERTHREE",
)

#: Heading-shaped lines. The 7xxx numbers are arbitrary integers chosen to look
#: like statute section numbers to the detector while naming nothing real.
HEADING_ONE = "7001. Sample filler heading alpha."
HEADING_TWO = "7002. Sample filler heading beta."
HEADING_THREE = "7003. Sample filler heading gamma."

#: The section *labels* the fixtures above declare, as opposed to the full
#: heading sentences. Two of those sentences differ only in one letter ("alpha"
#: / "beta"), so a substring test written against the sentences would report a
#: merge that is not there. Assert against the labels.
ALL_HEADING_LABELS: tuple[str, ...] = ("7001.", "7002.", "7003.")

#: A document is treated as a scan (no usable text layer) below this many
#: non-whitespace characters. Mirrors the documented extraction threshold.
#:
#: Imported rather than restated, so a change to the product constant cannot
#: leave the tests asserting against a number the code no longer uses.
SCAN_TEXT_THRESHOLD = MIN_TEXT_CHARS_THRESHOLD

#: Appended to a chunk to prove the JSON serialiser keeps non-ASCII readable.
UNICODE_SAMPLE = "ünïcödé sample é"

#: Filename stems in Devanagari. Real statute *names* rather than real statute
#: text: what is under test is that a filename retains its identity, and naming
#: the documents the project most needs to keep apart makes the stakes legible
#: without importing any actual legal wording.
_HINDI_STEMS: tuple[str, ...] = (
    "भारतीय संविधान",
    "भारतीय न्याय संहिता 2023",
    "भारतीय दण्ड संहिता",
)

#: Invented Devanagari filler. Not legal wording and nothing claims it is; it
#: only has to be Devanagari letters-and-marks with no Latin anywhere, which is
#: the property the scan test is being asked about.
DEVANAGARI_FILLER: tuple[str, ...] = (
    "यह एक नमूना अधिनियम है।",
    "इसमें कोई बंधनकारी उपबंध नहीं है।",
    "यह केवल उदाहरण के लिए लिखा गया है।",
)

#: System font carrying Devanagari glyphs, read by *buffer*.
#:
#: ``pymupdf.Font()`` is Noto Serif and ``pymupdf.Font(fontname="cjk")`` is
#: Droid Sans Fallback; neither has a single Devanagari glyph, so both write
#: ``"·· ·· ·····"``. Only a font taken from the host carries them.
#:
#: The **buffer** form is deliberate and portable. ``fontfile=`` makes MuPDF
#: locate the font by family name and index through its own font machinery,
#: which for ``Nirmala.ttc`` does not find the Devanagari face; ``fontbuffer=``
#: hands over the bytes and lets PyMuPDF read the file itself, which it does
#: correctly. That matters beyond this test: Nirmala UI ships as ``.ttc`` on
#: Windows and macOS and as ``.ttf`` on Debian, and this fixture has to build
#: on both rather than silently degrade to middle dots. The name is a constant
#: and the file is a fallback for when it is absent — see
#: :func:`_load_devanagari_font`.
_DEVA_FONT_FILENAME: str = "Nirmala.ttc"

#: Substrings that must never appear in a reason string safe to show a human.
FORBIDDEN_REASON_TOKENS: tuple[str, ...] = (
    "Traceback",
    'File "',
    "site-packages",
    "pymupdf.",
    "MuPDF",
)

#: Matches a Windows drive path, a UNC path or a common POSIX absolute path.
ABSOLUTE_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\[A-Za-z0-9_.$-]+[\\/]|/(?:tmp|home|usr|var)/)"
)


def assert_reason_is_neutral(
    reason: str, *, context: str, forbidden_paths: tuple[Path, ...] = ()
) -> None:
    """Assert a failure reason is safe to print.

    A reason string is written into an ingestion report and printed by the CLI.
    It must therefore read as a plain explanation, never as a crash dump: no
    traceback, no absolute path to this machine's disk, no library location.
    """
    assert isinstance(reason, str) and reason.strip(), f"{context}: reason must be a string"

    for token in FORBIDDEN_REASON_TOKENS:
        assert token not in reason, f"{context}: reason leaked {token!r}: {reason!r}"

    match = ABSOLUTE_PATH_RE.search(reason)
    assert match is None, f"{context}: reason contains a filesystem path: {reason!r}"
    assert "\\" not in reason, f"{context}: reason contains a backslash: {reason!r}"

    for path in forbidden_paths:
        assert str(path) not in reason, f"{context}: reason leaked path {str(path)!r}: {reason!r}"


# ---------------------------------------------------------------------------
# PDF builders. Every page is written by hand so the expected extracted text is
# fully predictable and no real-world document ever enters the repository.
# ---------------------------------------------------------------------------


def _write_pdf(path: Path, pages: list[list[str]]) -> Path:
    """Write a synthetic text-layer PDF, one list of lines per page.

    Blank lines are dropped on purpose: PyMuPDF does not lay out empty text
    runs, so a fixture that relies on preserved blank lines would be testing the
    renderer rather than the ingestion code.
    """
    document = pymupdf.open()
    try:
        for lines in pages:
            page = document.new_page()
            for index, line in enumerate(lines):
                if line.strip():
                    page.insert_text((60, 80 + 16 * index), line, fontsize=11)
        document.save(path)
    finally:
        document.close()
    return path


def _filler_lines(count: int, *, start: int = 0) -> list[str]:
    """Return ``count`` invented filler lines, cycling through the corpus."""
    return [FILLER_SENTENCES[(start + offset) % len(FILLER_SENTENCES)] for offset in range(count)]


def _load_devanagari_font() -> pymupdf.Font:
    """Return a font with Devanagari glyphs, or skip the test that needs one.

    Raises:
        pytest.skip.Exception: When no suitable font is installed. A missing
            Devanagari font is an environment fact, not a product failure, and
            the tests that use this must not report a red suite over it. It is
            a skip rather than a silent ASCII fallback because the fallback
            would write middle dots and the assertions would then fail for a
            reason that has nothing to do with the code under test.

    Returns:
        A font that has a glyph for ``"अ"``.
    """
    candidates: list[Path] = [Path("C:/Windows/Fonts") / _DEVA_FONT_FILENAME]
    candidates.extend(sorted(Path("/usr/share/fonts").rglob("*.tt[fc]")))

    for candidate in candidates:
        try:
            # fontbuffer=, not fontfile= — see _DEVA_FONT_FILENAME.
            font = pymupdf.Font(fontbuffer=candidate.read_bytes())
        except (OSError, ValueError, RuntimeError):
            continue
        if font.has_glyph(ord("अ")):
            return font

    pytest.skip(
        f"no Devanagari-capable font found (looked for {_DEVA_FONT_FILENAME!r} "
        "and system font directories); the Devanagari tests cannot build a "
        "realistic text layer without one"
    )


def _write_devanagari_pdf(path: Path, pages: list[list[str]]) -> Path:
    """Write a synthetic text-layer PDF containing Devanagari, no Latin.

    Uses :class:`pymupdf.TextWriter` with an explicit font rather than
    ``page.insert_text``. ``insert_text`` returns ``rc=1`` for characters the
    base-14 font cannot draw and writes U+00B7 MIDDLE DOT for each one, so a
    Devanagari fixture built with it silently becomes page furniture and the
    test asserts against a mangled document it never meant to create.
    """
    font = _load_devanagari_font()
    document = pymupdf.open()
    try:
        for lines in pages:
            page = document.new_page()
            writer = pymupdf.TextWriter(page.rect)
            for index, line in enumerate(lines):
                if not line.strip():
                    continue
                writer.append((60, 80 + 16 * index), line, font=font, fontsize=11)
            writer.write_text(page)
        document.save(path)
    finally:
        document.close()

    # Prove the fixture wrote what it claims. A font without the glyphs would
    # still "pass" a save, and every assertion downstream would be about a
    # document the fixture never actually produced.
    check = pymupdf.open(path)
    try:
        written = "".join(page.get_text() for page in check)
    finally:
        check.close()
    if not extraction_module._alpha_runs(written):
        pytest.fail(
            f"the Devanagari fixture wrote no letters (font lacked the glyphs): {written!r}"
        )
    return path


def _write_multipage_pdf(path: Path, page_count: int = 3) -> Path:
    """Write a PDF whose pages carry unique markers, for page-mapping tests.

    Each page gets a marker, a heading-shaped filler line and enough filler
    prose to clear the extraction threshold comfortably. The heading is placed
    *after* the marker so a chunk that starts mid-page still has a page
    identity to be checked against.
    """
    pages: list[list[str]] = []
    for number in range(1, page_count + 1):
        marker = PAGE_MARKERS[number - 1]
        heading = (HEADING_ONE, HEADING_TWO, HEADING_THREE)[number - 1]
        pages.append([marker, heading, *_filler_lines(4, start=number)])
    return _write_pdf(path, pages)


def _write_heading_pdf(path: Path) -> Path:
    """Write a PDF holding two clearly separated filler sections.

    Section 7002 starts far enough into the document that a naive fixed-width
    split would be tempted to cut across the boundary — which is exactly the
    merge of two distinct provisions that chunking must never do.
    """
    lines = [
        HEADING_ONE,
        *_filler_lines(5),
        HEADING_TWO,
        *_filler_lines(5, start=2),
    ]
    return _write_pdf(path, [lines])


def _write_scan_like_pdf(path: Path) -> Path:
    """Write a PDF with a page but no text layer — what a scanned page looks like."""
    document = pymupdf.open()
    try:
        page = document.new_page()
        page.draw_rect(pymupdf.Rect(60, 60, 400, 500), color=(0, 0, 0), fill=(0.6, 0.6, 0.6))
        document.save(path)
    finally:
        document.close()
    return path


def _write_corrupt_pdf(path: Path) -> Path:
    """Write bytes that are not a PDF at all, to exercise the unreadable path."""
    path.write_bytes(b"%PDF-1.7 truncated on purpose, this is not a document\n\x00\x01\x02")
    return path


class _FakeDocument:
    """A stand-in for ``pymupdf.Document`` used to reach error paths PyMuPDF
    will not let a test create.

    PyMuPDF refuses to *save* a zero-page PDF, and encrypting one on the fly
    needs a password we would rather not embed in the repository. Faking the
    object is the honest way to reach "no pages" and "encrypted" branches
    without shipping a real encrypted blob. It also records whether ``close()``
    ran, which is how the ``finally``-close contract is verified.
    """

    def __init__(self, *, page_count: int, encrypted: bool = False) -> None:
        self.page_count = page_count
        self.is_encrypted = encrypted
        self.needs_pass = encrypted
        self.closed = False

    def __len__(self) -> int:
        return self.page_count

    def __iter__(self) -> Iterator[Any]:
        return iter(())

    def __getitem__(self, index: int) -> Any:
        raise IndexError(index)

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> _FakeDocument:
        return self

    def __exit__(self, *exc_info: Any) -> bool:
        self.close()
        return False


def _patched_open(monkeypatch: pytest.MonkeyPatch, document: _FakeDocument) -> None:
    """Make ``pymupdf.open`` return ``document`` for the duration of a test.

    ``app.rag.extraction`` holds a reference to the ``pymupdf`` module, not to
    the ``open`` function, so patching the attribute on the module reaches it.
    monkeypatch restores the real function afterwards.
    """
    import app.rag.extraction as extraction_module

    monkeypatch.setattr(extraction_module.pymupdf, "open", lambda *args, **kwargs: document)


def _extract(path: Path) -> ExtractionResult:
    """Scan a single PDF and extract it, the way the pipeline does."""
    documents = scan_law_pdfs(path.parent)
    assert documents, f"expected {path.name} to be discovered by scan_law_pdfs"
    document = next(item for item in documents if item.path.name == path.name)
    return extract_document(document)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def laws_dir(tmp_path: Path) -> Path:
    """An empty, existing directory standing in for ``data/laws``."""
    directory = tmp_path / "laws"
    directory.mkdir()
    return directory


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    """A not-yet-existing directory standing in for ``data/index``.

    Deliberately absent so the "create index_dir if missing" behaviour of
    ``write_index`` is exercised rather than assumed.
    """
    return tmp_path / "index"


@pytest.fixture
def good_pdf(laws_dir: Path) -> Path:
    """A readable, three-page, text-layer PDF inside ``laws_dir``.

    The filename exercises the full normalisation path — spaces, parentheses
    and a year — because that is the shape of a real statute download.
    """
    return _write_multipage_pdf(laws_dir / "alpha 2019 (1).pdf", page_count=3)


@pytest.fixture
def corrupt_pdf(laws_dir: Path) -> Path:
    """An unreadable file that must become a failure record, not a crash."""
    return _write_corrupt_pdf(laws_dir / "beta_broken.pdf")


@pytest.fixture
def settings_obj() -> Any:
    """The session settings object, the one ``knowledge_base_ready`` reads.

    Provided for the handful of assertions that only need to observe it. Tests
    that must *redirect* the index directory use the ``settings_at`` fixture
    instead, which rebuilds the cached instance properly.
    """
    return get_settings()


# ---------------------------------------------------------------------------
# normalise_law_id
# ---------------------------------------------------------------------------

NORMALISE_CASES: tuple[tuple[str, str], ...] = (
    ("BNS 2023 (1)", "bns_2023_1"),
    ("bns_2023_1", "bns_2023_1"),
    ("BNS 2023", "bns_2023"),
    ("alpha act", "alpha_act"),
    ("Alpha Act 2019 (2)", "alpha_act_2019_2"),
    ("ALPHA", "alpha"),
    ("alpha", "alpha"),
)


@pytest.mark.parametrize(("stem", "expected"), NORMALISE_CASES)
def test_normalise_law_id_matches_the_documented_mapping(stem: str, expected: str) -> None:
    """The documented examples are the contract: stems become lowercase,
    space/punctuation-separated identifiers."""
    assert normalise_law_id(stem) == expected


@pytest.mark.parametrize("stem", [item[0] for item in NORMALISE_CASES])
def test_normalise_law_id_is_idempotent(stem: str) -> None:
    """Normalising an already-normalised id must be a no-op.

    ``law_id`` becomes part of ``chunk_id`` and is written into the index, so
    an id that drifts on a second pass would silently fork the identifier space
    between two ingestion runs over the same file.
    """
    once = normalise_law_id(stem)
    assert normalise_law_id(once) == once


@pytest.mark.parametrize(
    "stem",
    [
        "Mixed CASE With Spaces",
        "has.dots.in.it",
        "  leading and trailing  ",
        "multiple   inner   spaces",
        "(7)",
        "2023",
    ],
)
def test_normalise_law_id_strips_every_character_that_could_break_an_identifier(stem: str) -> None:
    """Whatever the input, the result is a safe lowercase token.

    Spaces, dots and parentheses would all make an id awkward to embed in a
    filename, a JSON key or a URL, so they must not survive.
    """
    result = normalise_law_id(stem)

    assert isinstance(result, str)
    assert result == result.lower(), f"{stem!r} -> {result!r} kept uppercase"
    for forbidden in (" ", "(", ")", "."):
        assert forbidden not in result, f"{stem!r} -> {result!r} kept {forbidden!r}"
    assert "__" not in result, f"{stem!r} -> {result!r} produced a doubled underscore"


@pytest.mark.parametrize("stem", ["", "   ", "...", "()", " - "])
def test_normalise_law_id_survives_empty_ish_input(stem: str) -> None:
    """A nameless or punctuation-only stem must not raise.

    The pipeline calls this on every discovered file; an exception here would
    abort a whole ingestion run over one oddly named PDF.
    """
    result = normalise_law_id(stem)

    assert isinstance(result, str)
    assert normalise_law_id(result) == result


def test_normalise_law_id_preserves_digits() -> None:
    """Digits are meaningful (they carry the year and sequence), so they stay."""
    assert "2019" in normalise_law_id("Alpha Act 2019 (3)")


# ---------------------------------------------------------------------------
# scan_law_pdfs
# ---------------------------------------------------------------------------


def test_scan_law_pdfs_discovers_a_real_pdf(laws_dir: Path) -> None:
    """A single PDF yields exactly one fully-populated SourceDocument.

    ``sha256`` and ``size_bytes`` are the provenance of the index: if they do
    not describe the bytes actually on disk, a later re-ingestion cannot tell
    whether the index is stale.
    """
    path = _write_multipage_pdf(laws_dir / "alpha_2019.pdf", page_count=1)

    documents = scan_law_pdfs(laws_dir)

    assert len(documents) == 1
    document = documents[0]
    assert isinstance(document, SourceDocument)
    assert document.law_id == "alpha_2019"
    assert document.act_name, "act_name must not be empty"
    assert document.act_name in document.law_id
    assert document.year == "2019"
    assert document.path == path.resolve() or document.path == path
    assert document.size_bytes == path.stat().st_size
    assert document.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_scan_law_pdfs_derives_the_year_only_when_one_is_present(laws_dir: Path) -> None:
    """``year`` is a 4-digit year found in the stem, and ``None`` otherwise.

    Returning a guessed year would put an unverified date into the index
    metadata, which a later citation formatter would happily print.
    """
    _write_multipage_pdf(laws_dir / "alpha_2019.pdf", page_count=1)
    _write_multipage_pdf(laws_dir / "gamma_no_year_here.pdf", page_count=1)

    documents = {document.path.name: document for document in scan_law_pdfs(laws_dir)}

    assert documents["alpha_2019.pdf"].year == "2019"
    assert documents["gamma_no_year_here.pdf"].year is None


def test_scan_law_pdfs_act_name_derives_from_the_stem(laws_dir: Path) -> None:
    """``act_name`` is a display-safe derivation of the filename stem.

    The contract's own example is ``bns_2023``, so a stem of exactly that shape
    must come back unchanged; a stem with a year and a copy suffix must still
    yield something that relates to the law_id rather than being invented.
    """
    _write_multipage_pdf(laws_dir / "bns_2023.pdf", page_count=1)
    _write_multipage_pdf(laws_dir / "Alpha Act 2019 (1).pdf", page_count=1)

    documents = {document.path.name: document for document in scan_law_pdfs(laws_dir)}

    assert documents["bns_2023.pdf"].act_name == "bns_2023"
    derived = documents["Alpha Act 2019 (1).pdf"].act_name
    assert derived, "act_name must not be empty"
    assert derived.lower() in documents["Alpha Act 2019 (1).pdf"].law_id


def test_scan_law_pdfs_ignores_non_pdf_files(laws_dir: Path) -> None:
    """Only PDFs are statutes-in-waiting; .txt and .docx must be ignored.

    Ingesting a .docx would mean the extraction layer meeting a format it
    cannot parse, and the run would report a failure for a file that was never
    supposed to be considered.
    """
    _write_multipage_pdf(laws_dir / "alpha_2019.pdf", page_count=1)
    (laws_dir / "notes.txt").write_text("Plain text filler, not a statute.", encoding="utf-8")
    (laws_dir / "memo.docx").write_bytes(b"PK\x03\x04 pretend office document")
    (laws_dir / "archive.tar.gz").write_bytes(b"\x1f\x8b pretend archive")

    documents = scan_law_pdfs(laws_dir)

    assert [document.path.name for document in documents] == ["alpha_2019.pdf"]


def test_scan_law_pdfs_matches_the_pdf_extension_case_insensitively(laws_dir: Path) -> None:
    """``.PDF`` and ``.Pdf`` are still PDFs.

    A statute pack assembled on a Windows machine or downloaded from a
    case-preserving source will not use one consistent casing.
    """
    _write_multipage_pdf(laws_dir / "ALPHA_UPPER.PDF", page_count=1)
    _write_multipage_pdf(laws_dir / "beta_mixed.Pdf", page_count=1)

    documents = scan_law_pdfs(laws_dir)

    names = sorted(document.path.name for document in documents)
    assert names == ["ALPHA_UPPER.PDF", "beta_mixed.Pdf"]


def test_scan_law_pdfs_surfaces_zero_byte_files(laws_dir: Path) -> None:
    """A zero-byte PDF is an interrupted download, and the operator must hear.

    It used to be dropped at the scan, which made it appear in no counter, no
    failure list and no exit code: a run over one good PDF and two empty ones
    reported ``documents_found=1, documents_failed=0`` and exited ``0``. The
    file is now described and handed on, so ``extract_document`` fails it for
    the reason it deserves and it shows up in the summary.
    """
    (laws_dir / "empty_download.pdf").write_bytes(b"")
    (laws_dir / "other_download.pdf").write_bytes(b"")
    _write_multipage_pdf(laws_dir / "alpha_2019.pdf", page_count=1)

    documents = scan_law_pdfs(laws_dir)

    assert [document.path.name for document in documents] == [
        "alpha_2019.pdf",
        "empty_download.pdf",
        "other_download.pdf",
    ]
    empty = [d for d in documents if d.size_bytes == 0]
    assert [d.path.name for d in empty] == ["empty_download.pdf", "other_download.pdf"]


def test_zero_byte_files_are_reported_as_failures(laws_dir: Path, index_dir: Path) -> None:
    """A truncated download must reach the failure list, not vanish.

    This is the end-to-end half of the scan test above: it pins that the file
    is *counted and reported*, which is the property that was actually broken.
    An operator whose corpus lost three Acts to interrupted transfers has to be
    able to see that from the exit code.
    """
    (laws_dir / "beta_act.pdf").write_bytes(b"")
    (laws_dir / "gamma_act.pdf").write_bytes(b"")
    _write_multipage_pdf(laws_dir / "alpha_2019.pdf", page_count=1)

    report = build_index(laws_dir, index_dir)

    assert report.documents_found == 3
    assert report.documents_ingested == 1
    assert report.documents_failed == 2
    assert {failure.filename for failure in report.failures} == {
        "beta_act.pdf",
        "gamma_act.pdf",
    }
    assert all(failure.reason == REASON_OPEN_FAILED for failure in report.failures)

    # And the artefacts on disk must agree, so a reader of the index sees it.
    metadata = json.loads((index_dir / METADATA_FILENAME).read_text(encoding="utf-8"))
    assert len(metadata["failures"]) == 2


def test_a_corpus_of_only_empty_files_is_reported_as_failures_not_success(
    laws_dir: Path, index_dir: Path
) -> None:
    """All-empty corpora must not produce a green run.

    This is the case that defeated the "no chunks written" guard: every file
    was skipped at the scan, so ``documents_found`` was 0, the guard found no
    pre-existing index, and the run wrote an empty index and exited ``0``.
    """
    for name in ("alpha_act.pdf", "beta_act.pdf", "gamma_act.pdf", "delta_act.pdf"):
        (laws_dir / name).write_bytes(b"")

    report = build_index(laws_dir, index_dir)

    assert report.documents_found == 4
    assert report.documents_ingested == 0
    assert report.documents_failed == 4
    assert report.chunks_written == 0


def test_scan_law_pdfs_is_sorted_and_deterministic(laws_dir: Path) -> None:
    """Two scans of the same directory return the same documents in the same order.

    Index build order must not depend on filesystem enumeration order, or two
    runs over an unchanged corpus would produce two different ``chunks.json``
    files and an unreproducible index.
    """
    for name in ("charlie.pdf", "alpha.pdf", "bravo.pdf", "delta.pdf"):
        _write_multipage_pdf(laws_dir / name, page_count=1)

    first = [document.law_id for document in scan_law_pdfs(laws_dir)]
    second = [document.law_id for document in scan_law_pdfs(laws_dir)]

    assert first == second
    assert first == sorted(first), f"scan order is not sorted by name: {first}"


def test_scan_law_pdfs_returns_empty_for_a_missing_directory(tmp_path: Path) -> None:
    """A missing directory is an empty result, not an exception.

    The CLI turns this into exit code 2 with a readable message; letting an
    ``OSError`` escape here would surface a raw filesystem error instead.
    """
    assert scan_law_pdfs(tmp_path / "does_not_exist") == ()


def test_scan_law_pdfs_returns_empty_for_an_empty_directory(laws_dir: Path) -> None:
    """An existing but empty directory is a valid, boring, zero-document run."""
    assert scan_law_pdfs(laws_dir) == ()


def test_scan_law_pdfs_does_not_recurse_into_subdirectories(laws_dir: Path) -> None:
    """Nested directories are out of scope.

    Recursion would pick up working copies, backups and unrelated archives
    whose contents nobody has vetted as statute text.
    """
    nested = laws_dir / "archive"
    nested.mkdir()
    _write_multipage_pdf(nested / "buried.pdf", page_count=1)
    _write_multipage_pdf(laws_dir / "top_level.pdf", page_count=1)

    assert [document.path.name for document in scan_law_pdfs(laws_dir)] == ["top_level.pdf"]


def test_scan_law_pdfs_returns_an_immutable_tuple(laws_dir: Path) -> None:
    """The scan result is immutable: callers must not be able to reorder it."""
    _write_multipage_pdf(laws_dir / "alpha_2019.pdf", page_count=1)

    documents = scan_law_pdfs(laws_dir)

    assert isinstance(documents, tuple)
    with pytest.raises((AttributeError, TypeError)):
        documents.append(None)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# extract_document — success paths
# ---------------------------------------------------------------------------


def test_extract_document_reads_every_page_in_order(good_pdf: Path) -> None:
    """Pages come back 1-based, in document order, with their text intact.

    Page numbers are what a citation will eventually point at, so a page that
    arrives out of order or numbered from zero is a correctness bug, not a
    cosmetic one.
    """
    result = _extract(good_pdf)

    assert isinstance(result, ExtractionResult)
    assert result.page_count == 3
    assert len(result.pages) == 3
    assert [page.page_number for page in result.pages] == [1, 2, 3]
    for number, page in enumerate(result.pages, start=1):
        assert isinstance(page, PageText)
        assert PAGE_MARKERS[number - 1] in page.text
    for earlier, later in zip(result.pages, result.pages[1:], strict=False):
        assert earlier.page_number < later.page_number


def test_extract_document_char_counts_match_the_page_text(good_pdf: Path) -> None:
    """``char_count`` describes the very text shipped alongside it."""
    result = _extract(good_pdf)

    for page in result.pages:
        assert page.char_count == len(page.text)
    assert result.total_chars > 0
    # total_chars is consistent with the joined text up to one separator per page.
    assert abs(result.total_chars - len(result.full_text)) <= len(result.pages)


def test_extract_document_full_text_preserves_page_order(good_pdf: Path) -> None:
    """``full_text`` is the concatenation, never a re-sorting.

    Chunk offsets are computed against this string, so a reordering here would
    silently attach every section label to the wrong page.
    """
    result = _extract(good_pdf)

    positions = [result.full_text.index(marker) for marker in PAGE_MARKERS]
    assert positions == sorted(positions), f"pages out of order in full_text: {positions}"


def test_extract_document_normalises_whitespace(good_pdf: Path) -> None:
    """Extracted text has no trailing line whitespace and is NFC-normalised.

    Trailing spaces survive PDF rendering constantly and would otherwise poison
    every chunk boundary comparison and every exact-match retrieval test.
    """
    result = _extract(good_pdf)

    for page in result.pages:
        for line in page.text.split("\n"):
            assert line == line.rstrip(), f"line kept trailing whitespace: {line!r}"
        assert "\n\n\n" not in page.text, "a run of 3+ blank lines was not collapsed"
        assert unicodedata.is_normalized("NFC", page.text)


def test_extract_document_is_deterministic(good_pdf: Path) -> None:
    """Two extractions of the same file agree exactly, warning tuples included.

    A warning that flickered in and out between runs would make the ingestion
    report useless for deciding whether a corpus needs re-processing.
    """
    first = _extract(good_pdf)
    second = _extract(good_pdf)

    assert first == second


def test_extract_document_carries_the_source_document(good_pdf: Path) -> None:
    """The result is self-describing: it knows which file it came from."""
    result = _extract(good_pdf)

    assert result.document.path.name == good_pdf.name
    assert result.document.sha256 == hashlib.sha256(good_pdf.read_bytes()).hexdigest()
    assert result.full_text.strip()


# ---------------------------------------------------------------------------
# extract_document — failure paths
# ---------------------------------------------------------------------------


def test_extract_document_raises_extraction_error_for_a_corrupt_file(corrupt_pdf: Path) -> None:
    """An unreadable PDF becomes ``ExtractionError``, never a raw library error.

    ``pymupdf`` raises its own exception types; letting one escape would put a
    vendor-specific error and a filesystem path into the pipeline's failure
    record and, from there, onto an operator's screen.
    """
    document = scan_law_pdfs(corrupt_pdf.parent)[0]

    with pytest.raises(ExtractionError) as excinfo:
        extract_document(document)

    assert type(excinfo.value) is ExtractionError
    assert_reason_is_neutral(
        str(excinfo.value), context="corrupt file", forbidden_paths=(corrupt_pdf,)
    )


def test_extraction_error_is_a_runtime_error() -> None:
    """Callers that only care that extraction failed can catch ``RuntimeError``."""
    assert issubclass(ExtractionError, RuntimeError)


def test_extract_document_raises_for_a_document_with_no_pages(
    laws_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A page-less document is a failure, not an empty success.

    PyMuPDF will not *save* a zero-page PDF, so the object is faked. The
    assertion on ``closed`` additionally pins the ``finally``-close contract: a
    handle leaked on the error path would exhaust file descriptors over a long
    ingestion run.
    """
    _write_multipage_pdf(laws_dir / "alpha_2019.pdf", page_count=1)
    document = scan_law_pdfs(laws_dir)[0]
    fake = _FakeDocument(page_count=0)
    _patched_open(monkeypatch, fake)

    with pytest.raises(ExtractionError) as excinfo:
        extract_document(document)

    assert fake.closed is True, "the document must be closed even when extraction fails"
    assert_reason_is_neutral(str(excinfo.value), context="zero pages", forbidden_paths=(laws_dir,))


def test_extract_document_raises_for_an_encrypted_document(
    laws_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A password-protected PDF is reported as such and never force-opened.

    Government statute PDFs are not usually encrypted, but a mis-scanned or
    DRM-stripped file can be, and "file is encrypted" is an actionable message
    whereas a MuPDF error is not.
    """
    _write_multipage_pdf(laws_dir / "alpha_2019.pdf", page_count=1)
    document = scan_law_pdfs(laws_dir)[0]
    fake = _FakeDocument(page_count=1, encrypted=True)
    _patched_open(monkeypatch, fake)

    with pytest.raises(ExtractionError) as excinfo:
        extract_document(document)

    assert fake.closed is True
    assert_reason_is_neutral(str(excinfo.value), context="encrypted", forbidden_paths=(laws_dir,))


def test_extract_document_raises_for_a_scan_with_no_text_layer(laws_dir: Path) -> None:
    """An image-only PDF is rejected rather than indexed as empty text.

    Indexing it would produce chunks with no content that still look like
    statute provisions in a citation — the exact failure mode the "never
    fabricate" rule exists to prevent.
    """
    path = _write_scan_like_pdf(laws_dir / "alpha_scan.pdf")

    with pytest.raises(ExtractionError) as excinfo:
        _extract(path)

    assert_reason_is_neutral(str(excinfo.value), context="scan", forbidden_paths=(laws_dir,))


def test_extract_document_raises_when_the_text_layer_is_empty(laws_dir: Path) -> None:
    """A PDF with pages but no text layer at all counts as a scan.

    This pins the real condition — *no* extractable text, not "not much text".
    A 200-character floor would also reject this file, so the test alone cannot
    tell the two apart; the short-document tests below are what hold the line
    against a regression that raises the bar back up.
    """
    path = _write_scan_like_pdf(laws_dir / "alpha_scan_only.pdf")

    with pytest.raises(ExtractionError) as excinfo:
        _extract(path)

    assert_reason_is_neutral(
        str(excinfo.value), context="no text layer", forbidden_paths=(laws_dir,)
    )


def test_extract_document_accepts_a_genuinely_short_document(laws_dir: Path) -> None:
    """A stub of a few characters is still statute text and must be indexed.

    A one-page amendment, a commencement notification or a repealed section's
    stub can easily fall under any arbitrary character count. Rejecting those
    reports a perfectly good PDF as a broken scan, and the provision silently
    never reaches the index — a wrong answer about what the system knows, which
    is the failure mode this project is built to avoid.
    """
    path = _write_pdf(laws_dir / "alpha_stub.pdf", [["Ab."]])
    total_non_whitespace = len("Ab.")

    assert total_non_whitespace >= SCAN_TEXT_THRESHOLD
    result = _extract(path)

    assert result.page_count == 1
    assert "Ab." in result.full_text


def test_extract_document_accepts_a_document_just_above_the_threshold(laws_dir: Path) -> None:
    """A full page of text extracts, as a sanity check on the boundary.

    Paired with the short-document test above: the bar rejects the empty text
    layer and nothing else.
    """
    lines = ["Filler line for the threshold boundary test."] * 6
    path = _write_pdf(laws_dir / "alpha_boundary.pdf", [lines])
    total_non_whitespace = sum(len(line.strip()) for line in lines)

    assert total_non_whitespace > SCAN_TEXT_THRESHOLD
    result = _extract(path)

    assert result.page_count == 1
    assert result.total_chars > 0


def test_extract_document_warns_but_succeeds_on_a_mixed_scan_text_document(laws_dir: Path) -> None:
    """A document that is mostly text but has empty pages is ingested with a warning.

    Failing outright would discard real provisions; ingesting silently would hide
    the fact that part of the document was never read. The contract's answer is
    a warning, and this test holds that line.

    Five of ten pages are blank — comfortably past the 20% threshold — while the
    text-bearing pages still carry well over the scan floor, so this fixture
    reaches the warning branch and not the scan branch.
    """
    filler_pages = [_filler_lines(5), _filler_lines(5, start=1), _filler_lines(5, start=3)]
    path = _write_pdf(laws_dir / "alpha_mixed.pdf", filler_pages + [[]] * 7)

    result = _extract(path)

    assert result.page_count == 10
    assert result.warnings, "a document with mostly empty pages must warn"
    for warning in result.warnings:
        assert isinstance(warning, str) and warning.strip()
        assert_reason_is_neutral(warning, context="extraction warning", forbidden_paths=(laws_dir,))
    assert result.total_chars > SCAN_TEXT_THRESHOLD


def test_extract_document_tolerates_a_single_blank_page(laws_dir: Path) -> None:
    """One blank page in a three-page document is not a warning-worthy event.

    A stray blank page — a verso, an insert — is ordinary in a bound statute.
    Warning on it every time would train an operator to ignore the field.
    """
    path = _write_pdf(
        laws_dir / "alpha_verso.pdf",
        [_filler_lines(5), [], _filler_lines(5, start=1)],
    )

    result = _extract(path)

    assert result.page_count == 3
    assert result.total_chars > SCAN_TEXT_THRESHOLD


def test_extract_document_emits_no_warning_for_a_clean_document(good_pdf: Path) -> None:
    """A fully-textual PDF warns about nothing.

    Otherwise the warnings tuple degrades into noise nobody reads.
    """
    result = _extract(good_pdf)

    assert result.warnings == ()


# ---------------------------------------------------------------------------
# detect_section_labels
# ---------------------------------------------------------------------------


DETECTION_CASES: tuple[str, ...] = (
    f"{HEADING_ONE}\n{FILLER_SENTENCES[0]}",
    f"{HEADING_ONE}\n\n{FILLER_SENTENCES[0]}\n\n{HEADING_TWO}\n{FILLER_SENTENCES[1]}",
    "Prose before. Section 7001 continues here. More prose after.",
    f"{HEADING_TWO} appears mid-line as an inline mention.",
    f"{FILLER_SENTENCES[0]} {FILLER_SENTENCES[1]}",
    "",
)


@pytest.mark.parametrize("text", DETECTION_CASES)
def test_detect_section_labels_only_ever_returns_verbatim_substrings(text: str) -> None:
    """Every label must literally occur in the text it came from.

    This is the single most important assertion in the chunking suite. If a
    label could be synthesised — a normalised number, an expanded name, a guess
    at what "the next section" is — the retrieval layer would eventually print
    it to a user as a citation, and the project would be inventing law.
    """
    detections = detect_section_labels(text)

    assert isinstance(detections, tuple)
    for detection in detections:
        offset, label, method = detection
        assert isinstance(offset, int) and offset >= 0
        assert isinstance(label, str) and label.strip()
        assert isinstance(method, str)
        assert label in text, f"label {label!r} does not occur in the source text"
        assert text[offset : offset + len(label)] == label, (
            f"offset {offset} does not point at {label!r}"
        )


@pytest.mark.parametrize("text", DETECTION_CASES)
def test_detect_section_labels_offsets_are_ordered_and_in_range(text: str) -> None:
    """Offsets ascend and stay inside the text, so a caller can slice blindly."""
    detections = detect_section_labels(text)

    offsets = [offset for offset, _, _ in detections]
    assert offsets == sorted(offsets)
    for offset, label, _ in detections:
        assert offset <= len(text) - len(label)


@pytest.mark.parametrize("text", DETECTION_CASES)
def test_detect_section_labels_methods_are_from_the_documented_set(text: str) -> None:
    """Method is ``heading`` or ``inline`` — nothing else, ever.

    The method tells a reader how much to trust the label. An undocumented third
    value would be a detection route nobody has reasoned about.
    """
    for _, _, method in detect_section_labels(text):
        assert method in {"heading", "inline"}


def test_detect_section_labels_finds_a_line_starting_heading() -> None:
    """A line beginning with a dotted number is reported as a ``heading``."""
    text = f"{HEADING_ONE}\n{FILLER_SENTENCES[0]}\n{FILLER_SENTENCES[1]}"

    detections = detect_section_labels(text)

    headings = [label for _, label, method in detections if method == "heading"]
    assert any(label.startswith("7001.") for label in headings), (
        f"expected a heading detection for {HEADING_ONE!r}, got {detections!r}"
    )


def test_detect_section_labels_finds_an_inline_section_mention() -> None:
    """A section number appearing mid-line is reported as ``inline``."""
    text = f"{FILLER_SENTENCES[0]} Section 7001 continues with filler. {FILLER_SENTENCES[1]}"

    detections = detect_section_labels(text)

    inline = [label for _, label, method in detections if method == "inline"]
    assert any("7001" in label for label in inline), f"expected an inline hit, got {detections!r}"
    for label in inline:
        assert label in text


def test_detect_section_labels_accepts_the_number_420_as_an_arbitrary_integer() -> None:
    """The documented ``420`` example works, with invented non-legal prose.

    420 is used here purely as an arbitrary integer for a regex fixture. It is
    never paired with real statutory wording, and the surrounding sentences are
    the same filler used everywhere else in this file.
    """
    text = "420. Placeholder filler heading for a detector test.\nAlpha filler sentence."

    detections = detect_section_labels(text)

    assert any("420" in label for _, label, _ in detections)
    for _, label, _ in detections:
        assert label in text


def test_detect_section_labels_returns_nothing_for_plain_prose() -> None:
    """Filler prose with no numbers in it yields no labels at all.

    Inventing a label out of nothing is worse than finding none.
    """
    text = "\n".join(FILLER_SENTENCES)

    assert detect_section_labels(text) == ()


def test_detect_section_labels_returns_nothing_for_empty_text() -> None:
    """Empty input is not an error and is not a source of phantom headings."""
    assert detect_section_labels("") == ()


def test_detect_section_labels_is_deterministic() -> None:
    """Repeated detection over the same text returns exactly the same answer."""
    text = f"{HEADING_ONE}\n{FILLER_SENTENCES[0]}\nProse with Section 7002 inline."

    assert detect_section_labels(text) == detect_section_labels(text)


def test_detect_section_labels_does_not_mutate_its_input() -> None:
    """Detection is a read-only query over a string."""
    text = f"{HEADING_ONE}\n{FILLER_SENTENCES[0]}"
    before = text

    detect_section_labels(text)

    assert text == before


# ---------------------------------------------------------------------------
# chunk_document
# ---------------------------------------------------------------------------


def test_chunking_config_defaults_match_the_contract() -> None:
    """The default sizes are part of the interface, not incidental tuning."""
    config = ChunkingConfig()

    assert config.target_chars == 900
    assert config.overlap_chars == 120
    assert config.min_chars == 120


def test_chunking_config_is_immutable() -> None:
    """Config is shared across a run; a stray mutation would poison later chunks."""
    config = ChunkingConfig()

    with pytest.raises(dataclasses.FrozenInstanceError):
        config.target_chars = 10  # type: ignore[misc]


def test_chunk_is_immutable() -> None:
    """Chunks leave the package and land in the index; they must not be mutable."""
    chunk = Chunk(
        chunk_id="alpha_2019::000000",
        law_id="alpha_2019",
        chunk_index=0,
        text="filler",
        page_start=1,
        page_end=1,
        char_start=0,
        char_end=6,
        section_label=None,
        section_detection="none",
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        chunk.text = "tampered"  # type: ignore[misc]


@pytest.fixture
def two_section_result(laws_dir: Path) -> ExtractionResult:
    """An extraction of a single page holding two separated filler sections."""
    return _extract(_write_heading_pdf(laws_dir / "alpha_sections.pdf"))


def test_chunk_document_never_spans_two_detected_sections(
    two_section_result: ExtractionResult,
) -> None:
    """A chunk contains at most one detected section heading.

    Merging two provisions into one retrievable blob blends two distinct
    meanings, and a model quoting that blob would attribute one section's words
    to another. This is the structural defence against that.
    """
    headings = [
        offset
        for offset, _, method in detect_section_labels(two_section_result.full_text)
        if method == "heading"
    ]
    assert len(headings) >= 2, "fixture must contain at least two detected sections"

    chunks = chunk_document(two_section_result)

    assert chunks, "expected at least one chunk"
    for chunk in chunks:
        inside = [offset for offset in headings if chunk.char_start <= offset < chunk.char_end]
        assert len(inside) <= 1, (
            f"chunk {chunk.chunk_id} spans sections at offsets {inside}: {chunk.text[:80]!r}"
        )


def test_chunk_document_keeps_each_section_in_its_own_chunk(
    two_section_result: ExtractionResult,
) -> None:
    """Each filler heading survives as its own chunk's label.

    The label on a chunk is what lets a future citation formatter point at the
    right place. If merging or trimming dropped it, retrieval would lose the
    only structural hint the text carries.
    """
    chunks = chunk_document(two_section_result)

    labels = [chunk.section_label for chunk in chunks if chunk.section_label]
    assert any(label and label.startswith("7001.") for label in labels)
    assert any(label and label.startswith("7002.") for label in labels)


def test_chunk_section_labels_are_verbatim_substrings_of_the_source(
    two_section_result: ExtractionResult,
) -> None:
    """A chunk's ``section_label`` occurs literally in the extracted text.

    Rule one of the project: a label may only ever be a string the source
    actually contains. Anything else is a fabricated citation.
    """
    for chunk in chunk_document(two_section_result):
        if chunk.section_label is None:
            continue
        assert chunk.section_label in two_section_result.full_text
        assert chunk.section_detection in {"heading", "inline", "none"}


def test_chunk_document_is_deterministic(good_pdf: Path) -> None:
    """Two chunkings of the same extraction produce equal chunks.

    Chunk ids are persisted, so a non-deterministic chunker would invalidate
    cached embeddings on every run for no reason.
    """
    result = _extract(good_pdf)

    assert chunk_document(result) == chunk_document(result)


def test_chunk_document_is_pure(good_pdf: Path, tmp_path: Path) -> None:
    """Chunking writes nothing and creates nothing.

    Chunking is a pure function from an extraction to chunks; if it needed the
    filesystem it could not be tested, replayed or reasoned about in isolation.
    """
    result = _extract(good_pdf)
    before = sorted(path.name for path in tmp_path.iterdir())

    chunk_document(result)

    assert sorted(path.name for path in tmp_path.iterdir()) == before


def test_chunk_ids_are_stable_and_sequential(good_pdf: Path) -> None:
    """``chunk_id`` is ``law_id`` zero-padded to six digits, from 0 upward.

    The format is the join key between a chunk and any future embedding row, so
    a change here silently invalidates a whole index.
    """
    result = _extract(good_pdf)

    chunks = chunk_document(result)

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert chunk.law_id == result.document.law_id
        assert chunk.chunk_id == f"{result.document.law_id}::{chunk.chunk_index:06d}"
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


def test_chunk_text_is_a_contiguous_slice_of_the_full_text(good_pdf: Path) -> None:
    """Each chunk's text occurs verbatim inside ``full_text``.

    Offsets are only meaningful if the text they address is really there. This
    also catches an implementation that quietly rewrote whitespace while
    splitting, which would desynchronise offsets from content.
    """
    result = _extract(good_pdf)

    for chunk in chunk_document(result):
        assert chunk.text in result.full_text, f"chunk {chunk.chunk_id} is not verbatim source text"
        assert chunk.text.strip(), f"chunk {chunk.chunk_id} is empty"
        assert chunk.char_start < chunk.char_end


def test_chunk_offsets_point_at_the_chunk_text(good_pdf: Path) -> None:
    """Declared offsets overlap the chunk's real position in ``full_text``.

    Overlap padding may extend a chunk to the left of ``char_start``, so the
    test asks for overlap rather than exact equality — but the declared range
    must genuinely intersect the text the chunk carries.
    """
    result = _extract(good_pdf)

    for chunk in chunk_document(result):
        actual_start = result.full_text.index(chunk.text)
        actual_end = actual_start + len(chunk.text)
        assert actual_start <= chunk.char_end, "char_start lies after the chunk's real text"
        assert actual_end >= chunk.char_start, "char_end lies before the chunk's real text"
        assert 0 <= chunk.char_start < chunk.char_end <= len(result.full_text)


def test_chunk_pages_are_mapped_from_real_page_offsets(good_pdf: Path) -> None:
    """``page_start``/``page_end`` are correct on a three-page document.

    A citation that says "page 2" must mean page 2. Each synthetic page carries
    a unique marker, so the page range of a chunk can be checked against the
    markers its text actually contains — no guessing, and no reliance on the
    implementation's own bookkeeping.
    """
    result = _extract(good_pdf)
    marker_page = {
        marker: page.page_number
        for page in result.pages
        for marker in PAGE_MARKERS
        if marker in page.text
    }
    assert len(marker_page) == 3, "each page must carry exactly one marker"

    chunks = chunk_document(result)

    assert chunks
    for chunk in chunks:
        assert 1 <= chunk.page_start <= chunk.page_end <= result.page_count
        mentioned = {marker_page[marker] for marker in PAGE_MARKERS if marker in chunk.text}
        assert mentioned, f"chunk {chunk.chunk_id} mentions no page marker"
        assert mentioned <= set(range(chunk.page_start, chunk.page_end + 1)), (
            f"chunk {chunk.chunk_id} claims pages {chunk.page_start}-{chunk.page_end} "
            f"but its text comes from pages {sorted(mentioned)}"
        )


def test_a_chunk_of_single_page_text_reports_exactly_that_page(laws_dir: Path) -> None:
    """A section that fits on one page is attributed to that page alone.

    Uses an oversized ``target_chars`` so each page becomes one chunk; the
    assertion is then exact rather than a range containment.
    """
    path = _write_multipage_pdf(laws_dir / "alpha_pages.pdf", page_count=3)
    result = _extract(path)
    config = ChunkingConfig(target_chars=100_000, overlap_chars=0, min_chars=10)

    chunks = chunk_document(result, config)

    by_marker = {}
    for chunk in chunks:
        for marker in PAGE_MARKERS:
            if marker in chunk.text:
                by_marker[marker] = chunk

    assert len(by_marker) == 3
    for page in result.pages:
        marker = next(item for item in PAGE_MARKERS if item in page.text)
        chunk = by_marker[marker]
        assert chunk.page_start == page.page_number
        assert chunk.page_end == page.page_number


def test_chunk_document_respects_a_tiny_target(good_pdf: Path) -> None:
    """A very small ``target_chars`` still yields well-formed, verbatim chunks.

    The pathological setting is where an off-by-one in the splitter shows up:
    a cut past the end of the text, or an infinite loop on a boundary.
    """
    result = _extract(good_pdf)
    config = ChunkingConfig(target_chars=64, overlap_chars=8, min_chars=10)

    chunks = chunk_document(result, config)

    assert len(chunks) > 1, "a 64-char target should split a three-page document"
    for chunk in chunks:
        assert chunk.text in result.full_text
        assert 0 <= chunk.char_start < chunk.char_end <= len(result.full_text)
        assert 1 <= chunk.page_start <= chunk.page_end <= result.page_count


def test_chunk_document_honours_a_large_min_chars_where_no_section_is_crossed(
    laws_dir: Path,
) -> None:
    """No chunk below ``min_chars`` is emitted when merging is legal.

    Emitting a three-word "chunk" would flood retrieval with noise that matches
    almost any query, which is the failure mode a floor exists to prevent.

    The fixture deliberately carries no section headings, so nothing here
    competes with the floor. Where headings *are* present the floor yields to
    them - see the next test, which is the one that matters legally.
    """
    path = _write_pdf(laws_dir / "alpha_floor.pdf", [_filler_lines(20)])
    result = _extract(path)
    config = ChunkingConfig(target_chars=300, overlap_chars=0, min_chars=400)

    chunks = chunk_document(result, config)

    assert chunks
    for chunk in chunks:
        assert len(chunk.text.strip()) >= config.min_chars, (
            f"chunk {chunk.chunk_id} is {len(chunk.text.strip())} chars, "
            f"below the configured floor of {config.min_chars}"
        )


def test_chunk_document_prefers_a_section_boundary_over_the_min_chars_floor(
    laws_dir: Path,
) -> None:
    """A sub-floor chunk is kept whole rather than merged across a section.

    This is the project's hardest invariant, and it is deliberately allowed to
    break the ``min_chars`` floor. Merging section 7001 into section 7002 would
    file one provision's text under the other's number, and the chunk keeps only
    the left label - so the citation the user finally sees names the wrong
    provision. A chunk that is slightly too small is recoverable; a misattributed
    section number is not.

    So the floor is a preference, and the boundary is a veto.
    """
    path = _write_multipage_pdf(laws_dir / "alpha_sections.pdf", page_count=3)
    result = _extract(path)
    config = ChunkingConfig(target_chars=300, overlap_chars=0, min_chars=400)

    chunks = chunk_document(result, config)

    assert chunks
    # Every chunk names exactly one provision, and the name it claims is the
    # only section marker its text contains. A chunk may legitimately begin
    # mid-provision, so the label need not be at offset zero - but if text from
    # a second provision had been merged in, that second marker would be here.
    for chunk in chunks:
        assert chunk.section_label is not None
        others = [label for label in ALL_HEADING_LABELS if label != chunk.section_label]
        assert not any(other in chunk.text for other in others), (
            f"chunk {chunk.chunk_id} merged two provisions: it carries "
            f"{chunk.section_label} and also "
            f"{[o for o in others if o in chunk.text]}"
        )
    # Some of them are below the floor, and that is the accepted cost.
    assert any(len(chunk.text.strip()) < config.min_chars for chunk in chunks)


def test_a_stray_blank_page_does_not_break_chunking(laws_dir: Path) -> None:
    """A blank page between two text pages still produces valid chunks.

    Blank pages are ordinary in a bound statute and must not shift page numbers
    or produce an empty chunk.
    """
    path = _write_pdf(
        laws_dir / "alpha_verso.pdf",
        [[HEADING_ONE, *_filler_lines(4)], [], [HEADING_TWO, *_filler_lines(4, start=2)]],
    )
    result = _extract(path)

    chunks = chunk_document(result)

    assert chunks
    for chunk in chunks:
        assert chunk.text.strip(), f"chunk {chunk.chunk_id} is blank"
        assert chunk.text in result.full_text
        assert 1 <= chunk.page_start <= chunk.page_end <= 3


def test_chunk_document_uses_the_default_config_when_none_is_given(good_pdf: Path) -> None:
    """Passing ``None`` must mean "the documented defaults", not "no chunking"."""
    result = _extract(good_pdf)

    assert chunk_document(result, None) == chunk_document(result, ChunkingConfig())


def test_chunk_document_handles_a_document_with_no_sections(good_pdf: Path) -> None:
    """Text with no detectable headings is still chunked, with ``None`` labels.

    A corpus of unnumbered prose must not silently produce zero chunks.
    """
    path = _write_pdf(good_pdf.parent / "alpha_plain.pdf", [_filler_lines(6)])
    result = _extract(path)

    assert detect_section_labels(result.full_text) == ()
    chunks = chunk_document(result)

    assert chunks
    assert all(chunk.section_label is None for chunk in chunks)
    assert all(chunk.section_detection == "none" for chunk in chunks)


def test_chunk_document_survives_a_single_character_document(laws_dir: Path) -> None:
    """Tiny input must not raise, and must not emit an empty chunk.

    Boundary conditions are where chunkers crash; the pipeline must survive
    whatever the corpus contains.
    """
    path = _write_pdf(laws_dir / "alpha_tiny.pdf", [["Alpha filler only."], ["Beta filler only."]])
    result = _extract(path)

    chunks = chunk_document(result, ChunkingConfig(target_chars=10, overlap_chars=0, min_chars=1))

    assert all(chunk.text.strip() for chunk in chunks)
    assert all(chunk.text in result.full_text for chunk in chunks)


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------


def test_build_index_on_an_empty_directory_reports_zero(laws_dir: Path, index_dir: Path) -> None:
    """An empty corpus is a successful zero-document run, not a failure.

    A fresh checkout has no statute PDFs yet. The pipeline has to be able to
    run and say so without erroring, so an operator can check their setup.
    """
    report = build_index(laws_dir, index_dir)

    assert isinstance(report, IngestionReport)
    assert report.documents_found == 0
    assert report.documents_ingested == 0
    assert report.documents_failed == 0
    assert report.chunks_written == 0
    assert report.failures == ()


def test_build_index_on_a_missing_directory_reports_zero(tmp_path: Path, index_dir: Path) -> None:
    """A missing laws directory yields the same quiet zero-document report."""
    report = build_index(tmp_path / "absent_laws", index_dir)

    assert report.documents_found == 0
    assert report.documents_ingested == 0
    assert report.documents_failed == 0


def test_build_index_counts_a_single_good_document(
    laws_dir: Path, index_dir: Path, good_pdf: Path
) -> None:
    """One readable PDF is found, ingested and chunked."""
    report = build_index(laws_dir, index_dir)

    assert report.documents_found == 1
    assert report.documents_ingested == 1
    assert report.documents_failed == 0
    assert report.failures == ()
    assert report.chunks_written > 0


def test_build_index_ingests_the_good_file_when_another_is_corrupt(
    laws_dir: Path, index_dir: Path, good_pdf: Path, corrupt_pdf: Path
) -> None:
    """One bad PDF must not abort the run.

    This is the most operationally important behaviour of the pipeline: a
    corpus of hundreds of statute PDFs will always contain one damaged file,
    and a pipeline that stops there would need a human to intervene before it
    could index anything at all.
    """
    report = build_index(laws_dir, index_dir)

    assert report.documents_found == 2
    assert report.documents_ingested == 1
    assert report.documents_failed == 1
    assert report.chunks_written > 0, "the good document must still land"
    assert len(report.failures) == 1

    failure = report.failures[0]
    assert isinstance(failure, IngestionFailure)
    assert failure.filename == corrupt_pdf.name
    assert_reason_is_neutral(
        failure.reason, context="ingestion failure", forbidden_paths=(laws_dir, corrupt_pdf)
    )


def test_build_index_failure_records_every_bad_file(laws_dir: Path, index_dir: Path) -> None:
    """Every unreadable file gets its own record; none are swallowed silently."""
    _write_corrupt_pdf(laws_dir / "alpha_broken.pdf")
    _write_corrupt_pdf(laws_dir / "bravo_broken.pdf")
    _write_scan_like_pdf(laws_dir / "charlie_scan.pdf")

    report = build_index(laws_dir, index_dir)

    assert report.documents_found == 3
    assert report.documents_ingested == 0
    assert report.documents_failed == 3
    assert sorted(failure.filename for failure in report.failures) == [
        "alpha_broken.pdf",
        "bravo_broken.pdf",
        "charlie_scan.pdf",
    ]
    for failure in report.failures:
        assert_reason_is_neutral(
            failure.reason, context="bulk failure", forbidden_paths=(laws_dir,)
        )


def test_build_index_failure_law_id_is_still_usable(laws_dir: Path, index_dir: Path) -> None:
    """A failure record carries the law_id derived from the filename.

    An operator triaging a report needs to know *which* statute failed without
    opening the source directory, and the law_id is the only identifier that
    survives into later stages.
    """
    _write_corrupt_pdf(laws_dir / "alpha_broken.pdf")

    report = build_index(laws_dir, index_dir)

    failure = report.failures[0]
    assert failure.law_id == normalise_law_id("alpha_broken")
    assert failure.law_id


def test_build_index_report_records_the_directories_it_used(
    laws_dir: Path, index_dir: Path, good_pdf: Path
) -> None:
    """The report says which directories it touched.

    Without that, an operator cannot tell where an index came from when several
    checkouts exist on one machine.
    """
    report = build_index(laws_dir, index_dir)

    assert report.laws_dir == laws_dir
    assert report.index_dir == index_dir
    assert isinstance(report.source, str) and report.source.strip()


def test_build_index_is_deterministic(laws_dir: Path, tmp_path: Path, good_pdf: Path) -> None:
    """Two builds over the same corpus report the same numbers."""
    first = build_index(laws_dir, tmp_path / "index_a")
    second = build_index(laws_dir, tmp_path / "index_b")

    assert first.documents_found == second.documents_found
    assert first.documents_ingested == second.documents_ingested
    assert first.chunks_written == second.chunks_written


def test_ingestion_report_and_failure_are_immutable(laws_dir: Path, index_dir: Path) -> None:
    """Reports are returned to callers and cached; they must not be mutable."""
    report = build_index(laws_dir, index_dir)

    with pytest.raises(dataclasses.FrozenInstanceError):
        report.documents_ingested = 99  # type: ignore[misc]


def test_source_document_and_page_text_are_immutable(good_pdf: Path) -> None:
    """The value types leaving the extraction layer are frozen."""
    result = _extract(good_pdf)

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.document.law_id = "tampered"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.pages[0].text = "tampered"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# write_index
# ---------------------------------------------------------------------------


@pytest.fixture
def built_chunks(good_pdf: Path) -> tuple[list[Chunk], list[SourceDocument]]:
    """Real chunks and their source documents, produced the way the pipeline does.

    ``write_index`` is tested against genuine output rather than hand-built
    dataclasses, so a mismatch between the chunker and the serialiser cannot
    hide behind a convenient fixture.
    """
    result = _extract(good_pdf)
    return list(chunk_document(result)), [result.document]


def test_write_index_writes_exactly_the_two_stage_two_artefacts(
    index_dir: Path, built_chunks: tuple[list[Chunk], list[SourceDocument]]
) -> None:
    """Stage 2 writes ``chunks.json`` and ``index_metadata.json``, and creates the dir."""
    chunks, documents = built_chunks
    assert not index_dir.exists()

    written = write_index(chunks, documents, index_dir)

    assert written == len(chunks)
    assert index_dir.is_dir()
    assert (index_dir / "chunks.json").is_file()
    assert (index_dir / "index_metadata.json").is_file()


def test_write_index_does_not_write_embeddings(
    index_dir: Path, built_chunks: tuple[list[Chunk], list[SourceDocument]]
) -> None:
    """No ``embeddings.npy`` at Stage 2 — there is no embedding model installed.

    Writing a placeholder or an empty array would flip ``knowledge_base_ready``
    to true and have the application advertise a knowledge base it cannot
    search. The absence of this file is the honesty mechanism.
    """
    chunks, documents = built_chunks

    write_index(chunks, documents, index_dir)

    assert not (index_dir / "embeddings.npy").exists()
    assert sorted(path.name for path in index_dir.iterdir()) == [
        "chunks.json",
        "index_metadata.json",
    ]


def test_write_index_leaves_no_temporary_file_behind(
    index_dir: Path, built_chunks: tuple[list[Chunk], list[SourceDocument]]
) -> None:
    """The atomic write cleans up after itself.

    A leftover ``.tmp`` is the visible symptom of a crashed run; leaving them
    around makes a directory of half-written indexes indistinguishable from a
    healthy one.
    """
    chunks, documents = built_chunks

    write_index(chunks, documents, index_dir)

    leftovers = [path.name for path in index_dir.iterdir() if path.name.endswith(".tmp")]
    assert leftovers == [], f"temporary files left behind: {leftovers}"


def test_write_index_replaces_a_previous_index_wholesale(index_dir: Path, good_pdf: Path) -> None:
    """A second run overwrites the artefacts instead of merging into them.

    ``os.replace`` semantics are what guarantee this. An implementation that
    appended, or that opened in text mode without truncating, would leave a
    Frankenstein index whose chunk_count disagrees with its contents.
    """
    index_dir.mkdir(parents=True)
    (index_dir / "chunks.json").write_text("this is stale garbage, not json", encoding="utf-8")
    (index_dir / "index_metadata.json").write_text("{stale", encoding="utf-8")

    result = _extract(good_pdf)
    chunks = list(chunk_document(result))

    write_index(chunks, [result.document], index_dir)

    payload = json.loads((index_dir / "chunks.json").read_text(encoding="utf-8"))
    assert payload["chunks"], "the stale content was not replaced"
    json.loads((index_dir / "index_metadata.json").read_text(encoding="utf-8"))


def test_write_index_removes_a_temporary_left_by_a_crashed_run(
    index_dir: Path, tmp_path: Path, good_pdf: Path
) -> None:
    """A stale ``*.tmp`` from an earlier crash does not survive a good run.

    Temp files are the visible evidence of a crashed ingestion. A healthy run
    that leaves them behind is indistinguishable from a crashed one by
    inspecting the directory.
    """
    index_dir.mkdir(parents=True)
    (index_dir / "chunks.json.tmp").write_text("half-written garbage", encoding="utf-8")

    result = _extract(good_pdf)
    write_index(list(chunk_document(result)), [result.document], index_dir)

    assert list(index_dir.glob("*.tmp")) == [], "a stale temporary file survived the run"


def test_chunks_json_has_the_documented_shape(
    index_dir: Path, built_chunks: tuple[list[Chunk], list[SourceDocument]]
) -> None:
    """Every chunk object carries exactly the documented keys.

    A retrieval stage written against these keys will not notice a missing
    field until a user searches, so the shape is pinned here.
    """
    chunks, documents = built_chunks

    write_index(chunks, documents, index_dir)
    payload = json.loads((index_dir / "chunks.json").read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert isinstance(payload["chunks"], list)
    assert len(payload["chunks"]) == len(chunks)
    expected_keys = {
        "chunk_id",
        "law_id",
        "chunk_index",
        "text",
        "page_start",
        "page_end",
        "char_start",
        "char_end",
        "section_label",
        "section_detection",
    }
    for entry in payload["chunks"]:
        assert set(entry) == expected_keys
        assert isinstance(entry["chunk_index"], int)
        assert isinstance(entry["page_start"], int)
        assert isinstance(entry["page_end"], int)
        assert entry["section_detection"] in {"heading", "inline", "none"}
        assert entry["section_label"] is None or isinstance(entry["section_label"], str)


def test_chunks_json_serialises_a_missing_label_as_null(index_dir: Path, good_pdf: Path) -> None:
    """``section_label`` is JSON ``null``, never the string ``"None"``.

    A stringified sentinel would be indistinguishable from a real label once
    it reached the citation formatter.
    """
    result = _extract(_write_pdf(index_dir.parent / "alpha_plain.pdf", [_filler_lines(6)]))
    chunks = list(chunk_document(result))
    assert chunks and all(chunk.section_label is None for chunk in chunks)

    write_index(chunks, [result.document], index_dir)
    raw = (index_dir / "chunks.json").read_text(encoding="utf-8")

    assert '"section_label": null' in raw
    assert "None" not in raw


def test_chunks_json_is_written_as_utf8_without_ascii_escaping(
    index_dir: Path, good_pdf: Path
) -> None:
    """Non-ASCII statute text stays readable on disk instead of becoming escapes.

    ``ensure_ascii=False`` is in the contract because the corpus is not purely
    English and an operator opening ``chunks.json`` to debug a bad extraction
    needs to read the text as printed.
    """
    result = _extract(good_pdf)
    chunks = [
        dataclasses.replace(chunk, text=f"{chunk.text} {UNICODE_SAMPLE}")
        for chunk in chunk_document(result)
    ]

    write_index(chunks, [result.document], index_dir)
    raw = (index_dir / "chunks.json").read_bytes().decode("utf-8")

    assert "ünïcödé sample é" in raw
    assert "\\u00fc" not in raw


def test_chunks_json_is_indented_for_human_review(index_dir: Path, built_chunks) -> None:
    """``indent=2`` keeps the artefact diffable and reviewable."""
    chunks, documents = built_chunks

    write_index(chunks, documents, index_dir)
    raw = (index_dir / "chunks.json").read_text(encoding="utf-8")

    assert "\n  " in raw, "chunks.json is expected to be indented"


def test_index_metadata_has_the_documented_shape(
    index_dir: Path, built_chunks: tuple[list[Chunk], list[SourceDocument]]
) -> None:
    """Metadata records what was indexed and which script produced it.

    ``generated_by`` is how someone reading a deployed index knows which command
    to re-run after upgrading the pipeline.
    """
    chunks, documents = built_chunks

    write_index(chunks, documents, index_dir)
    metadata = json.loads((index_dir / "index_metadata.json").read_text(encoding="utf-8"))

    assert metadata["schema_version"] == 1
    assert metadata["chunk_count"] == len(chunks)
    assert metadata["document_count"] == len(documents)
    assert metadata["generated_by"] == "scripts/ingest_laws.py"
    assert isinstance(metadata["failures"], list)

    assert len(metadata["documents"]) == len(documents)
    for entry in metadata["documents"]:
        required = {
            "law_id",
            "act_name",
            "year",
            "filename",
            "size_bytes",
            "sha256",
            "chunk_count",
        }
        assert required <= set(entry), f"missing keys: {sorted(required - set(entry))}"
        assert isinstance(entry["size_bytes"], int)
        assert isinstance(entry["chunk_count"], int)
        assert len(entry["sha256"]) == 64
        assert entry["filename"].lower().endswith(".pdf")
        if "page_count" in entry:
            assert isinstance(entry["page_count"], int) and entry["page_count"] > 0


def test_index_metadata_chunk_counts_add_up(
    index_dir: Path, built_chunks: tuple[list[Chunk], list[SourceDocument]]
) -> None:
    """Per-document chunk counts must sum to the reported total.

    A mismatch is the classic symptom of a stale file surviving an atomic
    write, and it is exactly the number a health endpoint will show a user.
    """
    chunks, documents = built_chunks

    write_index(chunks, documents, index_dir)
    metadata = json.loads((index_dir / "index_metadata.json").read_text(encoding="utf-8"))

    assert sum(entry["chunk_count"] for entry in metadata["documents"]) == metadata["chunk_count"]


def test_index_metadata_records_failures_passed_through(
    index_dir: Path, built_chunks: tuple[list[Chunk], list[SourceDocument]]
) -> None:
    """The failures key is always present, even when the list is empty.

    A consumer that reads ``metadata["failures"]`` without a default would crash
    on a clean run.
    """
    chunks, documents = built_chunks

    write_index(chunks, documents, index_dir)
    metadata = json.loads((index_dir / "index_metadata.json").read_text(encoding="utf-8"))

    assert metadata["failures"] == []


def test_write_index_is_byte_for_byte_deterministic(
    index_dir: Path, tmp_path: Path, good_pdf: Path
) -> None:
    """Two writes of the same chunks produce identical bytes.

    This is what makes an index reviewable in version control and what makes
    "did anything actually change?" answerable without a semantic diff.
    """
    result = _extract(good_pdf)
    chunks = list(chunk_document(result))

    write_index(chunks, [result.document], index_dir)
    write_index(chunks, [result.document], tmp_path / "second")

    first = (index_dir / "chunks.json").read_bytes()
    second = (tmp_path / "second" / "chunks.json").read_bytes()
    assert first == second

    first_meta = (index_dir / "index_metadata.json").read_bytes()
    second_meta = (tmp_path / "second" / "index_metadata.json").read_bytes()
    assert first_meta == second_meta


def test_write_index_handles_an_empty_chunk_list(index_dir: Path) -> None:
    """A zero-chunk write still produces valid artefacts.

    The CLI can reach this state (empty corpus), and it must produce a readable
    index rather than crash on an empty sequence.
    """
    written = write_index([], [], index_dir)

    assert written == 0
    payload = json.loads((index_dir / "chunks.json").read_text(encoding="utf-8"))
    assert payload == {"schema_version": 1, "chunks": []}
    metadata = json.loads((index_dir / "index_metadata.json").read_text(encoding="utf-8"))
    assert metadata["chunk_count"] == 0


# ---------------------------------------------------------------------------
# The honesty guard
# ---------------------------------------------------------------------------


@pytest.fixture
def settings_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Any:
    """Rebuild the cached :class:`Settings` object against a temporary index dir.

    ``knowledge_base_ready`` is a property of the *cached* settings instance,
    so redirecting it means rebuilding that instance: mutating ``INDEX_DIR`` on
    the live object would bypass pydantic's validators and leave a bare string
    where a ``Path`` is expected. ``get_settings.cache_clear()`` plus a fresh
    call is the supported way, and the teardown restores the session-wide
    configuration ``tests/conftest.py`` installed.
    """
    index_location = tmp_path / "live_index"
    monkeypatch.setenv("INDEX_DIR", str(index_location))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


def test_knowledge_base_stays_not_ready_after_a_build(
    laws_dir: Path, index_dir: Path, settings_at: Any, good_pdf: Path
) -> None:
    """A Stage 2 build must NOT make the app claim a searchable knowledge base.

    ``knowledge_base_ready`` requires all three artefacts including
    ``embeddings.npy``, which Stage 3 will produce. Until then, reporting ready
    would send a user to an assistant that retrieves nothing and answers from
    the model's own memory — presented, wrongly, as grounded in statute text.
    This is the single most important behavioural assertion in the file.

    The settings are pointed at ``index_dir`` first, so what is asserted is the
    real deployed arrangement: the index exists, and the app still says no.
    """
    settings_at.INDEX_DIR = index_dir
    build_index(laws_dir, index_dir)

    assert (index_dir / "chunks.json").is_file(), "the build should have produced chunks"
    assert (index_dir / "index_metadata.json").is_file()
    assert not (index_dir / "embeddings.npy").exists()

    assert settings_at.knowledge_base_ready is False, (
        "Stage 2 must leave knowledge_base_ready False: without embeddings.npy the "
        "index cannot be searched, and claiming otherwise would advertise a "
        "grounded answer the system cannot give."
    )


def test_knowledge_base_is_ready_once_every_artefact_exists(
    index_dir: Path, settings_at: Any, good_pdf: Path
) -> None:
    """The flag flips only when the last missing artefact arrives.

    The counterpart to the test above: it proves the flag is genuinely computed
    from the artefacts on disk rather than hard-wired to ``False``, so Stage 3
    will not have to unpick a stuck guard.
    """
    settings_at.INDEX_DIR = index_dir
    result = _extract(good_pdf)
    write_index(list(chunk_document(result)), [result.document], index_dir)

    assert settings_at.knowledge_base_ready is False

    (index_dir / "embeddings.npy").write_bytes(b"\x93NUMPY fake placeholder for this test")

    assert settings_at.knowledge_base_ready is True


def test_health_endpoint_does_not_claim_readiness_after_a_build(
    laws_dir: Path, index_dir: Path, settings_at: Any, good_pdf: Path
) -> None:
    """The user-visible health payload agrees with the settings flag.

    A correct flag that a route ignores is no protection at all, so the claim is
    checked where a user would actually see it. The app is imported here, after
    the environment is already redirected, which is the ordering
    ``tests/conftest.py`` exists to guarantee.
    """
    settings_at.INDEX_DIR = index_dir
    build_index(laws_dir, index_dir)

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as test_client:
        knowledge_base = test_client.get("/api/health").json()["knowledge_base"]

    assert knowledge_base["ready"] is False, (
        "/api/health must not report a ready knowledge base after a Stage 2 build"
    )


# ---------------------------------------------------------------------------
# scripts/ingest_laws.py
# ---------------------------------------------------------------------------


def _load_cli() -> SimpleNamespace:
    """Import the ingestion CLI, skipping if it has not been written yet.

    The CLI is a sibling deliverable of this stage. Skipping with a clear reason
    keeps the rest of this file runnable and reports the gap honestly instead of
    turning a missing module into a collection error for every other test.
    """
    try:
        import scripts.ingest_laws as cli_module
    except ImportError as error:  # pragma: no cover - depends on sibling agent
        pytest.skip(f"scripts/ingest_laws.py is not importable yet: {error}")
    return SimpleNamespace(module=cli_module)


def test_cli_dry_run_writes_nothing(
    laws_dir: Path, index_dir: Path, good_pdf: Path
) -> None:
    """``--dry-run`` reports and writes nothing.

    This is the mode an operator uses to preview an ingestion before touching
    their index, so a single stray file is a contract violation.
    """
    cli = _load_cli()

    exit_code = cli.module.main(
        ["--laws-dir", str(laws_dir), "--index-dir", str(index_dir), "--dry-run"]
    )

    assert exit_code == 0
    assert not index_dir.exists(), "--dry-run must not create the index directory"
    assert list(laws_dir.glob("*.json")) == []


def test_cli_dry_run_prints_a_summary_without_statute_text(
    laws_dir: Path, index_dir: Path, capsys: Any, good_pdf: Path
) -> None:
    """The summary carries counts, never the text it just read.

    Statute text on a console is one stray copy-paste away from a bug report
    filed in public, and it is not what an operator needs to see.
    """
    cli = _load_cli()

    cli.module.main(["--laws-dir", str(laws_dir), "--index-dir", str(index_dir), "--dry-run"])
    output = capsys.readouterr().out

    assert output.strip(), "the CLI must print something"
    assert PAGE_MARKERS[0] not in output, "statute text leaked to stdout"
    assert HEADING_ONE not in output, "statute text leaked to stdout"
    assert "1" in output


def test_cli_writes_the_index_without_dry_run(
    laws_dir: Path, index_dir: Path, good_pdf: Path
) -> None:
    """A normal run produces the two Stage 2 artefacts and exits 0."""
    cli = _load_cli()

    exit_code = cli.module.main(["--laws-dir", str(laws_dir), "--index-dir", str(index_dir)])

    assert exit_code == 0
    assert (index_dir / "chunks.json").is_file()
    assert (index_dir / "index_metadata.json").is_file()
    assert not (index_dir / "embeddings.npy").exists()


def test_cli_exits_one_when_a_document_fails(
    laws_dir: Path, index_dir: Path, capsys: Any, good_pdf: Path, corrupt_pdf: Path
) -> None:
    """A partial run exits 1 so a CI job or wrapper script notices.

    The good document still gets indexed; the non-zero code is what stops an
    operator believing the whole corpus was processed. Only the failure *line*
    is scanned for leaked paths — the summary line legitimately names the
    directories it was told to use.
    """
    cli = _load_cli()

    exit_code = cli.module.main(["--laws-dir", str(laws_dir), "--index-dir", str(index_dir)])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert corrupt_pdf.name in output, "the failing filename must be reported"
    assert (index_dir / "chunks.json").is_file(), "the good document must still land"

    failure_lines = [line for line in output.splitlines() if corrupt_pdf.name in line]
    assert failure_lines, "the failing filename must appear on a line of its own"
    for line in failure_lines:
        assert "Traceback" not in line
        assert "site-packages" not in line
        assert str(laws_dir) not in line, f"the failure line leaked a directory: {line!r}"


def test_cli_exits_two_when_the_laws_directory_is_missing(tmp_path: Path, index_dir: Path) -> None:
    """A missing corpus directory is a setup error, distinct from a parse failure.

    Exit 2 tells the operator "you have not pointed me at the statutes" rather
    than "your statutes are broken".
    """
    cli = _load_cli()

    exit_code = cli.module.main(
        ["--laws-dir", str(tmp_path / "no_such_dir"), "--index-dir", str(index_dir), "--dry-run"]
    )

    assert exit_code == 2


def test_cli_exits_two_for_an_empty_laws_directory(laws_dir: Path, index_dir: Path) -> None:
    """An empty corpus directory also exits 2.

    There is nothing to ingest, and saying so with a dedicated code is more
    useful than a cheerful "0 documents ingested".
    """
    cli = _load_cli()

    exit_code = cli.module.main(
        ["--laws-dir", str(laws_dir), "--index-dir", str(index_dir), "--dry-run"]
    )

    assert exit_code == 2


def test_cli_output_never_contains_a_traceback(
    laws_dir: Path, index_dir: Path, capsys: Any, good_pdf: Path
) -> None:
    """No run, successful or not, prints a stack trace.

    The CLI is the operator's window into the pipeline; a traceback there means
    an implementation detail escaped the "catch, normalise, record" rule.
    """
    cli = _load_cli()

    cli.module.main(["--laws-dir", str(laws_dir), "--index-dir", str(index_dir)])
    output = capsys.readouterr()

    for stream in (output.out, output.err):
        assert "Traceback" not in stream
        assert 'File "' not in stream
        assert "site-packages" not in stream


def test_cli_module_is_runnable_as_a_script() -> None:
    """``python scripts/ingest_laws.py`` is the documented invocation.

    The script must be able to find the ``app`` package on its own, which means
    it puts the backend root on ``sys.path`` the same way ``tests/conftest.py``
    does. This is checked structurally because running it would touch the real
    ``data/laws`` directory.
    """
    script = Path(__file__).resolve().parent.parent / "scripts" / "ingest_laws.py"

    if not script.is_file():  # pragma: no cover - depends on sibling agent
        pytest.skip("scripts/ingest_laws.py has not been written yet")

    source = script.read_text(encoding="utf-8")
    assert "sys.path" in source, "the script must extend sys.path to import the app package"
    assert 'raise SystemExit(main())' in source, "the script must use the documented entry point"


# ---------------------------------------------------------------------------
# Cross-cutting provenance guards
# ---------------------------------------------------------------------------


def test_no_artefact_records_an_absolute_path(
    index_dir: Path, laws_dir: Path, good_pdf: Path
) -> None:
    """The written index must not embed this machine's directory layout.

    An index is a derived artefact that may be committed, copied between
    machines or shipped in a container image. Absolute paths inside it leak the
    operator's username and break as soon as the tree moves.
    """
    result = _extract(good_pdf)
    write_index(list(chunk_document(result)), [result.document], index_dir)

    for name in ("chunks.json", "index_metadata.json"):
        raw = (index_dir / name).read_text(encoding="utf-8")
        assert str(laws_dir) not in raw, f"{name} leaked the laws directory"
        assert str(good_pdf) not in raw, f"{name} leaked a source file path"
        assert str(index_dir) not in raw, f"{name} leaked the index directory"


def test_ingestion_reads_only_the_directory_it_is_given(
    good_pdf: Path, tmp_path: Path, index_dir: Path, monkeypatch: Any
) -> None:
    """Ingestion reads the directory it is handed and no other.

    A pipeline that also globbed the configured ``data/laws`` "for convenience"
    would pull real statute files into a test run, or — worse — write an index
    derived from them into a temporary directory.

    The spy is installed on ``app.rag.pipeline`` rather than on
    ``app.rag.extraction``. That is the seam the product actually calls through,
    and patching it is what makes this an assertion about *ingestion* instead of
    about the scanner in isolation.
    """
    import app.rag.pipeline as pipeline_module

    observed: list[Path] = []
    original = pipeline_module._extraction.scan_law_pdfs

    def _spy(directory: Path) -> Any:
        observed.append(Path(directory))
        return original(directory)

    monkeypatch.setattr(pipeline_module._extraction, "scan_law_pdfs", _spy)
    build_index(good_pdf.parent, index_dir)

    assert observed, "the spy did not see the scan call"
    for directory in observed:
        assert directory == good_pdf.parent
    assert index_dir.is_dir(), "the run produced no index to inspect"

    metadata = json.loads((index_dir / "index_metadata.json").read_text(encoding="utf-8"))
    for entry in metadata["documents"]:
        assert entry["filename"] == good_pdf.name
        assert str(tmp_path) not in json.dumps(metadata)


def test_extraction_failure_text_never_names_a_library(laws_dir: Path, index_dir: Path) -> None:
    """Failure text stays technology-neutral across every failure mode.

    Naming ``pymupdf`` in a message couples our operator-facing output to a
    dependency choice, and invites the reader to go look at third-party source
    code instead of fixing their corpus.
    """
    _write_corrupt_pdf(laws_dir / "alpha_broken.pdf")
    _write_scan_like_pdf(laws_dir / "bravo_scan.pdf")

    report = build_index(laws_dir, index_dir)

    assert report.documents_failed == 2
    for failure in report.failures:
        reason = failure.reason.lower()
        assert_reason_is_neutral(
            failure.reason, context="library-neutral reason", forbidden_paths=(laws_dir,)
        )
        assert "pymupdf" not in reason
        assert "fitz" not in reason


# ===========================================================================
# Second review round.
#
# Each block below pins one behaviour that was wrong and is now right. The
# docstrings say why the behaviour matters, because a test that only records
# what the code happens to do stops being a test.
# ===========================================================================


def _write_page_furniture_pdf(path: Path, page_count: int = 4) -> Path:
    """Write a PDF whose pages carry page numbers and nothing else.

    This is the realistic shape of an image-only scan that still has a text
    layer: folios, a running head, a stamp. It is *not* an empty text layer,
    and that is the whole point — a character-count threshold cannot tell the
    two apart at any value.
    """
    return _write_pdf(path, [[f"- {number} -"] for number in range(1, page_count + 1)])


def test_a_scan_carrying_page_numbers_is_not_indexed_as_a_statute(
    laws_dir: Path, index_dir: Path
) -> None:
    """Page furniture must never reach the index under a real ``law_id``.

    A four-page scan of a 1957 Act extracts ``"- 1 -\\n- 2 -\\n- 3 -\\n- 4 -"``:
    20 characters, no words. Under a character-count threshold low enough to
    admit a genuine one-page amendment, that string was indexed as the contents
    of the Act, with no warning and ``documents_failed: 0``.

    The failure this prevents is worse than the one it replaces. Rejecting a
    real but short statute is a visible annoyance the operator can fix;
    presenting ``"- 1 -"`` to a user as statutory text is fabrication.
    """
    _write_page_furniture_pdf(laws_dir / "Scanned Nagaland Act 1957.pdf")

    report = build_index(laws_dir, index_dir)

    assert report.documents_failed == 1, (
        f"the scan was not rejected: {report.failures}"
    )
    assert report.documents_ingested == 0
    assert report.chunks_written == 0

    chunks = json.loads((index_dir / CHUNKS_FILENAME).read_text(encoding="utf-8"))["chunks"]
    assert chunks == [], "page furniture was indexed as statute text"


def test_page_furniture_has_characters_but_no_words() -> None:
    """The word test, stated directly: 20 characters and zero words is a scan.

    Kept separate from the pipeline test so the *argument* is visible: the
    numbers are the whole case, and they belong in the test rather than being
    implied by a fixture name.
    """
    furniture = "- 1 -\n- 2 -\n- 3 -\n- 4 -"
    usable = sum(len("".join(part.split())) for part in furniture.split("\n"))
    words = extraction_module._alpha_runs(furniture)

    # It clears the character floor comfortably...
    assert usable >= MIN_TEXT_CHARS_THRESHOLD
    # ...and still contains not one word.
    assert not any(len(run) >= MIN_ALPHA_RUN_CHARS for run in words), (
        f"page furniture unexpectedly produced words: {words}"
    )


def test_a_genuinely_short_document_is_still_accepted(laws_dir: Path) -> None:
    """The word test must not reject the short statutes it exists to admit.

    ``"Ab."`` is two letters and three characters — the shortest genuine stub
    worth indexing. A fix that rejected it would be trading one false negative
    for another, so both halves are pinned together.
    """
    _write_pdf(laws_dir / "commencement_notification.pdf", [["Ab."]])

    (document,) = scan_law_pdfs(laws_dir)
    result = extract_document(document)

    assert "Ab" in result.full_text
    assert result.total_chars == len("Ab.")


def test_a_devanagari_statute_is_not_mistaken_for_a_scan(laws_dir: Path) -> None:
    """A Hindi statute must be admitted on the strength of Devanagari alone.

    The scan test looks for a word. Defining "word" as a Latin letter run means
    a perfectly good Hindi statute scores zero and gets reported to the operator
    as an image-only scan, when the document is in fact fully typed text — the
    failure mode the whole scan test exists to prevent, aimed at the corpus the
    project most needs.
    """
    _write_devanagari_pdf(laws_dir / "hindi_act.pdf", [list(DEVANAGARI_FILLER)])

    (document,) = scan_law_pdfs(laws_dir)
    result = extract_document(document)

    assert "अधिनियम" in result.full_text, (
        f"the Devanagari text layer was rejected as a scan: {result.full_text!r}"
    )
    # The document must genuinely contain no Latin word either, or the test
    # would pass on the old code for the wrong reason: the scan test looks for
    # a word *anywhere* in the document, so a stray ASCII token in the fixture
    # would mask the very defect under test.
    assert not any(character.isascii() and character.isalpha() for character in result.full_text), (
        f"the fixture leaked Latin characters: {result.full_text!r}"
    )


def test_the_word_test_counts_devanagari_as_words() -> None:
    """The unit behind the test above, stated without a PDF in the way.

    End-to-end, the assertion is "the document was not rejected", which is also
    what a change to the *character floor* would produce. Pinned here directly
    against the word finder, so a regression names itself.
    """
    runs = extraction_module._alpha_runs("यह एक नमूना अधिनियम है।")

    assert "नमूना" in runs, f"a matra-bearing word was split: {runs}"
    assert "अधिनियम" in runs, f"a matra-bearing word was split: {runs}"


def test_short_devanagari_words_still_score_as_words() -> None:
    """Short Hindi prose must clear the word threshold, not sit under it.

    This is the half of the scan test that failed even after the first fix. A
    Devanagari syllable is a consonant plus its matra, and the matra *is* the
    vowel — ``न`` alone is ``na``, ``नि`` is ``ni`` — so counting letters only
    measures the syllables that happen to carry a written vowel. ``"क्या कुछ
    हिन्दी"`` is ordinary prose in which every word is one or two such
    syllables, and it scored a longest run of **one** character against a
    threshold of :data:`MIN_ALPHA_RUN_CHARS`, so a perfectly typed Hindi statute
    was reported to the operator as an image-only scan.

    The failure was proportional to how short the words were, which is why it
    read as "short documents get rejected" — the same visible complaint the
    scan test was introduced to trade away, in a corpus the project cannot
    afford to lose.
    """
    hindi = "क्या कुछ हिन्दी"

    runs = extraction_module._alpha_runs(hindi)

    assert runs == ("क्या", "कुछ", "हिन्दी"), f"words were not recovered: {runs}"
    longest = max(len(run) for run in runs)
    assert longest >= MIN_ALPHA_RUN_CHARS, (
        f"ordinary Hindi prose scores {longest}, under the threshold of "
        f"{MIN_ALPHA_RUN_CHARS}"
    )


def test_a_mark_alone_does_not_count_as_a_word() -> None:
    """Including marks must not let bare diacritics pass as words.

    The fix for the split-matra problem admits combining marks, which opens a
    door in the other direction: a text layer of stray marks, with no letters
    anywhere, would score as a document full of very long "words". Nothing
    produces that in a real PDF, and a page of it would be exactly as useless
    as a page of ``"- 1 -"``.
    """
    assert not extraction_module._alpha_runs("िा")
    # Digits are not words either: a page folio must not pass the scan test.
    assert not extraction_module._alpha_runs("- 2023 -")


def test_digits_never_count_as_words() -> None:
    """``"- 2023 -"`` is page furniture, not a four-letter word.

    :data:`_ID_CATEGORIES` includes ``Nd`` and ``No`` because digits belong in
    a ``law_id``. The word test deliberately excludes them, and the two sets
    drifting into one another would quietly reopen the scan hole the word test
    was added to close.
    """
    assert not extraction_module._alpha_runs("2023")
    assert extraction_module._alpha_runs("Article 7001 of the Act") == (
        "Article",
        "of",
        "the",
        "Act",
    )


def test_middle_dots_do_not_count_as_words() -> None:
    """A mangled text layer must not pass the scan test by accident.

    When a PDF writer lacks the glyphs it writes U+00B7 for each character. The
    characters are present and plentiful, so a character-count test waves them
    straight through; only a real word test rejects them. This is the failure
    that would otherwise let a broken *fixture* look like a working document.
    """
    assert not extraction_module._alpha_runs("·· ·· ····· ······· ···")


def test_a_roman_paginated_scan_is_not_mistaken_for_a_statute(laws_dir: Path) -> None:
    """Roman folios are furniture written with letters, not with digits.

    Excluding digits is what rejects ``- 12 -``, but a Roman-paginated Act
    prints the same furniture as ``- iii -`` and that scores a three-character
    *word*. Without this the exact defect the word test exists to prevent
    survives for every Act that numbers its pages in Roman numerals, which is a
    real and common way to print an Indian statute.
    """
    folios = ("i", "ii", "iii", "iv", "v")
    _write_pdf(laws_dir / "roman_folio_scan.pdf", [[f"- {folio} -"] for folio in folios])

    (document,) = scan_law_pdfs(laws_dir)
    with pytest.raises(ExtractionError) as excinfo:
        extract_document(document)

    assert_reason_is_neutral(str(excinfo.value), context="roman folio", forbidden_paths=(laws_dir,))


def test_roman_folios_are_rejected_in_every_case_a_scan_is_printed(laws_dir: Path) -> None:
    """Case is not a property a folio can be required to have.

    Lower case is the common form and upper the scholarly one, so a test written
    against only one of them rejects the wrong half: ``i`` while ``I`` sails
    through as statute text. Both must be caught.
    """
    cases = (("lower", ("i", "ii", "iii")), ("upper", ("I", "II", "III")), ("mixed", ("Iv", "Vi")))
    for label, folios in cases:
        directory = laws_dir / label
        directory.mkdir()
        _write_pdf(directory / f"scan_{label}.pdf", [[f"- {folio} -"] for folio in folios])

        (document,) = scan_law_pdfs(directory)
        with pytest.raises(ExtractionError):
            extract_document(document)


def test_civil_is_not_mistaken_for_a_roman_numeral() -> None:
    """The folio test must not swallow the commonest word in legal prose.

    Every character of **civil** is in the set ``IVXLCDM``, so a folio test
    written as a character-set membership check — the obvious way round — would
    classify "civil court" as a page number and throw away the single most
    common phrase in Indian legal text. The canonical-form check is what keeps
    it: ``CIVIL`` is not a numeral even though all five of its letters are
    numeral symbols.
    """
    assert not extraction_module._is_roman_numeral("civil")
    assert not extraction_module._is_roman_numeral("CIVIL")
    # And the ones that *are* numerals, including the subtractive pairs.
    assert extraction_module._is_roman_numeral("iii")
    assert extraction_module._is_roman_numeral("IV")
    assert extraction_module._is_roman_numeral("MCMXCIV")


def test_a_statute_quoting_a_roman_numeral_is_still_accepted(laws_dir: Path) -> None:
    """A typed Act that happens to contain one numeral must survive.

    The folio rule counts *pages* that are entirely numerals rather than
    testing any single run, precisely so that a Roman numeral appearing in the
    middle of a sentence cannot reach the threshold a wholly scanned document
    does. A document quoting its own divisions is ordinary in an Act.
    """
    _write_pdf(
        laws_dir / "quoting_act.pdf",
        [["1. Short title. The divisions iv and vi are referred to in the Schedule."]],
    )

    (document,) = scan_law_pdfs(laws_dir)
    result = extract_document(document)

    assert "iv" in result.full_text


def test_a_scan_with_one_wordy_cover_page_is_still_warned_about(
    laws_dir: Path, index_dir: Path
) -> None:
    """A single title page must not smuggle a scan past the only check.

    The word test is document-level, so a scan whose cover page carries a title
    passes it. The proportion-of-wordless-pages warning is what catches the
    remainder, and it has to fire — and the warning has to reach the caller — or
    the document-level test is a loophole.
    """
    pages = [["Nagaland Acts, 1957"]] + [[f"- {number} -"] for number in range(2, 11)]
    _write_pdf(laws_dir / "scan_with_cover.pdf", pages)

    (document,) = scan_law_pdfs(laws_dir)
    result = extract_document(document)
    assert any("no words" in warning for warning in result.warnings), (
        f"a mostly-wordless scan produced no warning: {result.warnings}"
    )

    report = build_index(laws_dir, index_dir)
    assert any("no words" in warning for warning in report.warnings), (
        f"the warning did not survive into the report: {report.warnings}"
    )


# --- One corrupt page must not void a whole Act -------------------------------


class _RaisingPage:
    """A page whose text layer always raises, to reach an unreadable page."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def get_text(self, *args: Any, **kwargs: Any) -> str:
        raise RuntimeError("content stream is corrupt")


class _OneBadPageDocument:
    """A PDF stand-in whose third page's text layer always raises.

    PyMuPDF will not produce a genuinely corrupt content stream on demand, so
    the failure is injected at the seam instead.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    @property
    def page_count(self) -> int:
        return self._inner.page_count

    def __getitem__(self, index: int) -> Any:
        if index == 2:
            return _RaisingPage(self._inner[index])
        return self._inner[index]

    def close(self) -> None:
        self._inner.close()


class _AllBadPagesDocument:
    """A PDF stand-in in which no page's text layer can be read."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    @property
    def page_count(self) -> int:
        return self._inner.page_count

    def __getitem__(self, index: int) -> Any:
        return _RaisingPage(self._inner[index])

    def close(self) -> None:
        self._inner.close()


def test_one_corrupt_page_does_not_discard_the_whole_document(
    laws_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 300-page Act must not vanish because page 47 is unreadable.

    The old behaviour raised on the first bad page and threw away every page
    that read perfectly well. For a real statute that is the difference between
    indexing an Act and silently dropping it from the knowledge base — and the
    failure reason gave the operator no way to know the other pages were fine.
    """
    _write_multipage_pdf(laws_dir / "broken_act.pdf", page_count=3)
    (document,) = scan_law_pdfs(laws_dir)

    real_open = extraction_module._open_document
    monkeypatch.setattr(
        extraction_module,
        "_open_document",
        lambda path: _OneBadPageDocument(real_open(path)),
    )

    result = extract_document(document)

    assert result.page_count == 3
    assert result.total_chars > 0, "the readable pages were thrown away"
    assert any("could not be read" in warning for warning in result.warnings), (
        f"an unreadable page produced no warning: {result.warnings}"
    )
    assert any("3" in warning for warning in result.warnings), (
        f"the warning does not name which page failed: {result.warnings}"
    )


def test_a_document_whose_every_page_fails_is_still_an_error(
    laws_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All-pages-unreadable has no partial result, so it must still raise.

    This is the line the per-page fix must not cross: relaxing the page loop
    cannot turn "nothing was readable" into a successful ingestion of nothing.
    """
    _write_multipage_pdf(laws_dir / "wholly_broken.pdf", page_count=3)
    (document,) = scan_law_pdfs(laws_dir)

    real_open = extraction_module._open_document
    monkeypatch.setattr(
        extraction_module,
        "_open_document",
        lambda path: _AllBadPagesDocument(real_open(path)),
    )

    with pytest.raises(ExtractionError) as caught:
        extract_document(document)
    assert str(caught.value) == REASON_TEXT_READ_FAILED


def test_page_number_summaries_are_compact() -> None:
    """The warning must stay a sentence, not a 300-number list.

    Checked directly on the helper because the readable form is part of the
    contract: ``1-3`` is useful, ``1, 2, 3`` is not, and a 300-page scan must
    not produce a warning nobody reads.
    """
    summarise = extraction_module._summarise_page_numbers

    assert summarise((3,)) == "3"
    assert summarise((1, 2, 3)) == "1-3"
    assert summarise((1, 2, 3, 7, 9, 10)) == "1-3, 7, 9-10"
    summary = summarise(tuple(range(1, 30)))
    assert "more" in summary
    assert len(summary) < 60


# --- Devanagari filenames must keep their identity ----------------------------


def test_normalise_law_id_keeps_devanagari_letters() -> None:
    """A Hindi statute must not collapse to the fallback id.

    The character class was ASCII-only while the comment claimed to be Unicode
    aware, so ``"भारतीय संविधान"`` — the Constitution of India — normalised to
    the literal string ``"law"``. Two different Acts then shared one identifier
    and were told apart only by an invented ``_2`` suffix. Losing a statute's
    identity is the failure this project can least afford.
    """
    assert normalise_law_id("भारतीय संविधान") == "भारतीय_संविधान"
    assert normalise_law_id("भारतीय न्याय संहिता 2023") == "भारतीय_न्याय_संहिता_2023"
    assert normalise_law_id("भारतीय संविधान") != normalise_law_id("भारतीय दण्ड संहिता")
    assert "law" not in {normalise_law_id(stem) for stem in _HINDI_STEMS}


def test_normalise_law_id_stays_idempotent_for_every_script() -> None:
    """The idempotence guarantee must survive the character-class change.

    It is what makes a re-run produce a byte-identical index, so it is worth
    checking across scripts rather than only for ASCII input.
    """
    for stem in (*_HINDI_STEMS, "BNS 2023 (1)", "../Indian Penal Code", "---", "BNS___2023"):
        once = normalise_law_id(stem)
        assert normalise_law_id(once) == once, f"not idempotent for {stem!r}: {once!r}"


def test_devanagari_documents_keep_distinct_metadata(
    laws_dir: Path, index_dir: Path
) -> None:
    """Two Hindi-named Acts must not share a ``law_id`` in the written index.

    The end-to-end half: ``index_metadata.json`` is what a later stage reads to
    name an Act in a citation, so this is where a collapsed identity would
    actually mislead a user rather than an operator.
    """
    _write_pdf(laws_dir / "भारतीय संविधान.pdf", [_filler_lines(3)])
    _write_pdf(laws_dir / "भारतीय न्याय संहिता 2023.pdf", [_filler_lines(3, start=3)])

    report = build_index(laws_dir, index_dir)

    assert report.documents_ingested == 2, f"documents failed: {report.failures}"
    metadata = json.loads((index_dir / METADATA_FILENAME).read_text(encoding="utf-8"))
    law_ids = [entry["law_id"] for entry in metadata["documents"]]
    assert len(set(law_ids)) == 2, f"two Hindi statutes collapsed to one id: {law_ids}"
    assert "law" not in law_ids, f"a statute was filed under the fallback id: {law_ids}"


# --- Path masking -------------------------------------------------------------


def test_neutral_reason_masks_paths_containing_spaces() -> None:
    """A laws directory under a personal folder must be masked whole.

    ``C:\\Users\\Jane Doe\\laws\\BNS.pdf`` is an ordinary Windows path. The old
    pattern stopped at the first space and left ``Doe\\laws\\BNS.pdf`` sitting in
    the message — which is precisely the part that names the person.
    """
    assert neutral_reason(r"could not open C:\Users\Jane Doe\laws\BNS.pdf") == (
        "could not open <path>"
    )


def test_neutral_reason_masks_unc_share_paths() -> None:
    """A UNC share leaks the machine and often the organisation; mask it whole."""
    assert neutral_reason(r"\\fileserver\legal_share\laws\BNS.pdf") == "<path>"


@pytest.mark.parametrize(
    "raw",
    [
        r"C:\Program Files\BCK\laws\BNS.pdf",
        r"/home/jane/My Laws/BNS.pdf",
        "/var/lib/bck/laws/BNS.pdf",
    ],
    ids=["windows-space", "home-space", "posix"],
)
def test_neutral_reason_masks_space_bearing_paths_in_any_position(raw: str) -> None:
    """The property, tested across the shapes that matter on each platform."""
    assert neutral_reason(f"failure while reading {raw}") == "failure while reading <path>"


# --- The index pair must not tear ---------------------------------------------


def _fail_second_dump(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the second ``_dump_json`` call raise, as a full disk would."""
    real_dump = pipeline_module._dump_json
    calls: dict[str, int] = {"n": 0}

    def failing_second_dump(payload: object) -> str:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError(28, "No space left on device")
        return real_dump(payload)

    monkeypatch.setattr(pipeline_module, "_dump_json", failing_second_dump)


def test_a_failed_second_write_leaves_the_previous_index_intact(
    laws_dir: Path, index_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A disk that fills between the two writes must not corrupt the index.

    Each file was written atomically, but the *pair* was not, so a failure
    between them left chunks from the new run beside metadata describing the old
    one. Nothing on disk tied the new chunks to any source document, and a
    health check reading the metadata under-reported a real index by the size of
    the entire new corpus.
    """
    _write_multipage_pdf(laws_dir / "alpha_act.pdf", page_count=1)
    first = build_index(laws_dir, index_dir)
    assert first.chunks_written > 0

    good_chunks = (index_dir / CHUNKS_FILENAME).read_bytes()
    good_metadata = (index_dir / METADATA_FILENAME).read_bytes()

    # Grow the corpus so the second run has more to write.
    for number in range(5):
        _write_multipage_pdf(laws_dir / f"extra_act_{number}.pdf", page_count=1)

    _fail_second_dump(monkeypatch)

    with pytest.raises(OSError):
        build_index(laws_dir, index_dir)

    assert (index_dir / CHUNKS_FILENAME).read_bytes() == good_chunks, (
        "chunks.json was replaced even though the run failed"
    )
    assert (index_dir / METADATA_FILENAME).read_bytes() == good_metadata, (
        "index_metadata.json was replaced even though the run failed"
    )


def test_a_failed_write_leaves_no_temporary_files_behind(
    laws_dir: Path, index_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Staging must clean up after itself, or the next run trips over it."""
    _write_multipage_pdf(laws_dir / "alpha_act.pdf", page_count=1)

    _fail_second_dump(monkeypatch)

    with pytest.raises(OSError):
        build_index(laws_dir, index_dir)

    leftovers = sorted(path.name for path in index_dir.iterdir() if path.name.endswith(".tmp"))
    assert leftovers == [], f"temporary files left behind: {leftovers}"


# --- The "an index already exists" guard --------------------------------------


@pytest.mark.parametrize(
    "pre_existing",
    ["chunks.json.tmp", "notes.txt", "chunks.json.bak"],
    ids=["stale-tmp", "unrelated-file", "stale-backup"],
)
def test_a_stray_file_does_not_count_as_a_protected_index(
    laws_dir: Path, index_dir: Path, pre_existing: str
) -> None:
    """Only real artefacts should block a run or claim to have been preserved.

    The guard tested directory non-emptiness, so a leftover ``.tmp`` from a
    crashed run — or any unrelated file — made the CLI report that a working
    index had been left untouched when there was none, and refuse to ingest
    until the operator deleted a directory that was not theirs to worry about.
    """
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / pre_existing).write_text("unrelated", encoding="utf-8")
    _write_corrupt_pdf(laws_dir / "broken.pdf")

    # Not a "protected index", so the run is allowed to write.
    report = build_index(laws_dir, index_dir)

    assert report.documents_failed == 1
    assert (index_dir / CHUNKS_FILENAME).is_file(), (
        f"{pre_existing} was mistaken for an index, so nothing was written"
    )


def test_a_real_index_is_still_protected(laws_dir: Path, index_dir: Path) -> None:
    """The other half: the guard must still fire for an actual index.

    A fix that simply deleted the check would fail this test, which is the
    point — the protection is correct behaviour, and the stray-file case was
    only ever over-broad.
    """
    _write_multipage_pdf(laws_dir / "alpha_act.pdf", page_count=1)
    build_index(laws_dir, index_dir)
    before = (index_dir / CHUNKS_FILENAME).read_bytes()

    # Now a corpus that produces nothing.
    (laws_dir / "alpha_act.pdf").unlink()
    _write_corrupt_pdf(laws_dir / "broken.pdf")

    with pytest.raises(IndexNotWrittenError):
        build_index(laws_dir, index_dir)

    assert (index_dir / CHUNKS_FILENAME).read_bytes() == before
