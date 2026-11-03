# Publication evidence V2

Sanitized derived report; not byte-identical to the private V1 original. Historical test results/command examples below describe V1 unless explicitly labelled V2. Use the public migration guide for current V2 commands. No human approval or current-law claim is added.

# Stage 2F — passage review and evidence approval

**Infrastructure implemented; real evidence promotion remains BLOCKED.**
There are **zero real pending submissions, review events, approvals or eligible
allowlist entries**. No source or processed text was changed. No currentness
claim is supported by an approval in this workflow.

[Machine-readable specification and JSON Schemas](legal-passage-review-stage2f.json)
contains the pinned source catalogue, candidate/decision/event schemas,
transitions, hard exclusions and the explicitly empty initial allowlist.

## Record binding and deterministic validation

A candidate binds:

- Exact raw PDF SHA-256/path, processed JSON SHA-256/path and document ID.
- QA report hash and a canonical catalogue hash pinning approved Stage 2C–2E
  inputs and review implementation. Changed inputs fail closed, including while
  a catalogue instance is already loaded.
- Original metadata/provenance, source URL, official title, authority, version and
  catalogue Act/notification identifiers. Provenance stays user_supplied /
  not_independently_verified; legal_currentness stays unknown.
- One to three ordered physical pages with exact page IDs and inclusive,
  one-based normalized line ranges. Each span has its exact UTF-8 text hash.
- Explicit enclosing context spans and rationale. Passage/context hashes cover
  canonical JSON containing page IDs, page/line boundaries AND exact text;
  no silent cross-page concatenation is used.
- An immutable content-derived candidate ID. Altered fields require a new ID,
  and recomputing that ID does not bypass source/policy checks.

Candidates contain no approval/status field. Decisions live only in audit events.
The CLI defaults to document-only attribution, which permits only archival
document/page citations. A printed identifier must be literally present as a
label at the start of the selected text, with an exact single-line anchor.
An isolated (2), an inferred Section 106(2), or a prose cross-reference cannot
be promoted into a verified subsection label by this infrastructure.

Cross-page passages require consecutive pages, selection through the end of
each preceding page and from line 1 of each following page, enclosing context
for every selection, an explicit cross-page explanation and a separate reviewer
attestation. Skips, overlaps, ambiguous gaps and missing context are rejected.
This intentionally conservative rule includes source page furniture rather than
silently discarding it. It does not reconstruct legal hierarchy.

Previewing, hashing, QA consistency or an agent's visual spot check never
constitutes approval. Real reviewer identity, decision time and rationale must
be supplied by the operator; the program does not invent them.

## Decisions and exclusions

| Current state | Allowed next decision |
| --- | --- |
| New candidate | pending only, via explicit submission |
| pending | approved, rejected, needs_correction |
| approved | rejected, needs_correction |
| needs_correction | pending, rejected |
| rejected | terminal |

Rejections and needs_correction decisions remove eligibility immediately.
Reopening needs_correction requires a pending event before another approval.
Source/text corrections must produce a separately reviewed derived version and
new candidate, never edits to the original candidate, raw PDF or Stage 2D JSON.

Approval requires ALL of:

1. One exact candidate ID, a single decision JSON object, explicit confirmation
   of that ID, and the separate --approve-one flag.
2. A nonempty reviewer identifier, timezone-aware decision time normalized to UTC,
   rationale and hash-matching evidence references.
3. Rendered-PDF evidence and QA references for every selected AND context page.
   Evidence is a reviewer claim identifying the source/pages actually inspected,
   not an automatically certified rendering.
4. Explicit visual-comparison, boundary/attribution, preserved-qualifier and
   archival-scope attestations; cross-page context attestation where applicable.
5. Current source/catalogue/QA/text hashes and no unresolved exclusion.
6. For export, a separately retained trusted latest audit checkpoint.

Hard exclusions conservatively quarantine whole selected/context pages containing
unresolved Hindi glyph mapping, legacy Hindi codes, schedule/table/form layout,
ambiguous marginal citations, replacement/control/private/invisible Unicode,
mojibake, empty or duplicate page signals. Page-wide quarantine deliberately
covers detached associations and non-text graphics such as checkboxes.
There is no override field or approval option to bypass these gates.
A future finer-grained policy requires a separately approved QA/policy version.

If a selected span intersects a notification's operative paragraph, it must
include the complete paragraph. Selecting only an appointed date while dropping
an exception is blocked even when the exception exists elsewhere in context.

The BNS section 106(2) exception and the BNSS First Schedule entry exception
remain in the unchanged source records. Approval of original enacted text,
including the presence of a subsection or table entry, cannot certify
commencement. The only approval scope is archival_text_only; current legal
applicability, subsequent amendments and later commencement remain unknown.

## Append-only history and its limits

Storage is fixed under backend/data/reviews/stage2f/v1/. Read-only commands do
not create this directory. Every write publishes ONE new, sequence-numbered,
hash-named event through an exclusive temporary file and non-overwriting atomic
hard-link publication. Events carry the previous event digest, candidate,
reviewer-supplied decision/time/rationale and evidence. Published events become
read-only. No update, delete, reset or bulk-approval command exists.
A cooperative exclusive writer lock prevents concurrent append races.

All history is replayed and validated before use. Modified entries, sequence gaps,
wrong filenames, invalid transitions and a mismatch with a trusted checkpoint
fail closed. Export revalidates approved source/evidence hashes; stale approvals
are excluded rather than silently refreshed.

**This is application-level append-only, tamper-evident storage, not WORM storage
or authenticated signatures.** A privileged filesystem owner can change
permissions and rewrite/delete the entire store. Reviewer identifiers,
attestations and timestamps are explicit user claims, not identity verification
or trusted timestamping. No OS trust, permissions policy, signing keys, remote
storage or global settings were installed.

Retain the latest sequence/event digest from EVERY write in a separately trusted
place. A checkpoint is not a secret, but its integrity and freshness matter.
A checkpoint supplied to verify/allowlist must match the exact latest head.
Without a checkpoint, approved records are NOT exported. Copying a freshly
reported head from an already compromised store is not independent proof.
This design detects tail removal relative to the retained checkpoint; it cannot
detect wholesale replacement without an independently protected anchor.

A crash may leave a writer lock or unpublished temporary file in the parent.
The tool never deletes unknown audit entries or tries to repair history.
Investigate cooperative access and preserve evidence before any manual recovery.

## Read-only commands for the existing corpus

Run from the repository root:

~~~powershell
# Run from the repository root.
& '.\.venv\Scripts\python.exe' -B -m backend.review documents
& '.\.venv\Scripts\python.exe' -B -m backend.review list
& '.\.venv\Scripts\python.exe' -B -m backend.review verify
& '.\.venv\Scripts\python.exe' -B -m backend.review allowlist
& '.\.venv\Scripts\python.exe' -B -m backend.review history
~~~

Expected: six catalogue documents; empty pending/history lists; zero eligible
entries. verify checks the chain and reports zero eligible records.
A future submitted candidate can be inspected read-only with:

~~~powershell
# Replace with one actual submitted candidate ID. This does not write a decision.
# & '.\.venv\Scripts\python.exe' -B -m backend.review inspect 'passage_<64 hex digits>'
~~~

Preview is also read-only. It writes a proposed candidate to stdout only:
use documents to obtain the document ID, then provide explicit --span and
--context values in physical_page:start_line:end_line form and a context rationale.
No source passages are automatically enumerated or submitted as candidates.

list --state approved/rejected/needs_correction can inspect those states; listing
an approved state is not itself eligibility. Only live allowlist validation with
the retained latest checkpoint may return an eligible archival passage.

## Manual workflow — SYNTHETIC data only

The generator below creates two clearly labelled SYNTHETIC PDF pages, synthetic
metadata/QA, a candidate and UNSIGNED pending/approval request templates in a new
isolated directory. It does not submit a candidate or create any decision event.
It uses the existing ingestion pipeline on synthetic data only. Its fictional
template actor and clock are labelled test data, not real approvals.

### 1. Create an isolated demonstration; inspect before any submission

~~~powershell
$demo = Join-Path '.\backend\data\qa\stage2f-demo' ([guid]::NewGuid().ToString('N'))
$generated = & '.\.venv\Scripts\python.exe' -B -m backend.review.synthetic_demo --output-dir $demo
if ($LASTEXITCODE -ne 0) { throw 'Synthetic fixture generation failed.' }
$fixture = $generated | ConvertFrom-Json
$demo = $fixture.synthetic_workspace
$candidateId = $fixture.candidate_id
Get-Content -LiteralPath (Join-Path $demo 'candidate.json') -Raw -Encoding UTF8
& '.\.venv\Scripts\python.exe' -B -m backend.review --synthetic-workspace $demo list
& '.\.venv\Scripts\python.exe' -B -m backend.review --synthetic-workspace $demo allowlist
# Open the SYNTHETIC PDF and compare its exact lines:
# Invoke-Item -LiteralPath (Join-Path $demo 'backend\data\raw\synthetic-not-law.pdf')
~~~

Expected: no events, no pending records, empty allowlist. Existing destinations
are rejected. --synthetic-workspace rejects documents whose source_type is not
synthetic. It never merges demonstration history into the real catalogue.

### 2. Explicitly submit ONE synthetic pending candidate

This writes only an event inside the synthetic demonstration workspace.
Enter your own reviewer identifier; it is a claim, not authenticated identity.

~~~powershell
$reviewer = Read-Host 'Your reviewer identifier for this SYNTHETIC exercise'
if ([string]::IsNullOrWhiteSpace($reviewer)) { throw 'Reviewer identifier required.' }
$pendingPath = Join-Path $demo 'pending-request.json'
$pending = Get-Content -LiteralPath $pendingPath -Raw -Encoding UTF8 | ConvertFrom-Json
$pending.reviewer_id = $reviewer
$pending.decision_time = (Get-Date).ToUniversalTime().ToString('o')
$pending.rationale = 'SYNTHETIC exercise: submitted for passage review, not legal evidence.'
$pending | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $pendingPath -Encoding UTF8
$submitted = & '.\.venv\Scripts\python.exe' -B -m backend.review --synthetic-workspace $demo submit --candidate-file (Join-Path $demo 'candidate.json') --decision-file $pendingPath --confirm-candidate $candidateId
if ($LASTEXITCODE -ne 0) { throw 'Pending submission failed.' }
$submissionReceipt = $submitted | ConvertFrom-Json
& '.\.venv\Scripts\python.exe' -B -m backend.review --synthetic-workspace $demo list
& '.\.venv\Scripts\python.exe' -B -m backend.review --synthetic-workspace $demo inspect $candidateId
~~~

Expected: one pending candidate. Inspect prints the original extracted selection,
enclosing context, page/line IDs, QA findings and exclusions. Nothing is eligible.

### 3. Only after personally reviewing the SYNTHETIC source, record ONE decision

Do not run this step unless its attestations are true. This is an explicit manual
exercise, not an auto-approval routine or an example approving real legislation.
Unsigned templates deliberately contain false attestations and cannot approve
anything unchanged. You may instead record rejected or needs_correction using
a request with that decision and omit --approve-one.

~~~powershell
$approvalPath = Join-Path $demo 'approval-request.json'
$approval = Get-Content -LiteralPath $approvalPath -Raw -Encoding UTF8 | ConvertFrom-Json
$approval.reviewer_id = $reviewer
$approval.decision_time = (Get-Date).ToUniversalTime().ToString('o')
$approval.rationale = 'SYNTHETIC ONLY: I visually compared the exact selected lines, context and QA; no legal applicability claim.'
$approval.attestations.visual_comparison_performed = $true
$approval.attestations.boundaries_and_attribution_verified = $true
$approval.attestations.qualifiers_and_exceptions_preserved = $true
$approval.attestations.archival_scope_only = $true
# This fixture candidate is single-page; do not assert a cross-page review.
$approval.attestations.cross_page_context_verified = $false
$approval | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $approvalPath -Encoding UTF8
$confirmation = Read-Host 'Type the exact SYNTHETIC candidate ID to approve one reviewed candidate'
if ($confirmation -cne $candidateId) { throw 'Candidate confirmation differs.' }
$written = & '.\.venv\Scripts\python.exe' -B -m backend.review --synthetic-workspace $demo record-decision --candidate $candidateId --decision-file $approvalPath --confirm-candidate $confirmation --approve-one
if ($LASTEXITCODE -ne 0) { throw 'Decision rejected; inspect the error, do not bypass gates.' }
$receipt = $written | ConvertFrom-Json
$receipt.retain_checkpoint | Format-List
# Retain this latest receipt independently of the event store.
$checkpoint = '{0}:{1}' -f $receipt.retain_checkpoint.sequence,$receipt.retain_checkpoint.event_sha256
& '.\.venv\Scripts\python.exe' -B -m backend.review --synthetic-workspace $demo verify --checkpoint $checkpoint
& '.\.venv\Scripts\python.exe' -B -m backend.review --synthetic-workspace $demo allowlist --checkpoint $checkpoint
& '.\.venv\Scripts\python.exe' -B -m backend.review --synthetic-workspace $demo history
~~~

Expected: one eligible SYNTHETIC archival-text candidate in this isolated
workspace only; two immutable events. Without --checkpoint the same allowlist
exports no approved entries. A wrong/stale checkpoint, changed PDF/JSON/QA,
changed evidence or prohibited QA page fails closed. Rejection or
needs_correction adds a new event and withdraws eligibility; retain the new head.

### 4. Confirm the real store remains empty

~~~powershell
$real = & '.\.venv\Scripts\python.exe' -B -m backend.review allowlist
if ($LASTEXITCODE -ne 0) { throw 'Real catalogue verification failed.' }
$realAllowlist = $real | ConvertFrom-Json
if (@($realAllowlist.entries).Count -ne 0) { throw 'Expected zero real approvals.' }
& '.\.venv\Scripts\python.exe' -B -m backend.review list
~~~

These commands do not submit/approve anything in the real corpus. Do not copy
the synthetic actor, rationale, clock or requests into a real review. A real
review requires separately authorized human inspection and truthful inputs.

## Test and preservation results

The complete backend suite passed: **131 passed, 0 failed, 0 skipped, 1 warning
in 23.85 seconds**. This includes 30 new review test cases and the existing 101
backend/QA cases. The existing Starlette TestClient/HTTPX deprecation warning
remains; no dependency changes were made.

Tests cover stale raw/processed/QA/catalogue/evidence hashes, source-version
changes, candidate/event tampering, explicit single-candidate confirmation,
missing reviewer/time/rationale/evidence, missing attestations, invalid/backdated
transitions, safe cross-page context, ambiguous attribution, prohibited page
types, dropped notification qualifiers, unsafe bulk requests, audit checkpoints,
tail deletion, and zero-write read-only defaults. All approval events created by
tests exist only in clearly labelled synthetic pytest workspaces.

~~~powershell
$testScratch = '.\backend\data\test-runs\manual-stage2f-' + [guid]::NewGuid().ToString('N')
& '.\.venv\Scripts\python.exe' -B -m pytest backend/tests -q --basetemp $testScratch -p no:cacheprovider
~~~

Use a fresh scratch directory: pytest owns it. Review modules and schemas are
under backend/review/; focused tests are in backend/tests/test_passage_review.py.
This stage adds no frontend, API integration, chunks, embeddings, BM25, FAISS,
RAG, LLM, voice, downloads, legal corrections, commits or pushes.

**Stage 2F stops here for manual verification and approval.**
