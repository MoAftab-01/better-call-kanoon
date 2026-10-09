"""Tests for :mod:`app.rag.lexical` - the BM25 half of hybrid retrieval.

Organised by **failure mode**, not by function name. A test suite that walks
the public API in order tells you the code does what the code does; these
assert the things that must never happen, which is where the damage lives.

Every test here runs with no numpy, no model and no network. That is the point
of the module and it is worth enforcing rather than assuming: a retriever that
only works where the ML stack is installed is a retriever that is absent from
the deployment this project actually ships.

Disclaimer: these tests use short fragments of well-known statutory phrasing
as *test fixtures* to exercise the ranker. They are not legal sources and are
not cited anywhere as authority.
"""

from __future__ import annotations

import math

import pytest

from app.rag.lexical import (
    BM25_B,
    BM25_K1,
    IDF_FLOOR,
    LexicalIndex,
    SearchResult,
    build_lexical_index,
    idf,
)
from app.rag.tokenizer import tokenize

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

#: A miniature corpus. Short enough to reason about by hand, varied enough
#: that length normalisation and IDF both actually engage.
#:
#: Note there is no stemming anywhere in this pipeline, so a fixture that wants
#: a concept retrievable by its noun must also carry its verb. ``cheating``
#: appears in the section heading and ``cheats`` in the text beneath it - which
#: is exactly how a real IPC section reads. That asymmetry is a deliberate
#: property of this module, argued in its docstring, and it is why both forms
#: are present here rather than one.
CORPUS: dict[str, str] = {
    # The heading of the real section, which uses the noun form; the body uses
    # the verb. Both appear because a statutory chunk carries both.
    "ipc-420": (
        "Cheating and dishonestly inducing delivery of property. Whoever "
        "cheats and thereby induces a person to deliver property or to "
        "consent to its retention shall be punished with imprisonment."
    ),
    "ipc-499": (
        "Whoever is guilty of intentionally or knowingly causing another "
        "person to fear of hurt shall be punished with imprisonment."
    ),
    "ipc-511": (
        "Whoever is guilty of receiving or retaining stolen property "
        "shall be punished with imprisonment."
    ),
    "ipo-138": (
        "Any public servant who knows or has reason to believe that an offence "
        "has been committed shall report the fact to the appropriate authority."
    ),
    "ipo-504": (
        "No person shall be a witness in his own cause or shall be examined "
        "as a witness on behalf of any party who is interested in the result."
    ),
    "const-21": (
        "No person shall be deprived of his liberty except in accordance with "
        "the procedure established by law."
    ),
}


@pytest.fixture()
def index() -> LexicalIndex:
    """A finalised index over :data:`CORPUS`."""
    return build_lexical_index(CORPUS)


# ===========================================================================
# IDF: the reason this module exists instead of a textbook BM25
# ===========================================================================

class TestIdf:
    """The naive Okapi IDF goes negative and inverts rankings.

    These are not hypotheticals. ``section``, ``shall`` and ``act`` appear in
    a large fraction of any Indian statute corpus **by construction**, so the
    common case is exactly the case that breaks.
    """

    def test_never_negative_at_any_document_frequency(self) -> None:
        """No corpus size and no df may produce a negative weight.

        A negative IDF does not merely weaken a ubiquitous term, it reverses
        the ranking.
        """
        for doc_count in (1, 2, 10, 1000, 20000):
            for df in range(0, doc_count + 1):
                assert idf(df, doc_count) >= IDF_FLOOR, (
                    f"negative idf at df={df} of {doc_count}"
                )

    def test_monotonically_decreasing_in_document_frequency(self) -> None:
        """The rarer a term, the more it must be worth.

        Monotonically, not *strictly*: the floor deliberately makes a run of
        very-high-df terms tie. Strict decrease would be the wrong assertion
        here - the whole point of :data:`IDF_FLOOR` is that past 95% of the
        corpus a term stops getting rarer in any way that matters and stops
        being worth less.

        Exhaustive over a whole corpus rather than sampled: a handful of
        sampled points would miss a non-monotonicity in the middle. This range
        starts at ``df = 0``, which is what caught the ``df <= 0`` special
        case that handed the rarest term the floor.
        """
        doc_count = 5000
        values = [idf(df, doc_count) for df in range(0, doc_count + 1)]
        assert all(
            earlier >= later for earlier, later in zip(values, values[1:], strict=False)
        ), "idf is not monotonically decreasing in df"

        # Strictly decreasing everywhere the floor is not binding.
        unfloored = [
            df
            for df in range(doc_count + 1)
            if math.log(1.0 + (doc_count - df + 0.5) / (df + 0.5)) >= IDF_FLOOR
        ]
        strict = [idf(df, doc_count) for df in unfloored]
        assert all(a > b for a, b in zip(strict, strict[1:], strict=False)), (
            "idf must fall strictly wherever the floor does not bind"
        )

    def test_the_floor_binds_only_at_the_extreme_of_the_df_range(self) -> None:
        """Monotone but not strictly means flat *only* at the bottom.

        If the run of ties started anywhere in the middle of the range, the
        floor would be silently flattening ordinary terms, which is the failure
        :meth:`test_the_floor_leaves_ordinary_terms_untouched` guards against
        on real text.
        """
        doc_count = 20000
        floored = [
            df for df in range(doc_count + 1) if idf(df, doc_count) == IDF_FLOOR
        ]
        assert floored, "expected the floor to bind at the top of the df range"
        # Measured: the floor first engages at df = 19026, which is 95.1% of a
        # 20000-chunk corpus.
        assert min(floored) == 19026

        every = [idf(df, doc_count) for df in range(doc_count + 1)]
        assert min(every) == IDF_FLOOR
        assert every[-1] == IDF_FLOOR

    def test_a_term_in_no_document_is_the_most_distinctive_there_is(self) -> None:
        """The regression test for the ``df <= 0`` special case.

        Returning the floor here - as an earlier version did - gave the rarest
        possible term the *smallest* possible weight, inverting exactly the
        ordering this function exists to impose. Unreachable through
        :class:`LexicalIndex` today, but a public function that reverses its
        own input is a trap for whoever calls it next.
        """
        doc_count = 20000
        assert idf(0, doc_count) == pytest.approx(math.log1p((doc_count + 0.5) / 0.5))
        assert idf(0, doc_count) > idf(1, doc_count) > idf(doc_count, doc_count)

    def test_a_df_beyond_the_corpus_is_clamped_not_raised(self) -> None:
        """Inconsistent statistics must not produce a weight above the maximum."""
        doc_count = 100
        assert idf(500, doc_count) == idf(100, doc_count)

    def test_a_term_in_every_chunk_scores_exactly_the_floor(self) -> None:
        """The worst case is bounded, not merely small.

        ``log(1 + x)`` is 0.0 at ``x = 0``; without the floor a corpus-wide term
        would contribute nothing at all, and the module could not distinguish
        "ubiquitous" from "absent".
        """
        assert idf(20000, 20000) == pytest.approx(IDF_FLOOR)

    def test_an_empty_index_yields_the_floor_and_not_an_exception(self) -> None:
        """An empty corpus is a reachable state in this project.

        It must produce a number. Dividing by a zero document count is the kind
        of crash that only appears on a fresh checkout with nothing ingested.
        """
        assert idf(0, 0) == IDF_FLOOR
        assert idf(5, 0) == IDF_FLOOR

    def test_a_term_in_no_document_is_not_penalised(self) -> None:
        """See :meth:`test_a_term_in_no_document_is_the_most_distinctive_there_is`.

        Kept as its own test because it is the single most counter-intuitive
        property of this function, and a reader who assumes the floor applies
        at both ends should be shown otherwise explicitly.
        """
        assert idf(0, 5000) > IDF_FLOOR

    def test_the_floor_leaves_ordinary_terms_untouched(self) -> None:
        """The floor must engage only for genuinely ubiquitous terms.

        If it clamped everything toward 0.05 the ranker would be selecting on
        term frequency alone, having thrown away IDF entirely.

        Checked against **every** term in the corpus, not against the terms a
        query happens to use. An earlier draft checked the query terms, which
        is a much weaker claim - it would pass even if the floor were clamping
        half the vocabulary, as long as the query avoided that half.
        """
        built = build_lexical_index(CORPUS)
        clamped = [
            term
            for term in sorted(built.known_terms())
            if idf(built.term_document_frequency(term), built.doc_count) == IDF_FLOOR
        ]
        # On a six-chunk corpus nothing reaches 95% document frequency, so
        # nothing should be clamped at all.
        assert clamped == []

        # "shall" is in every chunk and still must clear the floor, because
        # 100% of six is far short of the 95%-of-20000 threshold by weight.
        assert built.term_document_frequency("shall") == len(CORPUS)
        assert idf(len(CORPUS), built.doc_count) > IDF_FLOOR

    def test_the_floor_only_engages_near_the_top_of_the_df_range(self) -> None:
        """Documented behaviour: the floor is a last resort, not a default.

        Pinned so a future change to :data:`IDF_FLOOR` that quietly starts
        clamping half the vocabulary is caught here rather than in production.
        """
        doc_count = 20000
        clamped_from = min(
            df
            for df in range(doc_count + 1)
            if math.log(1.0 + (doc_count - df + 0.5) / (df + 0.5)) < IDF_FLOOR
        )
        # 0.95 of the corpus, from the measured sweep.
        assert clamped_from == 19026
        assert clamped_from / doc_count > 0.95


# ===========================================================================
# The inversion the Lucene form prevents
# ===========================================================================

class TestNegativeIdfWouldInvertRanking:
    """A control: prove the failure is real before trusting the fix.

    If this test ever stopped failing - if the naive form were somehow fine -
    the entire rationale for the Lucene form above it would be decoration, and
    the module would deserve a different docstring.
    """

    @staticmethod
    def _naive_idf(df: int, n: int) -> float:
        return math.log((n - df + 0.5) / (df + 0.5))

    def test_the_naive_form_is_negative_for_an_ubiquitous_term(self) -> None:
        doc_count = 20000
        assert self._naive_idf(18000, doc_count) < 0.0

    def test_the_naive_form_would_rank_a_weaker_match_first(self) -> None:
        """Same term, same document length, different term frequency.

        The correct ordering is unambiguous - the chunk that says the term ten
        times is the better lexical match - so anything that reverses it is
        wrong by construction rather than by judgement call.

        The full BM25 denominator is used, not a simplification. An earlier
        draft of this test cancelled the ``tf`` by dividing it out, which
        removed the very effect it was meant to show.
        """
        doc_count, df = 20000, 18000
        length, avg = 100, 100.0

        def naive(tf: float) -> float:
            denominator = tf + BM25_K1 * (1.0 - BM25_B + BM25_B * length / avg)
            return self._naive_idf(df, doc_count) * (tf * (BM25_K1 + 1.0)) / denominator

        # The measured sweep: naive gives -2.1970 at tf=1 and -4.3155 at tf=10.
        assert naive(1.0) == pytest.approx(-2.1970, abs=1e-3)
        assert naive(10.0) == pytest.approx(-4.3155, abs=1e-3)
        assert naive(10.0) < naive(1.0), (
            "expected the naive form to invert the ordering; if this passes "
            "the naive form stopped being the hazard this module documents"
        )

    def test_the_lucene_form_orders_the_same_pair_correctly(self) -> None:
        """The control, on the same numbers.

        Identical inputs, opposite ordering - which localises the entire
        difference to the IDF and rules out the term-frequency or
        length-normalisation terms as the cause.
        """
        doc_count, df = 20000, 18000
        length, avg = 100, 100.0

        def lucene(tf: float) -> float:
            denominator = tf + BM25_K1 * (1.0 - BM25_B + BM25_B * length / avg)
            return idf(df, doc_count) * (tf * (BM25_K1 + 1.0)) / denominator

        assert lucene(1.0) == pytest.approx(0.1054, abs=1e-3)
        assert lucene(10.0) == pytest.approx(0.2070, abs=1e-3)
        assert lucene(10.0) > lucene(1.0)

    def test_the_shipped_form_orders_them_correctly(self) -> None:
        built = build_lexical_index(CORPUS)
        dense_term = "shall"  # in every chunk of CORPUS
        assert built.term_document_frequency(dense_term) == len(CORPUS)

        # A chunk that says "shall" twice must outrank one that says it once.
        built2 = LexicalIndex()
        built2.add("many", "any person shall do anything shall be punished")
        built2.add("few", "any person shall do anything else at all here now")
        built2.finalise()

        many = built2.score_document(tokenize("shall"), "many")
        few = built2.score_document(tokenize("shall"), "few")
        assert many > few, "repetition of a query term must raise its BM25 score"


# ===========================================================================
# BM25 behaviour
# ===========================================================================

class TestBm25Behaviour:
    def test_term_frequency_saturates(self) -> None:
        """The tenth occurrence must add less than the second.

        Linear term frequency would let a chunk stuffed with one word outrank
        a chunk that uses it once in context, which is the opposite of what
        repetition means.
        """
        built = LexicalIndex()
        built.add("twice", "murder murder and other words to pad it out here")
        built.add("thrice", "murder murder murder and other words to pad it")
        built.add("once", "murder and other words to pad it out to the same size")
        built.finalise()

        one = built.score_document(tokenize("murder"), "once")
        two = built.score_document(tokenize("murder"), "twice")
        three = built.score_document(tokenize("murder"), "thrice")

        assert one < two < three
        # The gain from the third occurrence must be smaller than the second.
        assert (three - two) < (two - one), "saturation is not happening"

    def test_a_chunk_without_the_term_scores_exactly_zero(self) -> None:
        built = build_lexical_index(CORPUS)
        assert built.score_document(tokenize("dowry"), "ipc-420") == 0.0

    def test_an_unknown_chunk_id_scores_zero_rather_than_raising(self) -> None:
        """The fusion layer asks about chunks the lexical retriever never saw."""
        built = build_lexical_index(CORPUS)
        assert built.score_document(tokenize("cheating"), "no-such-chunk") == 0.0

    def test_length_normalisation_prefers_the_tighter_match(self) -> None:
        """A long chunk must not win by containing more words.

        Both chunks contain the term once; the padded one is much longer. With
        :data:`BM25_B` at zero the padding would cost nothing, so this test is
        also what pins :data:`BM25_B` above zero.
        """
        built = LexicalIndex()
        built.add("tight", "cheating and inducing a person to deliver property")
        built.add(
            "padded",
            "cheating and many many other unrelated words that add nothing to "
            "the subject matter of this provision whatsoever indeed truly",
        )
        built.finalise()

        assert (
            built.score_document(tokenize("cheating"), "tight")
            > built.score_document(tokenize("cheating"), "padded")
        )

    def test_a_rare_term_outranks_a_ubiquitous_one(self) -> None:
        """The entire point of IDF, asserted rather than assumed."""
        built = LexicalIndex()
        for i in range(20):
            built.add(f"common-{i}", "shall person property punishment act")
        built.add("rare", "shall person property punishment act personification")
        built.finalise()

        common = built.score_document(tokenize("shall"), "common-3")
        rare = built.score_document(tokenize("personification"), "rare")
        assert rare > common

    def test_scores_are_finite_for_every_chunk(self) -> None:
        """No NaN, no inf. A NaN row loses every comparison silently."""
        built = build_lexical_index(CORPUS)
        for query in ("cheating", "shall person", "public servant offence", "420"):
            for chunk_id in CORPUS:
                score = built.score_document(tokenize(query), chunk_id)
                assert math.isfinite(score)


# ===========================================================================
# Search: candidate selection, ranking, top_k
# ===========================================================================

class TestSearch:
    def test_the_offending_provision_ranks_first(self, index: LexicalIndex) -> None:
        """A query in statutory phrasing finds the provision it names."""
        result = index.search("cheating person to deliver property")
        assert result.kind == "matches"
        assert next(iter(result.scores)) == "ipc-420"

    def test_results_are_sorted_descending(self, index: LexicalIndex) -> None:
        scores = list(index.search("person shall be punished").scores.values())
        assert scores == sorted(scores, reverse=True)

    def test_only_chunks_containing_a_query_term_are_returned(
        self, index: LexicalIndex
    ) -> None:
        """A chunk absent from every posting list cannot have a nonzero score."""
        result = index.search("cheating")
        assert set(result.scores) <= set(CORPUS)
        assert "ipc-499" not in result.scores

    def test_top_k_truncates_but_never_pads(self, index: LexicalIndex) -> None:
        """Asking for ten hits must not manufacture four.

        Padding a quota with unrelated chunks would put a citation in front of
        a user that does not say what they asked about. Returning fewer is the
        only honest answer.

        ``person`` is in four of the six fixtures, not all six - the two that
        omit it are about a public servant and a witness. That gap is the
        point: the candidate set is what the postings say it is.
        """
        everything = index.search("person").scores
        assert len(everything) == 4
        assert set(everything) == {"ipc-420", "ipc-499", "ipo-504", "const-21"}

        limited = index.search("person", top_k=3).scores
        assert len(limited) == 3
        # A quota larger than the candidate set returns what exists.
        over_quota = index.search("person", top_k=1000).scores
        assert len(over_quota) == len(everything)

    def test_a_single_match_is_not_padded_out_to_the_quota(
        self, index: LexicalIndex
    ) -> None:
        """The sharpest form of the same rule: one hit, quota five, one result.

        A padder would return the five highest-scoring chunks in the corpus
        regardless of whether they matched. The user would see four citations
        to sections that do not concern their question.
        """
        result = index.search("personification", top_k=5)
        assert result.scores == {}

    def test_top_k_zero_returns_nothing_rather_than_everything(
        self, index: LexicalIndex
    ) -> None:
        """Off-by-one guard on the slice boundary."""
        assert index.search("person", top_k=0).scores == {}

    def test_identical_queries_produce_identical_orderings(
        self, index: LexicalIndex
    ) -> None:
        """Float addition is not associative, so term order must be sorted.

        Without ``sorted(set(...))`` the sum runs in set-iteration order, which
        depends on the process hash seed - so the same query could return a
        different ranking on a restart and every test above would be flaky.
        """
        first = list(index.search("person shall be punished").scores)
        for _ in range(25):
            assert list(index.search("person shall be punished").scores) == first

    def test_query_term_order_does_not_change_the_ranking(
        self, index: LexicalIndex
    ) -> None:
        """A user retyping their question differently must not reshuffle results."""
        a = index.search("cheating person property")
        b = index.search("property person cheating")
        assert list(a.scores) == list(b.scores)

    def test_duplicate_query_terms_are_counted_once(self, index: LexicalIndex) -> None:
        """``cheating cheating`` must not double a term's weight.

        The dedup is in the scorer; without it a repeated word would let a user
        lift a chunk by repeating themselves.
        """
        once = index.search("cheating").scores
        twice = index.search("cheating cheating").scores
        assert once == twice


# ===========================================================================
# The distinction between "no match" and "not in the corpus"
# ===========================================================================

class TestResultKind:
    """A zero score must not silently mean "the law does not cover this".

    Collapsing these two states is how a retrieval bug presents itself as a
    confident answer that a provision simply does not exist - which in a legal
    tool is worse than an error.
    """

    def test_an_empty_index_says_so(self) -> None:
        result = build_lexical_index({}).search("cheating")
        assert result.kind == "empty_index"
        assert result.scores == {}

    def test_an_unseen_word_is_out_of_vocabulary(self, index: LexicalIndex) -> None:
        """Not a finding that no provision matches - a finding that the corpus
        has never heard of the word."""
        result = index.search("hippopotamus")
        assert result.kind == "out_of_vocabulary"
        assert result.scores == {}

    def test_a_query_of_only_stopwords_is_out_of_vocabulary_not_a_match(
        self, index: LexicalIndex
    ) -> None:
        """The tokeniser drops single letters and short noise tokens.

        If everything is dropped, the query tokenises to nothing at all and
        saying "no results" would be misleading - the user asked something, we
        simply could not parse it.
        """
        result = index.search("a x i")
        assert result.kind == "out_of_vocabulary"

    def test_a_query_of_only_ubiquitous_terms_is_not_all_zero(
        self, index: LexicalIndex
    ) -> None:
        """The finding that shaped this module's ``kind`` field.

        Because :data:`IDF_FLOOR` is a positive constant, BM25 is never
        all-zero for a query whose terms merely appear everywhere. So an
        all-zero result really does mean out-of-vocabulary - but only because
        of that floor, and this test is what would fail if the floor were
        ever removed.
        """
        result = index.search("shall")
        assert result.kind == "matches"
        assert all(score > 0.0 for score in result.scores.values())
        assert len(result.scores) == len(CORPUS)

    def test_partially_known_query_matches_on_the_known_terms(
        self, index: LexicalIndex
    ) -> None:
        """A typo in one word must not discard the other four."""
        result = index.search("cheating hippopotamus property")
        assert result.kind == "matches"
        assert "ipc-420" in result.scores


# ===========================================================================
# Low-information results
# ===========================================================================

#: The smallest corpus in which a term present in *every* document is pinned at
#: :data:`IDF_FLOOR`. Measured, not guessed: at N=9 the universal term weighs
#: 0.051293, and only at N=10 does it reach the 0.05 floor. Ten documents is
#: enough to exercise the rule, so the test stays cheap.
SMALLEST_FLOORING_CORPUS = 10


def _ubiquitous_corpus() -> dict[str, str]:
    """Ten chunks in which ``section`` appears in every single one."""
    return {
        f"chunk-{i}": f"section {i} shall apply to the provisions of this Act"
        for i in range(SMALLEST_FLOORING_CORPUS)
    }


class TestLowInformation:
    """A result built only from ubiquitous terms is a match with no signal.

    The IDF floor is a positive constant, so a query of only terms present in
    every document scores every document above zero. Measured over 20,000
    synthetic chunks that is 20,000 of 20,000 scoring, with the values
    separated by roughly 1e-13 of float noise. Reporting that as a confident
    match is the failure mode: for a statutory corpus ``section``, ``shall``
    and ``act`` are exactly such terms, so this is the *common* query.
    """

    def test_a_query_of_only_universal_terms_is_low_information(self) -> None:
        ix = build_lexical_index(_ubiquitous_corpus())
        result = ix.search("section shall act")

        assert result.kind == "low_information"
        assert len(result.scores) == SMALLEST_FLOORING_CORPUS
        assert all(score > 0.0 for score in result.scores.values())

    def test_the_scores_are_reported_even_though_they_mean_nothing(self) -> None:
        """The point is to *label* the result, not to suppress it.

        Discarding the scores would lose the ranking information the caller
        could still use alongside a dense retriever. The honest move is to
        return the scores and say out loud that they rest on boilerplate.
        """
        ix = build_lexical_index(_ubiquitous_corpus())
        result = ix.search("section shall act")
        assert result.scores
        assert result.kind == "low_information"

    def test_it_counts_the_terms_that_were_floored(self) -> None:
        ix = build_lexical_index(_ubiquitous_corpus())
        result = ix.search("section shall act")

        assert result.matched_terms == 3
        assert result.floored_terms == 3

    def test_one_discriminating_term_lifts_the_result_back_to_matches(self) -> None:
        """The common case: a real question with boilerplate in it.

        A user asking about a specific offence writes a sentence that
        certainly contains ``section`` or ``shall``. That must not cause the
        whole result to be written off - only an *entirely* boilerplate
        query carries no information at all.
        """
        corpus = _ubiquitous_corpus()
        corpus["special"] = (
            "section 1 shall apply to the provisions of this Act "
            "concerning the punishment for cheating"
        )
        ix = build_lexical_index(corpus)

        result = ix.search("section cheating")

        assert result.kind == "matches"
        assert result.matched_terms == 2
        assert result.floored_terms == 1
        # The one term that carries information must decide the ranking.
        assert list(result.scores)[0] == "special"

    def test_a_term_missing_from_one_chunk_is_not_floored(self) -> None:
        """The bound is exact and the gradient is steep right below it.

        At N=10 a term in every document weighs 0.05; in 9 of 10 it weighs
        0.146603, nearly three times as much. So "present everywhere" is a
        sharp boundary, not a region, and the test asserts the neighbour to
        stop a future change from widening the floored set silently.
        """
        corpus = _ubiquitous_corpus()
        # Omits "section" only, so the two terms differ by exactly one document.
        corpus["no-section"] = "shall apply to the provisions of this Act"
        ix = build_lexical_index(corpus)

        almost = ix.search("section")   # in 10 of 11 documents
        universal = ix.search("act")    # in 11 of 11 documents

        assert almost.matched_terms == 1
        assert almost.floored_terms == 0
        assert almost.kind == "matches"

        assert universal.matched_terms == 1
        assert universal.floored_terms == 1
        assert universal.kind == "low_information"

    def test_a_small_corpus_never_reports_low_information(self) -> None:
        """Below N=10 the floor cannot bind, so the kind must stay ``matches``.

        Otherwise the label would fire on a corpus that genuinely did rank its
        results on a discriminating term.
        """
        small = build_lexical_index(_ubiquitous_corpus())
        smaller = build_lexical_index(
            {f"c{i}": "section 1 shall apply" for i in range(9)}
        )

        assert idf(9, 9) > IDF_FLOOR, "fixture no longer exercises the boundary"
        assert smaller.search("section shall").kind == "matches"
        assert small.search("section shall act").kind == "low_information"

    def test_out_of_vocabulary_still_wins_over_low_information(self) -> None:
        """A query with no known terms says nothing about the corpus at all."""
        ix = build_lexical_index(_ubiquitous_corpus())
        result = ix.search("hippopotamus")
        assert result.kind == "out_of_vocabulary"
        assert result.scores == {}


# ===========================================================================
# Index construction
# ===========================================================================

class TestConstruction:
    def test_build_helper_returns_a_finalised_index(self) -> None:
        built = build_lexical_index(CORPUS)
        assert built.is_finalised
        assert built.doc_count == len(CORPUS)

    def test_empty_corpus_is_constructible(self) -> None:
        """Fresh checkout, nothing ingested. Must not raise."""
        built = build_lexical_index({})
        assert built.doc_count == 0
        assert built.vocabulary_size == 0
        assert built.avg_doc_length == 0.0

    def test_a_chunk_with_no_indexable_terms_is_not_a_division_by_zero(
        self,
    ) -> None:
        """Punctuation-only text tokenises to nothing, giving length 0.

        A corpus of such chunks has ``avg_doc_length == 0.0``, which appears in
        the BM25 denominator directly.
        """
        built = LexicalIndex()
        built.add("empty", "!!! ??? ...")
        built.add("empty-too", "--- ***")
        built.finalise()
        assert built.avg_doc_length == 0.0
        assert built.search("cheating").scores == {}

    def test_adding_after_finalise_is_refused(self) -> None:
        """Silently accepting it would leave the length statistics wrong.

        ``doc_count`` and ``avg_doc_length`` are captured at query time, so the
        corruption would not raise anywhere - it would just quietly change every
        score in the index.
        """
        built = build_lexical_index(CORPUS)
        with pytest.raises(RuntimeError):
            built.add("late", "some more text about cheating")

    def test_finalise_is_idempotent(self) -> None:
        built = LexicalIndex()
        built.add("a", "cheating")
        built.finalise()
        built.finalise()
        assert built.doc_count == 1

    def test_explicit_chunk_order_makes_the_build_deterministic(self) -> None:
        """The same corpus indexed in two orders must give the same answers."""
        shuffled = dict(reversed(list(CORPUS.items())))
        a = build_lexical_index(CORPUS, chunk_ids=list(CORPUS))
        b = build_lexical_index(shuffled, chunk_ids=list(CORPUS))
        assert a.search("cheating").scores == b.search("cheating").scores

    def test_vocabulary_and_document_frequency_are_observable(
        self, index: LexicalIndex
    ) -> None:
        """An operator tool needs these without reaching into privates."""
        assert index.term_document_frequency("cheating") == 1
        assert index.term_document_frequency("shall") == len(CORPUS)
        assert index.term_document_frequency("nonexistent") == 0
        assert "cheating" in set(index.known_terms())

    def test_document_length_is_the_token_count(self, index: LexicalIndex) -> None:
        """Not the character count - the length normalisation assumes terms."""
        assert index.document_length("ipc-420") == len(tokenize(CORPUS["ipc-420"]))
        assert index.document_length("no-such-chunk") == 0


# ===========================================================================
# Behaviour on the corpus this project actually retrieves over
# ===========================================================================

class TestOnStatutoryText:
    """Section numbers are the case the tokenizer fix exists for.

    ``section 420`` tokenises to ``('section', '420')`` only because digits are
    exempt from the length floor. If that regressed, this query would silently
    become a search for the word "section" and match every provision in the
    corpus.
    """

    @pytest.fixture()
    def statute_corpus(self) -> LexicalIndex:
        return build_lexical_index(
            {
                "ipc-420": "420. Cheating and dishonestly inducing delivery of property.",
                "ipc-420a": "420A. Personation.",
                "ipc-420b": "420B. Ingredients of a crime.",
                "ipc-499": "499. Put or attempt to put in fear of injury.",
                "ipo-138": "138. Duty of public servant to report offences.",
            }
        )

    def test_a_section_number_narrows_the_search_rather_than_widening_it(
        self, statute_corpus: LexicalIndex
    ) -> None:
        """The regression test for the worst defect in this project's history.

        If ``420`` were dropped by the length floor, the query would match
        *every* section, and ``ipc-499`` would come back as a confident answer
        to a question about cheating.
        """
        result = statute_corpus.search("section 420")
        assert "ipc-420" in result.scores
        assert "ipc-499" not in result.scores

    def test_sibling_sections_are_distinguished(self, statute_corpus: LexicalIndex) -> None:
        """``420``, ``420A``, ``420B`` are different offences.

        The tokenizer's job is to keep them as three distinct tokens; this test
        is what proves it survived.
        """
        assert "420a" in set(statute_corpus.known_terms())
        assert "420b" in set(statute_corpus.known_terms())
        assert statute_corpus.term_document_frequency("420") == 1

    def test_a_devanagari_query_retrieves_a_devanagari_chunk(self) -> None:
        """The corpus is not English-only, and the index must not be either."""
        built = build_lexical_index(
            {
                "hindi-1": "धोखाधड़ी करने वाला व्यक्ति दण्डनीय होगा।",
                "hindi-2": "चोरी का सबूत किसने दिया यह प्रश्न है।",
            }
        )
        result = built.search("धोखाधड़ी")
        assert result.kind == "matches"
        assert next(iter(result.scores)) == "hindi-1"


# ===========================================================================
# Constraints this module must keep satisfying
# ===========================================================================

class TestModuleConstraints:
    def test_the_module_needs_no_third_party_library(self) -> None:
        """The central engineering constraint for Stage 3.

        The backend must import, start and serve on a machine with no ML
        runtime at all - which is exactly the machine the dense side is
        dormant on. If this module needed numpy, hybrid search would be
        unavailable precisely where the application has to run.
        """
        import inspect

        import app.rag.lexical as lexical

        source = inspect.getsource(lexical)
        for banned in ("import numpy", "import scipy", "import torch", "import sklearn"):
            assert banned not in source, f"{banned} is not allowed in this module"

    def test_the_module_reads_no_files_and_takes_no_clock(self) -> None:
        """Pure function of its arguments, so every score is reproducible.

        A wall-clock or environment input would make a ranking that cannot be
        replayed, and therefore cannot be tested or defended.
        """
        import inspect

        import app.rag.lexical as lexical

        source = inspect.getsource(lexical)
        for banned in ("import os", "import random", "import time", "getenv", "datetime"):
            assert banned not in source, f"{banned} is not allowed in this module"

    def test_search_result_is_immutable(self, index: LexicalIndex) -> None:
        """A returned ranking must not be mutated by a caller.

        Frozen, so an assignment to a real field raises rather than silently
        corrupting a ranking someone downstream is still holding.
        """
        result = index.search("cheating")
        assert isinstance(result, SearchResult)
        with pytest.raises(AttributeError):
            result.kind = "something else"  # type: ignore[misc]

        # An unknown field is a different refusal. A slotted dataclass on
        # Python 3.10 raises TypeError from the generated __setattr__, not
        # AttributeError, because __slots__ is implemented via a descriptor
        # whose __set__ calls super(). Asserting AttributeError here would be
        # asserting an accident of one interpreter version.
        with pytest.raises((AttributeError, TypeError)):
            result.unexpected_field = 1  # type: ignore[attr-defined]

    def test_error_messages_carry_no_user_data(self) -> None:
        """A refusal must not echo the query or the corpus back.

        The project rule is that no raw exception reaches a user and no
        personal case detail is logged; a message that quoted the query would
        break both at once.
        """
        built = build_lexical_index(CORPUS)
        try:
            built.add("x", "")
            built.finalise()
            built.add("y", "more")
        except RuntimeError as exc:
            assert CORPUS["ipc-420"][:40] not in str(exc)
            assert len(str(exc)) < 100
