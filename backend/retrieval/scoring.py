"""Dependency-free deterministic lexical scoring and common query safety gates."""
from collections import Counter
import math
import re

STOP = set("a an the of in on at to for and or is are was were does do what when which this that it its said me my please tell about".split())
TOPICS = {"bns": ("bharatiya nyaya sanhita", "850"),
          "bnss": ("bharatiya nagarik suraksha sanhita", "848"),
          "bsa": ("bharatiya sakshya adhiniyam", "849")}
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
        query_terms = set(tokens(query))
        result = []
        for doc, length in zip(self.documents, self.lengths, strict=True):
            score = 0.0
            for term in query_terms:
                tf = doc[term]
                if tf:
                    df = self.frequency[term]
                    idf = math.log(1 + (len(self.documents) - df + .5) / (df + .5))
                    score += idf * tf * 2.5 / (tf + 1.5 * (.25 + .75 * length / max(self.average, 1)))
            result.append(score)
        return result


def query_policy(question):
    """Return explicit filters, or None when the existing archival scope denies."""
    if INJECTION.search(question) or OUTSIDE.search(question):
        return None
    if re.search(r"\b(my|i am|am i|should i|will i|current|today|now|legal advice)\b", question, re.I):
        return None
    specific = set(tokens(question)) - {"bns", "bnss", "bsa", "topic_bns", "topic_bnss", "topic_bsa", "act", "section", "explain", "says", "say", "states", "state", "law"}
    if not specific:
        return None
    requested = {t for t in tokens(question) if t.startswith("topic_")}
    if re.search(r"first\s+schedule", question, re.I):
        requested = {"topic_bnss"}
    printed = re.search(r"\bsection\s+(\d+)(?:\s*\((\d+)\))?", question, re.I)
    notification = bool(re.search(r"notificat|commenc|first\s+schedule|(?:come|came|into).{0,15}force|s\.?\s*o\.?\s*(?:848|849|850)", question, re.I))
    if notification and re.search(r"\b(theft|murder|bail|punishment|penalty|compensation|fraud|rape)\b", question, re.I):
        return None
    return specific, requested, printed, notification
