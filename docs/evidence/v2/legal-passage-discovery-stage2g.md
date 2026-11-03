# Publication evidence V2

Sanitized derived report; not byte-identical to the private V1 original. Historical test results/command examples below describe V1 unless explicitly labelled V2. Use the public migration guide for current V2 commands. No human approval or current-law claim is added.

# Stage 2G — controlled passage discovery and review preparation

**Discovery complete: 3 proposed packets from 3 original documents.**
Every packet is labelled **PROPOSED / NOT SUBMITTED / NOT APPROVED**.
There are **zero real pending candidates, audit events, approvals or eligible
allowlist entries** before and after discovery/export.

This stage prepares human inspection only. Passing discovery gates does not
constitute passage approval, visual verification, commencement verification or a
claim of present legal applicability.

## Proposed passages

| Original document | Physical PDF page | Selected normalized lines | Enclosing context lines | Selected characters |
| --- | ---: | --- | --- | ---: |
| BSA notification — S.O. 849(E) | 2 | 8–10 | 1–67 | 283 |
| BNS notification — S.O. 850(E) | 2 | 8–11 | 1–66 | 332 |
| BNSS notification — S.O. 848(E) | 2 | 8–11 | 1–67 | 410 |

All selections are complete English operative paragraphs already located in
Stage 2E QA. Context is the **entire same English page**, including blank lines,
headings, dates, references and publication/signature furniture. Nothing is
removed or rewritten to pass a gate. Each full notification still has a Hindi
first page; that page is outside this narrowly defined English profile and
remains explicitly unverified. Publication dates remain sourced from the pinned
catalogue; they are not inferred from the English instrument date.

Packets are separate read-only scratch files under
**backend/data/qa/stage2g/v1/**:

- **BSA notification**: [passage_387beabd136be071872b1464ab0554aa9bde26bcb8b0b3e0e3695dded9458427](../backend/data/qa/stage2g/v1/proposal_passage_387beabd136be071872b1464ab0554aa9bde26bcb8b0b3e0e3695dded9458427.json); packet SHA-256 b2c15957a71eb948580a6bc21be5881eb540a2172a30191393db60c929ef89ac.
- **BNS notification**: [passage_40486354c037790a907b1b8ea9bebd2e7cda17a4c20291776b421eef783d5aba](../backend/data/qa/stage2g/v1/proposal_passage_40486354c037790a907b1b8ea9bebd2e7cda17a4c20291776b421eef783d5aba.json); packet SHA-256 9ba16245991f7cb322d348a20ffb2e58a4319cec57fbaf36415f4094244fb3bc.
- **BNSS notification**: [passage_353f187453111fb0b0c31f3db4f9bd8b77593ff236b6150dac5fcd90320da4b7](../backend/data/qa/stage2g/v1/proposal_passage_353f187453111fb0b0c31f3db4f9bd8b77593ff236b6150dac5fcd90320da4b7.json); packet SHA-256 6a802b64fad3ecfbf17cd07044937ec662316a29854aa1bdd41edccef72a7e4a.

[Machine-readable discovery report](legal-passage-discovery-stage2g.json) records
source checks, candidate IDs, line/text hashes, catalogue/QA hashes, packet paths
and hashes, skipped documents, unchanged review state and verification results.
Packet files are covered by the existing backend/data/ ignore rule; they exist
locally and are not review/audit records.

## Scope, exclusions and limitations

The discovery profile considers only single-page, complete English operative
paragraphs with exact existing QA location/text anchors. It examines at most five
operative paragraphs and returns at most five proposals TOTAL, not per document.
Default limit is five; this run examined three and proposed all three.
Sorting uses source URL and document ID, with no clock/randomness in proposal
selection or IDs. Repeated discovery produced identical reports and packets.

**No considered notification paragraph failed a hard gate in this run.**
The **three Acts were skipped** with outside_notification_paragraph_scope:
their bare-numbered provisions, heuristic headings and continuation/context
boundaries are not automatically treated as verified passage boundaries.
Other potentially suitable archival Act passages were not exhaustively searched.
No quota was forced, and this does not claim that no suitable Act text exists.

The informational hard-signal inventory, using the existing Stage 2F policy:

- **BSA act**: 11 physical pages carry Stage 2F hard signals; exact pages/reasons are in source_checks.qa_hard_signal_inventory.
- **BNS act**: 15 physical pages carry Stage 2F hard signals; exact pages/reasons are in source_checks.qa_hard_signal_inventory.
- **BNSS act**: 126 physical pages carry Stage 2F hard signals; exact pages/reasons are in source_checks.qa_hard_signal_inventory.
- **BSA notification**: 1 physical pages carry Stage 2F hard signals; exact pages/reasons are in source_checks.qa_hard_signal_inventory.
- **BNS notification**: 1 physical pages carry Stage 2F hard signals; exact pages/reasons are in source_checks.qa_hard_signal_inventory.
- **BNSS notification**: 1 physical pages carry Stage 2F hard signals; exact pages/reasons are in source_checks.qa_hard_signal_inventory.

This inventory is not a list of newly generated candidates. Unresolved Hindi
glyph mapping, marginal citations, schedules/tables/forms/checkbox associations,
suspicious Unicode and other hard-excluded pages are not bypassed. Final
candidate/context gating calls the unchanged Stage 2F exclusion function.
If a selected OR context page has a hard exclusion, the entire proposal is skipped.

Cross-page discovery is intentionally unsupported. Extra context requirements,
multiple-page anchors, gaps, incomplete/out-of-range lines or uncertain QA
profiles are skipped rather than stitched or re-attributed. Stage 2F's explicit
cross-page review infrastructure remains unchanged.

The English-script check is only a Latin-letter sanity check applied to the
existing QA English-paragraph profile, not independent language/translation
certification. No Hindi repair, OCR, dehyphenation, text folding, table
reconstruction, heading promotion or legal interpretation occurs.

## Reuse of Stage 2F and source binding

The new standalone backend/discovery/ implementation calls the existing Stage 2F
Catalog, preview, validate_candidate, exclusion_reasons and read-only inspect/
history/allowlist functions. It does not redefine approval policy, edit the
catalogue, change transitions or call ReviewStore.append.

Every proposal retains the Stage 2F candidate schema:

- Raw PDF and processed JSON SHA-256 values and paths; original document ID.
- Pinned catalogue and Stage 2E QA hashes.
- Complete source metadata, identity, authority, version and supplied provenance.
- Exact physical page/page ID, inclusive normalized lines, UTF-8 span hashes and
  canonical text-with-boundaries passage/context hashes.
- Explicit full-page context and rationale, archival_text_only scope and
  document_only attribution. No inferred section/subsection label is assigned.
- Unknown currentness/applicability and not_independently_verified provenance.

All six source pairs are hash-validated before proposals are constructed and
rechecked before completion. A stale source or pinned QA/catalogue fails the
run; it is not disguised as a harmless zero-candidate result.

Packets include the unmodified text/context, original PDF page references,
all relevant retained QA findings, the exclusion result and a human checklist.
Residual non-hard QA signals remain visible, including sorted-reading-order
differences, delimiter/continuation signals and publication/signature text.
Matching extracted text is not proof of visual fidelity or current law.

A packet's outer kind is discovery_review_packet; it is deliberately not a
Stage 2F Candidate submission object or an audit event. It contains no reviewer,
decision time or approval record. Extracting its nested candidate does not
submit it. Separate future authorization would still be required for any review
submission or approval; none is performed or requested here.

## Commencement exceptions preserved

The full paragraphs remain exact, including:

- **BNS S.O. 850(E):** exception for BNS section 106(2).
- **BNSS S.O. 848(E):** exception for the First Schedule entry concerning
  **BNS section 106(2)**, not BNSS section 106(2).
- **BSA S.O. 849(E):** no provision-specific exception stated in this operative
  paragraph. This is not a universal-applicability assertion.

No later commencement, amendment, corrigendum or present legal status is
determined. Original enactment text and an original commencement notification
are not proof of current applicability.

## Read-only CLI

From the repository root:

~~~powershell
# Run from the repository root.
$liveJson = & '.\.venv\Scripts\python.exe' -B -m backend.discovery discover
if ($LASTEXITCODE -ne 0) { throw 'Discovery failed; inspect the source/QA error.' }
$live = $liveJson | ConvertFrom-Json
$live | Select-Object label,proposed_count,examined_operative_paragraphs,candidate_limit
$live.proposals | Select-Object document,candidate_id,spans,eligible | Format-List
$live.skipped | Select-Object document,reason | Format-Table -AutoSize

$id = $live.proposals[0].candidate_id
& '.\.venv\Scripts\python.exe' -B -m backend.discovery preview $id
if ($LASTEXITCODE -ne 0) { throw 'Packet preview failed.' }
~~~

discover and preview write nothing. --limit accepts only integers 1–5.
preview recomputes the current proposals and only returns an ID in that limited
result. Neither command submits candidates or creates a review directory.
The tool refuses a nonempty review history rather than resetting/ignoring it.

An optional export command exists for an explicitly chosen NEW child directory
of backend/data/qa/stage2g/. It never overwrites an existing destination or writes
under sources, processed records, QA, docs, review ledgers or Git metadata.
It is not needed to inspect the three supplied files:

~~~powershell
# Optional syntax only; do not create duplicate packet exports for verification:
# & '.\.venv\Scripts\python.exe' -B -m backend.discovery export --output-dir '.\backend\data\qa\stage2g\NEW-UNUSED-NAME'
~~~

An interrupted export can leave incomplete, clearly unapproved scratch files;
there is no automatic cleanup or promotion. Preserve them for inspection and
choose a new output directory if an export must be repeated.

## Manual verification

### 1. Packet count, labels, hashes and exact text

~~~powershell
$saved = Get-Content -LiteralPath '.\docs\legal-passage-discovery-stage2g.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$files = @(Get-ChildItem -LiteralPath $saved.packet_export.directory -File -Filter 'proposal_passage_*.json')
if ($files.Count -ne $saved.discovery.proposed_count -or $files.Count -gt 5) {
    throw 'Unexpected packet count.'
}
foreach ($entry in $saved.packet_export.files) {
    $file = Get-Item -LiteralPath $entry.path
    if ((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ine $entry.sha256 -or
        $file.Length -ne $entry.bytes -or -not $file.IsReadOnly) {
        throw "Packet hash/size/read-only mismatch: $($entry.candidate_id)"
    }
    $packet = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($packet.label -ne 'PROPOSED / NOT SUBMITTED / NOT APPROVED' -or
        $packet.submitted -or $packet.approved -or $packet.eligible) {
        throw 'Unexpected packet status.'
    }
    $packet | Select-Object document,candidate_id,label,citation_kind
    $packet.candidate.spans | Format-List
    $packet.exact_passage[0].text
    $packet.surrounding_context[0].text
    $packet.qa_pages | ConvertTo-Json -Depth 16
}
~~~

### 2. Recompute discovery and validate every packet against Stage 2F

This is inspection only; no submissions, events or approvals are written.

~~~powershell
@'
from pathlib import Path
import json, stat
from backend.discovery.passages import discover, LABEL
from backend.review.models import Candidate
from backend.review.service import Catalog, ReviewStore, sha, validate_candidate, exclusion_reasons

root = Path.cwd()
saved = json.loads(Path("docs/legal-passage-discovery-stage2g.json").read_text(encoding="utf-8"))
live, packets = discover(root)
assert live == saved["discovery"]
assert len(packets) == 3 and len(packets) <= 5
current = {p["candidate_id"]: p for p in packets}
catalog = Catalog(root)
for entry in saved["packet_export"]["files"]:
    path = Path(entry["path"])
    data = path.read_bytes()
    assert sha(data) == entry["sha256"] and len(data) == entry["bytes"]
    assert not path.stat().st_mode & stat.S_IWRITE
    packet = json.loads(data)
    assert packet == current[entry["candidate_id"]]
    assert packet["label"] == LABEL
    assert not any(packet[k] for k in ("submitted", "approved", "eligible"))
    candidate = Candidate.model_validate(packet["candidate"])
    item, _ = validate_candidate(catalog, candidate)
    assert not exclusion_reasons(item, candidate)
    inspected = ReviewStore(catalog).inspect(candidate)
    assert inspected["selected"] == packet["exact_passage"]
    assert inspected["context"] == packet["surrounding_context"]
    assert candidate.attribution.kind == "document_only"
    print(packet["document"], "packet/source/text/context/gates: PASS")
for name, expected in saved["implementation_inputs"].items():
    assert sha(Path(name).read_bytes()) == expected
store = ReviewStore(catalog)
assert store.replay() == ([], {})
assert store.allowlist()["entries"] == []
print("PASS: three PROPOSED packets; zero real submissions, events or eligible passages.")
'@ | & '.\.venv\Scripts\python.exe' -B -
if ($LASTEXITCODE -ne 0) { throw 'Packet verification failed.' }
~~~

### 3. Confirm the real review history and allowlist remain empty

~~~powershell
& '.\.venv\Scripts\python.exe' -B -m backend.review list
& '.\.venv\Scripts\python.exe' -B -m backend.review history
& '.\.venv\Scripts\python.exe' -B -m backend.review verify
& '.\.venv\Scripts\python.exe' -B -m backend.review allowlist
~~~

Expected: empty pending/history lists; audit chain PASS; zero eligible entries.

### 4. Human comparison checklist

- [ ] Recheck packet/raw/processed/QA hashes; confirm PROPOSED status.
- [ ] Open each ORIGINAL PDF, physical page 2, and compare the complete English
      paragraph at the selected lines. Inspect the entire context page.
- [ ] Compare S.O. number, issuing authority, dated instrument and file reference.
      Keep notification date (23 February) distinct from Gazette publication
      date (24 February), as recorded in the source metadata.
- [ ] Confirm the precise BNS and BNSS exceptions; do not conflate the BNSS
      First Schedule entry with a BNSS subsection.
- [ ] Inspect every residual QA signal and surrounding furniture. Do not silently
      remove, correct, reorder or reinterpret text.
- [ ] Keep Hindi page 1 unverified; no bilingual-equivalence claim is supplied.
- [ ] Keep currentness and applicability unknown. This checklist creates no
      submission, review decision, approval or allowlist entry.

To open the source PDFs manually:

~~~powershell
foreach ($entry in $saved.packet_export.files) {
    $packet = Get-Content -LiteralPath $entry.path -Raw -Encoding UTF8 | ConvertFrom-Json
    Invoke-Item -LiteralPath $packet.source_pdf.path
}
# Navigate to physical PDF page 2; these commands open viewers only.
~~~

### 5. Backend tests

~~~powershell
$testScratch = '.\backend\data\test-runs\manual-stage2g-' + [guid]::NewGuid().ToString('N')
& '.\.venv\Scripts\python.exe' -B -m pytest backend/tests -q --basetemp $testScratch -p no:cacheprovider
~~~

Use a fresh scratch directory; pytest owns it.

## Verification results and created files

**155 passed, 0 failed, 0 skipped, 1 warning in 54.40 seconds.**
This includes **24 new discovery tests** plus the existing 131 backend tests.
The existing Starlette TestClient/HTTPX deprecation warning remains.

Tests cover deterministic discovery, zero suitable passages, raw/processed/QA
changes, source versions, whole-context hard exclusions, ambiguous/cross-page
anchors, complete qualifiers, no automatic append/approval, empty history,
safe export paths, immutable source inputs, packet/submission separation and
the global five-proposal limit.

Created backend/discovery/ tooling, backend/tests/test_passage_discovery.py,
the two Stage 2G reports and three read-only scratch packets.
No dependencies changed. Full packet comparison and repeated discovery passed.
SHA-256, modification-time and mode checks matched for all **1,277 protected files**.
All seven documented PowerShell blocks parse; read-only CLI/hash examples and
the exact Python packet verification executed successfully.

The Stage 2F catalogue, transitions and audit semantics are unchanged. No raw
PDF, Stage 2D JSON, Stage 2E finding, prior report, frontend or Git metadata was
modified. No new legal downloads, correction, OCR, chunks, embeddings, BM25,
FAISS, RAG, LLM, voice, commit or push.

**Stopped after Stage 2G for manual verification and approval.**
