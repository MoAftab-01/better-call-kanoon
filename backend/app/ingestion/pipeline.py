"""Bounded local reads, content-addressed records, and non-overwriting JSON writes."""

import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .extraction import extract_pages, extract_sections
from .models import DocumentManifest, LegalDocument, ManifestEntry, SourceFile
from .paths import checked_path, output_path, source_path, validate_relative_path

DEFAULT_MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_COLLECTION_BYTES = 100 * 1024 * 1024
MAX_COLLECTION_CHARACTERS = 10_000_000
MAX_OUTPUT_BYTES = 128 * 1024 * 1024


@dataclass(frozen=True)
class IngestionResult:
    document_id: str
    status: str
    output_path: Path


def canonical_json(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def validation_message(error: ValidationError) -> str:
    # Do not echo manifest values (which may accidentally contain credentials).
    details = error.errors(include_input=False, include_url=False, include_context=False)
    return "; ".join(f"{'.'.join(map(str, item['loc']))}: {item['msg']}" for item in details[:10])


def read_bounded(path: Path, limit: int) -> bytes:
    path = checked_path(path)
    with path.open("rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Input must be a regular file.")
        if info.st_size > limit:
            raise ValueError(f"File exceeds the configured {limit}-byte size limit.")
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if (info.st_size, info.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or len(data) != info.st_size:
            raise ValueError("Input changed while being read; retry with an immutable source file.")
    if len(data) > limit:
        raise ValueError(f"File exceeds the configured {limit}-byte size limit.")
    if not data:
        raise ValueError("Empty files are not supported.")
    return data


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON keys are not allowed.")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("Non-finite JSON numbers are not allowed.")


def load_manifest(path: Path) -> DocumentManifest:
    data = read_bounded(path, MAX_MANIFEST_BYTES)
    try:
        value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Manifest must be valid UTF-8 JSON.") from exc
    try:
        return DocumentManifest.model_validate(value)
    except ValidationError as exc:
        raise ValueError("Invalid metadata manifest: " + validation_message(exc)) from exc


def _prepare(entry: ManifestEntry, root: Path, max_file_bytes: int, timestamp: datetime) -> LegalDocument:
    path = source_path(root, entry.file_path)
    suffix = path.suffix.lower()
    if suffix not in {".txt", ".pdf"}:
        raise ValueError("Only UTF-8 .txt and text-based .pdf sources are supported.")
    data = read_bounded(path, max_file_bytes)
    digest = hashlib.sha256(data).hexdigest()
    if entry.expected_sha256 is not None and digest != entry.expected_sha256:
        raise ValueError("Source SHA-256 does not match expected_sha256 in the manifest.")
    source = SourceFile(
        sha256=digest, size_bytes=len(data),
        media_type="application/pdf" if suffix == ".pdf" else "text/plain",
    )
    identity = {
        "schema_version": 1, "pipeline_version": "stage2a-v1",
        "metadata": entry.metadata.model_dump(mode="json"),
        "source_file": source.model_dump(mode="json"),
    }
    document_id = "doc_" + hashlib.sha256(canonical_json(identity)).hexdigest()
    pages, extraction = extract_pages(data, suffix, document_id)
    warnings = [
        "legal_applicability_not_independently_determined",
        "provenance_not_independently_verified", "structure_detection_is_heuristic",
    ]
    if entry.metadata.source_type == "synthetic":
        warnings.append("synthetic_fixture_not_law")
    return LegalDocument(
        document_id=document_id, metadata=entry.metadata, source_file=source,
        ingested_at=timestamp, extraction=extraction,
        pages=pages, sections=extract_sections(pages, document_id), warnings=sorted(warnings),
    )


def _existing_matches(target: Path, candidate: LegalDocument) -> bool:
    checked_path(target)
    if not target.exists():
        return False
    try:
        # Strict JSON decoding also rejects duplicated keys in a pre-existing output.
        value = json.loads(read_bounded(target, MAX_OUTPUT_BYTES).decode("utf-8"),
                           object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        previous = LegalDocument.model_validate(value)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Existing output is invalid; refusing to overwrite it.") from exc
    if previous.model_dump(mode="json", exclude={"ingested_at"}) != candidate.model_dump(mode="json", exclude={"ingested_at"}):
        raise ValueError("Existing output conflicts with extraction; refusing to overwrite it.")
    return True


def _write_new(root: Path, document: LegalDocument) -> IngestionResult:
    target = output_path(root, document.document_id)
    if _existing_matches(target, document):
        return IngestionResult(document.document_id, "unchanged", target)

    payload = canonical_json(document.model_dump(mode="json"))
    if len(payload) > MAX_OUTPUT_BYTES:
        raise ValueError("Normalized output exceeds the output size limit.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".ingest-", suffix=".tmp", dir=checked_path(root), delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        target = output_path(root, document.document_id)
        try:
            # Same-directory hard-link publication is atomic and NEVER replaces a file.
            # A crash before publication leaves at most an unreferenced .ingest-*.tmp.
            os.link(temporary, target, follow_symlinks=False)
        except FileExistsError:
            if _existing_matches(target, document):
                return IngestionResult(document.document_id, "unchanged", target)
            raise ValueError("Output appeared during ingestion; refusing to overwrite it.")
    finally:
        if temporary is not None:
            temporary = checked_path(temporary)
            temporary.unlink(missing_ok=True)
    return IngestionResult(document.document_id, "created", target)


def ingest_manifest(
    manifest_path: Path,
    output_dir: Path,
    *,
    source_root: Path | None = None,
    document: str | None = None,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ingested_at: datetime | None = None,
) -> list[IngestionResult]:
    if type(max_file_bytes) is not int or not 1 <= max_file_bytes <= MAX_COLLECTION_BYTES:
        raise ValueError("max_file_bytes must be positive and no more than 100 MiB.")
    manifest_path = checked_path(Path(manifest_path))
    root = checked_path(Path(source_root) if source_root is not None else manifest_path.parent)
    output = checked_path(Path(output_dir))
    if any(part.casefold() == ".git" for part in output.parts):
        raise ValueError("Ingestion output cannot be written inside Git metadata.")
    manifest = load_manifest(manifest_path)
    entries = manifest.documents
    if document is not None:
        validate_relative_path(document)
        entries = [entry for entry in entries if entry.file_path == document]
        if not entries:
            raise ValueError("The requested document is not listed in the manifest.")
    timestamp = ingested_at if ingested_at is not None else datetime.now(timezone.utc)
    prepared = []
    byte_count = character_count = 0
    # Complete validation/extraction before creating an output directory or any JSON.
    for entry in entries:
        record = _prepare(entry, root, max_file_bytes, timestamp)
        byte_count += record.source_file.size_bytes
        character_count += sum(len(page.text) for page in record.pages)
        if byte_count > MAX_COLLECTION_BYTES or character_count > MAX_COLLECTION_CHARACTERS:
            raise ValueError("Collection exceeds the 100-MiB input or 10,000,000-character text limit.")
        target = output_path(output, record.document_id)
        _existing_matches(target, record)
        prepared.append(record)
    output.mkdir(parents=True, exist_ok=True)
    checked_path(output)
    return [_write_new(output, record) for record in prepared]
