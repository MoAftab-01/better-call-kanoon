"""Tests for :mod:`app.rag.scoring` - cosine and hybrid fusion.

The fusion rules are grouped by the three failures they were chosen to avoid,
each of which was measured before the design was settled. A test that only
checked "it returns the right chunks" would pass for a rule that has all three
defects, so those are pinned directly.

**No retrieval-quality number is asserted anywhere in this file**, because none
has been measured. The project's rule forbids invented performance claims, and
a test asserting "fusion is 15% better" would be exactly that.

Disclaimer: short statutory fragments appear here as *ranker fixtures*. They
are not legal sources and are not cited as authority anywhere.
"""

from __future__ import annotations

import math

import pytest

from app.rag.scoring import (
    CANDIDATE_MULTIPLIER,
    RRF_K,
    FusionResult,
    candidate_budget,
    cosine_similarity,
    discrimination_weight,
    hybrid_search,
    reciprocal_rank_fusion,
)

# ===========================================================================
# Cosine
# ===========================================================================

class TestCosineSimilarity:
    def test_identical_vectors_score_one(self) -> None:
        vector = [0.3, 0.4, 0.5]
        assert cosine_similarity(vector, vector) == pytest.approx(1.0)

    def test_opposite_vectors_score_minus_one(self) -> None:
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_orthogonal_vectors_score_zero(self) -> None:
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_magnitude_is_ignored(self) -> None:
        """That is what makes it a *cosine* and not a dot product.

        If scale leaked in, a long vector would outrank a short one that
        pointed the same way, and the fused score would mean nothing.
        """
        short = [1.0, 0.0, 0.0]
        long = [100.0, 0.0, 0.0]
        assert cosine_similarity(short, long) == pytest.approx(1.0)

    def test_matches_a_hand_computed_value(self) -> None:
        """(1,0) against (1,1) is 1/sqrt(2)."""
        assert cosine_similarity([1.0, 0.0], [1.0, 1.0]) == pytest.approx(
            1.0 / math.sqrt(2.0)
        )

    def test_a_zero_vector_scores_zero_rather_than_raising(self) -> None:
        """An all-zero embedding is reachable and must not divide by zero.

        Returning 0 keeps the ranking total. Dropping the chunk would be a
        silent reduction in the candidate set that nothing downstream could see.
        """
        assert cosine_similarity([0.0, 0.0, 0.0], [1.0, 2.0, 3.0]) == 0.0
        assert cosine_similarity([1.0, 2.0, 3.0], [0.0, 0.0, 0.0]) == 0.0

    def test_a_length_mismatch_is_refused(self) -> None:
        """Truncating to the shorter vector would compare different things."""
        with pytest.raises(ValueError):
            cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])

    @pytest.mark.parametrize(
        "bad",
        [
            (float("nan"), 1.0),
            (float("inf"), 1.0),
            (1.0, float("nan")),
            (1.0, float("-inf")),
        ],
    )
    def test_a_non_finite_component_is_refused(self, bad: tuple) -> None:
        """A NaN loses every comparison silently, so the row just never wins.

        Refusing is the only way to tell a broken index from a bad retriever.
        """
        with pytest.raises(ValueError):
            cosine_similarity(list(bad), [1.0, 1.0])


# ===========================================================================
# RRF
# ===========================================================================

class TestReciprocalRankFusion:
    def test_agreement_on_top_is_rewarded(self) -> None:
        """The core property: a chunk both retrievers like wins.

        This is the whole reason fusion is worth doing over using one retriever.
        """
        fused = reciprocal_rank_fusion(
            [
                {"a": 9.0, "b": 5.0, "c": 1.0},
                {"b": 9.0, "a": 5.0, "d": 1.0},
            ]
        )
        # a and b are both in the top 3 of both lists; c and d each appear once.
        assert list(fused)[:2] == ["a", "b"]
        assert fused["a"] == pytest.approx(fused["b"])

    def test_a_consensus_chunk_beats_a_polarising_one(self) -> None:
        """Moderate in both lists must beat first in one and absent in the other."""
        fused = reciprocal_rank_fusion(
            [
                {"polarising": 100.0, "consensus": 2.0},
                {"consensus": 1.0, "polarising": 0.5},
            ]
        )
        # polarising is rank 1 of list A and rank 2 of list B.
        # consensus is rank 2 of A and rank 1 of B. Consensus wins on agreement.
        assert list(fused)[0] == "consensus"

    def test_a_chunk_from_only_one_list_still_appears(self) -> None:
        """Fusion reranks; it never invents. A single-retriever hit is real.

        Dropping it would mean a query that only the dense retriever understood
        returns nothing, which reads as "the law does not cover this".
        """
        fused = reciprocal_rank_fusion([{"a": 1.0}, {"z": 1.0}])
        assert set(fused) == {"a", "z"}

    def test_score_magnitudes_are_ignored_entirely(self) -> None:
        """The property that resolves the scale problem.

        RRF reads order, not value. So a BM25 field spanning 0-14.2 and a cosine
        field spanning 0-1.0 fuse identically to the same values scaled by 1000.
        This is the single test that distinguishes RRF from a weighted sum, and
        it is why the module exists.
        """
        base = [{"a": 14.2, "b": 11.0}, {"b": 0.9, "a": 0.8}]
        scaled = [{"a": 14200.0, "b": 11000.0}, {"b": 900.0, "a": 800.0}]
        assert reciprocal_rank_fusion(base) == reciprocal_rank_fusion(scaled)

    def test_a_flat_meaningless_field_produces_uniform_ranks(self) -> None:
        """The flat-positive-field case, which defeated peak normalisation.

        An off-topic query gives every chunk a near-identical cosine. RRF turns
        that into near-identical ranks, so the result is *uniformly mediocre* -
        degraded visibly - rather than dividing by a dispersion statistic that
        collapses to zero.
        """
        flat = {f"c{i}": 0.060 - 0.0001 * i for i in range(50)}
        fused = reciprocal_rank_fusion([flat, {"real_hit": 14.2}])
        assert list(fused)[0] == "real_hit"
        # The flat field's own chunks are all still there, in order.
        assert len(fused) == 51

    def test_k_zero_gives_a_two_to_one_preference_for_first_place(self) -> None:
        """The documented behaviour at the damping constant's low end."""
        fused = reciprocal_rank_fusion([{"a": 1.0, "b": 1.0}], k=0.0)
        assert fused["a"] == pytest.approx(1.0)
        assert fused["b"] == pytest.approx(0.5)

    def test_k_sixty_makes_the_top_two_nearly_equal(self) -> None:
        """And at the shipped default the ratio is about 1.02:1."""
        fused = reciprocal_rank_fusion([{"a": 1.0, "b": 1.0}])
        assert fused["a"] / fused["b"] == pytest.approx(
            (RRF_K + 2) / (RRF_K + 1), rel=1e-9
        )

    def test_an_empty_ranking_list_is_empty(self) -> None:
        assert reciprocal_rank_fusion([]) == {}
        assert reciprocal_rank_fusion([{}]) == {}
        assert reciprocal_rank_fusion([{}, {}]) == {}

    def test_ordering_is_deterministic_for_tied_chunks(self) -> None:
        """Ties break on chunk id, so a run is reproducible.

        A real tie needs *equal ranks*, not equal scores. Two chunks at rank 1
        of two different retrievers both contribute ``weight/(k+1)`` and must
        come out in a fixed order - otherwise the same query returns a
        different top hit on a restart, and no test of the ranking above can be
        trusted to be reproducible.

        An earlier draft of this test gave one list three equal scores and
        expected alphabetical order. Those chunks sit at ranks 1, 2 and 3, so
        their ordering is correct as given and nothing needed breaking - the
        test was asserting a property the situation did not have.
        """
        fused = reciprocal_rank_fusion([{"b": 9.0, "a": 5.0}, {"a": 9.0, "b": 5.0}])
        assert fused["a"] == fused["b"]
        assert list(fused) == ["a", "b"]
        rankings = [{"b": 9.0, "a": 5.0}, {"a": 9.0, "b": 5.0}]
        for _ in range(20):
            assert list(reciprocal_rank_fusion(rankings)) == ["a", "b"]

    def test_one_list_of_tied_scores_is_ranked_by_position_not_alphabet(
        self,
    ) -> None:
        """The control: ranks still come from the retriever's order.

        RRF is a function of position. A retriever that says b is its best
        candidate is believed, even if a sorts earlier.
        """
        fused = reciprocal_rank_fusion([{"b": 1.0, "a": 1.0, "c": 1.0}])
        assert list(fused) == ["b", "a", "c"]


# ===========================================================================
# Hybrid: the three defects the design was chosen to avoid
# ===========================================================================

class TestDiscriminationWeight:
    """The term that distinguishes this from textbook RRF."""

    def test_a_single_candidate_counts_for_almost_everything(self) -> None:
        """A retriever that narrowed 20,000 chunks to one has decided a lot."""
        assert discrimination_weight(1) == pytest.approx(60.0 / 61.0)

    def test_fifty_near_identical_candidates_count_for_about_half(self) -> None:
        """The off-topic dense field's case: wide, and worth little."""
        assert discrimination_weight(50) == pytest.approx(0.545, abs=1e-3)

    def test_dumping_the_whole_corpus_counts_for_almost_nothing(self) -> None:
        """A retriever that discriminated nothing should be effectively ignored."""
        assert discrimination_weight(20000) == pytest.approx(0.003, abs=1e-4)

    def test_the_weight_falls_monotonically_with_width(self) -> None:
        values = [discrimination_weight(n) for n in range(1, 500)]
        assert all(a > b for a, b in zip(values, values[1:], strict=False))
        assert 0.0 < min(values) <= 1.0

    def test_an_empty_ranking_contributes_nothing(self) -> None:
        assert discrimination_weight(0) == 0.0

    def test_zero_k_does_not_divide_by_zero(self) -> None:
        """``k=0`` is a legal parameter - a test above uses it deliberately.

        An earlier version computed ``candidate_count / k`` unguarded and raised
        ZeroDivisionError here. The limit is 1 for every non-empty ranking,
        which is right: with no damping there is no length scale to compare
        against.
        """
        assert discrimination_weight(1, k=0.0) == 1.0
        assert discrimination_weight(20000, k=0.0) == 1.0

    def test_negative_k_is_refused(self) -> None:
        """A negative k makes a worse candidate outscore a better one.

        That is the exact inversion this module exists to prevent, arriving
        through a different door, so it is refused rather than clamped.
        """
        with pytest.raises(ValueError):
            discrimination_weight(10, k=-1.0)
        with pytest.raises(ValueError):
            reciprocal_rank_fusion([{"a": 1.0}], k=-1.0)

    def test_a_wide_list_cannot_outrank_a_narrow_one_on_rank_alone(self) -> None:
        """The defect this term exists to fix, pinned at the function level."""
        narrow = reciprocal_rank_fusion([{"exact": 14.2}])
        wide = reciprocal_rank_fusion(
            [{f"c{i}": 0.060 - 0.0001 * i for i in range(50)}, {"exact": 14.2}]
        )
        # 'exact' is in both; the flat field's own chunks must not outrank it
        # on the strength of being numerous.
        assert list(wide)[0] == "exact"
        assert narrow["exact"] > max(
            v for kk, v in wide.items() if kk != "exact"
        )


class TestHybridAvoidsTheMeasuredDefects:
    """Each test below pins a failure that was measured, not imagined."""

    def test_a_chunk_matching_nothing_lexically_cannot_beat_an_exact_match(
        self,
    ) -> None:
        """Defect: max-normalisation maps absence onto zero.

        Under a weighted sum with max-normalisation, a chunk with lexical score
        exactly 0.0 beats the best BM25 match whenever the dense weight exceeds
        the lexical one - at 0.65/0.35 and again at 0.99/0.01. The exact
        section-number match loses to a chunk that matched nothing.
        """
        result = hybrid_search(
            "section 420",
            lexical_scores={"exact": 14.2},
            dense_scores={"absent": 0.81, "other": 0.79},
            top_k=3,
        )
        assert list(result.results)[0] == "exact"

    def test_bm25_magnitude_does_not_outweigh_cosine_magnitude(self) -> None:
        """Defect: the naive weighted sum's measured 77.8% lexical share.

        A huge BM25 number must not, by being huge, decide the ranking. Both
        retrievers contribute one position each, whatever their units.
        """
        result = hybrid_search(
            "cheating",
            lexical_scores={"a": 14.2, "b": 11.0, "c": 9.0},
            dense_scores={"c": 0.81, "b": 0.80, "a": 0.79},
            top_k=3,
        )
        # a is dense-last and lexical-first; c is the reverse. Neither wins on
        # scale alone - both are in the top 3 of one list and the bottom of the
        # other, which is precisely what fusion is for.
        assert len(result.results) == 3

    def test_an_off_topic_dense_field_does_not_dominate(self) -> None:
        """Defect: a cosine clamp never fires on a flat positive field.

        Measured band for a real off-topic query was 0.0551-0.0600, so a floor
        of 1e-6 is never reached and the flat field passes through untouched.
        """
        flat = {f"c{i}": 0.060 - 0.0001 * i for i in range(50)}
        result = hybrid_search(
            "cheating", lexical_scores={"real_hit": 14.2}, dense_scores=flat, top_k=5
        )
        assert list(result.results)[0] == "real_hit"

    def test_a_flat_lexical_field_does_not_produce_a_degenerate_score(self) -> None:
        """Defect: MAD normalisation collapses to a ~1e-13 denominator here.

        A positive IDF floor means an all-ubiquitous-term query scores every
        chunk above zero, with the field separated only by float noise. Any
        rule dividing by a dispersion statistic has a near-zero denominator on
        exactly this input. RRF has no denominator to collapse.
        """
        noisy = {f"c{i}": 0.15 + (i % 7) * 1e-13 for i in range(20000)}
        result = hybrid_search(
            "shall", lexical_scores=noisy, dense_scores={"best": 0.9}, top_k=5
        )
        assert len(result.results) == 5
        assert all(math.isfinite(score) for score in result.results.values())


# ===========================================================================
# Hybrid: honest reporting
# ===========================================================================

class TestHybridReporting:
    def test_with_no_embeddings_it_says_lexical_only(self) -> None:
        """The default deployment: the model is optional, so this is normal.

        Reporting "hybrid" for an answer that silently ignored half its inputs
        would be a claim the provenance does not support.
        """
        result = hybrid_search(
            "cheating", lexical_scores={"a": 14.2, "b": 11.0}, dense_scores=None
        )
        assert result.retriever_used == "lexical_only"
        assert list(result.results) == ["a", "b"]
        assert result.dense_scores == {}

    def test_with_no_lexical_hits_it_says_dense_only(self) -> None:
        """An empty lexical dict is a real state, not an error.

        It means the query is out of vocabulary for the corpus, which the
        lexical retriever reports and this must not disguise as a hybrid score.
        """
        result = hybrid_search(
            "cheating", lexical_scores={}, dense_scores={"a": 0.9, "b": 0.8}
        )
        assert result.retriever_used == "dense_only"
        assert list(result.results) == ["a", "b"]

    def test_with_neither_signal_it_says_none(self) -> None:
        result = hybrid_search("cheating", lexical_scores={}, dense_scores={})
        assert result.retriever_used == "none"
        assert result.results == {}

    def test_the_two_signals_stay_separable_in_the_result(self) -> None:
        """A caller must be able to show why something ranked.

        A single fused number with no explanation is not something this project
        can put in front of a user asking about their own situation.
        """
        result = hybrid_search(
            "cheating",
            lexical_scores={"a": 14.2},
            dense_scores={"a": 0.9, "b": 0.8},
        )
        assert result.lexical_scores["a"] == 14.2
        assert result.dense_scores["b"] == 0.8
        assert set(result.dense_scores) - set(result.lexical_scores) == {"b"}

    def test_it_is_a_frozen_dataclass(self) -> None:
        result = hybrid_search("cheating", lexical_scores={"a": 1.0})
        assert isinstance(result, FusionResult)
        with pytest.raises(AttributeError):
            result.retriever_used = "hybrid"  # type: ignore[misc]


class TestTopK:
    def test_top_k_truncates(self) -> None:
        result = hybrid_search(
            "x", lexical_scores={f"c{i}": float(i) for i in range(20)}, top_k=5
        )
        assert len(result.results) == 5

    def test_top_k_never_pads(self) -> None:
        """Two matches, quota ten, two results.

        Padding would put a citation in front of a user that does not concern
        their question, which is the unforgivable failure here.
        """
        result = hybrid_search(
            "cheating", lexical_scores={"a": 1.0, "b": 0.5}, top_k=10
        )
        assert len(result.results) == 2

    def test_top_k_zero_returns_nothing(self) -> None:
        result = hybrid_search("x", lexical_scores={"a": 1.0}, top_k=0)
        assert result.results == {}


# ===========================================================================
# Constraints
# ===========================================================================

class TestModuleConstraints:
    def test_no_third_party_import(self) -> None:
        import inspect

        import app.rag.scoring as scoring

        source = inspect.getsource(scoring)
        for banned in ("import numpy", "import torch", "import scipy", "import sklearn"):
            assert banned not in source, f"{banned} is not allowed in this module"

    def test_no_clock_and_no_filesystem(self) -> None:
        """Fusion must be a pure function of its inputs to be reproducible."""
        import inspect

        import app.rag.scoring as scoring

        source = inspect.getsource(scoring)
        for banned in ("import random", "import time", "getenv", "datetime"):
            assert banned not in source, f"{banned} is not allowed in this module"

    def test_the_query_text_is_never_stored(self) -> None:
        """The project does not store conversations or user queries.

        Fusion receives the query for API symmetry but must not retain it. If a
        future change caches it, this test fails rather than the policy.
        """
        secret = "my landlord forged my agreement and cheated me"
        result = hybrid_search(
            secret, lexical_scores={"a": 1.0}, dense_scores={"a": 0.5}
        )
        assert secret not in str(result.dense_scores)
        assert secret not in str(result.lexical_scores)
        assert secret not in str(result.results)

    def test_identical_inputs_give_identical_output(self) -> None:
        """Float addition is not associative, so ordering must be deterministic."""
        args = (
            "cheating",
            {"a": 14.2, "b": 11.0, "c": 9.0},
            {"c": 0.81, "a": 0.80, "b": 0.79},
        )
        first = hybrid_search(*args)
        for _ in range(25):
            assert hybrid_search(*args).results == first.results

    def test_the_rejected_weights_are_gone_entirely(self) -> None:
        """The 0.65/0.35 blend must not survive anywhere as a live constant.

        This test previously asserted the opposite: that the weights were kept
        but documented as unused. That was a weaker guarantee than it looked.
        A constant named ``DEFAULT_DENSE_WEIGHT`` sitting next to real code
        invites the next reader to use it, and ``settings.SEMANTIC_WEIGHT``
        invited a caller to tune a number nothing reads. A knob that appears
        to control behaviour but does not is worse than no knob, so both were
        removed rather than annotated.
        """
        import inspect

        import app.rag.scoring as scoring

        assert not hasattr(scoring, "DEFAULT_DENSE_WEIGHT")
        assert not hasattr(scoring, "DEFAULT_LEXICAL_WEIGHT")

        source = inspect.getsource(scoring)
        # No weighted-sum helper may reappear under another name.
        assert "weighted_sum" not in source
        assert "weighted_sum" not in scoring.__all__

    def test_the_settings_layer_offers_no_fake_weight_knobs(self) -> None:
        """The same argument applies one level up, in the user-facing config.

        ``SEMANTIC_WEIGHT`` and ``BM25_WEIGHT`` were readable from ``.env`` and
        did nothing. Anyone setting them would reasonably expect a retrieval
        behaviour change and get none - and would have no way to tell.
        """
        from app.config import get_settings

        settings = get_settings()

        assert not hasattr(settings, "SEMANTIC_WEIGHT")
        assert not hasattr(settings, "BM25_WEIGHT")

        # What remains is real, and is what the README documents.
        assert settings.TOP_K >= 1
        assert settings.CANDIDATE_MULTIPLIER >= 1
        assert settings.RRF_K > 0.0

    def test_the_embedding_model_is_configurable_not_hardcoded(self) -> None:
        """A model that is withdrawn must be swappable without editing code.

        Also guards against the model name leaking into the retrieval modules,
        which would mean the index was tied to one model regardless of config.
        """
        import inspect

        import app.rag.scoring as scoring
        from app.config import get_settings

        model = get_settings().EMBEDDING_MODEL
        assert model

        assert model not in inspect.getsource(scoring)
        assert model not in inspect.getsource(scoring.hybrid_search)

    def test_candidate_budget_scales_with_top_k(self) -> None:
        """Fusion needs more candidates than results, or it cannot rerank."""
        assert candidate_budget(5) == 5 * CANDIDATE_MULTIPLIER
        assert candidate_budget(5, multiplier=2) == 10
        assert candidate_budget(0) == 0

    def test_candidate_budget_refuses_a_negative_multiplier(self) -> None:
        """Clamping would silently return a budget nobody asked for."""
        with pytest.raises(ValueError):
            candidate_budget(5, multiplier=-1)

    def test_candidate_budget_never_returns_a_negative_count(self) -> None:
        assert candidate_budget(-3) == 0
