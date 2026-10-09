"""Legal-text-aware segmentation of extracted statute text into retrievable chunks.

The segmenter is deliberately conservative about where a chunk may begin and
end, because two provisions of a statute are two distinct legal statements and a
retrieval chunk that blended both would answer a question with a blend nobody
wrote. Two kinds of boundary are therefore hard:

* a detected section heading, and
* a page boundary.

Text never crosses either. A chunk that spans two sections would let a model
attribute one provision's words to another; a chunk that spans two pages would
make "page 2" in a citation a range rather than a place. Both are avoided by
construction rather than by a post-hoc repair.

Inside a page-aligned section the text is split on paragraph breaks first, then
sentence boundaries, then a hard character cut, and consecutive pieces overlap
slightly so a provision split across a boundary is still retrievable from either
side.

Two floors keep retrieval clean. A chunk shorter than ``min_chars`` is merged
into a neighbour rather than emitted, because a three-word "chunk" matches almost
any query and floods retrieval with noise. Whitespace-only fragments are dropped
outright, since they carry nothing at all.

Section detection is a HEURISTIC for navigation only. ``section_label`` is
always a string that literally occurs in the source PDF text (enforced by an
explicit check in :func:`detect_section_labels`), because the one unforgivable
error in a legal-information tool is inventing a section number that does not
exist. But "the label is verbatim" is not the same as "the label is the right
citation": a numbered list item reads exactly like a heading, and a cross
reference reads exactly like a label. Both are recorded with the method that
found them, and citation normalisation happens downstream (Stage 8) where a real
citation resolver can check the number against the act.

This module is pure. It reads no files, writes none, logs nothing, touches no
clock and no randomness, and mutates no global state: the same
:class:`ExtractionResult` always yields byte-identical chunks.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass

from app.rag.documents import PAGE_SEPARATOR, ExtractionResult

__all__ = [
    "Chunk",
    "ChunkingConfig",
    "chunk_document",
    "detect_section_labels",
]


# ---------------------------------------------------------------------------
# Section-label detection
# ---------------------------------------------------------------------------

#: A line that *starts* with a section number: "420. Cheating by personation."
#:
#: The label is reported as the number *with its trailing dot* — "420." — because
#: the dot is what makes the match unambiguous (it is what distinguishes a
#: heading from a bare page number or a decimal), and because the heading's
#: trailing title depends on line wrapping in the source PDF, so including it
#: would make labels unstable across extractions of the same act.
#:
#: The dot must be followed by whitespace and a further character, and up to 8
#: leading spaces are tolerated because justified two-column layouts indent
#: headings. A number further in than that is prose, not a heading.
#:
#: This pattern cannot tell a heading from a numbered list item — both look like
#: "420. Something". Resolving that needs a citation resolver, not a regular
#: expression, so the match is reported with the "heading" method and the caller
#: decides how much to trust it.
_HEADING_RE: re.Pattern[str] = re.compile(
    r"^[ \t]{0,8}(?P<label>\d{1,6}[A-Za-z]{0,3}(?:-\d{1,6}[A-Za-z]{0,3})*\.)[ \t]+\S",
    re.MULTILINE,
)

#: A section number mentioned mid-line: "as referred to in Section 420".
#:
#: The reported label is the whole match ("Section 420"), taken verbatim from
#: the source including whatever capitalisation the PDF used.
_INLINE_RE: re.Pattern[str] = re.compile(
    r"\b[Ss]ection[ \t]+(?P<number>\d{1,6}[A-Za-z]{0,3})",
)

#: Detection methods recorded on a :class:`Chunk`.
METHOD_HEADING: str = "heading"
METHOD_INLINE: str = "inline"
METHOD_NONE: str = "none"


# ---------------------------------------------------------------------------
# Splitting primitives
# ---------------------------------------------------------------------------

#: Two or more newlines: the paragraph break the extractor leaves behind.
_PARAGRAPH_BREAK_RE: re.Pattern[str] = re.compile(r"\n[ \t]*\n+")

#: End of a sentence. Closing quotes and brackets stay with the sentence, and
#: the terminator itself is kept, so a chunk never loses its full stop.
_SENTENCE_END_RE: re.Pattern[str] = re.compile(r"[.!?]+[\"'’”)\]]*(?=[ \t]|\Z)")

#: Any run of horizontal whitespace: the preferred place to make a hard cut.
_HORIZONTAL_SPACE_RE: re.Pattern[str] = re.compile(r"[ \t]+")


# ---------------------------------------------------------------------------
# Public value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChunkingConfig:
    """Tuning for :func:`chunk_document`.

    Attributes:
        target_chars: Soft ceiling on the characters in one chunk, overlap
            included. Text inside a page-aligned section is split to stay
            within it; a hard cut lands on the last space inside the window so
            words stay whole.
        overlap_chars: Characters of the previous chunk repeated at the head of
            the next one, so a provision split across a boundary is still
            retrievable from either side. Never applied across a page or section
            boundary, and clamped so at least ``min_chars`` of new text remains.
        min_chars: Hard floor. A chunk shorter than this is merged into a
            neighbour instead of being emitted. Chunks below the floor match
            almost any query and are pure retrieval noise.
    """

    target_chars: int = 900
    overlap_chars: int = 120
    min_chars: int = 120


@dataclass(frozen=True)
class Chunk:
    """One retrievable slice of a single statute, confined to one page run.

    Attributes:
        chunk_id: Stable identifier, ``"{law_id}::{chunk_index:06d}"``.
        law_id: Identifier of the source document.
        chunk_index: 0-based position of this chunk within its document.
        text: The chunk body. Always exactly ``full_text[char_start:char_end]``
            of the source, so the offsets and the text can never disagree.
        page_start: First page the chunk touches, as printed on the page.
        page_end: Last page the chunk touches. Equal to ``page_start`` unless
            the ``min_chars`` floor forced a merge across a page boundary.
        char_start: Start offset into ``ExtractionResult.full_text``.
        char_end: End offset (exclusive) into ``ExtractionResult.full_text``.
        section_label: A section marker that literally occurs in the source
            text, or ``None`` in front matter or in text with no detected
            marker.
        section_detection: How the label was found — ``"heading"``, ``"inline"``
            or ``"none"``. A heuristic hint for navigation, never a verified
            citation.
    """

    chunk_id: str
    law_id: str
    chunk_index: int
    text: str
    page_start: int
    page_end: int
    char_start: int
    char_end: int
    section_label: str | None
    section_detection: str


# ---------------------------------------------------------------------------
# Label detection
# ---------------------------------------------------------------------------


def detect_section_labels(text: str) -> tuple[tuple[int, str, str], ...]:
    """Find section markers in extracted statute text.

    Two shapes are recognised, and each is reported with the method that found
    it so a consumer can weigh it:

    * ``"heading"`` — a line that begins with a number, e.g.
      ``"420. Cheating by personation."``. The label is the number with its
      trailing dot (``"420."``), which is the part that identifies a provision
      and is stable regardless of how the title wraps in the PDF.
    * ``"inline"`` — ``"Section 420"`` appearing mid-line, usually a cross
      reference. The label is the whole matched span, verbatim.

    Only the FIRST occurrence of a given inline label is reported. A repeated
    cross reference points at a provision that was already marked, and turning
    every mention into a hard boundary would shatter the surrounding text into
    one-chunk-per-mention fragments. Headings are never deduplicated: a heading
    that recurs is a provision continuing across a page break.

    Detection is a HEURISTIC. A numbered list item is indistinguishable from a
    heading here, so the result is fit for navigation and grouping only. It must
    never be presented as a verified citation — normalising and verifying
    section numbers is Stage 8's job.

    Args:
        text: The full extracted text of one document.

    Returns:
        Tuples of ``(offset, label, method)`` sorted by offset, where ``offset``
        is where the label starts in ``text`` and ``method`` is ``"heading"`` or
        ``"inline"``. Empty tuple when nothing matched — never ``None``.

    Raises:
        ValueError: If a label somehow is not a substring of ``text``. This is
            an internal invariant, not a user error: it means the detector
            fabricated a section number, which must never reach an index.
    """
    labels: list[tuple[int, str, str]] = []
    heading_lines: list[tuple[int, int]] = []

    for match in _HEADING_RE.finditer(text):
        labels.append((match.start("label"), match.group("label"), METHOD_HEADING))
        line_end = text.find("\n", match.start())
        heading_lines.append((match.start(), len(text) if line_end < 0 else line_end))

    seen_inline: set[str] = set()
    line_index = 0
    for match in _INLINE_RE.finditer(text):
        start = match.start()
        # `heading_lines` is already ordered; walk it forward once. An inline
        # mention inside a heading line is part of that heading, not a separate
        # boundary.
        while line_index < len(heading_lines) and heading_lines[line_index][1] <= start:
            line_index += 1
        if line_index < len(heading_lines) and heading_lines[line_index][0] <= start:
            continue
        label = match.group(0)
        if label in seen_inline:
            continue
        seen_inline.add(label)
        labels.append((start, label, METHOD_INLINE))

    labels.sort(key=lambda item: (item[0], item[2]))

    for _offset, label, _method in labels:
        if label not in text:
            raise ValueError(
                "Section detection produced a label that is absent from the source text."
            )

    return tuple(labels)


# ---------------------------------------------------------------------------
# Offset helpers
# ---------------------------------------------------------------------------


def _trimmed_span(text: str, start: int, end: int) -> tuple[int, int] | None:
    """Shrink ``[start, end)`` past surrounding whitespace.

    Args:
        text: The document text the offsets index into.
        start: Inclusive start offset.
        end: Exclusive end offset.

    Returns:
        The tightened span, or ``None`` when nothing but whitespace was left.
    """
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return None if start >= end else (start, end)


def _page_offsets(result: ExtractionResult) -> tuple[int, ...]:
    """Build the offset at which each page starts inside ``full_text``.

    ``ExtractionResult.full_text`` is the pages joined by
    :data:`~app.rag.documents.PAGE_SEPARATOR`, so the offsets follow from
    accumulating ``len(page.text) + len(PAGE_SEPARATOR)``. Reading the separator
    from the extractor means this table cannot drift from the join rule it
    mirrors. That identity is checked first. If a hand-built or future extractor
    ever joins pages some other way, each page is instead located by a forward
    search for its own text, which is still exact rather than estimated; a page
    whose text is genuinely absent is left out of the table and contributes no
    characters.

    Args:
        result: The extraction to map.

    Returns:
        One start offset per mappable page, in page order.
    """
    texts: tuple[str, ...] = tuple(page.text for page in result.pages)
    gap: int = len(PAGE_SEPARATOR)

    offsets: list[int] = []
    cursor = 0
    for page_text in texts:
        offsets.append(cursor)
        cursor += len(page_text) + gap

    if PAGE_SEPARATOR.join(texts) == result.full_text:
        return tuple(offsets)

    fallback: list[int] = []
    search_from = 0
    for page_text in texts:
        if not page_text:
            continue
        found = result.full_text.find(page_text, search_from)
        if found < 0:
            continue
        fallback.append(found)
        search_from = found + len(page_text)
    return tuple(fallback)


def _page_for_offset(offsets: tuple[int, ...], offset: int) -> int:
    """Return the 1-based page number containing ``offset``.

    ``offsets`` is sorted, so ``bisect_right`` finds the page whose start is the
    last one at or before ``offset``. The answer is an exact lookup into the
    table built from the pages themselves — a page number is never guessed from
    the size of the text.

    Args:
        offsets: Page start offsets from :func:`_page_offsets`.
        offset: A character offset into ``full_text``.

    Returns:
        The printed page number, or ``1`` when the table is empty.
    """
    if not offsets:
        return 1
    index = bisect_right(offsets, offset) - 1
    return max(0, min(index, len(offsets) - 1)) + 1


# ---------------------------------------------------------------------------
# Unit splitting
# ---------------------------------------------------------------------------


def _paragraph_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Split ``[start, end)`` on blank lines.

    Args:
        text: The document text.
        start: Inclusive start offset of the region.
        end: Exclusive end offset of the region.

    Returns:
        Whitespace-trimmed spans, in order. Empty when the region is blank.
    """
    spans: list[tuple[int, int]] = []
    cursor = start
    for match in _PARAGRAPH_BREAK_RE.finditer(text, start, end):
        span = _trimmed_span(text, cursor, match.start())
        if span is not None:
            spans.append(span)
        cursor = match.end()
    tail = _trimmed_span(text, cursor, end)
    if tail is not None:
        spans.append(tail)
    return spans


def _sentence_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Split ``[start, end)`` after sentence-terminating punctuation.

    The terminator and any closing quote or bracket stay inside the sentence, so
    no punctuation is lost at a chunk boundary.

    Args:
        text: The document text.
        start: Inclusive start offset of the region.
        end: Exclusive end offset of the region.

    Returns:
        Whitespace-trimmed spans, in order.
    """
    spans: list[tuple[int, int]] = []
    cursor = start
    for match in _SENTENCE_END_RE.finditer(text, start, end):
        span = _trimmed_span(text, cursor, match.end())
        if span is not None:
            spans.append(span)
        cursor = match.end()
    tail = _trimmed_span(text, cursor, end)
    if tail is not None:
        spans.append(tail)
    return spans


def _hard_spans(text: str, start: int, end: int, cut_chars: int) -> list[tuple[int, int]]:
    """Cut a span that is still too long at the last space before ``cut_chars``.

    A single sentence can run to several pages — a long enumerated list, a
    schedule, a table flattened into text. There is no better boundary inside
    it, so the cut lands at the last horizontal whitespace inside the window so
    words stay whole, and at exactly ``cut_chars`` when the window has none.

    Args:
        text: The document text.
        start: Inclusive start offset of the region.
        end: Exclusive end offset of the region.
        cut_chars: Maximum characters per piece; never below 1.

    Returns:
        Whitespace-trimmed spans, in order.
    """
    spans: list[tuple[int, int]] = []
    cursor = start
    floor: int = max(1, cut_chars // 2)
    while end - cursor > cut_chars:
        window_end = cursor + cut_chars
        cut = window_end
        last_space = -1
        for match in _HORIZONTAL_SPACE_RE.finditer(text, cursor, window_end):
            last_space = match.end()
        if last_space > cursor and last_space - cursor >= floor:
            cut = last_space
        span = _trimmed_span(text, cursor, cut)
        if span is not None:
            spans.append(span)
        cursor = cut
    tail = _trimmed_span(text, cursor, end)
    if tail is not None:
        spans.append(tail)
    return spans


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def _page_regions(
    text_length: int,
    bounds: list[tuple[int, int, str | None, str]],
    page_table: tuple[int, ...],
) -> list[tuple[int, int, str | None, str]]:
    """Split each section at every page boundary it crosses.

    Page and section boundaries intersect, and a chunk must respect both. The
    regions produced here are the finest such division: each one lies wholly
    inside a single section AND a single page, so a chunk built from one region
    can break neither invariant.

    A page's start offset is clamped into the section. Without that clamp a
    section beginning mid-page would produce a region that reached back into the
    preceding page — and into the preceding section's text — which is precisely
    the blend the boundaries exist to prevent.

    Args:
        text_length: Length of the full document text.
        bounds: Section boundaries from :func:`_section_bounds`.
        page_table: Page start offsets from :func:`_page_offsets`.

    Returns:
        Regions as ``(start, end, label, method)``, in order, non-overlapping,
        and covering the whole document.
    """
    regions: list[tuple[int, int, str | None, str]] = []
    gap: int = len(PAGE_SEPARATOR)

    for section_start, section_end, label, method in bounds:
        cursor = section_start
        for offset in page_table:
            # The separator between two pages belongs to neither page's text, so
            # a region ends before it and the next begins after it.
            boundary = offset - gap
            if boundary <= cursor:
                continue
            if boundary >= section_end:
                break
            if boundary > cursor:
                regions.append((cursor, boundary, label, method))
                cursor = boundary
        if cursor < section_end:
            regions.append((cursor, section_end, label, method))
    return regions


def _effective_target(config: ChunkingConfig) -> int:
    """Return the character ceiling, never smaller than ``min_chars``.

    A configuration asking for a target below its own minimum is contradictory;
    the minimum wins, because a hard cut shorter than ``min_chars`` would be
    guaranteed useless.

    Args:
        config: The requested tuning.

    Returns:
        The chunk size ceiling actually applied.
    """
    return max(1, config.target_chars, config.min_chars)


def _effective_overlap(config: ChunkingConfig) -> int:
    """Return the overlap, clamped so ``min_chars`` of new text always remains.

    Args:
        config: The requested tuning.

    Returns:
        The overlap actually applied, never negative.
    """
    budget: int = _effective_target(config) - max(0, config.min_chars)
    return max(0, min(config.overlap_chars, budget))


def _overlap_start(
    text: str,
    emitted_start: int,
    emitted_end: int,
    region_start: int,
    next_unit_start: int,
    overlap_chars: int,
) -> int:
    """Return where the piece after an emitted one should begin.

    The overlap is carved backwards out of the chunk just emitted and then
    advanced past whitespace, so it begins on real text. It never reaches back
    before ``region_start``, because the region is bounded by a page or section
    edge that a chunk must not cross.

    Args:
        text: The document text.
        emitted_start: Start offset of the chunk just emitted.
        emitted_end: End offset of the chunk just emitted.
        region_start: Start offset of the page-aligned region being split.
        next_unit_start: Start offset of the next unit of text, used when no
            overlap is possible.
        overlap_chars: Overlap requested by the configuration.

    Returns:
        An absolute offset strictly inside the current region.
    """
    if overlap_chars <= 0 or emitted_end - emitted_start <= overlap_chars:
        return next_unit_start
    window = emitted_end - overlap_chars
    if window <= region_start:
        return next_unit_start
    cursor = window
    while cursor < emitted_end and text[cursor].isspace():
        cursor += 1
    return next_unit_start if cursor >= emitted_end else cursor


def _pack_ranges(
    text: str,
    region_start: int,
    units: list[tuple[int, int]],
    target_chars: int,
    overlap_chars: int,
) -> list[tuple[int, int]]:
    """Greedily fill chunks up to ``target_chars`` from ordered units.

    The overlap is counted inside the target: a chunk is never longer than
    ``target_chars`` even though part of it was already emitted.

    Args:
        text: The document text.
        region_start: Start offset of the region, clamping the overlap.
        units: Ordered, non-overlapping, whitespace-trimmed spans.
        target_chars: Character ceiling per chunk.
        overlap_chars: Overlap to carry into the next chunk.

    Returns:
        The chunk ranges, in order.
    """
    ranges: list[tuple[int, int]] = []
    current: list[int] | None = None

    for unit_start, unit_end in units:
        if current is None:
            current = [unit_start, unit_end]
            continue
        if unit_end - current[0] <= target_chars:
            current[1] = unit_end
            continue
        ranges.append((current[0], current[1]))
        start = _overlap_start(
            text, current[0], current[1], region_start, unit_start, overlap_chars
        )
        current = [start, unit_end]

    if current is not None:
        ranges.append((current[0], current[1]))
    return ranges


# ---------------------------------------------------------------------------
# Boundary computation
# ---------------------------------------------------------------------------


def _section_bounds(
    text_length: int, labels: tuple[tuple[int, str, str], ...]
) -> list[tuple[int, int, str | None, str]]:
    """Turn detected labels into hard section boundaries.

    Text before the first heading is front matter and becomes its own section
    with no label, so no text is left without an owner. Each section runs from
    its heading up to the next one.

    Args:
        text_length: Length of the full document text.
        labels: Output of :func:`detect_section_labels`.

    Returns:
        Tuples of ``(start, end, label, method)`` covering the whole document
        with no gaps and no overlaps.
    """
    bounds: list[tuple[int, int, str | None, str]] = []
    if not labels:
        return [(0, text_length, None, METHOD_NONE)]

    first_offset = labels[0][0]
    if first_offset > 0:
        bounds.append((0, first_offset, None, METHOD_NONE))

    for index, (offset, label, method) in enumerate(labels):
        end = labels[index + 1][0] if index + 1 < len(labels) else text_length
        if end > offset:
            bounds.append((offset, end, label, method))
    return bounds


def _heading_count(headings: list[int], start: int, end: int) -> int:
    """Count detected heading offsets inside ``[start, end)``.

    Args:
        headings: Offsets of every detection whose method is ``"heading"``.
        start: Inclusive start offset.
        end: Exclusive end offset.

    Returns:
        How many section headings the span covers.
    """
    return sum(1 for offset in headings if start <= offset < end)


def _merge_candidate(
    left: list[str | int | None],
    right: list[str | int | None],
    headings: list[int],
    page_table: tuple[int, ...],
) -> tuple[int, list[str | int | None]] | None:
    """Score a candidate merge of two adjacent chunks.

    Merges are ranked so the least disruptive one wins. Staying on one page is
    preferred, because page alignment is a citation *presentation* concern and
    a floor-driven merge may legitimately cross it.

    Crossing a detected section heading is different in kind, and is **not** a
    ranked fallback. Merging two provisions blends two distinct legal meanings
    into one retrievable unit, and the surviving chunk keeps only the left
    label — so the merge would file text from section 2 under section 1's
    number. That is exactly the misattributed citation this project must never
    emit, so a merge spanning two headings is rejected outright rather than
    ranked last. See :func:`_apply_min_chars_floor`.

    Args:
        left: The earlier chunk, as ``[start, end, label, method]``.
        right: The later chunk, in the same shape.
        headings: Offsets of every detected heading.
        page_table: Page start offsets from :func:`_page_offsets`.

    Returns:
        The ranking (lower is better) and the merged chunk, or ``None`` when the
        merge would cross a detected section heading and must not happen.
    """
    start = int(left[0])
    end = int(right[1])
    if _heading_count(headings, start, end) > 1:
        return None
    label = left[2] if left[2] is not None else right[2]
    method = left[3] if left[2] is not None else right[3]
    one_page = _page_for_offset(page_table, start) == _page_for_offset(page_table, end - 1)
    return (0 if one_page else 1), [start, end, label, method]


def _apply_min_chars_floor(
    text: str,
    chunks: list[list[str | int | None]],
    headings: list[int],
    min_chars: int,
    page_table: tuple[int, ...],
) -> list[list[str | int | None]]:
    """Merge chunks shorter than ``min_chars`` into a neighbour.

    A sub-floor chunk matches almost any query, so emitting one floods retrieval
    with noise. Merging is preferred in the least disruptive direction available:
    same page first, then across a page boundary. Forward merges win ties so the
    result stays close to document order.

    **A merge that would cross a detected section heading is never performed.**
    Section boundaries outrank the floor: two provisions must never be blended
    into one chunk, and the surviving chunk would carry only the left-hand
    label, filing the right-hand provision under the wrong section number. When
    the only available merge would cross a heading — which is the *common* case
    for a statute of many short provisions — the sub-floor chunk is kept as it
    is. A slightly small, correctly-scoped chunk is the right trade; a small
    chunk that quietly misattributes half its text is not.

    Each merge removes one chunk, so the loop always terminates. A chunk that
    has been refused a legal merge is *exempt* from the floor from then on:
    it keeps its own text and its own label rather than being dropped, and is
    not reconsidered. Exempting by start offset is stable because a merge
    always keeps the left-hand chunk's start, so a live chunk's start offset
    never changes and never collides with another chunk's.

    Args:
        text: The document text.
        chunks: Chunks as mutable ``[start, end, label, method]`` records.
        headings: Offsets of every detected heading.
        min_chars: The floor below which a chunk is merged away.
        page_table: Page start offsets from :func:`_page_offsets`.

    Returns:
        The surviving chunks, still in document order.
    """
    working: list[list[str | int | None]] = [list(item) for item in chunks]
    exempt: set[int] = set()

    while True:
        index = next(
            (
                position
                for position, item in enumerate(working)
                if int(item[1]) - int(item[0]) < min_chars
                and int(item[0]) not in exempt
            ),
            None,
        )
        if index is None:
            return working

        best: tuple[int, int, list[str | int | None]] | None = None
        for direction in (1, -1):
            neighbour = index + direction
            if not 0 <= neighbour < len(working):
                continue
            low, high = sorted((index, neighbour))
            candidate = _merge_candidate(working[low], working[high], headings, page_table)
            if candidate is None:
                continue
            priority, merged = candidate
            if best is None or priority < best[0]:
                best = (priority, low, merged)

        if best is None:
            # No adjacent merge is legal. Keep this chunk whole and stop asking.
            exempt.add(int(working[index][0]))
            continue
        _priority, low, merged = best
        working[low : low + 2] = [merged]


def chunk_document(
    result: ExtractionResult, config: ChunkingConfig | None = None
) -> tuple[Chunk, ...]:
    """Split one extracted document into retrievable chunks.

    Two boundaries are hard. A detected section heading ends the current chunk,
    because a chunk spanning two provisions would blend two distinct legal
    meanings into one answer. A page boundary does the same, because it makes
    "page 2" in a citation a place rather than a range. Inside one
    section-and-page region the text is split on paragraph breaks, then
    sentences, then a hard character cut, and consecutive pieces overlap by
    ``overlap_chars`` so a provision split across a boundary is still
    retrievable from either side.

    A piece shorter than ``min_chars`` is merged into a neighbour rather than
    emitted, since a sub-floor chunk matches almost any query and is pure
    retrieval noise. A whitespace-only piece is dropped outright. The floor is
    allowed to override *page* alignment — when a page holds nothing but a few
    stray characters, the merge crosses the page boundary rather than emitting a
    chunk below the floor.

    The floor does **not** override a section boundary. A merge that would span
    two detected sections is never performed, however convenient it would be:
    two provisions must not be blended into one chunk, and the merged chunk
    would carry only the left-hand section label, misfiling the right-hand
    provision under the wrong number. For a statute of many short provisions
    that means sub-floor chunks are routinely kept rather than merged. That is
    deliberate — a slightly small chunk that cites the right provision beats a
    larger one that cites the wrong one.

    Page numbers are mapped, never estimated. The offset table is built from the
    pages themselves and every chunk's offsets are looked up in it.

    The function is pure and deterministic. The same ``result`` and ``config``
    always produce the same chunks, in the same order, with the same text.

    Args:
        result: The extraction to segment.
        config: Optional tuning; the defaults target 900 characters with 120
            characters of overlap and a 120-character floor.

    Returns:
        Chunks in document order, numbered from 0. Empty tuple when the
        document holds no text.
    """
    settings: ChunkingConfig = config if config is not None else ChunkingConfig()
    text: str = result.full_text
    if not text.strip():
        return ()

    target_chars: int = _effective_target(settings)
    overlap_chars: int = _effective_overlap(settings)
    #: Hard-cut window. A chunk that opens with the overlap and then holds one
    #: whole unit is ``overlap_chars + cut_chars`` long, so leaving that overlap
    #: room here is what keeps every chunk within ``target_chars`` in the
    #: long-single-sentence case where a unit is itself the whole chunk.
    cut_chars: int = max(1, target_chars - overlap_chars)
    page_table: tuple[int, ...] = _page_offsets(result)

    labels: tuple[tuple[int, str, str], ...] = detect_section_labels(text)
    bounds: list[tuple[int, int, str | None, str]] = _section_bounds(len(text), labels)
    headings: list[int] = [offset for offset, _label, method in labels if method == METHOD_HEADING]

    pieces: list[list[str | int | None]] = []
    for region_start, region_end, label, method in _page_regions(len(text), bounds, page_table):
        units: list[tuple[int, int]] = []
        for paragraph in _paragraph_spans(text, region_start, region_end):
            for sentence in _sentence_spans(text, paragraph[0], paragraph[1]):
                if sentence[1] - sentence[0] > cut_chars:
                    units.extend(_hard_spans(text, sentence[0], sentence[1], cut_chars))
                else:
                    units.append(sentence)
        if not units:
            continue

        for start, end in _pack_ranges(text, region_start, units, target_chars, overlap_chars):
            span = _trimmed_span(text, start, end)
            if span is None:
                # Whitespace-only fragment: nothing to retrieve, nothing lost.
                continue
            pieces.append([span[0], span[1], label, method])

    survivors: list[list[str | int | None]] = _apply_min_chars_floor(
        text, pieces, headings, settings.min_chars, page_table
    )

    chunks: list[Chunk] = []
    for piece in survivors:
        char_start = int(piece[0])
        char_end = int(piece[1])
        index = len(chunks)
        chunks.append(
            Chunk(
                chunk_id=f"{result.document.law_id}::{index:06d}",
                law_id=result.document.law_id,
                chunk_index=index,
                text=text[char_start:char_end],
                page_start=_page_for_offset(page_table, char_start),
                page_end=_page_for_offset(page_table, char_end - 1),
                char_start=char_start,
                char_end=char_end,
                section_label=piece[2] if isinstance(piece[2], str) else None,
                section_detection=piece[3] if isinstance(piece[3], str) else METHOD_NONE,
            )
        )
    return tuple(chunks)
