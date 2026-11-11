"""Small deterministic BM25 index over complete, policy-eligible paragraphs.

No embeddings are downloaded. Every search revalidates source bindings. Indexing
is not approval; this release exports no VERIFIED_REVIEWED evidence.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

from backend.publication.bindings import ReadOnlyReview, verify_metadata
from backend.review.models import Candidate
from backend.review.service import exclusion_reasons, span_text, validate_candidate

ROOT = Path(__file__).resolve().parents[2]
from .scoring import BM25, INJECTION, OUTSIDE, tokens, reciprocal_rank_fusion


@dataclass(frozen=True)
class Passage:
    candidate: Candidate
    text: str
    title: str
    instrument: str
    search_text: str
    printed_number: str | None = None
    qa_flags: tuple[str, ...] = ()

    @property
    def identifier(self):
        return self.candidate.candidate_id


class ArchivalIndex:
    mode = "bm25"
    semantic_status = "unavailable: no configured local embedding model; no downloads attempted"

    def __init__(self, root=ROOT, loader=verify_metadata, *, expand=True, semantic=None, retrieval_mode=None):
        self.root = Path(root)
        self.loader = loader
        self.passages = []
        self.quarantined = 0
        self.catalog = None
        self.coverage = {}
        self.semantic = None
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
            if expand:
                from .archival import discover
                selections, self.coverage = discover(self.catalog, invalid_documents)
                for c, text, label, flags in selections:
                    if INJECTION.search(text) or (c.raw_sha256, c.passage_sha256) in seen:
                        continue
                    seen.add((c.raw_sha256, c.passage_sha256))
                    title = c.source_metadata.official_title
                    instrument = "Act " + str(c.original_identifiers.get("act_number", "unknown"))
                    if c.original_identifiers.get("act_year"):
                        instrument += "/" + str(c.original_identifiers["act_year"])
                    self.passages.append(Passage(c, text, title, instrument,
                        text + " " + title, label, tuple(flags)))
            self.passages.sort(key=lambda p: p.candidate.candidate_id)
            self.reason = "Unapproved archival notification paragraphs and conservative single-page Act selections; currentness unknown."
        except (ValueError, OSError, KeyError, TypeError):
            self.passages = []
            self.catalog = None
        self.bm25 = BM25([p.search_text for p in self.passages])
        self.version = hashlib.sha256(json.dumps(["archival-single-page-v1",
            [p.candidate.candidate_id for p in self.passages]], separators=(",", ":")).encode()).hexdigest()
        selected_mode = retrieval_mode or os.environ.get("RETRIEVAL_MODE", "auto")
        if selected_mode not in {"auto", "bm25", "hybrid"}:
            raise ValueError("Unsupported retrieval mode")
        model_path = os.environ.get("KANOON_EMBEDDING_MODEL_PATH", "")
        if selected_mode != "bm25" and (semantic is not None or (model_path and self.passages)):
            try:
                from .semantic import LocalSemantic
                self.semantic = semantic or LocalSemantic(model_path, self.passages)
                self.mode, self.semantic_status = "hybrid", "local Sentence Transformers + FAISS; no downloads"
            except (ImportError, OSError, ValueError, RuntimeError):
                self.semantic_status = "unavailable: local embedding initialization failed; BM25 retained; no downloads"

    def search(self, question, limit=3, max_characters=12000, *, source_ids=None, mode=None):
        if type(limit) is not int or not 1 <= limit <= 5:
            raise ValueError("top-k must be between one and five")
        if not self.catalog or INJECTION.search(question) or OUTSIDE.search(question):
            return []
        if re.search(r"\b(my|i am|am i|should i|will i|current|today|now|legal advice)\b", question, re.I):
            return []
        specific = set(tokens(question)) - {"bns", "bnss", "bsa", "topic_bns", "topic_bnss", "topic_bsa", "act", "section", "explain", "says", "say", "states", "state", "law"}
        if not specific:
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
        lexical = [n for n, score in ranked if score > 0]
        order = lexical
        if self.semantic and mode != "bm25":
            order = reciprocal_rank_fusion([lexical[:50], self.semantic.rank(question, 50)])
        result, size = [], 0
        printed = re.search(r"\bsection\s+(\d+)(?:\s*\((\d+)\))?", question, re.I)
        notification_query = bool(re.search(r"notificat|commenc|first\s+schedule|(?:come|came|into).{0,15}force|s\.?\s*o\.?\s*(?:848|849|850)", question, re.I))
        if notification_query and re.search(r"\b(theft|murder|bail|punishment|penalty|compensation|fraud|rape)\b", question, re.I):
            return []  # These commencement records do not answer offence-specific requests.
        for number in order:
            p = self.passages[number]
            topic = {"S.O. 850(E)": "topic_bns", "S.O. 848(E)": "topic_bnss", "S.O. 849(E)": "topic_bsa"}.get(p.instrument)
            if topic is None:
                topic = next((t for t in tokens(p.title) if t.startswith("topic_")), None)
            if ((requested and topic not in requested) or
                    (source_ids is not None and p.candidate.document_id not in source_ids)):
                continue
            if notification_query != (p.printed_number is None):
                continue
            if printed and not notification_query and (p.printed_number != printed[1] or printed[2]):
                continue  # No inferred subsection attribution.
            if not notification_query and not printed:
                overlap = specific.intersection(tokens(p.text)) - {"punishment", "provisions", "document"}
                if len(overlap) < 2:
                    continue  # Dense similarity alone cannot justify unsupported evidence.
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
                    index_version=self.version, coverage=self.coverage,
                    quarantined_pages=sum(v["hard_quarantined_pages"] for v in self.coverage.values()),
                    selected_pages=len({(p.candidate.document_id, p.candidate.spans[0].physical_page) for p in self.passages}),
                    semantic_version=getattr(self.semantic, "version", None),
                    passages=len(self.passages), quarantined=self.quarantined,
                    evidence_status="ARCHIVAL_UNVERIFIED" if self.passages else "INSUFFICIENT_EVIDENCE",
                    detail=self.reason)
