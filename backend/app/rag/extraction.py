"""PyMuPDF wrapper that turns statute PDFs on disk into plain text.

This is the only module that touches ``pymupdf``. It does two jobs:

* :func:`scan_law_pdfs` — list the ``*.pdf`` files in a directory and describe
  each one (:class:`~app.rag.documents.SourceDocument`) without opening it.
* :func:`extract_document` — open one PDF and return its text layer, cleaned.

Two invariants matter more than anything else here.

**No raw exception ever reaches a caller.** A PyMuPDF failure carries the
absolute path of the file it choked on, and that string must not end up in a
report, a log line a user sees, or an API response. Every failure therefore
becomes an :class:`ExtractionError` whose message is one of a small fixed
vocabulary of neutral reasons (:data:`REASONS`). The underlying exception is
discarded (``raise ... from None``); only its *class name* is kept, for the
debug log. Where an open failure's cause is genuinely ambiguous — a corrupt
file and an encrypted file both raise — the raw message is inspected
*internally* to pick the right reason, and only the fixed reason string is
ever emitted.

**Nothing legal is ever invented.** Every string this module produces is a
mechanical derivative of the file: the ``law_id`` comes from the filename, the
year from the filename, the text from the page's text layer. No section number,
act name or heading is guessed here — not even the year is read out of the page
body, because a year printed on a page is not reliably the year of the Act.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from dataclasses import replace
from pathlib import Path

import pymupdf

from app.rag.documents import (
    EMPTY_PAGE_WARN_RATIO,
    FOLIO_SCAN_WARN_RATIO,
    MIN_ALPHA_RUN_CHARS,
    MIN_TEXT_CHARS_THRESHOLD,
    PAGE_SEPARATOR,
    WORDLESS_PAGE_WARN_RATIO,
    ExtractionResult,
    PageText,
    SourceDocument,
)

logger = logging.getLogger(__name__)

#: Size of one block read while hashing a source file, in bytes.
#:
#: A statute PDF can be hundreds of megabytes, so the digest is computed from a
#: streaming read rather than from ``path.read_bytes()``.
_HASH_BLOCK_BYTES: int = 1024 * 1024

#: A four-digit run in a filename stem, not part of a longer number.
_YEAR_PATTERN = re.compile(r"(?<!\d)(\d{4})(?!\d)")

#: A trailing parenthesised duplicate marker, e.g. the ``(1)`` in
#: ``BNS 2023 (1)``. Stripped when deriving a display name so repeated copies
#: of one Act share a name.
_DUPLICATE_MARKER_PATTERN = re.compile(r"\s*\(\s*\d+\s*\)\s*$")

#: One ASCII word character, used on the fast path in :func:`_is_id_char`.
_ASCII_WORD_CHAR = re.compile(r"\w")

#: Unicode general categories that may appear inside a ``law_id``: letters in
#: any of the four scripts, decimal and any other digits, and combining marks.
_ID_CATEGORIES: frozenset[str] = frozenset(
    {"Lu", "Ll", "Lt", "Lm", "Lo", "Nd", "No", "Mn", "Mc"}
)

#: Matches one run of characters that cannot appear inside a ``law_id``, or one
#: run of two or more underscores.
#:
#: The class is deliberately a *superset* of the rejected characters, not a
#: subset. ``\w`` cannot be used on its own because it misses combining marks —
#: the Devanagari vowel signs that carry most of a Hindi word's meaning — and a
#: *subset* class has no way to include a category the stdlib ``re`` cannot name.
#: ``re`` has no ``\p{...}``; enumerating the mark blocks of the scripts this
#: project serves is the closest a portable pattern gets, and it is not the
#: last word: :func:`_is_id_char` decides every run, so a script whose marks sit
#: outside these ranges still normalises correctly. Over-matching is free here
#: because the replacer reads the match rather than discarding it.
_NON_ID_RUN = re.compile(
    r"[^\ẁ-ͯ҃-҉֑-ֽؐ-ؚ"
    r"ً-ٰٟۖ-ۜऀ-ःऺ-ॏ"
    r"॑-ॗॢ-ॣਁ-ਃଁ-ଃ"
    r"ัิ-ฺ็-๎ཱ-྄ါ-ှ"
    r"፝-፟᪰-᫿᷀-᷿⃐-⃰︀-️]+"
    r"|_{2,}",
    re.UNICODE,
)


def _is_id_char(character: str) -> bool:
    """Return True when ``character`` belongs inside a ``law_id``.

    A ``law_id`` keeps letters, digits and combining marks in **any** script.
    Neither half of that is what a regex character class gives you:

    * An ASCII-only class erases every Devanagari codepoint, so
      ``"भारतीय संविधान"`` collapsed to the fallback ``"law"`` — the
      Constitution of India and the Bharatiya Nyaya Sanhita filed under one
      identifier and told apart only by an invented numeric suffix.
    * ``\\w`` fixes that and introduces a quieter version of the same bug.
      ``\\w`` is letters and *digits*; most Devanagari vowel signs are category
      ``Mn``, marks rather than letters, so ``"भारतीय संविधान"`` became
      ``"भ_रत_य_स_व_ध_न"`` — every matra shredded off the consonant it belongs
      to, and two statutes differing only in their vowels would collide.

    :func:`str.isidentifier` looks like the obvious tool and is the wrong one.
    Asked about a *lone* combining mark it answers ``False`` — a mark is only
    legal in an identifier in continuation position, which a one-character
    string is not — so it rejects exactly the characters it appears to promise.
    Read as a prefix instead it gives a different wrong answer, because ``\\w``
    excludes the mark: ``isidentifier`` on the stem alone would tell a Kannada
    and a Malayalam statute apart by their consonants alone.

    :func:`unicodedata.category` is the Unicode database itself, so it answers
    per character with no positional subtlety. ``Mc`` (spacing combining marks)
    is included deliberately: it covers the scripts that draw their vowels as
    separate letters — Kannada, Malayalam, Tamil, Telugu — which is most of the
    official languages of the states this project serves. Keeping a mark is safe
    because NFC has already run by the time this is called: a mark that
    survived normalisation is one that belongs where it sits.

    Args:
        character: A single character of a filename stem.

    Returns:
        True when the character may appear in a ``law_id``.
    """
    if character.isascii():
        # The common case: a statute named in English. Skips the Unicode
        # database lookup, which is the expensive part.
        return bool(_ASCII_WORD_CHAR.fullmatch(character))
    return unicodedata.category(character) in _ID_CATEGORIES


def _collapse_non_id_chars(match: re.Match[str]) -> str:
    r"""Rewrite one run of characters, keeping whatever belongs in a ``law_id``.

    Rewritten rather than substituted, for two reasons a plain ``sub("_", ...)``
    gets wrong. The pattern over-matches, so the match holds letters and marks
    that must survive — substituting one ``"_"`` for the whole run would shred
    every Hindi word the same way ``\w`` alone does. And a run of three spaces
    is one separator, not three.

    Args:
        match: A :data:`_NON_ID_RUN` match.

    Returns:
        The run with its rejected characters replaced by a single ``"_"``, in
        the position of the first of them.
    """
    parts: list[str] = []
    collapsed = False
    for character in match.group():
        if _is_id_char(character):
            parts.append(character)
        elif not collapsed:
            parts.append("_")
            collapsed = True
    return "".join(parts)



#: Fallback ``law_id`` for a stem with no alphanumeric characters at all
#: (e.g. ``"---.pdf"``). A stable constant keeps the function total and
#: idempotent; such a file is not a plausible statute, and a collision is
#: harmless because ``sha256`` still distinguishes the sources.
_FALLBACK_LAW_ID: str = "law"

# ---------------------------------------------------------------------------
# The neutral-reason vocabulary.
#
# Every :class:`ExtractionError` message is exactly one of these strings. They
# are module constants so a caller (or a test) can assert on the vocabulary
# rather than on prose, and so no code path is tempted to interpolate a path,
# a filename or an exception message into one.
# ---------------------------------------------------------------------------

#: The file could not be opened at all: not a PDF, truncated, or corrupt.
REASON_OPEN_FAILED: str = "file could not be opened (corrupt or not a PDF)"

#: The PDF is encrypted and PyMuPDF has no password for it.
REASON_ENCRYPTED: str = "file is encrypted and needs a password"

#: The file opened and has pages, but effectively no text — it is a scan.
REASON_NO_TEXT: str = "file contains no extractable text (it may be a scan)"

#: The file opened but reports zero pages.
REASON_NO_PAGES: str = "file contains no pages"

#: The file opened but its text layer could not be read.
REASON_TEXT_READ_FAILED: str = "file text could not be read"

#: Every neutral reason this module can produce, for callers that want to
#: assert a message came from the fixed vocabulary rather than from an
#: exception.
REASONS: frozenset[str] = frozenset(
    {
        REASON_OPEN_FAILED,
        REASON_ENCRYPTED,
        REASON_NO_TEXT,
        REASON_NO_PAGES,
        REASON_TEXT_READ_FAILED,
    }
)

# Substrings that identify an encrypted PDF in a PyMuPDF message. Used only to
# choose between two fixed reasons; the message itself is never emitted.
_ENCRYPTION_MARKERS: tuple[str, ...] = ("encrypt", "password")


class ExtractionError(RuntimeError):
    """Raised when a PDF cannot yield usable text.

    The message is always a NEUTRAL reason string drawn from :data:`REASONS`
    and is safe to record in a report or show a user: it names the *category*
    of problem and never the file path, the filename, the library version or
    the text of the underlying exception.

    Catch this — not :class:`RuntimeError`, not a bare ``Exception`` — to treat
    one unreadable document as a failed document. :func:`scan_law_pdfs` and
    :func:`extract_document` guarantee that no ``pymupdf`` exception escapes,
    so this is the only exception type extraction raises for a bad file.
    """


def normalise_law_id(stem: str) -> str:
    """Turn a filename stem into a stable, path-free identifier.

    Lowercases the stem, replaces every run of non-alphanumeric characters with
    a single ``"_"``, and strips leading and trailing underscores. So
    ``"BNS 2023 (1)"`` becomes ``"bns_2023_1"`` and ``"../Indian Penal Code"``
    becomes ``"indian_penal_code"``.

    Letters, digits and combining marks of **any** script are kept. This is
    not a nicety: the project's own corpus is bilingual, and an ASCII-only rule
    maps ``"भारतीय संविधान"`` to nothing at all, so the Constitution of India
    and the Bharatiya Nyaya Sanhita would both be filed under the fallback
    ``"law"`` and told apart only by an invented numeric suffix. Losing a
    statute's identity is exactly the failure this project must not have. Marks
    are kept alongside letters because Devanagari writes its vowels *into* its
    consonants — see :func:`_is_id_char`.

    The operation is idempotent — ``normalise_law_id(normalise_law_id(x))``
    always equals ``normalise_law_id(x)`` — because the output contains only
    lowercase letters, digits, marks and interior underscores, all of which the
    rule maps to themselves. It never returns an empty string: a stem with no
    such characters yields :data:`_FALLBACK_LAW_ID`.

    Args:
        stem: A filename stem, with or without its ``.pdf`` suffix.

    Returns:
        A non-empty identifier containing only letters, digits, combining marks
        and underscores, in any script, with no leading or trailing underscore.
    """
    lowered = unicodedata.normalize("NFC", stem).lower()
    collapsed = _NON_ID_RUN.sub(_collapse_non_id_chars, lowered).strip("_")
    return collapsed or _FALLBACK_LAW_ID


def _derive_act_name(stem: str) -> str:
    """Derive a display name for a document from its filename stem.

    Removes any trailing parenthesised duplicate marker (``"(1)"``) so that
    several copies of one Act share a name, then normalises the remainder the
    same way :func:`normalise_law_id` does.

    ``"BNS 2023 (1)"`` yields ``"bns_2023"``. Falls back to
    :func:`normalise_law_id` of the raw stem when stripping the marker leaves
    nothing behind.

    Args:
        stem: A filename stem.

    Returns:
        A non-empty display name.
    """
    without_marker = _DUPLICATE_MARKER_PATTERN.sub("", unicodedata.normalize("NFC", stem))
    return normalise_law_id(without_marker) or normalise_law_id(stem)


def _derive_year(stem: str) -> str | None:
    """Return the first four-digit year in a filename stem, or ``None``.

    Only the filename is consulted. A year is deliberately *not* read out of
    the page body: a year printed inside a document is a printing or amendment
    year and is not reliably the year of the Act, so trusting it would put an
    unverified claim into the index.

    Args:
        stem: A filename stem.

    Returns:
        The four-digit year as a string, or ``None`` when the stem has none.
    """
    match = _YEAR_PATTERN.search(stem)
    return match.group(1) if match else None


def _sha256_of_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of a file's raw bytes.

    Streamed in :data:`_HASH_BLOCK_BYTES` blocks: the whole file is never held
    in memory, so a large scanned statute costs one block of RAM.

    Args:
        path: File to digest.

    Returns:
        The 64-character lowercase hex digest.

    Raises:
        OSError: If the file cannot be read.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_HASH_BLOCK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def _describe_pdf(path: Path) -> SourceDocument | None:
    """Build a :class:`SourceDocument` for one PDF, or ``None`` to skip it.

    The file is stat-ed and hashed but never opened — this is the cheap pass
    that lets an operator see what is on disk before anything is parsed.

    A **zero-byte** file is described, not skipped. It is the signature of an
    interrupted download, and an operator whose corpus silently lost three Acts
    to truncated transfers has been given no signal at all: dropping the file
    here meant it appeared in no counter, no failure list and no exit code, so
    a run over two good files and two empty ones reported
    ``documents_found=1, documents_failed=0`` and exited ``0``. Describing it
    hands the file to :func:`extract_document`, which fails it for the reason it
    deserves and surfaces it in the failure list like any other bad document.

    A file that vanishes or becomes unreadable between listing and stat-ing is
    still skipped, with a debug log — there the thing on disk genuinely is not
    a document, and there is nothing useful to report.

    Args:
        path: Path to a candidate ``*.pdf`` file.

    Returns:
        A populated :class:`SourceDocument`, or ``None`` when the file should be
        omitted from the scan.
    """
    try:
        size_bytes = path.stat().st_size
    except OSError:
        logger.debug("Skipping law file that could not be stat-ed: %s (%s)", path.name, "OSError")
        return None

    try:
        digest = _sha256_of_file(path)
    except OSError:
        logger.debug("Skipping law file that could not be read: %s (%s)", path.name, "OSError")
        return None

    stem = path.stem
    return SourceDocument(
        law_id=normalise_law_id(stem),
        act_name=_derive_act_name(stem),
        year=_derive_year(stem),
        path=path.resolve(),
        size_bytes=size_bytes,
        sha256=digest,
    )


def _make_law_id_unique(document: SourceDocument, taken: set[str]) -> SourceDocument:
    """Return ``document`` with a ``law_id`` not already in ``taken``.

    Normalisation is many-to-one, so distinct filenames routinely collide:
    ``"Alpha Act.pdf"``, ``"Alpha-Act.pdf"`` and ``"alpha_act.PDF"`` all
    normalise to ``"alpha_act"``. Without this, three documents would share one
    id, every ``chunk_id`` derived from it would be minted twice, and
    ``index_metadata.json`` would report the same chunk count under three
    entries. A retrieval index whose keys are not unique is not an index.

    The suffix is a counter starting at ``2`` and increasing in scan order, so
    the result is deterministic for a given directory. It is appended to the
    id alone — never to ``act_name``, which stays the shared display label —
    and ``sha256`` still records the true provenance of each file.

    Args:
        document: The document whose id may collide.
        taken: Law ids already assigned in this scan; not mutated.

    Returns:
        ``document`` unchanged when its id is free, otherwise a copy carrying
        the first free ``"<id>_N"``.
    """
    if document.law_id not in taken:
        return document
    suffix = 2
    while f"{document.law_id}_{suffix}" in taken:
        suffix += 1
    logger.warning(
        "Law id %r already taken by an earlier file; using %r for %s.",
        document.law_id,
        f"{document.law_id}_{suffix}",
        document.path.name,
    )
    return replace(document, law_id=f"{document.law_id}_{suffix}")


def scan_law_pdfs(laws_dir: Path) -> tuple[SourceDocument, ...]:
    """Describe every statute PDF sitting directly in ``laws_dir``.

    Non-recursive: subdirectories are ignored, so an operator who points the
    ingester at ``data/`` instead of ``data/laws/`` gets an honest empty result
    rather than a surprise crawl. Only ``*.pdf`` is considered, matched
    case-insensitively so ``.PDF`` files are not silently dropped.

    Missing, empty or non-existent directories are not errors — this function
    returns ``()``. Deciding whether an empty laws directory is a *failure* is
    the CLI's job, not the scanner's.

    Results are sorted by filename, lowercased first so the order is the same
    whether the filesystem is case-sensitive or not, which is what makes a
    generated index byte-for-byte reproducible. That sort also decides who
    wins a law-id collision, so the suffixes are stable across runs.

    Args:
        laws_dir: Directory to scan. Not required to exist.

    Returns:
        A tuple of :class:`~app.rag.documents.SourceDocument` values in a
        deterministic order, with unique ``law_id`` values; empty when there
        is nothing to ingest.
    """
    try:
        entries = sorted(laws_dir.iterdir(), key=lambda item: (item.name.lower(), item.name))
    except OSError:
        logger.debug("Laws directory not readable; treating as empty: %s", laws_dir.name)
        return ()

    documents: list[SourceDocument] = []
    taken: set[str] = set()
    for entry in entries:
        try:
            if not entry.is_file() or entry.suffix.lower() != ".pdf":
                continue
        except OSError:
            continue
        document = _describe_pdf(entry)
        if document is None:
            continue
        document = _make_law_id_unique(document, taken)
        taken.add(document.law_id)
        documents.append(document)

    return tuple(documents)


def _blanks_for_run(run_length: int) -> list[str]:
    """Return the blank lines that stand for a run of ``run_length`` blanks.

    Args:
        run_length: How many consecutive blank lines the source had.

    Returns:
        A single empty string for any run of three or more (collapsed), one per
        blank line for a shorter run, and nothing for a run of zero.
    """
    if run_length <= 0:
        return []
    return [""] if run_length >= 3 else [""] * run_length


def _clean_page_text(raw_text: str) -> str:
    """Normalise one page's raw text layer.

    Four steps, in this order:

    1. **NFC** unicode normalisation, so Devanagari text from a Hindi statute
       PDF survives chunking unchanged instead of drifting into decomposed
       forms. No character is ever dropped as "non-ASCII".
    2. Line endings flattened to ``"\\n"`` — a PDF text layer mixes CR, LF and
       CRLF freely.
    3. Trailing whitespace stripped from each line (leading indentation is
       left alone; it can be meaningful in a table).
    4. Blank-line runs collapsed: a run of **three or more** blank lines becomes
       exactly one blank line. Runs of one or two blank lines are left as they
       are, since a single blank line is a paragraph break and two are a
       section break worth preserving.

    Leading and trailing blank lines are then removed. That is what makes the
    ``"\\n"`` join in :attr:`~app.rag.documents.ExtractionResult.full_text`
    predictable: page *n* starts at a known offset, so a chunk's character
    range maps back to a page by arithmetic rather than by guesswork.

    Args:
        raw_text: Text exactly as PyMuPDF returned it.

    Returns:
        The cleaned page text, possibly empty.
    """
    text = unicodedata.normalize("NFC", raw_text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]

    # Blank lines are buffered rather than emitted one by one, because whether
    # a run is squashed depends on how long it turns out to be: a run of 3 or
    # more collapses to exactly one blank line, while runs of 1 or 2 survive
    # (one is a paragraph break, two are a section break).
    cleaned: list[str] = []
    pending_blanks = 0
    for line in lines:
        if line:
            cleaned.extend(_blanks_for_run(pending_blanks))
            pending_blanks = 0
            cleaned.append(line)
        else:
            pending_blanks += 1
    cleaned.extend(_blanks_for_run(pending_blanks))

    while cleaned and not cleaned[0]:
        cleaned.pop(0)
    while cleaned and not cleaned[-1]:
        cleaned.pop()
    return "\n".join(cleaned)


def _open_document(path: Path) -> pymupdf.Document:
    """Open a PDF, translating every failure into an :class:`ExtractionError`.

    Encryption is checked twice because MuPDF signals it in two different
    ways: some encrypted files open successfully and report
    ``needs_pass``/``is_encrypted``, while others refuse to open at all. In
    the refusal case the exception message is matched against
    :data:`_ENCRYPTION_MARKERS` to choose between :data:`REASON_ENCRYPTED` and
    :data:`REASON_OPEN_FAILED`. The message itself is discarded — only one of
    the two fixed strings is ever raised.

    Args:
        path: PDF to open.

    Returns:
        An open :class:`pymupdf.Document`; the caller closes it.

    Raises:
        ExtractionError: If the file is missing, unreadable, corrupt, not a
            PDF, or encrypted.
    """
    try:
        document = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001 - deliberately broad; see docstring
        reason = REASON_OPEN_FAILED
        if any(marker in str(exc).lower() for marker in _ENCRYPTION_MARKERS):
            reason = REASON_ENCRYPTED
        logger.debug("PyMuPDF could not open %s: %s", path.name, type(exc).__name__)
        raise ExtractionError(reason) from None

    try:
        if bool(getattr(document, "needs_pass", False)) or bool(
            getattr(document, "is_encrypted", False)
        ):
            raise ExtractionError(REASON_ENCRYPTED)
    except ExtractionError:
        document.close()
        raise
    return document


def _page_count(document: pymupdf.Document) -> int:
    """Return a document's page count, treating any failure as zero pages.

    Args:
        document: An open PDF.

    Returns:
        The number of pages, or ``0`` when it cannot be determined.
    """
    try:
        return max(0, int(document.page_count))
    except Exception:  # noqa: BLE001 - a bad file must not crash the scan
        return 0


#: Longest page-number list a warning will spell out before it switches to a
#: count only. Beyond this the list is noise; "14 pages could not be read" is
#: the useful half of the sentence.
_MAX_LISTED_PAGES: int = 10


def _summarise_page_numbers(numbers: tuple[int, ...]) -> str:
    """Render 1-based page numbers compactly, collapsing long runs.

    ``(3,)`` renders ``"3"``; ``(1, 2, 3)`` renders ``"1-3"``; a list longer
    than :data:`_MAX_LISTED_PAGES` renders as a count with the first few named.

    Args:
        numbers: Ascending, non-empty tuple of 1-based page numbers.

    Returns:
        A short human-readable description of the pages.
    """
    if len(numbers) > _MAX_LISTED_PAGES:
        head = ", ".join(str(number) for number in numbers[:3])
        return f"{head} and {len(numbers) - 3} more"
    if len(numbers) == 1:
        return str(numbers[0])

    # Collapse consecutive runs into "start-end"; anything else is listed.
    ranges: list[str] = []
    start = previous = numbers[0]
    for number in numbers[1:]:
        if number == previous + 1:
            previous = number
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = number
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ", ".join(ranges)


#: Unicode general categories counted as part of a *word*: letters of any script
#: plus combining marks.
#:
#: Separate from :data:`_ID_CATEGORIES` because the two answer different
#: questions, and the difference is load-bearing. Digits belong in a
#: ``law_id`` — ``"bns_2023"`` is how an Act is named — but a digit is not a
#: word, and admitting them here would let a page folio like ``"- 2023 -"``
#: read as a four-letter word and walk straight through the scan test.
_ALPHA_CATEGORIES: frozenset[str] = frozenset(
    {"Lu", "Ll", "Lt", "Lm", "Lo", "Mn", "Mc"}
)


def _is_alpha_char(character: str) -> bool:
    """Return True when ``character`` is part of a word, in any script.

    The mark categories are the reason this is not :meth:`str.isalpha`. An
    Indic vowel sign is not a letter in the Unicode sense — most are ``Mc`` or
    ``Mn`` — but it is very much part of the word it sits inside, and
    :meth:`str.isalpha` answers ``False`` for every one of them.

    That is not a cosmetic difference here, and it is worth being exact about
    why. A Devanagari syllable is a consonant plus its matra, and a matra is
    the vowel: ``न`` alone is ``na`` while ``नि`` is ``ni``. Counting letters
    only therefore measures syllables that carry a written vowel, so ordinary
    Hindi short words collapse. ``"क्या कुछ हिन्दी"`` — entirely ordinary prose
    — scored a longest run of **one** character, below
    :data:`~app.rag.documents.MIN_ALPHA_RUN_CHARS`, and so was reported to the
    operator as an image-only scan. The test meant to catch scans was rejecting
    typed Hindi statutes instead, in proportion to how short their words were.

    :func:`unicodedata.combining` is the tempting shortcut and is wrong for this
    purpose: it reports the *canonical combining class*, which is zero for 140
    mark characters across Devanagari, Bengali, Gujarati, Tamil, Kannada,
    Telugu, Malayalam and Sinhala — precisely the scripts whose marks carry the
    vowel. The general category is the reliable primitive, and the module
    already depends on it for :func:`_is_id_char`.

    Args:
        character: A single character of page text.

    Returns:
        True when the character is a letter or a combining mark.
    """
    if character.isascii():
        # Fast path: skips the Unicode database lookup, which dominates the
        # cost of scanning a 300-page Act.
        return character.isalpha()
    return unicodedata.category(character) in _ALPHA_CATEGORIES


#: Largest value the canonical Roman notation below will represent.
#:
#: Bounds :func:`_is_roman_numeral` to the notation that actually appears in a
#: folio. Beyond 3999 Roman numerals stop being the page-numbering scheme of a
#: printed Act and start being arithmetic, and a run long enough to exceed it is
#: prose by definition.
_MAX_ROMAN_NUMERAL: int = 3999

#: Roman numeral symbols and their values.
_ROMAN_VALUES: dict[str, int] = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

#: The six subtractive pairs, largest value first, in the order the canonical
#: renderer below consumes them.
_ROMAN_TABLE: tuple[tuple[int, str], ...] = (
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
)


def _canonical_roman(value: int) -> str:
    """Render a non-negative integer in canonical Roman notation."""
    rendered: list[str] = []
    for amount, numeral in _ROMAN_TABLE:
        while value >= amount:
            rendered.append(numeral)
            value -= amount
    return "".join(rendered)


def _is_roman_numeral(run: str) -> bool:
    r"""Return True when ``run`` is a Roman page number.

    The scan test excludes digits, so a folio printed ``- 12 -`` scores no
    words and the document is correctly rejected as a scan. A Roman-paginated
    Act prints the same furniture with letters instead — ``- iii -`` — and
    that scores a three-character *word*, walking straight through the word
    test and into the index under a real ``law_id``.

    The test is canonical rather than a character-set test, and that
    distinction is the whole safety of it. ``IVXLCDM`` alone would reject
    **civil** — every character of it is in that set — and "civil court" is
    among the commonest phrases in Indian legal text. Re-rendering the parsed
    value and demanding it match the input rejects ``CIVIL`` (which is not a
    numeral) while admitting ``XII``, so the ordinary word survives and the
    folio does not.

    Case is normalised first, because a folio is as likely to be printed ``iii``
    as ``III`` and a test that only knew the upper case would reject every
    genuine folio while letting ``DC`` through.

    Args:
        run: A single run from :func:`_alpha_runs`.

    Returns:
        True when ``run`` is a canonical Roman numeral of at most
        :data:`_MAX_ROMAN_NUMERAL`, in either case.
    """
    if not run:
        return False
    folded = run.upper()
    # Every character, not just the first. A run like "ILLEGAL" starts with a
    # legal numeral symbol and is not a numeral; checking only the opening
    # character would let the lookup below raise KeyError on real statute text,
    # which is the one thing the extractor's no-raw-exception invariant forbids.
    if not all(symbol in _ROMAN_VALUES for symbol in folded):
        return False
    # Walk left to right, pairing a symbol with the one after it whenever that
    # one is larger, which is exactly what makes the six subtractive pairs.
    total = 0
    index = 0
    while index < len(folded):
        value = _ROMAN_VALUES[folded[index]]
        following = _ROMAN_VALUES.get(folded[index + 1]) if index + 1 < len(folded) else None
        if following is not None and following > value:
            total += following - value
            index += 2
        else:
            total += value
            index += 1
    return 0 < total <= _MAX_ROMAN_NUMERAL and _canonical_roman(total) == folded


def _folio_page_count(pages: tuple[PageText, ...]) -> int:
    """Count pages whose every word is a Roman page number.

    A page of ``- iii -`` passes :func:`_alpha_runs`, because "iii" is three
    letters, so the word test is not enough on its own and this is what closes
    the gap. The deciding property is not the shape of one run but that a scan
    puts *nothing but* folios on every page — so the count is over pages, and
    a single stray Roman page inside a typed Act cannot reach the threshold
    that a wholly scanned one does.

    Args:
        pages: Pages already extracted.

    Returns:
        The number of pages carrying at least one word and nothing but Roman
        page numbers.
    """
    folios = 0
    for page in pages:
        runs = _alpha_runs(page.text)
        if runs and all(_is_roman_numeral(run) for run in runs):
            folios += 1
    return folios


def _alpha_runs(text: str) -> tuple[str, ...]:
    r"""Return the runs of word-forming characters in ``text``, in any script.

    A character class cannot do this correctly. ``[^\W\d_]`` reads like
    "alphabetic" and holds for Latin, but ``\w`` is an approximation of
    ``\p{L}`` that quietly fails elsewhere — and here the failure is worse than
    a mangled filename. A fully typed Devanagari statute contains no ASCII word
    character at all, so the scan test scores it zero and reports a real
    statute as an image-only scan: the exact failure the scan test exists to
    prevent, aimed at the corpus this project most needs. The stdlib has no
    ``\p{...}``, so the question is asked per character instead.

    Combining marks continue a run but never start one, so a Devanagari word
    stays one run rather than splitting at every matra, and a stray mark
    between two words does not join them.

    Args:
        text: Page text, already cleaned.

    Returns:
        Each maximal run of letters and marks, in order.
    """
    runs: list[str] = []
    current: list[str] = []
    for character in text:
        if not _is_alpha_char(character):
            if current:
                runs.append("".join(current))
                current = []
            continue
        # A mark cannot open a word, so a run that has not started yet stays
        # unstarted; it attaches to the consonant it follows.
        if character.isalpha() or current:
            current.append(character)
    if current:
        runs.append("".join(current))
    return tuple(runs)


def _longest_alpha_run(pages: tuple[PageText, ...]) -> int:
    """Return the length of the longest run of alphabetic characters.

    Args:
        pages: Pages already extracted.

    Returns:
        The longest word-like run across all pages, or ``0`` when the text
        holds no letters at all.
    """
    return max(
        (len(run) for page in pages for run in _alpha_runs(page.text)),
        default=0,
    )


def _wordless_page_warning(pages: tuple[PageText, ...]) -> str | None:
    """Warn when many pages carry text but no words.

    A page of ``"- 12 -"`` is not empty, so :func:`_empty_page_warning` stays
    quiet about it. It is also worthless as statute, and a document made
    mostly of such pages is a scan that slipped through the word test because
    one cover page happened to carry a title.

    The message carries counts only, never the content of a page.

    Args:
        pages: Pages already extracted.

    Returns:
        A neutral warning string, or ``None`` when nothing is worth saying.
    """
    if not pages:
        return None
    wordless = sum(1 for page in pages if not _alpha_runs(page.text))
    if wordless / len(pages) > WORDLESS_PAGE_WARN_RATIO:
        return (
            f"{wordless} of {len(pages)} pages carry no words; this document "
            "may be an image-only scan."
        )
    return None


def _read_pages(
    document: pymupdf.Document, page_count: int
) -> tuple[tuple[PageText, ...], tuple[int, ...]]:
    """Extract and clean the text of every page, in order.

    A page whose text layer cannot be read is recorded as **empty** and the read
    continues. The alternative — abandoning the document — throws away every
    page that read perfectly well, and one corrupt content stream in the middle
    of a 300-page Act would silently remove that Act from the index entirely.
    The unreadable pages are not hidden: their page numbers are returned so the
    caller can warn about exactly how much text is missing.

    Args:
        document: An open PDF.
        page_count: Number of pages to read.

    Returns:
        ``(pages, unreadable)`` where ``pages`` is one
        :class:`~app.rag.documents.PageText` per page, numbered 1-based, with an
        unreadable page appearing as empty text; and ``unreadable`` is the
        1-based page numbers whose text layer could not be read.
    """
    pages: list[PageText] = []
    unreadable: list[int] = []
    for index in range(page_count):
        try:
            raw_text = document[index].get_text()
        except Exception:  # noqa: BLE001 - a bad page must not crash the run
            # Deliberately broad: PyMuPDF raises several unrelated types here
            # (RuntimeError on a broken content stream, ValueError on a bad
            # index), and one unreadable page is not a reason to lose the rest.
            logger.debug("Text layer unreadable on page %d", index + 1)
            unreadable.append(index + 1)
            pages.append(PageText(page_number=index + 1, text="", char_count=0))
            continue
        text = _clean_page_text(raw_text or "")
        pages.append(PageText(page_number=index + 1, text=text, char_count=len(text)))
    return tuple(pages), tuple(unreadable)


def _empty_page_warning(pages: tuple[PageText, ...]) -> str | None:
    """Warn when a document has suspiciously many pages with no text layer.

    This is the signature of a mixed scan/text PDF — a scanned cover, a typed
    body — which is still worth indexing, so it warns and carries on.

    The message carries counts only, never the title or content of a page.

    Args:
        pages: Pages already extracted.

    Returns:
        A neutral warning string, or ``None`` when nothing is worth saying.
    """
    if not pages:
        return None
    empty = sum(1 for page in pages if not page.text.strip())
    if empty / len(pages) > EMPTY_PAGE_WARN_RATIO:
        return (
            f"{empty} of {len(pages)} pages have no text layer; "
            "this document may be partly scanned."
        )
    return None


def extract_document(document: SourceDocument) -> ExtractionResult:
    """Extract the text layer of one statute PDF.

    Opening, reading and closing the file are all handled here; the caller
    never touches PyMuPDF. The document is closed in a ``finally`` block, so a
    failure mid-read cannot leave a file handle open on Windows.

    Three conditions are fatal, each reported as a neutral
    :class:`ExtractionError` reason:

    * **No pages** — the file opened but is empty.
    * **Every page unreadable** — the file opened and has pages, but not one
      text layer could be read. There is nothing to index, so this is an error
      rather than an empty success.
    * **No usable text** — no non-whitespace characters anywhere in the text
      layer. This catches the common case of a genuine scan, where the pages
      are images and the text layer holds nothing at all. Ingesting that would
      put stray glyph codes into the index as though they were statute text.

    A document that reads *partially* is not fatal, and this is the common case
    for a real corpus: a mixed scan, a truncated download, one corrupt content
    stream in a 300-page Act. Every page that did read is kept, and warnings are
    recorded for the pages that did not — naming how many, and which, so the
    operator can tell a two-page gap from a missing statute. Discarding a whole
    Act because page 47 is corrupt would be the larger loss.

    Args:
        document: A source document as returned by :func:`scan_law_pdfs`.

    Returns:
        An :class:`~app.rag.documents.ExtractionResult` whose ``full_text``
        joins the pages with exactly one ``"\\n"`` each, in page order.

    Raises:
        ExtractionError: If the file cannot be opened, is encrypted, has no
            pages, has no extractable text, or no page's text layer could be
            read. The message is always one of :data:`REASONS`.
    """
    pdf = _open_document(document.path)
    try:
        page_count = _page_count(pdf)
        if page_count == 0:
            raise ExtractionError(REASON_NO_PAGES)

        pages, unreadable = _read_pages(pdf, page_count)
    finally:
        pdf.close()

    if not pages:
        # No pages were walked at all. There is no partial result worth keeping.
        raise ExtractionError(REASON_TEXT_READ_FAILED)

    if len(unreadable) == len(pages):
        # Every page *was* walked and every one of them failed. Also fatal, but
        # it needs its own reason: letting this fall through to the character
        # count below would report "no extractable text (it may be a scan)",
        # sending the operator off to re-OCR a PDF whose text layer is
        # perfectly present and merely unreadable. The file is damaged; the
        # scanner will not fix it.
        raise ExtractionError(REASON_TEXT_READ_FAILED)

    usable_chars = sum(len("".join(page.text.split())) for page in pages)
    if usable_chars < MIN_TEXT_CHARS_THRESHOLD:
        raise ExtractionError(REASON_NO_TEXT)

    if _longest_alpha_run(pages) < MIN_ALPHA_RUN_CHARS:
        # Characters came out, but no *word* did. This is a scan carrying page
        # furniture, not a statute: the only text is running heads and page
        # numbers. Indexing it would put "- 1 -" into the index under a real
        # law_id, and a later step would have no way to tell that apart from
        # the Act's actual wording.
        raise ExtractionError(REASON_NO_TEXT)

    folios = _folio_page_count(pages)
    if folios > len(pages) * FOLIO_SCAN_WARN_RATIO:
        # A Roman-paginated Act is furniture written with letters rather than
        # digits, so it clears the word test above on "iii" and reaches here.
        # Checking every page rather than any single run is what makes this
        # safe: "civil", "mix" and "civil" are not numerals and still count as
        # words, so a typed Act with a Roman numeral somewhere in it is
        # untouched.
        raise ExtractionError(REASON_NO_TEXT)

    warnings: list[str] = []
    wordless_warning = _wordless_page_warning(pages)
    if wordless_warning:
        warnings.append(wordless_warning)
        logger.info("Mostly wordless text layer in %s: %s", document.law_id, wordless_warning)
    if unreadable:
        warning = (
            f"{len(unreadable)} of {len(pages)} pages could not be read "
            f"(page{'' if len(unreadable) == 1 else 's'} "
            f"{_summarise_page_numbers(unreadable)}); their text is missing from "
            "this index."
        )
        warnings.append(warning)
        logger.info("Partial text layer in %s: %s", document.law_id, warning)
    empty_warning = _empty_page_warning(pages)
    if empty_warning:
        warnings.append(empty_warning)
        logger.info("Partial text layer in %s: %s", document.law_id, empty_warning)

    full_text = PAGE_SEPARATOR.join(page.text for page in pages)
    return ExtractionResult(
        document=document,
        pages=pages,
        page_count=len(pages),
        total_chars=sum(page.char_count for page in pages),
        warnings=tuple(warnings),
        full_text=full_text,
    )


__all__ = [
    "REASONS",
    "REASON_ENCRYPTED",
    "REASON_NO_PAGES",
    "REASON_NO_TEXT",
    "REASON_OPEN_FAILED",
    "REASON_TEXT_READ_FAILED",
    "ExtractionError",
    "extract_document",
    "normalise_law_id",
    "scan_law_pdfs",
]
