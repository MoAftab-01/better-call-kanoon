"""Command-line entry point that builds the local retrieval index from PDFs.

Reads every ``*.pdf`` under a laws directory, extracts the text with PyMuPDF,
segments it into chunks and writes ``chunks.json`` plus
``index_metadata.json``. Entirely local: no network access, no API keys, no
third-party services.

Usage, from ``backend/``::

    python scripts/ingest_laws.py --dry-run
    python scripts/ingest_laws.py

What is printed is deliberately narrow - counts, one neutral line per failed
file, and nothing else. Statute text is never echoed to the terminal, and
neither is a traceback or a raw library message: an unreadable PDF is a
routine operational event, not a crash.

Exit codes: ``0`` success, ``1`` at least one document failed, ``2`` the laws
directory is missing, unreadable or holds no PDFs, ``3`` the run produced no
chunks and an existing index was therefore left untouched rather than
overwritten, ``4`` the index could not be written at all (unwritable
directory, full disk, revoked permission).

``3`` is the one an operator is most likely to meet by accident - a corpus that
is present but wholly unreadable will not quietly replace a working index with
an empty one. It is reported separately from ``1`` precisely because the two
call for different responses: ``1`` means the good documents were indexed and
some were not, ``3`` means nothing was indexed at all. ``4`` is the opposite
case again: there *was* something to index, and the filesystem refused it.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

# Put the backend root on sys.path before importing `app`, exactly as
# tests/conftest.py does, so `python scripts/ingest_laws.py` works from
# `backend/` without the package being installed.
_BACKEND_ROOT: Path = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.rag.pipeline import (  # noqa: E402
    IndexNotWrittenError,
    IngestionReport,
    build_index,
    default_index_dir,
    default_laws_dir,
    neutral_reason,
)

logger = logging.getLogger("scripts.ingest_laws")

#: Exit codes, named so the logic below reads as prose.
EXIT_OK: int = 0
EXIT_DOCUMENT_FAILED: int = 1
EXIT_NO_SOURCE: int = 2
#: Distinct from :data:`EXIT_DOCUMENT_FAILED` on purpose. "Some files failed but
#: the good ones were indexed" and "your working index was left alone because
#: this run found nothing" call for completely different operator responses, and
#: collapsing them into one code hides the second until someone notices the
#: knowledge base is stale.
EXIT_NOTHING_WRITTEN: int = 3

#: The index could not be written at all: the directory is unwritable, is a
#: file, the disk is full, or a permission was revoked mid-run. Distinct from
#: :data:`EXIT_NOTHING_WRITTEN` (which means "there was nothing to write and
#: your old index is safe") because here the run *did* have something to write
#: and could not. The operator has to fix the filesystem before retrying.
EXIT_WRITE_FAILED: int = 4

#: A filename on its own is not a secret and is what an operator needs in order
#: to fix the problem; the path to it is not needed and would leak the machine
#: layout, so failures print the bare name.
#:
#: A *display* budget, not a filesystem one. Nothing truncates the name on
#: disk: the full filename always survives in ``index_metadata.json``, and a
#: statute whose real name exceeds this is still indexed under its real
#: ``law_id``. This only bounds what one terminal line holds.
_MAX_FILENAME_CHARS: int = 80

#: How many characters of the tail a shortened filename keeps.
#:
#: Has to be long enough to carry the discriminating tail *and* the extension.
#: ``.pdf`` is four characters, and a name ending ``...BETA`` with no extension
#: reads as a directory rather than the file that failed.
_DISPLAY_SUFFIX_CHARS: int = 16


def _build_parser() -> argparse.ArgumentParser:
    """Construct the command-line parser.

    Returns:
        A parser with the ``--laws-dir``, ``--index-dir``, ``--dry-run`` and
        ``--verbose`` options.
    """
    parser = argparse.ArgumentParser(
        prog="ingest_laws",
        description=(
            "Build the local legal-information retrieval index from statute PDFs. "
            "Runs entirely locally: no network access and no API keys."
        ),
    )
    parser.add_argument(
        "--laws-dir",
        type=Path,
        default=default_laws_dir(),
        help="Directory of source *.pdf files (default: the configured data directory).",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=default_index_dir(),
        help="Directory to write the index into (default: the configured index directory).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report what would happen without writing any file.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Also emit per-document progress on the logging stream.",
    )
    return parser


def _shorten(filename: str) -> str:
    """Shorten a filename so two different failures stay distinguishable.

    A bare ``name[:80]`` produces this::

        FAILED Indian Penal Code 1860 as amended by Act YYYYYYYYYYYYYYYYYYY…
        FAILED Indian Penal Code 1860 as amended by Act YYYYYYYYYYYYYYYYYYY…

    Two genuinely different files print identically, so the operator cannot
    tell which one to re-download. Adding an ellipsis does not help — it marks
    the cut as *visible*, which is not the same as making the two lines
    differ, and it is the difference the operator actually needs.

    The head alone is therefore not enough, and neither is a longer head: the
    two names differ only in their final characters, so no prefix that fits the
    budget can ever separate them. What does separate them is the **tail**, so
    a shortened name keeps both ends::

        FAILED Indian Penal Code 1860 as amended by Act Y…PARTALPHA.pdf
        FAILED Indian Penal Code 1860 as amended by Act Y…PARTBETA.pdf

    Statute filenames follow a real pattern — ``Indian Penal Code 1860 as
    amended by Act X of YYYY`` — so the discriminating part sits at the end,
    where a head-truncation throws it away. The extension is forced into the
    tail as well, since ``PARTALPHA`` without ``.pdf`` reads as a directory.

    The full name always survives in ``index_metadata.json``, so nothing is
    lost either way; this only affects the summary a human reads.

    Args:
        filename: The bare filename.

    Returns:
        The filename unchanged when it fits the budget, otherwise its head and
        tail joined by an ellipsis, of at most :data:`_MAX_FILENAME_CHARS`
        characters in total.
    """
    if len(filename) <= _MAX_FILENAME_CHARS:
        return filename

    suffix = _DISPLAY_SUFFIX_CHARS
    # Two heads plus the ellipsis must fit the budget. The odd-width case keeps
    # the longer share on the head, which is the part carrying the statute's
    # identity; `//` is floor division, so the two shares never sum to more
    # than the space available.
    head_budget = (_MAX_FILENAME_CHARS - suffix) // 2
    tail_budget = _MAX_FILENAME_CHARS - suffix - head_budget
    return f"{filename[:head_budget]}…{filename[-tail_budget:]}"


def _has_pdf(laws_dir: Path) -> bool:
    """Return True when ``laws_dir`` holds at least one ``*.pdf`` file.

    Never raises. A directory that cannot be listed — denied permissions, a
    network share that dropped, a drive that went offline — answers False so
    the caller reports "no source PDFs" rather than crashing. That mirrors
    :func:`~app.rag.extraction.scan_law_pdfs`, which degrades to an empty tuple
    on the same condition.

    Args:
        laws_dir: Directory to check.

    Returns:
        True when a ``*.pdf`` regular file is present, else False.
    """
    try:
        return any(
            path.is_file() and path.suffix.lower() == ".pdf" for path in laws_dir.iterdir()
        )
    except OSError:
        logger.warning("Laws directory could not be listed; treating it as empty.")
        return False


def _configure_streams() -> None:
    """Make stdout and stderr able to carry a statute's own filename.

    A Hindi Act on disk is named in Devanagari, and this script prints that
    filename so the operator can find the file to fix. On the default Windows
    console the stream encodes as ``cp1252``, which cannot represent those
    characters at all — and the two failure modes are both unacceptable. With
    ``strict`` the operator gets a ``UnicodeEncodeError`` traceback after a
    perfectly good ingestion run; with the ``backslashreplace`` fallback that
    shells install, which is what a redirected pipe inherits, the name prints
    as ``à¤­à¤¾à¤°à¤¤à¥€``, mojibake they cannot read back to a filename.

    Reconfiguring to UTF-8 fixes the pipe. It cannot fix a console whose code
    page genuinely cannot hold the character, so ``backslashreplace`` stays the
    last resort — an escaped ``\\u092d...`` is still recoverable, where mojibake
    is not. Which of the three applies depends on the terminal, so all three
    are handled in order of preference.

    The attribute is absent on a stream replaced by a test double, hence the
    ``getattr`` guard: reporting a filename must never be the thing that
    raises.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except (ValueError, OSError, AttributeError):
            # A stream that refuses to be reconfigured (a closed or unusual
            # replacement) must not abort the run; backslashreplace is then
            # never installed and printing proceeds under the original rules.
            continue


def _configure_logging(verbose: bool) -> None:
    """Send library logging to stderr at a level chosen by ``--verbose``.

    Records go to stderr so that stdout stays a clean summary that a shell
    could redirect or parse.

    Args:
        verbose: When True, log at DEBUG, otherwise at WARNING.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _print_report(report: IngestionReport, *, dry_run: bool) -> None:
    """Print the human-readable run summary.

    Prints counts and one neutral line per failure. Never prints statute text.

    Args:
        report: The report produced by :func:`build_index`.
        dry_run: When True, word the summary to say nothing was written.
    """
    mode = "Dry run - nothing was written." if dry_run else "Index written."
    print(f"{report.source} ({mode})")
    print(f"  Laws directory      : {report.laws_dir}")
    print(f"  Index directory     : {report.index_dir}")
    print(f"  Documents found     : {report.documents_found}")
    print(f"  Documents ingested  : {report.documents_ingested}")
    print(f"  Documents failed    : {report.documents_failed}")
    print(f"  Chunks written      : {report.chunks_written}")

    for failure in report.failures:
        print(f"  FAILED {_shorten(failure.filename)}: {failure.reason}")

    for warning in report.warnings:
        print(f"  WARNING {warning}")

    if report.documents_ingested and not dry_run:
        print(
            "  Note: embeddings are not built yet, so the knowledge base still "
            "reports itself as not ready. That is expected."
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ingestion command line.

    Args:
        argv: Argument list excluding the program name. ``None`` (the default)
            reads ``sys.argv``.

    Returns:
        ``0`` on success, ``1`` if any document failed, ``2`` if the laws
        directory is missing, unreadable or contains no PDFs, ``3`` if the run
        produced no chunks and an existing index was therefore left untouched,
        ``4`` if the index could not be written at all.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_streams()
    _configure_logging(args.verbose)

    laws_dir: Path = args.laws_dir
    index_dir: Path = args.index_dir

    if not laws_dir.is_dir():
        print(f"No laws directory at {laws_dir}. Nothing to ingest.")
        return EXIT_NO_SOURCE

    # Check for an empty corpus BEFORE building. Building first would let a
    # zero-document run reach write_index, and an operator who deleted or moved
    # their PDFs would come back to a wiped index instead of an untouched one.
    if not _has_pdf(laws_dir):
        print(f"No PDF files in {laws_dir}. Nothing to ingest.")
        return EXIT_NO_SOURCE

    try:
        report = build_index(laws_dir, index_dir, dry_run=args.dry_run)
    except IndexNotWrittenError as exc:
        print(f"Nothing was written: {exc}")
        return EXIT_NOTHING_WRITTEN
    except OSError as exc:
        # An unwritable index directory, a disk that filled mid-write, a
        # revoked permission. Without this the process dies with a traceback
        # carrying absolute paths and OS error codes, which is exactly what
        # this script promises never to print. routed through neutral_reason,
        # the message keeps the category and loses the machine layout.
        print(f"Could not write the index: {neutral_reason(str(exc))}")
        print("  Your existing index, if any, was left untouched.")
        return EXIT_WRITE_FAILED

    _print_report(report, dry_run=args.dry_run)

    if report.documents_failed:
        return EXIT_DOCUMENT_FAILED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
