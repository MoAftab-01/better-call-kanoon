"""Conservative, unapproved research selections. Never writes a review record.

Only consecutive printed section starts on one page bound a selection. The last
section on every page is omitted, as are schedules, ambiguous sequences, hard-QA
pages and locally unbalanced/unfinished selections. Full page context is pinned.
This is a heuristic extraction boundary, not visual or legal verification.
"""
import re

from backend.review.service import HARD_EXCLUSIONS, exclusion_reasons, preview, span_text

POLICY = "archival-single-page-v1"
START = re.compile(r"^(\d{1,3})\.\s+(?=[A-Z(])")


def bounded_sections(lines):
    starts = [(i, int(m[1])) for i, line in enumerate(lines) if (m := START.match(line))]
    for (begin, number), (end, following) in zip(starts, starts[1:]):
        if following != number + 1:
            continue
        text = "\n".join(lines[begin:end])
        # No split qualifications, footer, chapter header or detached heading.
        if not 60 <= len(text) <= 4500 or not text.rstrip().endswith((".", ".\u201d", '."')):
            continue
        if any(text.count(a) != text.count(b) for a, b in [("(", ")"), ("[", "]")]):
            continue
        if re.search(r"THE GAZETTE|CHAPTER|SCHEDULE|_{4}|Sec\.\s*1\]", text):
            continue
        yield begin + 1, end, str(number)


def discover(catalog, invalid_documents):
    selections, diagnostics = [], {}
    for identifier in sorted(catalog.documents):
        if identifier in invalid_documents:
            continue
        item, doc = catalog.document(identifier)
        if doc.metadata.instrument_type != "act":
            continue
        stats = dict(pages=len(doc.pages), hard_quarantined_pages=0, selections=0,
                     skipped_boundary_or_layout_pages=0)
        diagnostics[identifier] = stats
        # One immutable validated model per document during discovery; avoid
        # rereading megabytes for every proposal. Search revalidates live bytes.
        class Snapshot:
            def __getattr__(self, name):
                return getattr(catalog, name)

            def document(self, requested):
                if requested != identifier:
                    raise ValueError("Discovery snapshot document mismatch")
                return item, doc

        snapshot = Snapshot()
        for page, quality in zip(doc.pages, item["pages"], strict=True):
            if (not all(quality["automatic_checks"].values()) or
                    any(f["code"] in HARD_EXCLUSIONS for f in quality["findings"])):
                stats["hard_quarantined_pages"] += 1
                continue
            lines = page.text.split("\n")
            # A schedule/form is never treated as ordinary numbered provisions.
            if re.search(r"\bSCHEDULE\b|\bFORM No\.", page.text):
                stats["skipped_boundary_or_layout_pages"] += 1
                continue
            for first, last, label in bounded_sections(lines):
                c = preview(snapshot, identifier, [(page.ordinal, first, last)],
                    [(page.ordinal, 1, len(lines))],
                    "Archival research only: consecutive printed numeric starts bound a single-page selection; "
                    "full page context retained. Document-only attribution; no visual approval or current-law claim.")
                if exclusion_reasons(item, c):
                    continue
                flags = sorted({f["code"] for f in quality["findings"]})
                selections.append((c, span_text(doc, c.spans[0]), label, flags))
                stats["selections"] += 1
        # A concurrent source change aborts discovery; no stale snapshot exposed.
        catalog.document(identifier)
    return selections, diagnostics
