# Publication evidence V2

Sanitized derived report; not byte-identical to the private V1 original. Historical test results/command examples below describe V1 unless explicitly labelled V2. Use the public migration guide for current V2 commands. No human approval or current-law claim is added.

# Stage 2D — controlled ingestion and extraction review

**Six documents ingested; six PARTIAL extraction-quality results; none BLOCKED.**
Integrity, metadata, page/line preservation and idempotency checks PASS.
PARTIAL records known Hindi/glyph limitations and pending visual review, not a
failed ingestion or a finding that a source law is invalid.

Output: **backend/data/processed/stage2d/v1/** — six content-addressed document JSON files.
The approved Stage 2A CLI/pipeline was used unchanged and offline.

[Machine-readable ingestion/quality audit](legal-document-ingestion-stage2d.json)
records commands, both runs, output hashes, per-page metrics, source acquisition
details, candidate headings and uncertainty flags keyed by document_id/page_id.

## Integrity and coverage

All six raw hashes matched the Stage 2C audit AND acquired manifest before
ingestion. Sizes matched and sources were read-only. Raw hashes, sizes,
modification times and read-only flags were rechecked afterwards.
The acquired manifest passed the strict Stage 2A loader/schema.

| Document | Extraction quality | Nonempty / PDF pages | Characters | Suspicious PDF pages | Source hash |
| --- | --- | ---: | ---: | --- | --- |
| BNS act | **PARTIAL** | 102/102 | 408,756 | 1 | PASS |
| BNSS act | **PARTIAL** | 249/249 | 855,966 | 1 | PASS |
| BSA act | **PARTIAL** | 47/47 | 170,521 | 1 | PASS |
| BNS notification | **PARTIAL** | 2/2 | 1,639 | 1 | PASS |
| BNSS notification | **PARTIAL** | 2/2 | 1,790 | 1 | PASS |
| BSA notification | **PARTIAL** | 2/2 | 1,547 | 1 | PASS |

**404/404 pages nonempty; 1,440,219 extracted Unicode characters; zero empty pages.**
These counts do not certify complete or correct semantic extraction.
Each page equals PyMuPDF extraction after documented Stage 2A normalization.
Section fragments reconstruct every normalized line without loss/overlap.
No text was corrected, dehyphenated, renumbered or inferred across pages.

Output mapping:

- **BNS act**: [doc_5d290011c13d9f72c4a2e5d98745efa61a195e10bf8b5546f425b9b7851b1574](../backend/data/processed/stage2d/v1/doc_5d290011c13d9f72c4a2e5d98745efa61a195e10bf8b5546f425b9b7851b1574.json); output SHA-256 26d15d1a54c64ba86bb17a776c9de26a73a727f3b245a066bd92f093b3e051fb.
- **BNSS act**: [doc_f38bf0b56725d0807173e5b9b633b5d3a98d36c60a16074c34be651b9cd34aa6](../backend/data/processed/stage2d/v1/doc_f38bf0b56725d0807173e5b9b633b5d3a98d36c60a16074c34be651b9cd34aa6.json); output SHA-256 579641be069ec37ce1324e4773604c572b4301b9cb97b3d410c90f15d714596e.
- **BSA act**: [doc_c70eadff021cda5bc6facfc7e764e83caeb7c4d114fe7b984de9a4fdcb19ae81](../backend/data/processed/stage2d/v1/doc_c70eadff021cda5bc6facfc7e764e83caeb7c4d114fe7b984de9a4fdcb19ae81.json); output SHA-256 33d8f596c53b0301a266ad795d4ff7631509cc1d9ebacbbb617b62c1586cd804.
- **BNS notification**: [doc_aff29a301e21598f7fe2e72f0a8bbc2e3bdf923b014480e5bb3e76564fd47654](../backend/data/processed/stage2d/v1/doc_aff29a301e21598f7fe2e72f0a8bbc2e3bdf923b014480e5bb3e76564fd47654.json); output SHA-256 eb7b007a054bacc0db8e3a9c10580974840db9a73034b508989c8a6111a120ee.
- **BNSS notification**: [doc_e694e3a724f30924d7cca0c493f3255db7c5e8ea9302fab401450da674b7c76e](../backend/data/processed/stage2d/v1/doc_e694e3a724f30924d7cca0c493f3255db7c5e8ea9302fab401450da674b7c76e.json); output SHA-256 2ca5bb047b91879f8baf62748175d7cb9507fb94713f321fb6bdd43a8cadee6a.
- **BSA notification**: [doc_648cf108a59bf5aad7e457f713d25da80c3e86c1cefbca84e419a48d1349a776](../backend/data/processed/stage2d/v1/doc_648cf108a59bf5aad7e457f713d25da80c3e86c1cefbca84e419a48d1349a776.json); output SHA-256 71cd76c2d13a9a675e5dc4d075507e3d6d5bb0c4c0e912e32a44c1856b81a429.

## Metadata and legal limitations

Every output's metadata exactly matches its acquired manifest entry: source URL,
original title, authority, supplied dates, retrieval date, version and provenance
evidence/limitations. Original Act/notification identifiers remain in source text
and references. The companion audit additionally preserves structured Stage 2C
identifiers, acquisition timestamps, final URLs, byte sizes and raw hashes.

The three original 2023 Acts remain distinct from the three 2024 commencement
notifications. No consolidated edition or later instrument was substituted.

Outputs retain user_supplied provenance, not_independently_verified verification,
an unverified manifest claim and null legal_applicability. Subsequent amendments,
corrigenda, commencement changes, State variations, savings/transition and
cryptographic PDF-signature validity remain unverified. This is not comprehensive
or certified current Indian law.

## Commencement preservation

The full English operative paragraphs and exact exceptions were matched against
Stage 2C evidence. Each notification remains its own two-page document. Observed
English paragraph boundaries are recorded by page ID and normalized line range:

- **BNS notification**: PDF page 2, normalized lines 8–11. Appoints 2024-07-01 except BNS section 106(2). Later commencement/status of that subsection remains unknown.
- **BNSS notification**: PDF page 2, normalized lines 8–11. Appoints 2024-07-01 except the First Schedule entry relating to BNS section 106(2); this does not exclude BNSS section 106(2). Later status remains unknown.
- **BSA notification**: PDF page 2, normalized lines 8–10. Appoints 2024-07-01; no provision-specific carve-out in this notification. This is not a finding of universal applicability or unchanged current law.

BNS, BNSS and their notifications retain effective_date **null**, avoiding an
all-provisions commencement claim. BSA's supplied 2024-07-01 date retains its
existing scope caveats. Later status of the excluded BNS subsection and
corresponding BNSS Schedule entry remains **unknown**.

## Hindi, Unicode and structure

| Document | Non-ASCII characters | Devanagari | Replacement characters | Candidate headings | Unidentified fragments |
| --- | ---: | ---: | ---: | ---: | ---: |
| BNS act | 864 | 9 | 0 | 21 | 99 |
| BNSS act | 757 | 9 | 0 | 40 | 245 |
| BSA act | 175 | 9 | 0 | 17 | 44 |
| BNS notification | 351 | 344 | 0 | 1 | 2 |
| BNSS notification | 409 | 402 | 0 | 1 | 2 |
| BSA notification | 325 | 318 | 0 | 1 | 2 |

BNS Act and BNS notification first pages were rendered and inspected in memory.
Visible Hindi is not faithfully represented by all extracted glyph codes.
Act headers using Vivek-BoldA produce Latin-coded strings such as vlk/kkj.k,
Hkkx and izkf/kdkj. Notification page 1 contains Devanagari but has unreliable
glyph substitutions/mapping. All six first pages require visual comparison.
Other documents were not exhaustively visually transcribed.

No OCR, transliteration, silent repair or fabricated missing text was applied.
Zero replacement characters does not prove correct Hindi. Empty/sparse text,
private-use and unexpected-control checks found no additional suspicious pages.
Reading order remains unverified for every PDF page. Columns/tables/forms and
cross-page provisions require review. Non-ASCII counts also include punctuation.

Detailed extra flags are in the companion audit; normalized records were not
post-edited. Metadata already preserves the Stage 2C Hindi warning, and pages
retain pipeline warnings.

Bare-numbered provisions remain text without invented section identifiers.
Chapter/Part headings remain heuristic candidates. Some PART II candidates are
Gazette mastheads, not an Act Part; these are not a validated legal hierarchy.

## Verification results

- First run: **created 6, unchanged 0**, exit 0.
- Second run: **created 0, unchanged 6**, exit 0.
- Output IDs, hashes, sizes, write times and original ingestion timestamps match.
  Exactly six output files; no duplicate or leftover temporary files.
- **84 backend tests passed**, zero failures/skips. One existing Starlette
  TestClient/HTTPX deprecation warning; no dependency change.
- Actual-corpus assertions passed: raw integrity/immutability, output schema,
  metadata equality, 404 physical pages, normalized text equality, complete
  section-line coverage and preservation of notification operative exceptions.
- No new tests/code were needed. Existing tests cover mismatched hashes,
  Unicode, provenance, pages, uncertain headings, offline use and idempotency.
- Fingerprints matched for **1,221** protected application, test,
  frontend, approved research/manifest and Git metadata files.

## Manual Windows PowerShell verification

Run from the repository root. Inspection does not change source or output files.

### File count, hashes and coverage

~~~powershell
# Run from the repository root.
$audit = Get-Content -LiteralPath '.\docs\legal-document-ingestion-stage2d.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$output = $audit.output_directory
$files = @(Get-ChildItem -LiteralPath $output -File -Filter 'doc_*.json')
if ($files.Count -ne 6) { throw 'Expected six output records.' }
$audit.documents | Select-Object document,status,pdf_pages,nonempty_pages,extracted_characters,suspicious_pages | Format-Table -AutoSize
foreach ($item in $audit.documents) {
    $raw = Get-Item -LiteralPath $item.raw_path
    if ((Get-FileHash -LiteralPath $raw.FullName -Algorithm SHA256).Hash -ine $item.source_sha256 -or -not $raw.IsReadOnly) {
        throw "Source mismatch/read-only flag missing: $($item.document)"
    }
    if ((Get-FileHash -LiteralPath $item.output_path -Algorithm SHA256).Hash -ine $item.output_sha256) {
        throw "Output mismatch: $($item.document)"
    }
    "PASS hashes: $($item.document)"
}
~~~

### Metadata, page references, English/Hindi samples and flags

~~~powershell
foreach ($item in $audit.documents) {
    $record = Get-Content -LiteralPath $item.output_path -Raw -Encoding UTF8 | ConvertFrom-Json
    "DOCUMENT: $($item.document) / $($record.document_id)"
    $record.metadata | ConvertTo-Json -Depth 8
    $record | Select-Object ingested_at,provenance_status,verification_status
    $record.pages | Select-Object ordinal,page_number,page_id,warnings | Format-Table -AutoSize
    $sample = if ($record.metadata.instrument_type -eq 'notification') { $record.pages[1] } else { $record.pages[0] }
    $sample.text
    $item.non_ascii_samples | ConvertTo-Json -Depth 8
    $item.page_metrics | Where-Object { $_.quality_flags.Count -gt 0 } | Select-Object pdf_page,page_id,quality_flags | Format-List
}
# Optional: open an original PDF for comparison.
# Invoke-Item -LiteralPath $audit.documents[0].raw_path
~~~

Confirm BNS/BNSS effective_date is null, and notification exceptions remain on
English page 2. Compare uncertain Hindi with rendered PDF page 1; do not treat
the extracted Hindi as a corrected authoritative transcript.

### Schema, page-text and section-line validation

~~~powershell
@'
from pathlib import Path
import hashlib, json
import pymupdf
from backend.app.ingestion.pipeline import load_manifest
from backend.app.ingestion.models import LegalDocument
from backend.app.ingestion.extraction import normalize_text
audit = json.loads(Path("docs/legal-document-ingestion-stage2d.json").read_text(encoding="utf-8"))
manifest = load_manifest(Path(audit["manifest_path"]))
entries = {e.expected_sha256: e for e in manifest.documents}
total = 0
for item in audit["documents"]:
    path = Path(item["output_path"])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item["output_sha256"]
    record = LegalDocument.model_validate_json(path.read_bytes())
    entry = entries[record.source_file.sha256]
    assert record.metadata == entry.metadata
    assert record.verification_status == "not_independently_verified"
    assert record.metadata.legal_applicability is None
    assert hashlib.sha256(Path(item["raw_path"]).read_bytes()).hexdigest() == entry.expected_sha256
    with pymupdf.open(item["raw_path"]) as pdf:
        assert len(pdf) == len(record.pages) == item["pdf_pages"]
        for number, (source, page) in enumerate(zip(pdf, record.pages, strict=True), 1):
            assert page.ordinal == page.page_number == number
            assert page.text == normalize_text(source.get_text("text", sort=False))
            parts = [s for s in record.sections if s.page_id == page.page_id]
            assert "\n".join(s.text for s in parts) == page.text
            for s in parts:
                assert s.page_number == number and s.uncertainties
                assert s.text == "\n".join(page.text.split("\n")[s.start_line-1:s.end_line])
    total += len(record.pages)
    print(item["document"], "schema/metadata/pages/lines: PASS")
assert total == 404
print("PASS: six records, 404 pages; inspection only.")
'@ | & '.\.venv\Scripts\python.exe' -B -
if ($LASTEXITCODE -ne 0) { throw 'Verification failed.' }
~~~

### Repeat ingestion and compare output hashes/write times

Do not change the manifest or records between commands. Changed metadata or
extractor versions require a separate output version, not an overwrite.

~~~powershell
$before = @{}
Get-ChildItem -LiteralPath $output -File -Filter 'doc_*.json' | ForEach-Object {
    $before[$_.Name] = @{Hash=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash;Ticks=$_.LastWriteTimeUtc.Ticks;Bytes=$_.Length}
}
$result = & '.\.venv\Scripts\python.exe' -B -m backend.app.ingestion --manifest '.\docs\acquired-legal-source-manifest-stage2c.json' --source-root '.\backend\data\raw' --output-dir $output
if ($LASTEXITCODE -ne 0) { throw 'Repeat ingestion failed.' }
$summary = $result | ConvertFrom-Json
if ($summary.created -ne 0 -or $summary.unchanged -ne 6) { throw 'Unexpected repeat summary.' }
$after = @(Get-ChildItem -LiteralPath $output -File -Filter 'doc_*.json')
if ($after.Count -ne $before.Count) { throw 'Output count changed.' }
foreach ($file in $after) {
    $prior = $before[$file.Name]
    if ($null -eq $prior -or $prior.Hash -ine (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -or $prior.Ticks -ne $file.LastWriteTimeUtc.Ticks -or $prior.Bytes -ne $file.Length) {
        throw "Output changed: $($file.Name)"
    }
}
$summary | Select-Object created,unchanged,verification_status
~~~

Expected: **created 0, unchanged 6**, with identical hashes/sizes/write times.

### Backend tests

~~~powershell
$testScratch = '.\backend\data\test-runs\manual-stage2d-' + [guid]::NewGuid().ToString('N')
& '.\.venv\Scripts\python.exe' -B -m pytest backend/tests -v --basetemp $testScratch -p no:cacheprovider
~~~

Use a fresh scratch directory; pytest owns its temporary contents.

## Artifacts and stop point

Created six normalized records, this report and the companion audit. Tests also
created isolated synthetic scratch data under backend/data/test-runs/.
Existing backend/data/ ignore rules cover raw/generated data.

No pipeline, API, frontend or dependency changes. No further acquisition, index,
embeddings, RAG, LLM, voice, commit or push. No next stage was started.

**Stopped for manual verification and approval.**
