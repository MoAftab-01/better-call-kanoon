"""Ingestion orchestration for the local law-PDF corpus.

This module is the seam between the three pure stages of Stage 2 - scanning
(``extraction``), text recovery (``documents``) and segmentation
(``chunking``) - and the two files on disk that make up the retrieval index.
It holds no parsing logic of its own: it walks a directory, drives the other
modules, and records what happened.

Two properties matter more than speed here.

**A bad PDF must never abort a run.** A single corrupt, encrypted or purely
scanned file is recorded as an :class:`IngestionFailure` and the walk
continues. Only a genuine programming error propagates, because swallowing
those would hide bugs behind a green run.

**Nothing outside the directory it was handed is read.** ``build_index``
takes its corpus as an argument and never consults ``settings.DATA_DIR``, so
a caller cannot accidentally ingest - or index - files it did not name.
Every collaborator is therefore imported as a module attribute and called
through it, rather than bound into this module's namespace at import time.
That is not a test-only concern: it is what keeps the guarantee checkable.

**The index is written atomically and honestly.** ``chunks.json`` and
``index_metadata.json`` are each written to a sibling ``*.tmp`` file and then
moved into place with :func:`os.replace`, so a crashed or killed run can never
leave a half-written index that reports itself as ready. This module
deliberately writes exactly those two files and never ``embeddings.npy``, so
``settings.knowledge_base_ready`` correctly reports ``False`` after a run.
That is the intended, honest state - a text index without vectors is not a
finished knowledge base, and the readiness flag says so.

**This is still true after Stage 3, and the reason has changed.** Stage 3
shipped the *lexical* half of hybrid retrieval (``rag.lexical`` and
``rag.scoring``), which needs no model and runs on the standard library alone.
The *dense* half needs an embedding backend that is not installed, so the
retriever reports ``retriever_used='lexical_only'`` rather than a hybrid score
that silently ignored half its inputs. The distinction is worth keeping sharp:
the retrieval code exists and is tested, but on a machine with no embedding
backend the fusion path runs single-retriever, and no measured claim is made
about its quality. See the module docstring in ``rag.scoring``.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.rag import chunking as _chunking
from app.rag import extraction as _extraction
from app.rag.chunking import Chunk, ChunkingConfig
from app.rag.documents import SourceDocument
from app.rag.extraction import ExtractionError

logger = logging.getLogger(__name__)

#: Version stamped into both index artefacts. Bump when the JSON shape changes
#: so a later stage can tell an old index from a new one instead of guessing.
SCHEMA_VERSION: int = 1

#: Recorded in ``index_metadata.json`` so an index can be traced back to the
#: command that produced it.
GENERATED_BY: str = "scripts/ingest_laws.py"

#: Human-readable provenance of an index, surfaced through ``/api/health``.
INGESTION_SOURCE: str = "local statute PDFs"

#: Filenames this module owns. ``embeddings.npy`` is absent on purpose - it
#: belongs to the dense retriever, whose backend is not installed, and
#: ``settings.INDEX_ARTEFACTS`` requires all three, so ``knowledge_base_ready``
#: stays False until embeddings exist. The lexical index is built in memory from
#: ``chunks.json`` on each search, so it needs no file of its own.
CHUNKS_FILENAME: str = "chunks.json"
METADATA_FILENAME: str = "index_metadata.json"

#: Suffix used for the sibling temporary file during a write.
_TEMP_SUFFIX: str = ".tmp"

#: The artefacts that together constitute a usable index.
#:
#: Used both to write the pair atomically and to decide whether an existing
#: index is worth protecting. Deliberately the *files*, not "is the directory
#: non-empty": a stray ``.tmp`` from a crashed run or an unrelated notes file
#: is not an index, and treating one as a working index blocks every
#: subsequent run behind a message that claims something was preserved.
INDEX_ARTEFACT_FILENAMES: tuple[str, ...] = (CHUNKS_FILENAME, METADATA_FILENAME)

#: Longest failure reason recorded or printed. A reason is a short label for a
#: human, not a diagnostic dump.
_MAX_REASON_CHARS: int = 200

# Windows drive paths (``C:\...``), UNC shares (``\\server\share\...``) and
# POSIX absolute paths (``/home/...``). A neutral failure reason should never
# carry one: it leaks the machine layout of whoever ran the build into a string
# that may be printed, logged or served.
#
# Each alternative is *closed* — ``[^\r\n"']*`` rather than a word character
# class — because a path may contain spaces. An operator's laws directory
# sitting under ``C:\Users\Jane Doe\laws`` or ``/home/jane/My Laws`` is
# ordinary, and a pattern that stops at the first space masks ``C:\Users\Jane``
# and then leaves `` Doe\laws\BNS.pdf`` sitting in the message, which is the
# part that actually identifies the person. A UNC share is matched whole for
# the same reason: the server name alone identifies the machine and often the
# organisation.
#
# Newline is the terminator, not whitespace, because a path runs to the end of
# its line. Two file paths in one message is ordinary — a tuple of candidates,
# a ``rename`` naming both ends — and stopping at the first space would mask
# only ``C:\Users\Jane Doe\laws\BNS.pdf`` and leave the second path in full.
# :func:`neutral_reason` collapses the newlines afterwards.
_ABS_PATH_RE = re.compile(
    r"[A-Za-z]:[\\/][^\r\n\"']*"
    r"|\\\\[^\r\n\"'\\/]+[\\/][^\r\n\"']*"
    r"|/(?:[^\r\n\"'/]+/)+[^\r\n\"']*"
)


class IndexNotWrittenError(RuntimeError):
    """Raised when a run would publish an empty index over a working one.

    The message states what was left alone and why; it never names a path.
    The CLI turns this into a distinct exit code so an operator can tell
    "nothing was written" apart from "some documents failed".
    """


@dataclass(frozen=True)
class IngestionFailure:
    """One source PDF that could not be turned into chunks.

    Attributes:
        law_id: Normalised identifier of the document that failed.
        filename: Bare filename, never a full path.
        reason: Neutral, human-readable explanation. Never an exception
            traceback and never a raw library message.
    """

    law_id: str
    filename: str
    reason: str


@dataclass(frozen=True)
class IngestionReport:
    """Outcome of a whole ingestion run.

    Attributes:
        documents_found: PDFs discovered under the laws directory.
        documents_ingested: PDFs successfully extracted and chunked.
        documents_failed: PDFs recorded as failures.
        chunks_written: Number of chunks produced across all documents.
        failures: One record per failed document, in scan order.
        warnings: Non-fatal notes, each prefixed with the law it concerns.
        index_dir: Directory the index artefacts were written to.
        laws_dir: Directory that was scanned.
        source: Provenance label for the resulting index.
    """

    documents_found: int
    documents_ingested: int
    documents_failed: int
    chunks_written: int
    failures: tuple[IngestionFailure, ...]
    warnings: tuple[str, ...]
    index_dir: Path
    laws_dir: Path
    source: str


def neutral_reason(raw: str) -> str:
    """Reduce an arbitrary message to a short, path-free, single-line label.

    Defence in depth for project rule 5. :class:`ExtractionError` already
    carries a neutral reason by contract, but this is the last gate before a
    message reaches a report, a log line or stdout - so anything that looks
    like a filesystem path is replaced, newlines are collapsed and the result
    is truncated.

    Args:
        raw: The message to sanitise. May be empty or contain anything.

    Returns:
        A single-line string of at most ``_MAX_REASON_CHARS`` characters, with
        absolute paths replaced by ``<path>``.
    """
    text = _ABS_PATH_RE.sub("<path>", str(raw))
    text = " ".join(text.split())
    if not text:
        return "unspecified reason"
    if len(text) > _MAX_REASON_CHARS:
        text = text[: _MAX_REASON_CHARS - 1].rstrip() + "…"
    return text


def _chunk_payload(chunk: Chunk) -> dict[str, object]:
    """Render one chunk as the exact JSON object written to ``chunks.json``.

    Fields are spelled out rather than dumped with ``dataclasses.asdict`` so a
    field added to :class:`Chunk` later cannot silently leak into the on-disk
    schema.

    Args:
        chunk: The chunk to serialise.

    Returns:
        A JSON-serialisable mapping with a fixed key order.
    """
    return {
        "chunk_id": chunk.chunk_id,
        "law_id": chunk.law_id,
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "section_label": chunk.section_label,
        "section_detection": chunk.section_detection,
    }


def _document_payload(
    document: SourceDocument,
    page_count: int,
    chunk_count: int,
) -> dict[str, object]:
    """Render one source document as its ``index_metadata.json`` entry.

    Args:
        document: The document the entry describes.
        page_count: Pages extracted from it during this run.
        chunk_count: Chunks produced from it during this run.

    Returns:
        A JSON-serialisable mapping with a fixed key order.
    """
    return {
        "law_id": document.law_id,
        "act_name": document.act_name,
        "year": document.year,
        "filename": document.path.name,
        "size_bytes": document.size_bytes,
        "sha256": document.sha256,
        "page_count": page_count,
        "chunk_count": chunk_count,
    }


def _failure_payload(failure: IngestionFailure) -> dict[str, str]:
    """Render one failure as its ``index_metadata.json`` entry.

    Args:
        failure: The failure to serialise.

    Returns:
        A JSON-serialisable mapping with a fixed key order.
    """
    return {
        "law_id": failure.law_id,
        "filename": failure.filename,
        "reason": failure.reason,
    }


def _atomic_write_text(path: Path, payload: str) -> None:
    """Write text to ``path`` atomically, leaving no ``*.tmp`` behind.

    The content goes to a sibling temporary file which is flushed and fsynced,
    then moved into place with :func:`os.replace`, which is atomic on Windows
    and POSIX alike. A reader therefore sees either the previous file or the
    complete new one - never a truncated index.

    Args:
        path: Destination file. Its parent directory must already exist.
        payload: Exact text to write, already serialised.

    Raises:
        OSError: If the temporary file cannot be written or moved into place.
            The temporary file is removed before the error propagates.
    """
    _stage_temp_file(path, payload)
    os.replace(path.with_name(path.name + _TEMP_SUFFIX), path)


def _stage_temp_file(path: Path, payload: str) -> None:
    """Write ``payload`` to ``path``'s sibling temporary file, fully flushed.

    Split out from :func:`_atomic_write_text` so that a *set* of files can be
    staged first and moved into place afterwards. Staging everything before
    moving anything is what makes the pair write all-or-nothing: if the third
    file cannot be written, nothing has been replaced yet.

    Args:
        path: The destination the temporary is staged for.
        payload: Exact text to write, already serialised.

    Raises:
        OSError: If the temporary file cannot be written.
    """
    tmp_path = path.with_name(path.name + _TEMP_SUFFIX)
    try:
        with tmp_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        # Includes KeyboardInterrupt/SystemExit: a killed run must not leave a
        # stray .tmp sitting next to the index.
        tmp_path.unlink(missing_ok=True)
        raise


def _dump_json(payload: object) -> str:
    """Serialise a payload to pretty-printed JSON text.

    ``ensure_ascii=False`` keeps Devanagari and every other non-Latin script
    readable in the artefact instead of escaping it to ``\\uXXXX``.

    Args:
        payload: Any JSON-serialisable object.

    Returns:
        The serialised document, newline-terminated.
    """
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write_index(
    report_chunks: Sequence[Chunk],
    documents: Sequence[SourceDocument],
    index_dir: Path,
    *,
    failures: Sequence[IngestionFailure] = (),
    page_counts: Mapping[str, int] | None = None,
) -> int:
    """Write ``chunks.json`` and ``index_metadata.json`` into ``index_dir``.

    Exactly two files are written. ``embeddings.npy`` is deliberately NOT
    written here: the dense retriever's backend is not installed, so after a
    run ``settings.knowledge_base_ready`` correctly reports ``False`` (it
    requires all three of ``settings.INDEX_ARTEFACTS``). A test pins that
    behaviour. Stage 3 does not change this - its lexical half reads
    ``chunks.json`` directly and writes nothing.

    Writes are atomic, so an interrupted run cannot leave an index that
    reports itself as ready.

    Args:
        report_chunks: Every chunk produced by the run, in document order.
        documents: The documents the chunks came from.
        index_dir: Destination directory; created if it does not exist.
        failures: Failures to record in the metadata file. Optional keyword so
            the documented three-argument call still works; without it the
            ``failures`` list is written empty.
        page_counts: Page count per ``law_id``. Optional keyword; when absent
            a document's page count is derived from its highest ``page_end``.

    Returns:
        The number of chunks written.
    """
    index_dir.mkdir(parents=True, exist_ok=True)

    derived_pages: dict[str, int] = {}
    chunk_counts: dict[str, int] = {}
    for chunk in report_chunks:
        chunk_counts[chunk.law_id] = chunk_counts.get(chunk.law_id, 0) + 1
        seen = derived_pages.get(chunk.law_id, 0)
        derived_pages[chunk.law_id] = max(seen, chunk.page_end)

    resolved_pages = derived_pages if page_counts is None else dict(page_counts)

    document_entries = [
        _document_payload(
            document,
            resolved_pages.get(document.law_id, 0),
            chunk_counts.get(document.law_id, 0),
        )
        for document in documents
    ]

    chunks_doc = {
        "schema_version": SCHEMA_VERSION,
        "chunks": [_chunk_payload(chunk) for chunk in report_chunks],
    }
    metadata_doc = {
        "schema_version": SCHEMA_VERSION,
        "chunk_count": len(report_chunks),
        "document_count": len(documents),
        "documents": document_entries,
        "failures": [_failure_payload(failure) for failure in failures],
        "generated_by": GENERATED_BY,
    }

    _write_index_atomically(
        (
            (index_dir / CHUNKS_FILENAME, _dump_json(chunks_doc)),
            (index_dir / METADATA_FILENAME, _dump_json(metadata_doc)),
        )
    )
    logger.info(
        "Wrote %d chunk(s) for %d document(s) to the index directory.",
        len(report_chunks),
        len(documents),
    )
    return len(report_chunks)


def _write_index_atomically(artefacts: Sequence[tuple[Path, str]]) -> None:
    """Write several index artefacts so that all or none of them land.

    Per-file atomicity is not enough for a set. Writing ``chunks.json`` and then
    ``index_metadata.json`` as two independent replacements means a disk that
    fills between them leaves a *torn* index: chunks from the new run,
    metadata still describing the old one. That is worse than either a stale
    index or a missing one, because the two files disagree about what exists and
    nothing on disk ties the new chunks to a source document. A health check
    reading the metadata then under-reports a real index by the size of the
    whole new corpus.

    So: stage every temporary file first, and only once all of them are written
    and fsynced does anything move into place. If staging fails, no
    destination has been touched and the previous index is intact.

    The moves themselves cannot be made atomic as a group — there is no
    multi-file rename — so the residual window is the microseconds between
    ``os.replace`` calls, during which a reader could still observe a mixed
    pair. Closing it entirely needs a directory-level swap, which is not
    portable to Windows. Staging removes the failure that actually happens in
    practice (a full disk mid-write) rather than the one that does not.

    Args:
        artefacts: ``(path, serialised text)`` pairs, in write order.

    Raises:
        OSError: If any file cannot be staged or moved. On a staging failure no
            destination was modified and no temporary is left behind.
    """
    staged: list[tuple[Path, Path]] = []
    try:
        for path, payload in artefacts:
            _stage_temp_file(path, payload)
            staged.append((path.with_name(path.name + _TEMP_SUFFIX), path))
    except BaseException:
        for tmp_path, _ in staged:
            tmp_path.unlink(missing_ok=True)
        raise

    for tmp_path, destination in staged:
        os.replace(tmp_path, destination)


def build_index(
    laws_dir: Path,
    index_dir: Path,
    config: ChunkingConfig | None = None,
    *,
    dry_run: bool = False,
) -> IngestionReport:
    """Scan a directory of law PDFs and write the retrieval index.

    One unusable PDF is recorded as an :class:`IngestionFailure` and the walk
    continues; only a programming error propagates. With ``dry_run=True`` the
    same walk runs and the same report is produced, but nothing is written and
    ``index_dir`` is not even created.

    Args:
        laws_dir: Directory holding the source ``*.pdf`` files. Scanned
            non-recursively. Missing or empty yields zero documents, not an
            error.
        index_dir: Directory the index artefacts are written to. Created by
            :func:`write_index` if missing; untouched when ``dry_run``.
        config: Chunking configuration; :class:`ChunkingConfig` defaults are
            used when omitted.
        dry_run: When True, do all the parsing and chunking but write nothing.
            Optional keyword; the documented three-argument call writes.

    Returns:
        An :class:`IngestionReport` describing what was found, ingested and
        failed. A missing or empty ``laws_dir`` produces a report with zeroes
        rather than an exception.
    """
    documents = _extraction.scan_law_pdfs(laws_dir)
    logger.info("Found %d law PDF(s) to ingest.", len(documents))

    chunks: list[Chunk] = []
    ingested: list[SourceDocument] = []
    page_counts: dict[str, int] = {}
    failures: list[IngestionFailure] = []
    warnings: list[str] = []

    for document in documents:
        filename = document.path.name
        try:
            extraction = _extraction.extract_document(document)
        except ExtractionError as exc:
            # The expected failure. Record it and move to the next file - one
            # unreadable PDF must not cost us the whole corpus.
            reason = neutral_reason(str(exc))
            logger.warning("Skipping %s: %s", filename, reason)
            failures.append(
                IngestionFailure(law_id=document.law_id, filename=filename, reason=reason)
            )
            continue

        document_chunks = _chunking.chunk_document(extraction, config)
        chunks.extend(document_chunks)
        ingested.append(document)
        page_counts[document.law_id] = extraction.page_count

        for warning in extraction.warnings:
            warnings.append(f"{document.law_id}: {warning}")

        logger.info(
            "Ingested %s: %d page(s), %d chunk(s).",
            filename,
            extraction.page_count,
            len(document_chunks),
        )

    if not dry_run and not chunks:
        # Refuse to publish an empty index over a working one.
        #
        # A zero-chunk result is almost never intended: the corpus is empty,
        # every file failed to extract, or a bad download overwrote a good
        # filename with an unreadable scan. Writing it would silently destroy
        # the only usable index, and the resulting artefacts would be
        # indistinguishable from a deliberately empty one. The operator is
        # better served by an error they can see than by an index that
        # reports zero documents and no explanation.
        if _has_existing_index(index_dir):
            raise IndexNotWrittenError(
                "the corpus produced no chunks, so the existing index was left "
                "untouched; remove the index directory yourself if you meant to "
                "empty it"
            )
        logger.warning(
            "No chunks were produced and no previous index exists; writing an empty index."
        )

    written = (
        0
        if dry_run
        else write_index(
            chunks,
            ingested,
            index_dir,
            failures=failures,
            page_counts=page_counts,
        )
    )

    return IngestionReport(
        documents_found=len(documents),
        documents_ingested=len(ingested),
        documents_failed=len(failures),
        chunks_written=written,
        failures=tuple(failures),
        warnings=tuple(warnings),
        index_dir=Path(index_dir),
        laws_dir=Path(laws_dir),
        source=INGESTION_SOURCE,
    )


def _has_existing_index(index_dir: Path) -> bool:
    """Return True when ``index_dir`` holds an index worth protecting.

    Tests for the artefacts this module actually owns, not for a non-empty
    directory. A directory holding only a stale ``chunks.json.tmp`` from a
    crashed run, or an unrelated notes file, contains no index — treating it
    as one blocks every future run behind a message asserting that something
    was preserved when nothing was.

    Args:
        index_dir: The index directory to inspect.

    Returns:
        True when at least one of :data:`INDEX_ARTEFACT_FILENAMES` is present.
    """
    for filename in INDEX_ARTEFACT_FILENAMES:
        try:
            if (index_dir / filename).exists():
                return True
        except OSError:
            continue
    return False


def default_laws_dir() -> Path:
    """Return the configured directory holding law PDFs.

    Returns:
        ``settings.DATA_DIR / "laws"``, resolved from the environment.
    """
    from app.config import get_settings

    return get_settings().DATA_DIR / "laws"


def default_index_dir() -> Path:
    """Return the configured index directory.

    Returns:
        ``settings.INDEX_DIR``, resolved from the environment.
    """
    from app.config import get_settings

    return get_settings().INDEX_DIR


__all__ = [
    "CHUNKS_FILENAME",
    "GENERATED_BY",
    "INDEX_ARTEFACT_FILENAMES",
    "INGESTION_SOURCE",
    "METADATA_FILENAME",
    "SCHEMA_VERSION",
    "IngestionFailure",
    "IngestionReport",
    "IndexNotWrittenError",
    "build_index",
    "default_index_dir",
    "default_laws_dir",
    "neutral_reason",
    "write_index",
]
