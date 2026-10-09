"""Cosine scoring and hybrid fusion - where the two retrievers become one ranking.

**The problem this module exists to solve.** BM25 is unbounded above; cosine
similarity lives in ``[-1, 1]``. A weighted sum like ``0.65 * cos + 0.35 * bm25``
therefore does not apply the weights it appears to: measured across corpus
sizes of 50, 500 and 5000 chunks, the lexical share of that sum came out at
**77.8%, 76.0% and 44.4%** - not the configured 35%. The weights are not
wrong, they are *scale-blind*.

Three repairs were measured before one was chosen, and the reasons they were
rejected are recorded here because they are the reason the fourth exists.

**Max-normalisation** (``score / max(score)``) fixes the scale and creates a
worse problem: a chunk with a lexical score of exactly ``0.0`` beats the best
BM25 match whenever the dense weight exceeds the lexical one, because "absent"
and "present but weak" both map onto ``0.0``. At 0.65/0.35 and again at
0.99/0.01, a chunk matching nothing lexically outranks a chunk matching an
exact section number.

**Clamping cosine at zero** does not help, because an off-topic query produces
a flat *positive* cosine field, not a negative one - measured band
0.0551 to 0.0600 - so a floor of ``1e-6`` never fires. Mean-normalisation maps
that same flat field to approximately 1.0. Neither peak- nor mean-normalisation
can tell "flat and meaningless" from "peaked and meaningful".

**Normalising by a dispersion statistic** (``median + k * MAD``) is the standard
remedy, and it is **degenerate on this corpus**. Because the IDF floor is a
positive constant, a query of only ubiquitous terms scores *every* chunk above
zero - 20,000 of 20,000 chunks, measured - with the scores separated by about
1e-13 of float noise. The MAD of that field is ~1e-13, so the denominator
collapses. And this is not a corner case: in Indian statute ``section``,
``shall`` and ``act`` appear in most chunks by construction, so the inputs that
break the rule are the ones the corpus produces most often.

**Reciprocal rank fusion is what this module implements**, and the reason is
that ranks carry no scale at all. RRF combines *positions*, so the scale
mismatch that defeats a weighted sum cannot arise, absence is not a score of
zero but an absence from the list, and a flat meaningless field produces
uniformly poor ranks rather than a collapsed denominator. It sidesteps all
three rejected repairs at once.

**One departure from textbook RRF**, and it is load-bearing. Vanilla RRF gives a
retriever's rank-1 item the same ``1/(k+1)`` whether that retriever narrowed
20,000 chunks down to **one** or down to **fifty near-identical scores**. Those
are not equal claims. On an off-topic query the measured dense field returns
50 chunks with cosine scores inside a 0.0551-0.0600 band - it has expressed no
opinion - while a lexical retriever that returns a single chunk has said the
corpus contains exactly one provision matching those terms. Vanilla RRF ties
them, and the tie is then broken alphabetically, which put ``absent`` above
``exact`` in the test that caught this.

So each retriever is weighted by how much it actually narrowed:

``weight_i = 1 / (1 + n_i / k)``

A retriever that returned one candidate is weighted 0.98 at ``k=60``; one that
returned fifty is weighted 0.55; one that dumped the whole 20,000-chunk corpus
is weighted 0.003 and is effectively ignored, which is the correct treatment
for a retriever that discriminated nothing. This uses no constant beyond the
already-documented ``k``, and needs no absolute score threshold - which matters,
because no evaluation has been run and so no threshold could honestly be set.

**The 0.65/0.35 weights are gone from this module and from ``settings``.** They
were kept here for a while, annotated as unused. That was a weaker guarantee than
it looked: a constant named ``DEFAULT_DENSE_WEIGHT`` beside live code invites the
next reader to use it, and ``SEMANTIC_WEIGHT`` in ``.env`` invited a user to tune
a number nothing read. A setting that looks load-bearing but is not is worse than
one that is absent, because its effect cannot be observed. ``settings`` now offers
``TOP_K``, ``CANDIDATE_MULTIPLIER`` and ``RRF_K``, all read by real code, and a
test asserts the removed names stay removed.

**What is still unvalidated.** No evaluation has been run for this project, so
no claim is made that this retrieves better than any alternative, and no
retrieval-quality number appears anywhere in this codebase or its README. The
weights below are documented defaults, not tuned values.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

__all__ = [
    "CANDIDATE_MULTIPLIER",
    "RRF_K",
    "FusionResult",
    "candidate_budget",
    "cosine_similarity",
    "discrimination_weight",
    "hybrid_search",
    "reciprocal_rank_fusion",
]


#: The damping constant in ``1 / (k + rank)``.
#:
#: 60 is the value from the original RRF paper and the one most RRF
#: implementations use. It controls how sharply rank 1 is preferred over rank 2:
#: at k=0 the top two are worth 1.0 and 0.5, a ratio of 2:1; at k=60 they are
#: worth 1/61 and 1/62, a ratio of about 1.02:1. **Not tuned for this corpus.**
#:
#: Overridable via the ``RRF_K`` setting; this module default applies when the
#: caller does not pass one. It is not read from ``settings`` when this module
#: loads, because :func:`hybrid_search` takes its values as arguments and a
#: module that captured global config could not be tested against a different
#: corpus.
RRF_K: float = 60.0


#: How many candidates to pull from each retriever before fusing.
#:
#: Fusion can only rerank what it is given, so a retriever that returns only 5
#: candidates bounds what fusion can do with it. Multiplying the requested
#: final ``TOP_K`` is the cheap approximation of "give me enough to rerank".
#:
#: **Not validated.** There is no recall measurement behind this number.
CANDIDATE_MULTIPLIER: int = 4


def candidate_budget(top_k: int, multiplier: int = CANDIDATE_MULTIPLIER) -> int:
    """How many candidates to pull from each retriever for a given ``TOP_K``.

    Args:
        top_k: The number of results the caller wants back.
        multiplier: Candidates to request per wanted result. Defaults to
            :data:`CANDIDATE_MULTIPLIER`; overridable so a caller can measure
            the effect of changing it rather than editing a constant.

    Returns:
        The per-retriever candidate count.

    Raises:
        ValueError: If ``multiplier`` is negative. A negative budget would ask
            for a nonsensical number of candidates and, if it reached
            ``search``, would truncate silently - it is refused rather than
            clamped, because a clamped budget is a budget nobody asked for.
    """
    if multiplier < 0:
        raise ValueError("multiplier must not be negative")
    return max(0, top_k) * multiplier


@dataclass(frozen=True, slots=True)
class FusionResult:
    """One fused ranking, and an honest account of how it was produced.

    Attributes:
        results: Chunk id to fused score, descending. Only chunks at least one
            retriever returned appear - fusion never invents a candidate.
        dense_scores: The dense retriever's raw cosine per chunk. Kept so a
            caller can show *why* something ranked, and so the two signals stay
            separable instead of being fused into one unexplainable number.
        lexical_scores: The lexical retriever's raw BM25 per chunk.
        retriever_used: ``"hybrid"``, ``"lexical_only"`` or ``"dense_only"``.
            Non-hybrid is a normal state, not an error: when no embeddings are
            installed - which is the default, since the model is optional - the
            dense retriever has nothing to say, and reporting "lexical_only" is
            far more useful than reporting a hybrid score that silently ignored
            half its inputs.
    """

    results: dict[str, float]
    dense_scores: dict[str, float]
    lexical_scores: dict[str, float]
    retriever_used: str


def cosine_similarity(
    left: Sequence[float], right: Sequence[float]
) -> float:
    """Cosine similarity of two vectors, without assuming either is normalised.

    Args:
        left: First vector.
        right: Second vector. Must be the same length as ``left``.

    Returns:
        Similarity in ``[-1, 1]``.

    Raises:
        ValueError: On a length mismatch or a non-finite component. Both are
            caller bugs that would otherwise become a silently wrong ranking;
            the project refuses to score a comparison it cannot make honestly.
    """
    if len(left) != len(right):
        raise ValueError("vectors must have the same length")
    total = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right, strict=True):
        if not (math.isfinite(a) and math.isfinite(b)):
            raise ValueError("vector contains a non-finite component")
        total += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm == 0.0 or right_norm == 0.0:
        # A zero vector has no direction, so its similarity to anything is
        # undefined. Zero is the truthful answer and keeps the ranking total
        # rather than dropping the chunk silently.
        return 0.0
    return total / (math.sqrt(left_norm) * math.sqrt(right_norm))


def discrimination_weight(
    candidate_count: int, k: float = RRF_K
) -> float:
    """How much a retriever's opinion should count, given how far it narrowed.

    Args:
        candidate_count: How many candidates that retriever returned.
        k: The damping constant, shared with :func:`reciprocal_rank_fusion`.

    Returns:
        A weight in ``(0, 1]``. At ``k=60``: a retriever returning one
        candidate scores 0.983, one returning fifty scores 0.545, and one
        returning a 20,000-chunk corpus scores 0.003.

    Raises:
        ValueError: If ``k`` is negative. A negative damping constant makes
            ``1 / (k + rank)`` *increase* with rank, so the retriever's worst
            candidate would outscore its best - the exact inversion this module
            exists to prevent, arriving through a different door.

    Notes:
        Vanilla RRF has no such term, and that is its one real weakness here:
        without it, a dense retriever that answered an off-topic query with 50
        chunks inside a 0.005-wide cosine band outranks a lexical retriever that
        answered with the single matching provision. Width of the returned set
        is the only evidence available that one retriever discriminated and the
        other merely enumerated.

        At ``k = 0`` the weight collapses to 1 for every non-empty ranking,
        which is the correct limit: with no damping there is no length scale to
        compare against, so every retriever counts fully. It is computed as a
        branch rather than as a division, because ``candidate_count / 0`` raises.
    """
    if k < 0.0:
        raise ValueError("k must not be negative")
    if candidate_count <= 0:
        return 0.0
    if k == 0.0:
        return 1.0
    return 1.0 / (1.0 + candidate_count / k)


def reciprocal_rank_fusion(
    rankings: Sequence[Mapping[str, float]],
    *,
    k: float = RRF_K,
) -> dict[str, float]:
    """Combine several rankings by *position* rather than by score.

    Args:
        rankings: One mapping per retriever, each ordered best-first by its own
            score. Only the ordering and the length are read; the magnitudes
            are ignored, which is the entire point.
        k: The damping constant.

    Returns:
        Chunk id to fused score, descending.

    Raises:
        ValueError: If ``k`` is negative, which would invert the ranking.

    Notes:
        Ties break on chunk id, so the same inputs always produce the same
        ordering.
    """
    if k < 0.0:
        raise ValueError("k must not be negative")
    if not rankings:
        return {}

    contributions: dict[str, float] = {}
    for ranking in rankings:
        # enumerate(start=1): RRF's rank is 1-based. A rank of 0 would make the
        # best-ranked chunk score higher than any other by an unbounded amount.
        weight = discrimination_weight(len(ranking), k)
        if weight <= 0.0:
            continue
        for position, chunk_id in enumerate(ranking, start=1):
            contributions[chunk_id] = contributions.get(chunk_id, 0.0) + (
                weight / (k + position)
            )

    return dict(
        sorted(contributions.items(), key=lambda pair: (-pair[1], pair[0]))
    )


def hybrid_search(
    query: str,
    lexical_scores: Mapping[str, float],
    dense_scores: Mapping[str, float] | None = None,
    *,
    top_k: int = 5,
) -> FusionResult:
    """Fuse a lexical ranking with a dense one into a single ranking.

    Args:
        query: The original query text. Accepted for the API's symmetry with
            the retriever that owns it; fusion is a function of the two score
            mappings alone and does not re-tokenise. Logging it is deliberately
            not done - the project does not store user queries.
        lexical_scores: BM25 score per chunk, best first. May be empty.
        dense_scores: Cosine similarity per chunk, best first, or ``None`` when
            no embedding backend is installed.
        top_k: How many results to return. **Never padded**: a short ranking is
            returned as-is, because filling a quota with chunks that matched
            nothing would present an irrelevant citation as a relevant one.

    Returns:
        A :class:`FusionResult` whose ``retriever_used`` names which signals
        actually contributed.
    """
    has_lexical = bool(lexical_scores)
    has_dense = bool(dense_scores)

    if not has_lexical and not has_dense:
        return FusionResult(
            results={},
            dense_scores={},
            lexical_scores={},
            retriever_used="none",
        )

    # Only one signal present: no fusion is possible or needed, and pretending
    # otherwise would attach a hybrid-looking number to a single-retriever
    # answer. This is the default state on a machine with no ML runtime.
    if not has_dense:
        ranked = sorted(lexical_scores.items(), key=lambda pair: (-pair[1], pair[0]))
        return FusionResult(
            results=dict(ranked[:top_k]),
            dense_scores={},
            lexical_scores=dict(ranked),
            retriever_used="lexical_only",
        )
    if not has_lexical:
        ranked = sorted(dense_scores.items(), key=lambda pair: (-pair[1], pair[0]))
        return FusionResult(
            results=dict(ranked[:top_k]),
            dense_scores=dict(ranked),
            lexical_scores={},
            retriever_used="dense_only",
        )

    # Ranked by each retriever's own score, then fused on position.
    # dict() preserves insertion order and list() materialises it, so the
    # ordering each retriever produced is what fusion sees.
    dense_ranking = dict(
        sorted(dense_scores.items(), key=lambda pair: (-pair[1], pair[0]))
    )
    lexical_ranking = dict(
        sorted(lexical_scores.items(), key=lambda pair: (-pair[1], pair[0]))
    )

    fused = reciprocal_rank_fusion([lexical_ranking, dense_ranking])
    return FusionResult(
        results=dict(list(fused.items())[:top_k]),
        dense_scores=dense_scores,
        lexical_scores=lexical_scores,
        retriever_used="hybrid",
    )
