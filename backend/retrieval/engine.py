"""Small deterministic BM25 index over complete, policy-eligible paragraphs.

No embeddings are downloaded. Every search revalidates source bindings. Indexing
is not approval; this release exports no VERIFIED_REVIEWED evidence.
"""
from collections import Counter
from dataclasses import dataclass
import math
from pathlib import Path
import re

from backend.publication.bindings import ReadOnlyReview, verify_metadata
from backend.review.models import Candidate
from backend.review.service import exclusion_reasons, span_text, validate_candidate

ROOT = Path(__file__).resolve().parents[2]
STOP = set("a an the of in on at to for and or is are was were does do what when which this that it its said me my please tell about".split())
TOPICS = {
    "bns": ("bharatiya nyaya sanhita", "850"),
    "bnss": ("bharatiya nagarik suraksha sanhita", "848"),
    "bsa": ("bharatiya sakshya adhiniyam", "849"),
}
INJECTION = re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|system)|system\s*(?:prompt|message)|reveal\s+(?:secrets|keys)|\[/?INST\]|<\|(?:system|assistant)", re.I)
OUTSIDE = re.compile(r"\b(consumer|tenant|tenancy|landlord|rental|employment|employer|salary|workplace|divorce|tax|copyright)\b", re.I)


def tokens(text):
    words = re.findall(r"[a-z]+|\d+", text.lower())
    result = [w for w in words if w not in STOP]
    for short, names in TOPICS.items():
        if short in result or any(name in text.lower() for name in names):
            result.append("topic_" + short)
    return result


def reciprocal_rank_fusion(rankings, k=60):
    scores = Counter()
    for ranking in rankings:
        for rank, identifier in enumerate(dict.fromkeys(ranking), 1):
            scores[identifier] += 1 / (k + rank)
    return sorted(scores, key=lambda key: (-scores[key], key))


class BM25:
    def __init__(self, texts):
        self.documents = [Counter(tokens(text)) for text in texts]
        self.lengths = [sum(d.values()) for d in self.documents]
        self.average = sum(self.lengths) / max(len(texts), 1)
        self.frequency = Counter(t for doc in self.documents for t in doc)

    def scores(self, query):
        result = []
        for doc, length in zip(self.documents, self.lengths, strict=True):
            score = 0.0
            for term in set(tokens(query)):
                tf = doc[term]
                if tf:
                    df = self.frequency[term]
                    idf = math.log(1 + (len(self.documents) - df + .5) / (df + .5))
                    score += idf * tf * 2.5 / (tf + 1.5 * (.25 + .75 * length / max(self.average, 1)))
            result.append(score)
        return result


@dataclass(frozen=True)
class Passage:
    candidate: Candidate
    text: str
    title: str
    instrument: str
    search_text: str


class ArchivalIndex:
    mode = "bm25"
    semantic_status = "unavailable: no configured local embedding model; no downloads attempted"

    def __init__(self, root=ROOT, loader=verify_metadata):
        self.root = Path(root)
        self.loader = loader
        self.passages = []
        self.quarantined = 0
        self.catalog = None
        self.reason = "No validated local evidence bundle is available."
        try:
            self.catalog, packets = loader(self.root)
            # A corrupt chain is not treated as an empty successful review store.
            ReadOnlyReview(self.catalog).replay()
            invalid_documents = set()
            for identifier in self.catalog.documents:
                try:
                    self.catalog.document(identifier)
                except (ValueError, OSError, KeyError, TypeError):
                    invalid_documents.add(identifier)
                    self.quarantined += 1
            seen = set()
            for packet in packets:
                try:
                    c = Candidate.model_validate(packet["candidate"])
                    if c.document_id in invalid_documents:
                        continue
                    item, doc = validate_candidate(self.catalog, c)
                    if exclusion_reasons(item, c) or len(c.spans) != 1:
                        raise ValueError("Excluded or ambiguous passage")
                    text = span_text(doc, c.spans[0])
                    if INJECTION.search(text):
                        raise ValueError("Instruction-like source quarantined")
                    key = (c.raw_sha256, c.passage_sha256)
                    if key in seen:
                        continue
                    seen.add(key)
                    instrument = str(c.original_identifiers.get("notification_number", ""))
                    title = c.source_metadata.official_title
                    self.passages.append(Passage(c, text, title, instrument,
                        text + " " + instrument + " " + str(c.original_identifiers)))
                except (ValueError, OSError, KeyError, TypeError):
                    self.quarantined += 1
            self.passages.sort(key=lambda p: p.candidate.candidate_id)
            self.reason = "Only complete archival notification paragraphs; legal currentness and applicability unknown."
        except (ValueError, OSError, KeyError, TypeError):
            self.passages = []
            self.catalog = None
        self.bm25 = BM25([p.search_text for p in self.passages])

    def search(self, question, limit=3, max_characters=6000):
        if not self.catalog or INJECTION.search(question) or OUTSIDE.search(question):
            return []
        # Only the supported source-description/commencement domain is enabled.
        if not re.search(r"commenc|notificat|except|first\s+schedule|(?:come|came).{0,20}force|s\.?\s*o\.?\s*(?:848|849|850)", question, re.I):
            return []
        if re.search(r"\b(my|arrest|punish\w*|liable|jail|rights|current|today|now|legal advice|murder|theft|bail|penalty|compensation|fraud|rape|convict\w*)\b", question, re.I):
            return []
        requested = {t for t in tokens(question) if t.startswith("topic_")}
        if re.search(r"first\s+schedule", question, re.I):
            requested = {"topic_bnss"}  # Only this indexed notification contains that phrase.
        try:
            # Re-read metadata and its bindings, rather than trusting a warm index.
            live, _ = self.loader(self.root)
            if live.digest != self.catalog.digest or live.qa_hash != self.catalog.qa_hash:
                return []
            ReadOnlyReview(live).replay()
        except (ValueError, OSError, KeyError, TypeError):
            return []
        ranked = sorted(enumerate(self.bm25.scores(question)),
                        key=lambda pair: (-pair[1], self.passages[pair[0]].candidate.candidate_id))
        result, size = [], 0
        for number, score in ranked:
            p = self.passages[number]
            topic = {"S.O. 850(E)": "topic_bns", "S.O. 848(E)": "topic_bnss", "S.O. 849(E)": "topic_bsa"}.get(p.instrument)
            if score <= 0 or (requested and topic not in requested):
                continue
            try:
                item, doc = validate_candidate(live, p.candidate)
                if exclusion_reasons(item, p.candidate) or span_text(doc, p.candidate.spans[0]) != p.text:
                    continue
            except (ValueError, OSError, KeyError, TypeError):
                continue
            if size + len(p.text) > max_characters:
                continue  # Never truncate an operative paragraph or exception.
            result.append(p)
            size += len(p.text)
            if len(result) == limit:
                break
        return result

    def status(self):
        return dict(mode=self.mode, semantic_status=self.semantic_status,
                    passages=len(self.passages), quarantined=self.quarantined,
                    evidence_status="ARCHIVAL_UNVERIFIED" if self.passages else "INSUFFICIENT_EVIDENCE",
                    detail=self.reason)
