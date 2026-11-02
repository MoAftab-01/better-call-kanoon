# Stage 2A: offline legal-document ingestion

This pipeline processes **user-supplied local files and metadata**. It does not
download documents, access source URLs, verify authenticity, determine applicable
law, map old statutes to replacement statutes, or provide Indian legal coverage.
The included fixture is fabricated software test data, **not an Indian law**.

## Install and test (Windows PowerShell)

From the repository root, reuse the existing `.venv`:

```powershell
# Run from the repository root.
& '.\.venv\Scripts\python.exe' -m pip install -r .\backend\requirements.txt
& '.\.venv\Scripts\python.exe' -m pytest backend/tests -v
& '.\.venv\Scripts\python.exe' -m backend.app.ingestion --help
```

The only newly installed package is PyMuPDF. Pydantic is now an explicit direct
dependency; it was already installed through FastAPI. PyMuPDF has AGPL/commercial
[licensing terms](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright).

If the execution sandbox cannot access pytest's system temporary folder, use a
**new, unused** scratch location inside ignored `backend/data/`:

```powershell
New-Item -ItemType Directory -Path .\backend\data\test-runs -Force | Out-Null
$testScratch = '.\backend\data\test-runs\manual-' + [guid]::NewGuid().ToString('N')
& '.\.venv\Scripts\python.exe' -m pytest backend/tests -v --basetemp $testScratch
```

Do not point `--basetemp` at a directory containing valuable files: pytest owns
and may clear that directory. The tests create their own synthetic PDFs,
including empty and encrypted examples, and test real symlink/junction guards.

## Ingest the synthetic TXT fixture

These commands do not alter the fixture or its manifest:

```powershell
$manifest = '.\backend\tests\fixtures\synthetic-manifest.json'
$output = '.\backend\data\ingested-synthetic'
$sourceBefore = (Get-FileHash -LiteralPath '.\backend\tests\fixtures\synthetic-not-law.txt' -Algorithm SHA256).Hash

& '.\.venv\Scripts\python.exe' -m backend.app.ingestion --manifest $manifest --output-dir $output --document synthetic-not-law.txt
if ($LASTEXITCODE -ne 0) { throw 'Ingestion failed.' }

$recordFile = Get-ChildItem -LiteralPath $output -Filter 'doc_*.json' | Select-Object -First 1
Get-Content -LiteralPath $recordFile.FullName -Raw -Encoding UTF8
$before = Get-FileHash -LiteralPath $recordFile.FullName -Algorithm SHA256

& '.\.venv\Scripts\python.exe' -m backend.app.ingestion --manifest $manifest --output-dir $output --document synthetic-not-law.txt
if ($LASTEXITCODE -ne 0) { throw 'Repeat ingestion failed.' }

$after = Get-FileHash -LiteralPath $recordFile.FullName -Algorithm SHA256
if ($before.Hash -ne $after.Hash) { throw 'Repeat ingestion changed the JSON.' }
$sourceAfter = (Get-FileHash -LiteralPath '.\backend\tests\fixtures\synthetic-not-law.txt' -Algorithm SHA256).Hash
if ($sourceBefore -ne $sourceAfter) { throw 'Source file changed.' }
```

Expected on the first run in a fresh output directory: exit code **0**, a JSON
summary with `"created": 1`, `"unchanged": 0`, and one `doc_<64 hex digits>.json`.
On the second run: `"created": 0`, `"unchanged": 1`, the same document ID and
byte-for-byte identical JSON, including the original ingestion timestamp.
If the output already exists from an earlier test, the first run also reports
`unchanged`. Errors return exit code **2**, an error object on stderr, and no
traceback. Manifest validation errors omit input values to avoid echoing secrets.

Inspect the output for:

- `source_file.sha256` matching the original bytes and a UTC `ingested_at`.
- The original source URL, or `null` for this local synthetic fixture.
- Unknown dates, authority, jurisdiction, and applicability retained as `null`.
- `pages[0].page_number: null`: TXT has no physical PDF page number.
- Hindi, Unicode punctuation, numbering, and the line-ending hyphen retained.
- A preamble with no identifier, followed by unverified `Section 1` and
  `Section 2` candidates. These are **synthetic labels**, not real provisions.

## Manifest contract

Use `backend/tests/fixtures/synthetic-manifest.json` as the complete shape.
Every entry contains `file_path` and `metadata`. The root has integer
`schema_version: 1` and a nonempty `documents` array. Unknown fields and duplicate
JSON keys are rejected. Optional `expected_sha256` is a lowercase 64-digit hash
of the exact source bytes; when supplied, a mismatch fails ingestion.

Required metadata keys are `official_title`, `instrument_type`, `jurisdiction`,
`issuing_authority`, `source_url`, `source_type`, `language`, and `provenance`.
An official title is a **user-supplied claim**, not a verified title. Use explicit
`null` for an unknown jurisdiction, authority, or URL. Required string values may
not be blank. Language uses a language tag such as `en`, `hi`, `en-IN`, or
`unknown`; language is not automatically detected.

Optional metadata fields default to `null`: `state`, `retrieval_date`,
`enactment_date`, `publication_date`, `effective_date`, `amendment_version`, and
`legal_applicability`. Dates must be full `YYYY-MM-DD` calendar dates. If only
a year, a partial commencement date, or an uncertain legal version is known,
leave the date `null` and describe the uncertainty in provenance notes.
`effective_date` can record a supplied commencement date; partial or staggered
commencement must be described in notes rather than flattened into an inference.

Instrument values: `act`, `rule`, `regulation`, `notification`, `judgment`,
`order`, `circular`, `constitution`, `ordinance`, `other`, `unknown`.
Source values: `official_portal`, `official_gazette`, `official_court`,
`government_portal`, `user_supplied`, `secondary`, `synthetic`, `unknown`.

URLs must be HTTP(S) without whitespace or embedded username/password credentials.
The supplied URL string is preserved without canonicalization. A domain such as
`indiacode.nic.in`, `egazette.gov.in`, or a court/government domain **never**
changes verification status. No request is made to that URL.

### Provenance and verification

`metadata.provenance` records `supplied_by`, optional `notes`,
`verification_claim`, and optional `verification_evidence`.

- `verification_claim: "unverified"` is the default.
- `"user_claimed_verified"` requires a nonempty `verification_evidence` statement.
  The statement is retained as a user claim; the pipeline does not corroborate it.
- Every output has `provenance_status: "user_supplied"` and
  `verification_status: "not_independently_verified"`.
- The manifest cannot set an independently verified status. No independent
  verification workflow is implemented in Stage 2A.
- A source hash establishes the identity/integrity of the bytes processed;
  it does not prove authenticity, currency, completeness, or legal applicability.

## A local PDF or a collection

Place user-supplied source files under one directory and create an explicit JSON
manifest listing them. Use relative paths with `/` separators, including on
Windows. A collection is simply multiple entries in `documents`; metadata is
explicit for every entry. The same command handles TXT and PDF according to
each entry's extension:

```powershell
& '.\.venv\Scripts\python.exe' -m backend.app.ingestion --manifest '.\backend\data\sources\manifest.json' --output-dir '.\backend\data\normalized'
```

Omit `--document` for the whole collection; include `--document 'subdir/file.pdf'`
to select only entries with that exact manifest `file_path`. By default, files
must be under the manifest's directory. A deliberately configured `--source-root`
can designate another local directory; it is never read from the manifest.
No absolute source paths, `..`, backslashes, drive-relative paths, alternate
data streams, Windows device names, symlinks, or junctions are accepted.

## Output and deterministic identity

Each record contains validated metadata, source hash/size/media type, ingestion
timestamp, provenance statuses, extraction engine/version, ordered `pages`,
ordered `sections`, and explicit warnings. Local absolute source paths are not
embedded. The manifest maps a source file to its hash; section references use
`page_id`, physical `page_number`, and one-based inclusive normalized line ranges.

An excerpt from the included synthetic fixture's actual normalized record
(other fields omitted here; the emitted file contains the complete model):

```json
{
  "document_id": "doc_896aad1669bd001f183192adde169a841503a34e60d54f5c0d38cdfede9a46ef",
  "ingested_at": "2026-10-25T21:51:05.942959Z",
  "provenance_status": "user_supplied",
  "source_file": {
    "media_type": "text/plain",
    "sha256": "bbd0c63319f89502cfea2c0c596a59f175ec2e7484107e232f9d1fed68ea808d",
    "size_bytes": 527
  },
  "verification_status": "not_independently_verified"
}
```

The timestamp will differ for a fresh ingestion. Raw byte changes, including
checkout line-ending changes, also change the source hash and document ID.

The `document_id` hashes canonical metadata, source hash/size/type, schema
version, and pipeline version. It identifies an **exact file and metadata
record**, not an abstract statute across all versions. Identical bytes and
metadata keep the ID even after renaming a file. Metadata corrections or new
source bytes produce new IDs. No correspondence between old and replacement
statutes is inferred.

JSON is UTF-8, sorted by key, indented, and newline terminated. With a fixed
ingestion clock and the same extractor version it is byte-for-byte deterministic.
Fresh independent ingestions have different timestamps; repeats in the same
output directory preserve the first timestamp and do not touch the existing file.
An existing malformed/conflicting record is an error, not an overwrite. A changed
extractor/runtime version can cause a conflict; use a separate output directory
for that extraction run and compare the records manually.

All documents are validated/extracted and existing outputs checked before any
JSON is published. Each file is written to a same-directory temporary file,
flushed, and published through a non-overwriting hard link. The output filesystem
must support hard links, such as NTFS. A collection is not a database transaction:
an I/O failure during publication can leave earlier complete records. Rerunning
is safe. An abrupt process/power failure may leave `.ingest-*.tmp` files; these
are never treated as completed records. Output names are generated from validated
IDs, output paths reject symlinks/junctions, and Git metadata is not an output target.

## Extraction limits and review requirements

- Local `.pdf` and valid UTF-8 `.txt` only; an initial UTF-8 BOM is accepted.
  Empty, malformed, unsupported, or password-protected documents are rejected.
- Default source limit: **25 MiB**, configurable with `--max-file-size-mb 1` through
  `100`. Manifests: **1 MiB**, **100 entries**; collections: **100 MiB** input and
  **10 million** extracted characters; each document: **5 million** characters;
  PDFs: **2,000 physical pages**. Limits fail without discarding text silently.
- PyMuPDF reads the captured source bytes and never saves a source PDF. Physical
  PDF pages are preserved, including empty pages. Printed page labels are not
  assumed to match physical page numbers.
- No OCR, table reconstruction, column reordering, ligature expansion, header/footer
  removal, automatic dehyphenation, Unicode folding, renumbering, or legal-text
  correction. Reading order is unverified for **every PDF page**. Image-only/empty
  pages in mixed PDFs are flagged; entirely textless PDFs fail with an OCR message.
- Normalization changes CRLF/CR to LF, trims trailing spaces/tabs per line, and
  removes outer blank lines. It keeps internal spaces, indentation, paragraph
  boundaries, Unicode, numbering, hyphens, and words unchanged.
- Only explicit short English labels such as `Section 12. …`, `Rule 3`, or
  `Chapter IV` become **unverified heading candidates**. Bare numbers, prose
  cross-references, and unrecognized/non-English headings stay text without a
  fabricated identifier. Original normalized page text remains available.
- Section fragments stop at physical page boundaries. A continuation on another
  page is not assigned the previous page's section number by inference. Candidate
  labels and unidentified text both carry uncertainty flags and require review.
- The local CLI assumes cooperative access to its output directory; it is not a
  sandbox against a privileged process racing filesystem changes or a hostile PDF
  exploiting the native parser. Atomic visibility is not a guarantee of full
  filesystem durability under power loss. There is no claim of comprehensive
  Indian legal coverage or current legal applicability.

The FastAPI endpoints and approved frontend are unchanged and are not connected
to ingestion in this stage.
