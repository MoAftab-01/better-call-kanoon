"""Immutable value types describing a source statute PDF and its extracted text.

These are the plain data records that travel between the extraction layer
(:mod:`app.rag.extraction`) and the chunking/index layer
(:mod:`app.rag.chunking`, :mod:`app.rag.pipeline`). They carry no behaviour and
no I/O: constructing one performs no file access, so a value can be built in a
test, serialised by the index writer, or logged (as metadata) without dragging
PyMuPDF along.

Everything that leaves this module is a frozen dataclass. A ``PageText`` or a
``Chunk`` handed to the chunker cannot afterwards be mutated by a caller, which
is what makes chunking reproducible: same PDF bytes in, same chunks out.

``full_text`` — the join of every page's text with exactly one ``"\\n"`` — is the
single source of truth for character offsets. Downstream code maps a chunk's
``char_start``/``char_end`` back to a page by counting those separators, never by
guessing, so the join rule lives here and is documented on the field.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Separator inserted between consecutive pages in ``ExtractionResult.full_text``.
#:
#: Exactly one newline, and page text is stripped of surrounding blank lines by
#: the extractor, so a page's text always starts at
#: ``sum(len(text_j) + 1 for j < page_index)`` in the joined string.
PAGE_SEPARATOR: str = "\n"

#: A file whose text layer holds fewer non-whitespace characters than this is
#: treated as a scan (an image of a page) rather than a text PDF.
#:
#: This is the "did anything come out at all" floor, and it is deliberately the
#: lowest useful value. It exists so that a file whose text layer is entirely
#: whitespace is rejected; it is not the scan test, because a character count
#: cannot be one. See :data:`MIN_ALPHA_RUN_CHARS` for that.
MIN_TEXT_CHARS_THRESHOLD: int = 1

#: Shortest run of word-forming characters that counts as a word.
#:
#: This is the actual scan test, and it is what tells a page image apart from
#: a page of statute. A scanned page does **not** yield an empty text layer — it
#: yields page furniture: ``"- 1 -"``, a running header, a stamp, an OCR speck.
#: A four-page scan of one Act extracts the string ``"- 1 -\n- 2 -\n- 3 -\n- 4 -"``,
#: which is 20 characters and clears any threshold low enough to admit a real
#: one-page amendment. So counting characters cannot separate the two cases at
#: any threshold: lowering the bar admits short statutes but lets page numbers
#: through as law; raising it rejects genuine one-page instruments.
#:
#: What actually separates them is whether there are *words*. Statute text is
#: made of words; page furniture is not. Requiring one run of two or more
#: word-forming characters admits ``"Ab."`` — the shortest genuine stub a test
#: can produce — while rejecting ``"- 1 -"``, and it does so on a categorical
#: property rather than a tuned number.
#:
#: "Word-forming" rather than "alphabetic" because a word is not a run of
#: letters in every script. In Devanagari a syllable is a consonant plus its
#: matra, and the matra is the vowel — ``न`` alone is ``na``, ``नि`` is
#: ``ni`` — so ordinary Hindi prose contains many one-syllable words. Counting
#: letters alone would score ``"क्या कुछ हिन्दी"`` at a longest run of *one*
#: character, and a fully typed Hindi statute would be reported to the operator
#: as an image-only scan: the failure this test exists to prevent, aimed at the
#: corpus the project most needs. See :func:`app.rag.extraction._is_alpha_char`.
#: Digits are excluded, so ``"- 2023 -"`` stays furniture.
#:
#: The failure this prevents is the damaging direction: indexing ``"- 1 -"``
#: under a real ``law_id`` means a later retrieval step can present it to a user
#: as the contents of that Act. Under-reporting a short statute as unreadable is
#: a visible, fixable annoyance; fabricating the contents of a statute is not.
MIN_ALPHA_RUN_CHARS: int = 2

#: Fraction of pages that may be *entirely* Roman page numbers before the
#: extractor treats the document as a scan.
#:
#: The word test above excludes digits, so a folio printed ``- 12 -`` scores no
#: words at all. A Roman-paginated Act prints the same furniture with letters,
#: and ``- iii -`` scores a three-character word — so without this the exact
#: defect the word test exists to prevent survives for every Act that numbers
#: its pages in Roman numerals.
#:
#: Deliberately a *ratio over pages* rather than a test on any single run.
#: ``CIVIL``, ``MIX`` and ``DIV`` are not numerals, so a typed Act that happens
#: to contain one of them is unaffected; what identifies a scan is that every
#: page is a folio and none of them is a sentence. Anything below the existing
#: :data:`WORDLESS_PAGE_WARN_RATIO` would fire on a document that merely quotes
#: a Roman numeral in its text.
FOLIO_SCAN_WARN_RATIO: float = 0.20

#: Fraction of pages that may carry no text before the extractor warns.
#:
#: A warning, not a failure: mixed scan/text documents (a cover page scanned,
#: the body typed) still yield real text and are worth indexing.
EMPTY_PAGE_WARN_RATIO: float = 0.20

#: Fraction of pages that may be entirely wordless before the extractor warns.
#:
#: Separate from :data:`EMPTY_PAGE_WARN_RATIO` because a page carrying only
#: page furniture ("- 12 -") is *not* empty — it has text — but it is equally
#: useless as statute, and it should not pass unremarked.
WORDLESS_PAGE_WARN_RATIO: float = 0.20


@dataclass(frozen=True)
class SourceDocument:
    """A statute PDF found on disk, described without reading its contents.

    Identity is ``law_id``, derived from the filename stem — never from the
    text inside the file — so the same file always gets the same id and the id
    can be quoted in a report without leaking a filesystem path. Within one
    scan the id is unique: see the ``law_id`` attribute note below for why
    that is not true of the stem alone.

    Attributes:
        law_id: Identifier for this document, e.g. ``"bns_2023_1"``. Derived
            from the filename stem, and **unique across one scan**. The stem is
            normalised to ``[a-z0-9_]``, but two distinct filenames can
            normalise to the same string — ``"Alpha Act.pdf"`` and
            ``"Alpha-Act.pdf"`` both give ``"alpha_act"`` — so
            :func:`~app.rag.extraction.scan_law_pdfs` appends ``"_2"``,
            ``"_3"`` and so on to later arrivals. It stays safe to display: no
            spaces, no directory components, and never a path.
        act_name: Display name derived from the stem with any trailing
            parenthesised duplicate marker removed, e.g. ``"bns_2023"``. Falls
            back to ``law_id`` when nothing usable remains. Deliberately
            *not* de-duplicated: it is a display label, so repeated copies of
            one Act share a name and can be told apart by ``filename``.
        year: Four-digit year found in the filename stem, else ``None``. The
            stem is the only source consulted; a year is never read out of the
            document body, because a year printed on a page is not reliably the
            year of the Act.
        path: Absolute path to the PDF on disk. Internal use only — a path must
            never be interpolated into a user-facing message.
        size_bytes: Size of the file in bytes, or ``0`` when unavailable.
        sha256: Lowercase hex digest of the raw file bytes. Computed over the
            whole file, streamed in blocks. This is the provenance key for an
            index entry: it changes if the source PDF changes.
    """

    law_id: str
    act_name: str
    year: str | None
    path: Path
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class PageText:
    """The text layer of a single PDF page.

    Attributes:
        page_number: 1-based page position within the document, matching the
            numbering a reader sees in a PDF viewer.
        text: Page text after unicode NFC normalisation, per-line trailing
            whitespace removal, blank-line collapsing, and stripping of
            surrounding blank lines. Surrounding blank lines are removed so the
            page joins its neighbours with exactly one separator; text
            otherwise, including all non-ASCII characters such as Devanagari,
            is preserved unchanged.
        char_count: Length of ``text`` in characters.
    """

    page_number: int
    text: str
    char_count: int


@dataclass(frozen=True)
class ExtractionResult:
    """Everything one source PDF yielded, in page order.

    Attributes:
        document: The source the text came from.
        pages: Per-page text, in document order, starting at page 1.
        page_count: Number of pages represented in ``pages``.
        total_chars: Sum of every page's ``char_count``.
        warnings: Neutral, human-readable notes about a document that was
            usable but imperfect — typically pages with no text layer. Not
            fatal, and never a raw exception message.
        full_text: Every page's text joined with exactly one ``"\\n"`` between
            pages and in page order. This is the string chunking indexes into,
            and the string all ``char_start``/``char_end`` offsets refer to.
    """

    document: SourceDocument
    pages: tuple[PageText, ...]
    page_count: int
    total_chars: int
    warnings: tuple[str, ...]
    full_text: str


__all__ = [
    "EMPTY_PAGE_WARN_RATIO",
    "MIN_ALPHA_RUN_CHARS",
    "FOLIO_SCAN_WARN_RATIO",
    "MIN_TEXT_CHARS_THRESHOLD",
    "PAGE_SEPARATOR",
    "WORDLESS_PAGE_WARN_RATIO",
    "ExtractionResult",
    "PageText",
    "SourceDocument",
]
