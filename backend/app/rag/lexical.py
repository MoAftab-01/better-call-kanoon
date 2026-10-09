"""Okapi BM25 over an in-memory inverted index - the lexical half of hybrid search.

This module needs no third-party library, no model, no settings object, no
clock and no filesystem. It receives documents and weights as arguments and
returns scores. That is what makes it exhaustively testable on a machine with
no ML runtime at all, which is the machine this project ships to.

**Why BM25 and not TF-IDF.** Term frequency saturates: the tenth occurrence of
a word in a chunk says far less than the first. BM25 makes that explicit with
:data:`K1`, and normalises by document length with :data:`B` so a long chunk
does not outrank a short precise one merely by containing more words.

**Why the IDF form here is Lucene's and not the textbook one.** The naive
Okapi form is ``log((N - df + 0.5) / (df + 0.5))``, and it goes **negative**
once a term appears in more than half the corpus - measured at ``-10.5967`` for
a term in all 20,000 of 20,000 chunks. A negative weight does not merely weaken
a ubiquitous term, it *reverses* the ranking: the chunk containing the query
term five times scores lower than the chunk containing it once, because the
whole term contribution is multiplied by a negative number. In a corpus of
Indian statute, terms like ``section``, ``shall`` and ``act`` appear in a large
fraction of chunks by construction, so this is the common case, not an edge
case.

The Lucene form is ``log(1 + (N - df + 0.5) / (df + 0.5))``, which is always
non-negative and monotonically decreasing in ``df``. :data:`IDF_FLOOR` then puts
a positive lower bound under it, so a term present in every document
contributes negligibly rather than exactly nothing.

**What the floor does not give you.** It is a positive constant, not zero, so
BM25 is *never* all-zero for a query whose terms are merely ubiquitous. An
all-zero result therefore means the query terms are **out of vocabulary**, not
"no matching provision". Those are different situations and a caller must treat
them differently; :func:`LexicalIndex.search` reports which one it is through
:attr:`SearchResult.kind` rather than leaving the caller to guess from a score.

**And the inverse failure, which the floor also cannot fix.** Because the floor
is positive, a query built entirely out of ubiquitous terms scores *every*
document above zero - measured over 20,000 synthetic chunks, 20,000 of 20,000
scored, with the values separated by about 1e-13 of float noise. Such a result
is arithmetically a match and semantically nothing. So the search reports a
fourth kind, ``low_information``, when every matched term was already pinned at
:data:`IDF_FLOOR` - derived from the existing constant rather than from a new
threshold, precisely because no evaluation has run that could tune one.

No stemming is performed, and none should be added casually: BM25's length
normalisation already penalises long documents, and the distinctions Indian
statute drafting depends on - ``murder``/``murdered``,
``punish``/``punishable``/``punishment`` - are exactly what an aggressive
stemmer would erase.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from app.rag.tokenizer import tokenize

__all__ = [
    "BM25_B",
    "BM25_K1",
    "IDF_FLOOR",
    "LexicalIndex",
    "SearchResult",
]


#: Term-frequency saturation. 1.2 is the value Lucene uses and the value most
#: BM25 literature reports; it has **not** been tuned against this corpus, and
#: no claim is made that it is optimal here.
#:
#: Range: 0 gives pure TF (no saturation), large values approach binary
#: presence/absence. 1.2 sits just below where saturation begins.
BM25_K1: float = 1.2


#: Document-length normalisation. 0.0 disables it entirely; 1.0 normalises
#: fully, so a document scores as if it were exactly average length.
#:
#: 0.75 is the value most BM25 literature reports for general text. **0.60 is
#: chosen for this corpus and is not derived from measurement here**: statute
#: chunks vary far less in length than web documents do, so full normalisation
#: would over-penalise the long, dense sections (a long proviso) that are often
#: exactly what a query is looking for. This is a judgement call and is marked
#: as one - it should be revisited when an evaluation harness exists.
BM25_B: float = 0.60


#: Lower bound on a term's IDF.
#:
#: The Lucene form already prevents a negative weight. This floor goes further:
#: it stops a term that appears in *every* chunk from contributing anything
#: meaningful, which is what makes a corpus-wide term like ``section`` behave
#: as the near-stopword it functionally is.
#:
#: **Not a tuned value.** 0.05 is roughly where ``log(1 + (N-df+0.5)/(df+0.5))``
#: lands for a term in 99.9% of a large corpus, chosen so the floor only
#: engages for genuinely ubiquitous terms and leaves ordinary IDF untouched.
IDF_FLOOR: float = 0.05


def idf(document_frequency: int, document_count: int) -> float:
    """Inverse document frequency, in the Lucene form.

    Args:
        document_frequency: How many documents contain the term. Clamped into
            ``[0, document_count]``; a value above the corpus size means the
            caller's statistics are inconsistent, and clamping is friendlier
            than raising from deep inside a scorer.
        document_count: Total documents in the index. Zero or negative yields
            the floor, so an empty index does not divide by zero.

    Returns:
        A non-negative IDF. Monotonically decreasing in ``document_frequency``
        across its whole range: a term in every document scores exactly
        :data:`IDF_FLOOR`, and a term in no document scores the most.
    """
    if document_count <= 0:
        return IDF_FLOOR

    # A term present in no document is the most distinctive term there is -
    # log(1 + (N + 0.5) / 0.5) is the maximum of the whole function. An
    # earlier version of this function special-cased df <= 0 and returned the
    # *floor*, which handed the rarest possible term the smallest possible
    # weight: precisely the inversion the Lucene form exists to remove, just
    # moved from the top of the df range to the bottom. No such term is
    # reachable through LexicalIndex today, because a term only gets postings
    # when a document contains it - but a public scoring function that inverts
    # its own input is a trap for the next caller, so the formula is simply
    # left to run.
    document_frequency = max(0, min(document_frequency, document_count))

    numerator = document_count - document_frequency + 0.5
    denominator = document_frequency + 0.5
    # log(1 + (N - df + 0.5) / (df + 0.5)) is non-negative everywhere on
    # [0, N], so the floor below it only ever raises. It is written as a max
    # rather than applied inside the log because a max *after* the log is the
    # only ordering that cannot make the function non-monotone.
    return max(math.log(1.0 + numerator / denominator), IDF_FLOOR)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """What a lexical search found, and what kind of nothing it found.

    Attributes:
        scores: Chunk id to BM25 score, descending by score. Only chunks that
            actually contain at least one query term appear.
        kind: ``"matches"``, ``"low_information"``, ``"out_of_vocabulary"``
            or ``"empty_index"``. ``out_of_vocabulary`` means every query term
            is absent from the index, which is **not** the same as "no
            provision matches": it usually means the corpus is empty or the
            query is spelled differently. Collapsing the two would let a
            retrieval bug present itself as a confident answer that the law
            does not cover the question, which is the failure this project
            exists to prevent.
        matched_terms: How many distinct query terms were found in the index.
            Retained so a caller can report *why* a result was weak; a query
            of three terms where one is known and two are not is a different
            situation from three terms all known, even when both score.
        floored_terms: The subset of ``matched_terms`` whose IDF is pinned at
            :data:`IDF_FLOOR` - terms common enough to appear in nearly every
            document, which is what ``section``, ``shall`` and ``act`` are in a
            statute corpus. These are the terms a query built out of statutory
            boilerplate actually matches on.
    """

    scores: dict[str, float]
    kind: str
    matched_terms: int = 0
    floored_terms: int = 0


@dataclass(slots=True)
class _Postings:
    """One term's postings list and the length statistics it needs."""

    #: Chunk id to term frequency. Values are > 0 by construction.
    postings: dict[str, int] = field(default_factory=dict)
    #: Total term occurrences in this term's documents, for a cheap sanity check.
    total_frequency: int = 0


class LexicalIndex:
    """An in-memory inverted index over pre-tokenised documents.

    Built by :meth:`add` and :meth:`finalise`, then queried by
    :meth:`search`. The two-phase build exists because average document length
    and the document count are not known until every document is in, and both
    appear in the BM25 denominator - a single-document index scores every
    query as if the corpus were that document.

    Not thread-safe for concurrent mutation. It is built once at startup and
    read thereafter, which is the only pattern the server uses.
    """

    def __init__(self) -> None:
        self._postings: dict[str, _Postings] = {}
        self._document_lengths: dict[str, int] = {}
        self._chunk_order: list[str] = []
        self._finalised = False

    # -- construction ------------------------------------------------------

    def add(self, chunk_id: str, text: str) -> None:
        """Index one document.

        Args:
            chunk_id: The document's stable identifier. Used as the key in
                results, so it must be unique.
            text: Raw document text in any script. Tokenised with the project's
                shared :func:`~app.rag.tokenizer.tokenize`, so the index and the
                query path cannot disagree about what a word is - two
                tokenisers would produce "no results" rather than an exception,
                which is the failure nothing detects.

        Raises:
            RuntimeError: If called after :meth:`finalise`, because the length
                statistics would be silently wrong.
        """
        if self._finalised:
            raise RuntimeError("cannot add documents to a finalised index")

        terms = tokenize(text)
        self._document_lengths[chunk_id] = len(terms)
        self._chunk_order.append(chunk_id)

        # Counted into a local dict first so a repeated term updates one
        # posting rather than racing through the index dict per occurrence.
        frequencies: dict[str, int] = {}
        for term in terms:
            frequencies[term] = frequencies.get(term, 0) + 1

        for term, count in frequencies.items():
            postings = self._postings.setdefault(term, _Postings())
            postings.postings[chunk_id] = count
            postings.total_frequency += count

    def finalise(self) -> None:
        """Freeze the index for querying.

        Records the corpus statistics that :func:`idf` and the BM25 denominator
        need. Calling it twice is harmless; calling :meth:`add` afterwards is
        an error rather than a silent inconsistency.
        """
        self._finalised = True

    # -- properties --------------------------------------------------------

    @property
    def doc_count(self) -> int:
        """Number of documents indexed."""
        return len(self._document_lengths)

    @property
    def is_finalised(self) -> bool:
        """Whether :meth:`finalise` has been called."""
        return self._finalised

    @property
    def vocabulary_size(self) -> int:
        """Number of distinct terms in the index."""
        return len(self._postings)

    @property
    def avg_doc_length(self) -> float:
        """Mean document length in terms.

        Zero for an empty index, so the BM25 denominator never divides by zero
        - an empty corpus is a reachable state in this project and must produce
        an empty result rather than a ``ZeroDivisionError``.
        """
        if not self._document_lengths:
            return 0.0
        return sum(self._document_lengths.values()) / len(self._document_lengths)

    def document_length(self, chunk_id: str) -> int:
        """Length in terms of one indexed document, or 0 if it is absent."""
        return self._document_lengths.get(chunk_id, 0)

    # -- querying ----------------------------------------------------------

    def score_document(self, query_terms: Sequence[str], chunk_id: str) -> float:
        """BM25 score of one document against a tokenised query.

        Exposed for testing and for the fusion layer, which needs per-document
        scores rather than a ranked list.

        Args:
            query_terms: Query terms, already tokenised.
            chunk_id: The document to score.

        Returns:
            The BM25 score, which is ``0.0`` when the document contains none of
            the query terms.
        """
        length = self._document_lengths.get(chunk_id)
        if length is None:
            return 0.0
        avg_length = self.avg_doc_length
        if avg_length == 0.0:
            return 0.0

        total = 0.0
        # Sorted, because float addition is not associative: summing the same
        # terms in a different order can differ in the last bit, and a
        # retriever whose ranking wobbles between identical queries is
        # impossible to test or to trust. Iterating a set here would make the
        # order depend on the process's hash seed.
        for term in sorted(set(query_terms)):
            postings = self._postings.get(term)
            if postings is None:
                continue
            frequency = postings.postings.get(chunk_id, 0)
            if frequency == 0:
                continue
            term_idf = idf(len(postings.postings), self.doc_count)
            denominator = frequency + BM25_K1 * (
                1.0 - BM25_B + BM25_B * length / avg_length
            )
            total += term_idf * (frequency * (BM25_K1 + 1.0)) / denominator
        return total

    def search(self, query: str, top_k: int | None = None) -> SearchResult:
        """Score every document that contains at least one query term.

        Args:
            query: Raw query text, tokenised with the shared tokenizer.
            top_k: If given, keep only this many results. A shorter list is
                returned as-is and **never padded**: filling a quota with
                low-scoring chunks would be inventing a citation, which is the
                unforgivable failure mode for a legal-information tool.

        Returns:
            A :class:`SearchResult`. ``kind`` distinguishes a genuine
            non-match from an out-of-vocabulary query - see that class.
        """
        if self.doc_count == 0:
            return SearchResult(scores={}, kind="empty_index")

        terms = tokenize(query)
        if not terms:
            return SearchResult(scores={}, kind="out_of_vocabulary")

        # Only documents that actually contain a query term are candidates.
        # Iterating the whole corpus and scoring each one would be the same
        # answer at far more cost, and on a large corpus that cost is what the
        # retriever is judged on.
        candidates: set[str] = set()
        matched_terms = 0
        floored_terms = 0
        for term in set(terms):
            postings = self._postings.get(term)
            if postings is None:
                continue
            matched_terms += 1
            # A term sitting at the IDF floor is present almost everywhere, so
            # it cannot separate one provision from another. Counting them is
            # what lets the caller distinguish "matched something specific"
            # from "matched only the boilerplate", which are otherwise
            # indistinguishable from the scores alone.
            if idf(len(postings.postings), self.doc_count) == IDF_FLOOR:
                floored_terms += 1
            candidates.update(postings.postings)

        if matched_terms == 0:
            return SearchResult(scores={}, kind="out_of_vocabulary")
        if not candidates:
            # Terms are known to the index but present in no single document.
            # Distinct from out_of_vocabulary: the corpus uses these words, just
            # never together.
            return SearchResult(scores={}, kind="out_of_vocabulary")

        scored = {
            chunk_id: self.score_document(terms, chunk_id)
            for chunk_id in candidates
        }
        # Descending by score. The chunk id breaks ties so the order is total
        # and reproducible - a stable sort on score alone would resolve ties by
        # the order of a set, which varies between processes.
        ranked = sorted(scored.items(), key=lambda pair: (-pair[1], pair[0]))
        if top_k is not None:
            ranked = ranked[:top_k]

        # Every matched term was at the floor: the field above is entirely made
        # of terms too common to discriminate, so it ranks documents but carries
        # no signal about which provision answers the question. This is the E5
        # case, and it is the *common* case for a statutory corpus - "section",
        # "shall" and "act" appear in most chunks by construction. Saying so
        # is the difference between "here are the best matches" and "here is a
        # number, and it means nothing".
        kind = "matches"
        if ranked and floored_terms == matched_terms:
            kind = "low_information"

        return SearchResult(
            scores=dict(ranked),
            kind=kind,
            matched_terms=matched_terms,
            floored_terms=floored_terms,
        )

    def term_document_frequency(self, term: str) -> int:
        """How many indexed documents contain ``term``.

        Args:
            term: A single token, already normalised by the tokenizer.

        Returns:
            The document frequency, or 0 for an unknown term.
        """
        postings = self._postings.get(term)
        return len(postings.postings) if postings else 0

    def known_terms(self) -> Iterable[str]:
        """Every distinct term in the index.

        Exposed so an operator tool can inspect the vocabulary, and so a test
        can assert what was actually indexed without reaching into privates.
        """
        return self._postings.keys()


def build_lexical_index(
    chunks: Mapping[str, str],
    *,
    chunk_ids: Sequence[str] | None = None,
) -> LexicalIndex:
    """Build a :class:`LexicalIndex` from a mapping of chunk id to text.

    Args:
        chunks: Chunk id to document text.
        chunk_ids: Optional explicit ordering, used to make the build
            deterministic. Insertion order of ``chunks`` is used when omitted.

    Returns:
        A finalised index, ready to query.
    """
    index = LexicalIndex()
    order = list(chunk_ids) if chunk_ids is not None else list(chunks)
    for chunk_id in order:
        index.add(chunk_id, chunks[chunk_id])
    index.finalise()
    return index
