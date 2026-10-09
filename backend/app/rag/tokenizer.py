"""Language-aware tokenisation for lexical retrieval over Indian statute text.

The corpus this project indexes is bilingual: English statutory prose, romanised
transliterations, section numbers, citations, and Devanagari. A retriever has to
treat all of those as searchable, and the ordinary English whitespace splitter
mangles the Devanagari half of it. This module supplies the one primitive BM25
actually needs - a list of term strings - and nothing else: no scoring, no IDF,
no stopword weighting policy.

Five decisions are worth stating up front, because each is a place where the
easy thing is wrong in a way that hurts *this* corpus.

**Combining marks belong to their consonant.** ``str.isalpha()`` is false for
almost every Devanagari matra, so a splitter built on it shatters ``नि`` into a
bare consonant plus a floating vowel sign, and ``हिन्दी`` into fragments that
match nothing. This module classifies characters the way
:func:`app.rag.extraction._is_alpha_char` does - by Unicode general category -
so a syllable is one term. The reasoning is inherited from the scan detector,
which learned it the hard way: counting letters alone reported typed Hindi
statutes as image-only scans, in proportion to how short their words were.

**Digits are part of a term, not separators.** In a general corpus ``420`` and
``cheating`` share nothing. In this one ``section 420``, ``420A``, ``420B`` and
``420C`` are four sibling offences under the Indian Penal Code, and the only
thing that distinguishes them is the number. Discarding digits would make every
section of every act lexically identical to every other section of every other
act. This is a deliberate departure from :func:`app.rag.extraction._is_alpha_char`,
which excludes digits for a different and correct reason: there, ``- 2023 -`` is
page furniture to be rejected, not a term to be indexed. The two modules ask
different questions about the same character, and both answers are right.

**Dotted initialisms are one term.** ``B.N.S.`` is written that way in the
official PDFs and typed as ``BNS`` in a query. Split on the dots and every
fragment is a single letter, below the length floor, so the whole thing vanishes
and a search for the Bharatiya Nyaya Sanhita finds nothing. Dots between single
letters are therefore removed before tokenising. Spaced initials are left alone:
they are names, not citations.

**A hyphen after a digit is part of an identifier, not a compound boundary.**
``304-A`` is one section of an Act; ``anti-national`` is two words. The rule is
narrow on purpose - only a hyphen *following a digit* joins - so it can never
glue a word to a number that follows it.

**Normalisation happens once, at index time and at query time alike.** NFKC
composes a decomposed ``क़`` (ka + nukta) into one codepoint, so text typed on
one keyboard matches text typed on another. Casefolding rather than ``lower()``
because it is the operation Unicode defines for caseless matching, and it handles
the German and Turkish edge cases ``lower()`` gets wrong. Both go through a
single helper so the indexer and the search path cannot drift apart: two
different normalisers is a bug that produces "no results" rather than an
exception, which is exactly the kind of failure nobody notices.

No stemming is performed. BM25's length normalisation already penalises long
documents, and a stemmer aggressive enough to help would collapse distinctions
Indian statute drafting depends on - ``murder``/``murdered``, ``punish``/
``punishable``/``punishment`` are separate provisions with separate meanings.
A third-party stemmer is not available here in any case; the argument above is
that we would not want it even if it were.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = [
    "STOPWORDS",
    "is_stopword",
    "normalize_for_index",
    "tokenize",
]

#: Unicode general categories that may appear *inside* a term.
#:
#: The mark categories (``Mn``/``Mc``) are the reason this is not a call to
#: :meth:`str.isalpha`. In Devanagari the matra carries the vowel - ``न`` is
#: ``na``, ``नि`` is ``ni`` - and most matras report as marks, so an
#: ``isalpha``-based splitter tears syllables apart. See
#: :func:`app.rag.extraction._is_alpha_char`, which reached the same conclusion
#: independently while solving for scan detection.
_MARK_CATEGORIES: frozenset[str] = frozenset({"Mn", "Mc"})

#: Categories that may *start* a term.
#:
#: Marks are excluded here even though they are welcome inside one. A leading
#: mark is the residue of a syllable that got split, or a stray combining
#: character in a scanned page; either way it is not searchable on its own, and
#: letting one open a term produces unpronounceable fragments that happen to
#: collide with real ones.
#:
#: Digits (``Nd``) are included, per the module docstring.
_TERM_START_CATEGORIES: frozenset[str] = frozenset({"Lu", "Ll", "Lt", "Lm", "Lo", "Nd"})

#: Categories that may appear inside a term but never start one.
_TERM_CONTINUE_CATEGORIES: frozenset[str] = frozenset(_TERM_START_CATEGORIES) | _MARK_CATEGORIES

#: The connector character, which neither starts nor ends a term but joins one.
#:
#: ``bns_2023`` is a single law id. The underscore is not a word character in
#: Unicode (``Pc``) so it falls through both category tests above and would be
#: treated as an unindexed symbol, splitting the id in two - and both halves
#: are useless alone. It is therefore handled explicitly here.
_CONNECTOR: str = "_"

#: Characters that separate terms but carry no meaning of their own.
#:
#: Whitespace is listed explicitly rather than tested with ``str.isspace()``
#: because the set has to be a fast membership test on the hot path, and because
#: Python's ``\s`` and :meth:`str.isspace` disagree about which exotic
#: separators count. The underscore is absent on purpose - ``bns_2023`` is one
#: law id, and splitting it yields two fragments that match nothing.
#:
#: Hyphens and dashes appear here, with one exception handled by
#: :func:`_join_identifier_hyphens`: a hyphen following a digit glues the two
#: halves of a section identifier together instead of splitting them.
_BREAK_CHARS: frozenset[str] = frozenset(
    " \t\n\r\v\f"
    "\x1c\x1d\x1e\x1f"
    "\x85    　"
    " ᠎"
    "       "
    "    "
    "-‐‑‒–—―−/\\"
    "()[]{}<>\"'`.,;:!?¿¡«»„“”‘’…"
    "|*+=~^&@#$%"
)

#: A run of *single* characters separated by dots, as in ``B.N.S.`` or
#: ``Cr.P.C.``.
#:
#: Every fragment must be exactly one character, which is what distinguishes an
#: initialism from an ordinary abbreviation: ``B.N.S.`` has one character per
#: fragment and is one term, while ``sec.2`` has a three-character fragment and
#: keeps its dot. Written out as a lookahead per fragment rather than the
#: tempting ``\S(?:\.\S)+\.?``, which silently accepts ``Cr.P.C.`` and drops the
#: ``PC`` - a match is not the same as a valid initialism.
#:
#: ``\b`` anchors to a real Unicode word boundary so the pattern cannot fire
#: inside a longer word. A weaker ``(?<!\S)`` would be wrong in a way that looks
#: correct: on ``Cr.P.C.`` it matches starting at the ``r``, so the "Cr" is
#: skipped and ``Cr.P.C.`` collapses to ``cr`` - a silent, plausible-looking
#: truncation rather than an error. The optional trailing dot is required in
#: practice: the gazette PDFs print ``B.N.S.`` with a final dot and nothing
#: after it.
_DOTTED_INITIALISM_RE = re.compile(r"\b(?:\S(?=\.)(?:\.(?=\S))?\.?)+")

#: Indian digit grouping, as in ``5,000``, ``1,00,000`` or ``12,34,567``.
#:
#: The first group is one to three digits; any groups after the first are
#: exactly two digits; the last is exactly three. That shape is what
#: distinguishes a lakh from a list: ``1,00,000`` groups as Indian money and
#: becomes ``100000``, while ``1,2,3`` in a string of enumerations and
#: ``Sections 1,2 and 3`` do not match and keep their commas. A looser rule
#: (``(?<=\d),(?=\d)``, join any digit-comma-digit) was rejected because it
#: fuses enumerations into invented numbers, and a number in a legal document
#: that does not exist in it is worse than a number that was merely split.
_INDIAN_GROUPED_NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{2})*,\d{3}")

#: A term must be this long to be indexed.
#:
#: One-character terms are stray debris and match almost anything. Two is the
#: same floor :data:`~app.rag.documents.MIN_ALPHA_RUN_CHARS` uses for calling a
#: run of text a word, applied here to the same end.
#:
#: **Pure digit runs are exempt** - see :func:`_is_all_digits` and
#: :func:`tokenize`.
MIN_TERM_CHARS: int = 2

#: Very common English and legal-English function words.
#:
#: **This list is a judgement call, not a derived or authoritative one.** It is
#: assembled from standard English function words plus connective tissue that
#: dominates Indian statutory prose, and it has not been validated against a
#: real corpus of Acts. Treat it as a starting point that should be measured,
#: not a fact.
#:
#: It is deliberately short. A long stopword list is actively harmful here: BM25
#: scores a document by the terms it *shares* with a query, and over-aggressive
#: filtering strips the words that carry statutory meaning. Every verb in this
#: corpus is a legal word - "shall" is not filler in a statute, it is the
#: difference between imposing a duty and conferring a power.
ENGLISH_STOPWORDS: frozenset[str] = frozenset(
    {
        "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
        "from", "has", "have", "here", "in", "is", "it", "its", "of", "on",
        "or", "that", "the", "their", "them", "there", "these", "they",
        "this", "those", "to", "was", "were", "what", "when", "which",
        "who", "whom", "will", "with", "would", "you", "your",
    }
)

#: Devanagari function words.
#:
#: **Same caveat as :data:`ENGLISH_STOPWORDS`: unvalidated.** Standard
#: postpositions, pronouns and conjunctions, kept short for the same reason and
#: because a longer list would need corpus evidence this project does not yet
#: have. ``किंतु`` and ``तथा`` are included because they carry the contrast and
#: conjunction structure of a proviso-heavy text; whether that helps or hurts
#: BM25 is an empirical question, not one to answer by assertion.
DEVANAGARI_STOPWORDS: frozenset[str] = frozenset(
    {
        "और", "का", "की", "के", "को", "से", "पर", "था", "थे", "थी", "है",
        "हैं", "हो", "होता", "होती", "होते", "यह", "वह", "इस", "उस", "एक",
        "लिए", "द्वारा", "कि", "जो", "तो", "या", "नहीं", "अपने", "अपनी",
    }
)

#: Every stopword, both scripts, as one lookup.
STOPWORDS: frozenset[str] = ENGLISH_STOPWORDS | DEVANAGARI_STOPWORDS


def normalize_for_index(text: str) -> str:
    """Apply the one normalisation this project indexes and searches with.

    NFKC folds composed and decomposed spellings of the same glyph together and
    collapses compatibility forms; casefolding is the caseless operation Unicode
    defines and, unlike :meth:`str.lower`, is correct for Turkish dotted I and
    German sharp s. Both index and query go through here, so the two can never
    disagree about what a word looks like.

    **Known limitation: digits are not folded across scripts.** NFKC leaves
    Devanagari digits as Devanagari digits, so ``१२`` and ``12`` are two
    distinct terms that never meet. A reader typing "section 4" on a Devanagari
    keyboard against an English-text corpus therefore gets no lexical match on
    the number. Folding them is a one-line change here - and deliberately not
    made yet, because this helper is shared by both sides of the search and a
    mistake in it produces "no results" rather than an exception, which is the
    failure mode nothing in the system would notice. It is recorded rather than
    quietly fixed, and pinned by a test so the day it changes, the change is
    visible.

    Args:
        text: Raw text, from a statute body or from a user's question.

    Returns:
        The normalised text. Returns ``""`` for empty input rather than raising.
    """
    return unicodedata.normalize("NFKC", text).casefold()


def _join_identifier_hyphens(text: str) -> str:
    """Remove a hyphen that sits between a digit and a letter.

    ``304-A`` and ``420-B`` are single section identifiers, and a reader asking
    about "section 304-A" expects to find a document that says "304-A". The
    converse case is left strictly alone: ``anti-national`` keeps its hyphen,
    because the rule only ever fires after a digit.

    Args:
        text: Normalised text.

    Returns:
        The same text with identifier hyphens removed.
    """
    return re.sub(r"(?<=\d)-(?=[^\W\d_])", "", text, flags=re.UNICODE)


def _join_grouped_numbers(text: str) -> str:
    """Strip the thousands separators from an Indian-grouped number.

    Indian money and population figures are printed with a comma every two
    digits: ``5,000``, ``1,00,000``, ``12,34,567``. A comma is a separator, so
    without this ``5,000/-`` tokenises to ``('000',)`` - the leading ``5`` is
    shorter than the length floor and is dropped, leaving a fragment that
    matches neither the corpus nor the query. Every monetary figure in the
    corpus is mangled this way.

    Only the Indian shape is joined (see
    :data:`_INDIAN_GROUPED_NUMBER_RE`). Western ``4,294`` is left split on
    purpose: it does not match the pattern's final group of three, so
    ``1,2,3`` and ``Sections 1,2 and 3`` are not fused into numbers that were
    never in the document.

    Args:
        text: Normalised text.

    Returns:
        The same text with Indian-grouped numbers written without commas.
    """
    return _INDIAN_GROUPED_NUMBER_RE.sub(lambda match: match.group(0).replace(",", ""), text)


def _collapse_initialisms(text: str) -> str:
    """Join a dotted run of single characters into one word.

    ``B.N.S.`` becomes ``bns``, so the abbreviation as printed and the
    abbreviation as typed meet. Only fragments of exactly one character are
    joined, so ``sec.2`` and ``no.5`` are left as they are.

    Args:
        text: Normalised text.

    Returns:
        Text with dotted initialisms collapsed.
    """
    return _DOTTED_INITIALISM_RE.sub(lambda match: match.group(0).replace(".", ""), text)


def _is_mark(character: str) -> bool:
    """Return True for a combining mark, in any script."""
    return unicodedata.category(character) in _MARK_CATEGORIES


def _category(character: str) -> str:
    """Return the Unicode general category of ``character``.

    Split out because the ASCII fast path below is worth more than the clarity
    of calling :func:`unicodedata.category` directly at both sites: it skips a
    dictionary lookup per character on the overwhelmingly Latin half of a
    bilingual corpus.
    """
    if character.isascii():
        if character.isalpha():
            return "Lu" if character.isupper() else "Ll"
        if character.isdigit():
            return "Nd"
        return "Po"  # treated as a boundary by the caller either way
    return unicodedata.category(character)


def _is_term_start(character: str) -> bool:
    """Return True for a character that may open a term.

    Digits are included (``Nd``): section numbers are the primary key of Indian
    statute and dropping them would make the corpus lexically flat. Marks are
    not, and that is the difference between this and :func:`_is_mark`.
    """
    return _category(character) in _TERM_START_CATEGORIES


def _is_term_continue(character: str) -> bool:
    """Return True for a character that may sit inside a term."""
    return _category(character) in _TERM_CONTINUE_CATEGORIES


def _is_all_digits(term: str) -> bool:
    """Return True when a term is nothing but decimal digits, of any script.

    Devanagari digits (``०१२``) are ``Nd`` and would otherwise be mangled by
    NFKC's compatibility decomposition into ASCII plus combining marks. The
    :meth:`str.isdecimal` test is the Unicode one, so it accepts every script's
    digits rather than only ``0``-``9``; ``str.isdigit`` is narrower and would
    leave ``१२`` failing the check that :func:`tokenize` is about to make.
    """
    return bool(term) and term.isdecimal()


def tokenize(text: str, *, drop_stopwords: bool = True) -> tuple[str, ...]:
    """Split text into normalised retrieval terms.

    Runs of term characters are accumulated across combining marks and digits,
    so a Devanagari syllable stays whole and ``420B`` stays one token.
    Everything else - punctuation, whitespace, symbols - is a boundary.

    A term consisting only of marks is dropped, and one shorter than
    :data:`MIN_TERM_CHARS` is dropped **unless it is a number**, as is any
    stopword when ``drop_stopwords`` is set. Duplicate terms are preserved and
    in order: BM25 needs the true term frequency, and de-duplicating here
    would silently rewrite it.

    Args:
        text: Raw text in any script.
        drop_stopwords: Remove :data:`STOPWORDS`. Leave this on for indexing
            and for queries alike - applying it to only one side would make the
            two vocabularies disagree.

    Returns:
        Terms in document order, possibly empty. Never raises on any ``str``
        input, including the empty string and strings of pure punctuation.

    Example:
        >>> tokenize("Section 420A: cheating by personation")
        ('420a', 'cheating', 'personation')
        >>> tokenize("fine of Rs. 5,000")
        ('fine', 'rs', '5000')
    """
    prepared = _collapse_initialisms(
        _join_grouped_numbers(_join_identifier_hyphens(normalize_for_index(text)))
    )

    terms: list[str] = []
    current: list[str] = []

    def _flush() -> None:
        if not current:
            return
        term = "".join(current)
        current.clear()
        # The length floor is a noise filter for *words*, and it is wrong for
        # numbers. Indian statute is numbered in single digits: section 4,
        # rule 9, article 5 of the Constitution. With the floor applied
        # unmodified, "section 4" tokenises to ('section',) - the one term
        # that identifies the provision is silently dropped, and the query
        # matches every section of every act that says the word "section". A
        # reader gets a confident answer to the wrong question, which is the
        # failure mode this project exists to avoid; a wrong answer is far
        # worse than a slightly noisy index.
        #
        # A bare digit is also a bad BM25 term in its own right: it has no
        # discriminative power and would sit in a large fraction of documents,
        # which is exactly the case the IDF floor exists to neutralise.
        if len(term) < MIN_TERM_CHARS and not _is_all_digits(term):
            return
        if drop_stopwords and term in STOPWORDS:
            return
        terms.append(term)

    for character in prepared:
        if character in _BREAK_CHARS:
            _flush()
            continue
        if _is_mark(character):
            # Only meaningful while a term is open; a mark with nothing before
            # it is residue, not a word.
            if current:
                current.append(character)
            continue
        if _is_term_start(character):
            current.append(character)
            continue
        if _is_term_continue(character):
            current.append(character)
            continue
        if character == _CONNECTOR and current:
            # Joins an identifier but never opens one: a leading underscore is
            # debris from a column header, and indexing it would produce a term
            # no reader would ever type.
            current.append(character)
            continue
        # Anything left is a symbol we do not index (a currency sign, a maths
        # operator). Treat it as a boundary rather than dropping it silently,
        # so it cannot fuse two words into one term that does not exist.
        _flush()

    _flush()
    return tuple(terms)


def is_stopword(term: str) -> bool:
    """Whether ``term`` is a stopword, after the same normalisation.

    Exposed so a caller building a query can ask about a single term without
    re-normalising the whole string.

    Args:
        term: A single term, in any script, normalised or not.

    Returns:
        True when the normalised form is in :data:`STOPWORDS`.
    """
    return normalize_for_index(term) in STOPWORDS
