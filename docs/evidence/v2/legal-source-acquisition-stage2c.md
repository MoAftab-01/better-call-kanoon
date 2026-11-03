# Publication evidence V2

Sanitized derived report; not byte-identical to the private V1 original. Historical test results/command examples below describe V1 unless explicitly labelled V2. Use the public migration guide for current V2 commands. No human approval or current-law claim is added.

# Stage 2C — resumed acquisition and validation

Review date: **2026-10-27 (Asia/Kolkata)**.

**6/6 acquired; six PASS for acquisition and printed-document identity.**
PASS does not certify legal currentness, comprehensive coverage, cryptographic
signature validity, or applicability to a particular proceeding or jurisdiction.

The [JSON acquisition audit](legal-source-acquisition-stage2c.json) records the
successful run, response metadata, timestamps, checks and page-specific evidence.
Its previous_runs[0] preserves the complete earlier TLS-blocked audit.
The approved Stage 2B inventory/proposal remain unchanged.

| Document | Acquisition / identity | Bytes | PDF pages |
| --- | --- | ---: | ---: |
| BNS act | **PASS** | 1,382,923 | 102 |
| BNSS act | **PASS** | 2,033,181 | 249 |
| BSA act | **PASS** | 1,218,408 | 47 |
| BNS notification | **PASS** | 922,134 | 2 |
| BNSS notification | **PASS** | 924,297 | 2 |
| BSA notification | **PASS** | 922,833 | 2 |

All six candidates returned **HTTP 200**, application/pdf, and matching
Content-Length. Each succeeded on its first attempt with **no redirects**.
No inaccessible source, identity mismatch, substituted source, or blocked
document remains in this run.

## Sources and raw files

- **BNS act**: [https://egazette.gov.in/WriteReadData/2023/250883.pdf](https://egazette.gov.in/WriteReadData/2023/250883.pdf); final URL identical; acquired 2026-10-26T20:23:09.608918+00:00; local backend/data/raw/bns-2023-act-45-original-gazette-250883.pdf.
- **BNSS act**: [https://egazette.gov.in/WriteReadData/2023/250884.pdf](https://egazette.gov.in/WriteReadData/2023/250884.pdf); final URL identical; acquired 2026-10-26T20:23:11.589698+00:00; local backend/data/raw/bnss-2023-act-46-original-gazette-250884.pdf.
- **BSA act**: [https://egazette.gov.in/WriteReadData/2023/250882.pdf](https://egazette.gov.in/WriteReadData/2023/250882.pdf); final URL identical; acquired 2026-10-26T20:23:12.881984+00:00; local backend/data/raw/bsa-2023-act-47-original-gazette-250882.pdf.
- **BNS notification**: [https://egazette.gov.in/WriteReadData/2024/252353.pdf](https://egazette.gov.in/WriteReadData/2024/252353.pdf); final URL identical; acquired 2026-10-26T20:23:13.572162+00:00; local backend/data/raw/bns-commencement-so-850e-2024-gazette-252353.pdf.
- **BNSS notification**: [https://egazette.gov.in/WriteReadData/2024/252354.pdf](https://egazette.gov.in/WriteReadData/2024/252354.pdf); final URL identical; acquired 2026-10-26T20:23:15.115602+00:00; local backend/data/raw/bnss-commencement-so-848e-2024-gazette-252354.pdf.
- **BSA notification**: [https://egazette.gov.in/WriteReadData/2024/252352.pdf](https://egazette.gov.in/WriteReadData/2024/252352.pdf); final URL identical; acquired 2026-10-26T20:23:15.869012+00:00; local backend/data/raw/bsa-commencement-so-849e-2024-gazette-252352.pdf.

The unchanged original bytes are under backend/data/raw/, with stable filenames
and the Windows read-only attribute. Existing differing files would have been
rejected, never replaced. Read-only is protection against accidental edits,
not WORM storage; check the hashes before future use.

SHA-256, recomputed from saved files:

- **bns-2023-act-45-original-gazette-250883.pdf**: 67c92f7869420685e6cdc29b1bdde19fff91312b10241b3ed3e1163c5399600b
- **bnss-2023-act-46-original-gazette-250884.pdf**: 5e60e2afe30d0fe7eca4f8126301146b76c86a444e690581f81eb564843517fe
- **bsa-2023-act-47-original-gazette-250882.pdf**: 31ee68ea57b5303bf6697b5d8cb2004b9eb9180d7e9cbcbbdbf5bccab7cda5c1
- **bns-commencement-so-850e-2024-gazette-252353.pdf**: dfcd5df23fb711f2996959b13ee6ff6bd32ed38be1e1f2d1c820cbba86e2a8c9
- **bnss-commencement-so-848e-2024-gazette-252354.pdf**: 0db8a86a0cf41fbf5ee304ee84b8b145da0bd523af510baf351d79d051ef657d
- **bsa-commencement-so-849e-2024-gazette-252352.pdf**: fde9e9722eb4c01375525c2a30442903371913f4199b8cef1d031535d88228e7

## Content and provenance verification

All three Acts' first PDF pages identify:

- Act 45/2023: **The Bharatiya Nyaya Sanhita, 2023**.
- Act 46/2023: **The Bharatiya Nagarik Suraksha Sanhita, 2023**.
- Act 47/2023: **The Bharatiya Sakshya Adhiniyam, 2023**.
- Presidential assent and Gazette publication: **25 December 2023**.
- Publishing department: **Ministry of Law and Justice (Legislative Department)**.
- Gazette identifiers 250883, 250884 and 250882 respectively.

These are original enactment Gazette artifacts, not the later India Code
reference/consolidated editions. End pages contain the publishing colophon.

Notifications identify **Ministry of Home Affairs**, the respective S.O. numbers,
and F. No. **1/3/2023-Judicial Cell-I**. Each instrument is dated
**23 February 2024**; its Gazette cover is dated **24 February 2024**.
The English heading is NOTIFICATION; no invented long title is assigned.
Both Hindi/English pages are retained unchanged.

## Exact commencement wording

**BNS notification — PDF page 2:**

> S.O. 850(E).—In exercise of the powers conferred by sub-section (2) of section 1 of the Bharatiya Nyaya Sanhita, 2023 (45 of 2023), the Central Government hereby appoints the 1st day of July, 2024 as the date on which the provisions of the said Sanhita, except the provision of sub-section (2) of section 106, shall come into force.

Appoints 2024-07-01 except BNS section 106(2). Later commencement/status of that subsection remains unknown.

**BNSS notification — PDF page 2:**

> S.O. 848(E).—In exercise of the powers conferred by sub-section (3) of section 1 of the Bharatiya Nagarik Suraksha Sanhita, 2023 (46 of 2023), the Central Government hereby appoints the 1st day of July, 2024 as the date on which the provisions of the said Sanhita, except the provisions of the entry relating to section 106(2) of the Bharatiya Nyaya Sanhita, 2023, in the First Schedule, shall come into force.

Appoints 2024-07-01 except the First Schedule entry relating to BNS section 106(2); this does not exclude BNSS section 106(2). Later status remains unknown.

**BSA notification — PDF page 2:**

> S.O. 849(E).— In exercise of the powers conferred by sub-section (3) of section 1 of the Bharatiya Sakshya Adhiniyam, 2023 (47 of 2023), the Central Government hereby appoints the 1st day of July, 2024 as the date on which the provisions of the said Adhiniyam, shall come into force.

Appoints 2024-07-01; no provision-specific carve-out in this notification. This is not a finding of universal applicability or unchanged current law.

These findings describe the acquired 2024 instruments. Whether later instruments
changed these exclusions remains **unknown**. BNS/BNSS scalar effective_date
fields remain null to preserve qualified commencement. BSA's supplied appointed
date is 2024-07-01, with applicability still unknown.

## Separate verification dimensions

| Dimension | Result |
| --- | --- |
| Byte integrity | PASS: all six saved hashes/sizes match received bytes and response lengths. |
| PDF structure | PASS: PDF magic, EOF marker, PyMuPDF parsing, no encryption/password requirement or parser repair. Text extraction succeeded on all 404 pages. |
| Printed identity | PASS: title, Act/notification number, authority, dates and Gazette identifiers match the preliminary inventory. |
| Official acquisition provenance | PASS: exact approved official URLs, strict Windows-backed TLS and hostname verification, plus matching printed identity. No fallback used. |
| Cryptographic PDF signature | NOT VERIFIED. Visible signature appearances are not cryptographic signature/trust validation. |
| Current legal applicability | UNVERIFIED. Subsequent commencement, amendments, corrigenda, State variations, transition/savings and case-specific application are not exhaustively established. |

Hindi in legacy-font headers and notification text is not reliably represented
by plain-text extraction. Inspect rendered original PDFs; no OCR, font repair,
transliteration or source rewriting was performed. English identity and operative
paragraphs were checked directly from extracted PDF contents.

Bounded additional official-domain searches returned no results. This does not
establish absence of subsequent instruments. Earlier research and the unresolved
watchlist remain in the audit; no currentness claim is made.

## Secure transport and file handling

Used the user-installed standalone **truststore 0.10.5**, an explicit
truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), and HTTPX verify=context.
Hostname checking and CERT_REQUIRED were asserted. trust_env=False and
follow_redirects=False. No global SSL injection, arbitrary certificates,
TLS bypass, certificate installation or trust-setting changes.

The exact e-Gazette and legacy/new India Code hosts are allowlisted in the audit.
HTTPS/port 443 only; no embedded credentials, downgrades, unsafe URLs or unexpected
hosts. Redirect destinations would be checked before following; none occurred.
Bounds: 8-second connect, 10-second read, 45-second total per document, at most
two attempts, four redirects, two concurrent documents and 25 MiB per file.
Unexpected encoding, invalid lengths, non-PDF payloads, encrypted/empty PDFs
and unsafe/reparse-point output paths were rejected by the acquisition checks.

Acquisition ran as a one-off in-memory command. No application or permanent
acquisition-tool code was added; no dependency file was modified.

## Acquired Stage 2A manifest

[acquired-legal-source-manifest-stage2c.json](acquired-legal-source-manifest-stage2c.json)
contains only the six genuinely acquired files, actual retrieval dates and exact
expected_sha256 values. **Stage 2A DocumentManifest validation passed.**

file_path is relative to the explicitly configured future source root
backend/data/raw, not the manifest's docs/ directory. Do not invoke ingestion yet.

verification_claim stays **unverified**. The audit records specific positive
acquisition checks without upgrading supplied provenance to independent
verification. Stage 2A continues to preserve user_supplied /
not_independently_verified if ingestion is approved later.
Unknown applicability remains null. Notification dates/numbers and qualified
commencement are recorded in provenance evidence/notes, without schema changes.

## Manual Windows PowerShell verification

Run from the repository root. These commands inspect local files only.

~~~powershell
# Run from the repository root.
$raw = @(Get-ChildItem -LiteralPath '.\backend\data\raw' -File -Filter '*.pdf')
"PDF count: $($raw.Count)"
if ($raw.Count -ne 6) { throw 'Expected six raw PDFs.' }
$raw | Select-Object Name,Length,IsReadOnly | Format-Table -AutoSize

$audit = Get-Content -LiteralPath '.\docs\legal-source-acquisition-stage2c.json' -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($record in $audit.records) {
    $file = Get-Item -LiteralPath $record.raw_path
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    if ($hash -ine $record.sha256 -or $file.Length -ne $record.byte_size) {
        throw "Hash/size mismatch: $($record.document)"
    }
    if (-not $file.IsReadOnly) { throw "Read-only attribute missing: $($file.Name)" }
    [pscustomobject]@{Document=$record.document;Status=$record.status;SHA256=$hash}
}
~~~

PDF inspection and manifest validation, **without ingestion**:

~~~powershell
@'
from pathlib import Path
import hashlib
import pymupdf
from backend.app.ingestion.models import DocumentManifest

raw = Path("backend/data/raw").resolve()
manifest_path = Path("docs/acquired-legal-source-manifest-stage2c.json")
manifest = DocumentManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
assert len(manifest.documents) == 6
for entry in manifest.documents:
    path = (raw / entry.file_path).resolve()
    assert path.is_relative_to(raw) and path.is_file()
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry.expected_sha256
    assert data.startswith(b"%PDF-") and b"%%EOF" in data[-4096:]
    with pymupdf.open(path) as pdf:
        assert pdf.is_pdf and not pdf.needs_pass and not pdf.is_encrypted
        assert not pdf.is_repaired and len(pdf) > 0
        for page in pdf:
            page.get_text("text")
        print(path.name, "pages:", len(pdf), "hash/PDF: PASS")
        page = pdf[1] if entry.metadata.instrument_type == "notification" else pdf[0]
        print(page.get_text("text").encode("ascii", "backslashreplace").decode("ascii"))
print("PASS: six-entry manifest, hashes, PDF headers and page parsing; no ingestion.")
'@ | & '.\.venv\Scripts\python.exe' -B -
if ($LASTEXITCODE -ne 0) { throw 'Local verification failed.' }
~~~

Optionally open each original for visual comparison:

~~~powershell
Get-ChildItem -LiteralPath '.\backend\data\raw' -File -Filter '*.pdf' |
    ForEach-Object { Invoke-Item -LiteralPath $_.FullName }
~~~

Check Act first pages and publication colophons; notification cover/page 2 dates,
numbers and full exceptions above. Expected counts: 102, 249, 47 and 2/2/2 pages.
Do not treat a viewer's visible signature stamp as signature validation.

## Changes, verification and stop point

Created six raw PDFs and the acquired manifest; updated this report and its JSON
audit. Initial TLS failures are preserved inside previous_runs.

Acquisition before/after content fingerprints matched for **1,213**
protected application, test, frontend, approved research and Git metadata files.
Raw files were separately rehashed after saving. No frontend, API, ingestion
implementation, existing test, dependency file or Git metadata changed.
No packages were installed by this run.

Backend/frontend tests were not rerun because only data and documentation changed.
Relevant verification: six PDF content/structure/hash checks and six-entry
Stage 2A schema validation. No ingestion/indexing, features, commit or push.

**Stage 2C stops here for manual verification and approval before ingestion.**
