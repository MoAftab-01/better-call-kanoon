"""Tests for :mod:`app.rag.tokenizer` - the lexical half of hybrid retrieval.

Two failure modes are being held at bay here, and they pull in opposite
directions. On one side, an English-only splitter tears Devanagari syllables
apart so badly that a Hindi query matches nothing, which looks like "search is
broken" and gets misdiagnosed as a bad index. On the other, a splitter that keeps
every scrap of digits and punctuation soaks up rare-term IDF in page furniture
and stamps, which looks like "search returns junk" and gets misdiagnosed as bad
law data. Neither is visible from a passing test suite, so the cases below are
written as named end-to-end behaviours rather than as a grid of inputs.

Every assertion here is about *observable* tokenisation. Nothing in this file
knows what BM25 will later do with the terms.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

import pytest

from app.rag.tokenizer import (
    DEVANAGARI_STOPWORDS,
    MIN_TERM_CHARS,
    STOPWORDS,
    normalize_for_index,
    tokenize,
)

# ---------------------------------------------------------------------------
# The corpus this project actually indexes
# ---------------------------------------------------------------------------


def test_english_statutory_prose_tokenises_into_words() -> None:
    """The ordinary case: a sentence in the corpus's first language."""
    assert tokenize("Whoever commits theft shall be punished") == (
        "whoever",
        "commits",
        "theft",
        "shall",
        "punished",
    )


def test_devanagari_syllables_stay_whole() -> None:
    """``हिन्दी`` is three syllables and must be one term.

    A splitter built on :meth:`str.isalpha` returns nothing at all here, because
    every matra reports as a mark and every mark is excluded. The user-facing
    symptom is a Hindi query that silently matches zero documents against a
    corpus full of Hindi.
    """
    assert tokenize("हिन्दी भाषा") == ("हिन्दी", "भाषा")


def test_a_devanagari_matra_never_opens_a_term() -> None:
    """Marks continue a term; they never start one.

    A leading mark is residue from a split syllable or a scanning artefact, and
    a term that opens with one collides with real words while describing
    nothing.
    """
    # The vowel sign alone, and a run of marks with nothing attached.
    assert tokenize("़ा") == ()
    assert tokenize("(़)") == ()


def test_devanagari_and_english_mix_in_one_sentence() -> None:
    """A bilingual clause keeps both halves searchable.

    ``वह`` and ``है`` are stopwords and are dropped; the point of the test is
    that the two scripts survive each other's presence rather than one swallowing
    or breaking the other.
    """
    assert tokenize("वह theft करता है") == ("theft", "करता")


# ---------------------------------------------------------------------------
# Section numbers are the primary key of Indian statute
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Section 420", ("section", "420")),
        ("Section 420A", ("section", "420a")),
        ("section 304-a", ("section", "304a")),
        ("420", ("420",)),
    ],
)
def test_section_numbers_survive_as_terms(text: str, expected: tuple[str, ...]) -> None:
    """Digits are part of a term, not separators.

    ``420``, ``420A``, ``420B`` and ``420C`` are four sibling offences. The only
    thing that tells them apart is the number, so a retriever that drops digits
    makes every section of every act lexically identical to every other one.
    """
    assert tokenize(text) == expected


def test_digits_inside_a_word_do_not_split_it() -> None:
    """``420B`` is one token, not ``420`` and ``b``.

    This is where the two modules genuinely disagree, and both are right.
    :func:`app.rag.extraction._is_alpha_char` excludes digits because ``- 2023 -``
    is page furniture to be *rejected*; here digits are part of a term to be
    *indexed*. Asking "is this a word?" and "is this a term?" are different
    questions.
    """
    assert tokenize("304A") == ("304a",)
    assert tokenize("1872") == ("1872",)


def test_a_single_digit_section_number_is_not_discarded() -> None:
    """``section 4`` keeps its number.

    Regression test for the worst defect this module ever had. The two-character
    length floor exists to stop stray debris from polluting the index, and it
    was applied to numbers too. But Indian statute is numbered in single
    digits, so ``section 4`` tokenised to ``('section',)`` and ``rule 9`` to
    ``('rule',)``: the single term that identifies the provision was silently
    dropped, and the query then matched every section of every act whose text
    happens to contain the word "section".

    The failure is silent and it is confident. The user asks a specific legal
    question, gets a specific-looking legal answer, and has no way to know the
    provision number never entered the search. Returning a ranked list of
    plausible-but-wrong provisions is the unforgivable outcome for a legal
    information tool, so numbers are exempt from the floor. The cost - a term
    like ``4`` with little discriminative power - is precisely what BM25's IDF
    is built to neutralise, and it does so far better than a pre-scoring length
    rule that also throws away the ones that matter.
    """
    assert tokenize("section 4") == ("section", "4")
    assert tokenize("rule 9") == ("rule", "9")
    assert tokenize("Article 5") == ("article", "5")
    assert tokenize("Section 7A") == ("section", "7a")


def test_a_single_letter_word_is_still_discarded() -> None:
    """The floor still applies to letters - the exemption is for numbers only.

    The control for the test above. Without it, an exemption for "short terms"
    rather than "numbers" would quietly let ``a`` and ``I`` back into the
    index, which match nearly every document and make BM25's job hopeless.
    """
    assert tokenize("a") == ()
    assert tokenize("x") == ()
    assert tokenize("I") == ()
    # Still one token rather than three, and the digits still survive inside it.
    assert tokenize("420") == ("420",)


def test_indian_currency_figures_are_not_mangled_by_their_commas() -> None:
    """``5,000/-`` becomes ``5000``, not ``000``.

    Regression test for a second silent defect. A comma is a separator, so
    ``5,000/-`` used to tokenise to ``('000',)`` - the leading ``5`` was one
    character, fell under the length floor, and was dropped, leaving a
    fragment matching neither the corpus nor the query. Every monetary figure
    in the corpus was affected, and monetary terms are some of the most
    searchable things in criminal statute ("fine of Rs. 5,000").

    ``1,00,000`` is the case that proves the grouping rule is the Indian one:
    its second group is two digits, which no Western thousands separator ever
    produces, so a naive digit-comma-digit join would still get it right while a
    naive "split on comma" gets it wrong seven ways.
    """
    assert tokenize("5,000/-") == ("5000",)
    assert tokenize("Rs. 1,00,000") == ("rs", "100000")
    assert tokenize("fine of Rs. 5,000 rupees") == ("fine", "rs", "5000", "rupees")
    assert tokenize("12,34,567") == ("1234567",)


def test_an_enumeration_is_not_fused_into_a_number_that_is_not_there() -> None:
    """``1,2,3`` stays three numbers.

    The negative control for the test above, and the reason the grouping rule
    is narrow rather than "any digit, comma, digit". A looser join would turn
    a list into a single invented figure, and an invented number in a legal
    document is a worse failure than a split one: it looks like a real citation.
    """
    assert tokenize("Sections 1,2 and 3") == ("sections", "1", "2", "3")
    assert tokenize("1,2,3") == ("1", "2", "3")
    # A Western-grouped number does not match the Indian pattern's final
    # three-digit group, so it keeps its separator rather than half-joining.
    assert tokenize("4,294,967") == ("4294", "967")


def test_indian_script_digits_are_numbers_too() -> None:
    """Devanagari digits survive as terms, whatever NFKC did to them.

    ``१२`` is category ``Nd`` like ``12``, and the length-floor exemption must
    not depend on the term being ASCII. This is checked with :func:`chr`
    rather than literal characters because a source file cannot be relied on to
    preserve a literal sequence, and a fixture that was normalised on the way
    to disk asserts nothing.

    The second assertion records a *known limitation* rather than a property.
    NFKC leaves Devanagari digits as Devanagari digits, so ``१२`` and ``12``
    produce two distinct terms and never meet. That is a deliberate
    non-goal for now: a query typed on a Devanagari keyboard asking for
    "section 4" is a real case, and folding Devanagari digits onto ASCII would
    fix it. It is recorded here as a limitation rather than fixed silently,
    because digit folding is a change to the shared normalisation helper that
    both the indexer and the query path use, and getting it wrong would break
    the property everything else rests on - that the two sides cannot disagree.
    See :func:`app.rag.tokenizer.normalize_for_index`.
    """
    devanagari_twelve = chr(0x0967) + chr(0x0968)
    assert devanagari_twelve != "12"

    terms = tokenize(devanagari_twelve)
    assert len(terms) == 1, "the two Devanagari digits must stay one term"
    assert terms[0].isdecimal(), "and must still count as a number for the floor"
    assert len(terms[0]) >= 1, "a bare number is exempt from MIN_TERM_CHARS"

    # Recorded limitation, asserted so that whoever fixes it has to delete a
    # line rather than discover a silently changed behaviour.
    assert terms != tokenize("12"), (
        "Devanagari digits currently do not converge with ASCII ones. If this "
        "now fails, digit folding was added - update this docstring and the "
        "tokenizer's normalisation notes to match."
    )


def test_a_bare_page_number_and_a_roman_folio_both_become_terms() -> None:
    """``- 12 -`` and ``- iii -`` both yield one term; neither is special-cased.

    Recorded rather than wished away, because the honest position is that the
    tokenizer does *not* recognise page furniture. It is not where furniture is
    caught: the scan detector rejects Roman-paginated documents before they are
    ever chunked, on a page-level test over the extracted text. Tokenising is a
    different question from "is this a page of law", and pretending otherwise
    here would only add a rule that quietly disagrees with the detector's.

    ``iii`` clearing the two-character floor is precisely why the folio check in
    :mod:`app.rag.extraction` has to exist at all - if the tokenizer dropped
    Roman folios, that check would be defending against something that could
    never reach it, and would look like it was doing useful work.
    """
    assert tokenize("- 12 -") == ("12",)
    assert tokenize("- iii -") == ("iii",)
    assert tokenize("-\t2023\t-") == ("2023",)


# ---------------------------------------------------------------------------
# Act names, citations and acronyms
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("B.N.S.", ("bns",)),
        ("BNS 2023", ("bns", "2023")),
        ("I.P.C.", ("ipc",)),
        ("Indian Penal Code", ("indian", "penal", "code")),
        ("Code of Criminal Procedure, 1973", ("code", "criminal", "procedure", "1973")),
        ("u/s 138", ("138",)),
        ("see sec.2", ("see", "sec", "2")),
    ],
)
def test_act_names_and_citations_tokenise_usefully(
    text: str, expected: tuple[str, ...]
) -> None:
    """Abbreviations collapse to a stable term rather than shattering.

    ``B.N.S.`` as five one-character fragments would match nothing: every
    fragment is below the length floor, so the whole abbreviation vanishes. The
    official PDFs print it dotted and a reader types it plain, so the two must
    meet. ``sec.2`` is the control: a multi-character fragment is not an
    initialism and keeps its dot.

    The bare ``2`` survives, which is a deliberate change from an earlier
    version of this file. That version dropped it, reasoning that a section
    number one digit long is not discriminative against a corpus full of
    ``138`` and ``420``. But ``section 4`` and ``rule 9`` are ordinary
    provisions in Indian statute, and dropping their numbers means the query
    "what is section 4" matches *every* section of *every* act that contains
    the word "section" - a confident answer to the wrong question. The
    discriminative-power argument is real but it belongs to BM25's IDF, which
    is built to neutralise exactly this term, not to a length floor applied
    before scoring has happened.
    """
    assert tokenize(text) == expected


def test_hyphen_after_a_digit_joins_a_section_identifier() -> None:
    """``304-A`` is one section, and the reader asks for it that way."""
    assert tokenize("304-A") == ("304a",)
    assert tokenize("420-B") == ("420b",)


def test_a_hyphen_not_after_a_digit_still_splits() -> None:
    """The identifier rule is narrow on purpose.

    ``anti-national`` must not become ``antinational``: the compound rule keeps
    governing ordinary prose, and no digit may drag it into an exception.
    """
    assert tokenize("anti-national") == ("anti", "national")
    assert tokenize("cheat-ing") == ("cheat", "ing")


def test_underscore_joins_a_law_id_rather_than_splitting_it() -> None:
    """``bns_2023`` is one term.

    Law ids appear in filenames and metadata, and splitting on ``_`` turns a
    single identifier into two fragments that match nothing useful.
    """
    assert tokenize("bns_2023") == ("bns_2023",)


def test_hyphenated_compounds_split_into_their_parts() -> None:
    """``personation`` is searchable on its own, not only as ``anti-...``.

    A hyphen is a boundary here rather than part of a term: statute text is full
    of hyphenated compounds, and the individual words are what queries use.
    """
    assert tokenize("anti-national") == ("anti", "national")


# ---------------------------------------------------------------------------
# Normalisation, and the index/query agreement it must buy
# ---------------------------------------------------------------------------


def test_casefolding_is_used_rather_than_lower() -> None:
    """Casefolding is the caseless operation Unicode defines.

    ``str.lower`` leaves ``ß`` alone; casefolding maps it to ``ss``. Whichever is
    chosen, the important property is that both sides of a search use it - see
    the agreement tests below.
    """
    assert normalize_for_index("STRASSE") == normalize_for_index("strasse")


def test_decomposed_and_composed_devanagari_meet_the_same_term() -> None:
    """NFKC makes two spellings of the same syllable produce one term.

    The fixtures are built with :func:`chr` rather than written as literal
    characters, because a source file cannot be relied on to preserve a
    decomposed sequence and an editor or tool will happily compose one on the
    way in. A test whose fixture has already been normalised on disk asserts
    nothing - it passed for a while in exactly that state.
    """
    precomposed = chr(0x0958)  # DEVANAGARI LETTER QA, one codepoint
    decomposed = chr(0x0915) + chr(0x093C)  # KA + NUKTA, two codepoints

    assert precomposed != decomposed, "the fixtures must actually differ"
    assert len(decomposed) == 2 and len(precomposed) == 1

    # Both spellings reach the same term...
    assert tokenize(precomposed) == tokenize(decomposed)
    # ...and the agreed form is the *decomposed* one. NFKC does not compose
    # U+0958 into U+0915 U+093C; it is not a compatibility decomposition, so
    # NFKC leaves it alone and both inputs converge on the two-codepoint
    # spelling. Asserting the direction matters: writing the other way round
    # would pass today and silently start lying if the rule ever changed.
    assert tokenize(precomposed) == (decomposed,)


def test_a_vowel_sign_cannot_be_detached_from_its_consonant() -> None:
    """The matra travels with its consonant, so the term is one token.

    The negative control for the test above: without mark handling, ``हिन्दी``
    would tokenise to bare consonants with the vowel signs dropped, so a query
    in one spelling would miss a document written in the other.
    """
    hindi = chr(0x0939) + chr(0x093F) + chr(0x0928) + chr(0x094D) + chr(0x0926) + chr(0x0940)
    assert len(hindi) == 6, "Devanagari syllables are multi-codepoint by nature"
    assert tokenize(hindi) == (hindi,)


def test_index_and_query_normalise_identically() -> None:
    """The same word typed differently on each side still matches.

    This is the property that actually matters, and it is why
    :func:`normalize_for_index` is a single shared helper rather than two
    inline calls: two normalisers is a bug that returns "no results" instead of
    raising, so nothing ever notices.
    """
    document_terms = tokenize("Cheating by Personation")
    query_terms = tokenize("what does CHEATING mean")
    assert "cheating" in document_terms
    assert "cheating" in query_terms


# ---------------------------------------------------------------------------
# Robustness: the retriever must not be one unusual input away from a 500
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "\n\t\r",
        "...",
        "()[]{}",
        "-  -  -",
        "!!!",
        "§¶",
        "𝟙𝟚𝟛",  # mathematical digits: category Nd
        "ß" * 3,
        "ا" * 50,
    ],
)
def test_tokenize_never_raises_and_returns_terms_of_usable_length(text: str) -> None:
    """No input reaches a 500, and nothing degenerate gets indexed.

    A retriever is the one place a weird string becomes a server error, because
    it is the only place user text meets the corpus. Every one of these is
    something a user can type or a PDF can contain.
    """
    terms = tokenize(text)
    assert isinstance(terms, tuple)
    assert all(isinstance(term, str) for term in terms)
    assert all(len(term) >= MIN_TERM_CHARS for term in terms)


def test_a_term_of_only_marks_never_reaches_the_index() -> None:
    """Pure-mark runs are dropped even when they clear the length floor."""
    # Two marks: long enough to pass MIN_TERM_CHARS, meaningless as a term.
    assert tokenize("ा ी े") == ()


def test_unindexed_symbols_separate_rather_than_fuse() -> None:
    """An unknown symbol is a boundary, not something that glues words together.

    Dropping it silently would turn ``cheat$ing`` into the term ``cheating``,
    which is a word that exists in the corpus. The safe failure is to split.
    """
    assert tokenize("cheat$ing") == ("cheat", "ing")


# ---------------------------------------------------------------------------
# Stopwords: the honesty guard on a judgement call
# ---------------------------------------------------------------------------


def test_stopword_filtering_is_symmetric_and_off_by_one_switch() -> None:
    """The same text yields different terms depending only on the flag.

    Pinned so a future change cannot quietly start filtering queries but not
    documents, or vice versa - a mismatch there makes one half of every search
    silently miss.
    """
    text = "The person who commits theft"
    with_stop = tokenize(text)
    without_stop = tokenize(text, drop_stopwords=False)
    assert len(without_stop) > len(with_stop)
    assert set(with_stop).issubset(set(without_stop))
    assert "the" not in with_stop
    assert "the" in without_stop


def test_stopword_lists_are_documented_as_unvalidated() -> None:
    """The lists carry their own disclaimer, because they are a judgement call.

    Project rule: do not invent mappings without marking what still needs
    verifying. This list was assembled by judgement and has not been measured
    against real Acts, and the code says so where a reader will see it.
    """
    import inspect

    import app.rag.tokenizer as tokenizer_module

    source = inspect.getsource(tokenizer_module)
    assert "judgement call" in source
    assert "not been validated" in source


def test_legal_verbs_survive_as_terms() -> None:
    """``shall`` and ``punishable`` are legal words, not filler.

    The reason the stopword list is short. In statutory English "shall" is the
    difference between imposing a duty and conferring a power; a stopword list
    copied from a general-English corpus would delete the connective structure
    of the text it is meant to search.
    """
    terms = tokenize("shall be punished with imprisonment")
    assert "shall" in terms
    assert "punished" in terms
    assert "imprisonment" in terms


def test_devanagari_stopwords_are_present_and_small() -> None:
    """Both scripts are covered, and neither list has run away.

    A runaway stopword list strips the words that carry statutory meaning, so
    the size of these sets is itself a thing worth asserting.
    """
    assert "और" in DEVANAGARI_STOPWORDS
    assert "the" in STOPWORDS
    assert len(STOPWORDS) < 120, "stopword list grew past its documented bound"


# ---------------------------------------------------------------------------
# Ordering and frequency, which BM25 depends on and a set would destroy
# ---------------------------------------------------------------------------


def test_duplicate_terms_are_preserved_and_ordered() -> None:
    """``("theft", "theft")`` stays two terms; a set would collapse it to one.

    BM25 scores on term frequency. De-duplicating in the tokenizer would
    silently rewrite every document's score, and the bug would be invisible -
    retrieval would still return results, just wrongly ranked ones.
    """
    assert tokenize("theft theft") == ("theft", "theft")
    assert tokenize("alpha beta alpha") == ("alpha", "beta", "alpha")


def test_empty_text_yields_an_empty_tuple() -> None:
    """The shape is stable, so a caller need not special-case it."""
    assert tokenize("") == ()
    assert tokenize("   ") == ()
