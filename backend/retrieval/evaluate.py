"""Measured local retrieval regression benchmark; never calls a model provider.

Output contains IDs and metrics, not private source text. This is not an
independent legal relevance judgment or a claim of corpus completeness.
"""
import argparse
import json
import math
from pathlib import Path
import statistics
import time

from backend.review.service import exclusion_reasons, span_text, validate_candidate
from .engine import ArchivalIndex


def evaluate(index, cases, mode):
    rows, recalls, reciprocal, ndcgs, abstentions = [], [], [], [], []
    valid, total = 0, 0
    for case in cases:
        started = time.perf_counter()
        hits = index.search(case["question"], limit=5, max_characters=24000, mode=mode)
        latency = (time.perf_counter() - started) * 1000
        expected = {p.candidate.candidate_id for p in index.passages if
            (case.get("instrument") and p.instrument == case["instrument"]) or
            (case.get("source") and case["source"] in p.title and p.printed_number == case["number"])}
        if not case.get("abstain") and not expected:
            raise ValueError("Benchmark expected source absent: " + case["id"])
        ranking = [p.candidate.candidate_id for p in hits]
        for p in hits:
            total += 1
            item, doc = validate_candidate(index.catalog, p.candidate)
            valid += not exclusion_reasons(item, p.candidate) and span_text(doc, p.candidate.spans[0]) == p.text
        relevant = [i for i, identifier in enumerate(ranking, 1) if identifier in expected]
        if case.get("abstain"):
            abstentions.append(not hits)
        else:
            recalls.append(len(set(ranking) & expected) / len(expected))
            reciprocal.append(1 / relevant[0] if relevant else 0)
            dcg = sum(1 / math.log2(rank + 1) for rank in relevant)
            ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(5, len(expected)) + 1))
            ndcgs.append(dcg / ideal)
        rows.append(dict(id=case["id"], expected=sorted(expected), retrieved=ranking,
                         abstained=not hits, latency_ms=round(latency, 2)))
    return dict(mode=mode, cases=len(cases), supported_cases=len(recalls), abstention_cases=len(abstentions),
        recall_at_5=statistics.mean(recalls), mrr=statistics.mean(reciprocal), ndcg_at_5=statistics.mean(ndcgs),
        citation_validity=valid / total if total else None, citations_checked=total,
        unsupported_answer_abstention=statistics.mean(abstentions),
        latency_median_ms=statistics.median(r["latency_ms"] for r in rows),
        latency_p95_ms=sorted(r["latency_ms"] for r in rows)[math.ceil(.95 * len(rows)) - 1], rows=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    index = ArchivalIndex()
    specification = json.loads(Path(__file__).with_name("benchmark.json").read_bytes())
    if not index.catalog or len(index.passages) <= 3:
        parser.error("Expanded local evidence bundle required; no results fabricated")
    report = dict(schema_version=1, scope=specification["scope"], index=index.status(),
        build_seconds=round(time.perf_counter() - started, 2),
        provider_calls=0, results=[evaluate(index, specification["cases"], "bm25")])
    if index.semantic:
        report["results"].append(evaluate(index, specification["cases"], "hybrid"))
    else:
        report["hybrid_blocker"] = index.semantic_status
    if args.output:
        target = args.output.resolve()
        allowed = (index.root / "backend/data/qa").resolve()
        if not target.is_relative_to(allowed):
            parser.error("Reports must stay under ignored backend/data/qa")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
    print(json.dumps({k:v for k,v in report.items() if k != "results"}, indent=2))
    for result in report["results"]:
        print(json.dumps({k:v for k,v in result.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
