# Public corpus and lightweight deployment

Status: **CONDITIONAL GO FOR DEPLOYMENT PREPARATION; NO-GO FOR PUBLIC CORPUS RELEASE**.
The code works with an explicitly approved artifact. No real publication decision,
legal-evidence approval, push or deployment has been made.

## Recovery and artifacts

The interrupted work was recovered on feat/working-legal-chat-mvp at 414537f:
four tracked files were modified and nine new Python files were present. The
implementation, tests and private candidate-v1 were preserved. Completion adds
deployment packaging/configuration, visible public citation provenance, stronger
publication gates, measurements and documentation. Candidate-v1 is an earlier
unpublished artifact; candidate-v2 supersedes its publication contract. Neither
was edited in place. Original PDFs, processed records and V1/V2 reviews are separate.

The reviewable metadata inventory is [public-corpus-candidate.json](public-corpus-candidate.json).
It contains no extracted corpus text. The local candidate directory is
backend/data/public-corpus/candidate-v2, with a sibling candidate-v2.zip.
Both remain ignored and unpublished. Its three files are manifest.json,
corpus.json and NOTICE.md. The compressed package is 378,552 bytes; the unpacked
files total 1,530,922 bytes. The manifest SHA-256 is
`bbbc799f2583145c0ac704c518cfe2f5d0049d490994d7e0cbabf19df47c1fa6`.

The candidate contains 555 unreviewed selections with context from 194 pages:
BNS Act 45/2023 (204), BNSS Act 46/2023 (259), BSA Act 47/2023 (89), and one
complete English paragraph from each commencement notification S.O. 850(E),
848(E), 849(E). All six source documents account for 404 original physical pages.
Official URLs, original PDF hashes, titles, authorities, dates and edition
descriptions are recorded in the inventory. These are original publications,
not consolidated or proven-current editions.

## Publication assessment: conditional, not clearance

Do not assume official government documents are public domain. The official
[Copyright Office statute](https://copyright.gov.in/Documents/Notification/Copyright_Act_1957.pdf)
was inspected with certificate-verified HTTPS; the relevant passage is on physical
page 25. SHA-256: ac3ec4fd5e04cb4cb87cc10e2568f027c1dd9ede572dccf617a34fb1f6feb8c9.

Section 52(1)(q)(i) addresses Gazette matter other than Acts; subclause (ii)
conditions Act reproduction on accompanying commentary or other original matter.
The candidate therefore distinguishes the notification and Act sources and adds
source-specific editorial notes and attribution. **Adding those notes is not proof
that all applicable statutory, website-use, copyright or publication conditions
have been satisfied.** The cited official compilation is not an assurance about
later changes, third-party rights, all possible interpretations, or other terms.
The [e-Gazette information page](https://egazette.gov.in/Aboutus.aspx) was also
checked; free access is not treated as a redistribution license. No blanket
open-license/public-domain claim is made. Applicable terms and the precise payload
still require an identified human publication review; if that review cannot
establish a safe basis, do not release the corpus.

There is no new legal text in Git or the runtime code package. Do not remove a
pending label, invent a reviewer, or create a real approval to make readiness pass.
Publication permission is independent of legal correctness, visual approval and
current applicability. All real legal-review events and allowlist entries stay zero.

The candidate omits raw PDFs, private processed records, private catalogue/QA
hashes and candidate IDs, review stores, private diagnostics, workstation paths,
user conversations, embedding weights and private indexes. Only source-derived
text, public provenance and quality flags are retained. Full-page textual context
can include public official names/addresses and detached marginal headings; that
context also needs publication/privacy review. Scanned signature images and private
user data are not included. No source text was corrected or silently repaired.

The preparer verifies all source bindings and reuses Stage 2F validation and hard
exclusions. It excludes uncertain Hindi glyph mapping, forms/tables, marginal
association failures and unsafe boundaries. Existing softer warnings remain
visible. Automatic eligibility is not visual verification; the 12-page release
sample does not certify the whole corpus. BNS section 106(2) and the BNSS First
Schedule entry exception remain separate, complete original notification text.

## Configuration and approval boundary

Local research: CORPUS_KIND=private; PRIVATE_CORPUS_ROOT is an optional explicit
workspace containing its own exact private bundle. RETRIEVAL_MODE=bm25 guarantees
no semantic initialization even if a model path is set. RETRIEVAL_MODE=auto or
hybrid retains the optional local model path/fallback behavior.

Production: KANOON_ENV=production, CORPUS_KIND=public, RETRIEVAL_MODE=bm25.
Production rejects private mode. It never falls back to private files.

Public mode requires:

- PUBLIC_CORPUS_DIR: directory with exactly the three manifest-controlled files.
- PUBLIC_CORPUS_MANIFEST_SHA256: independently reviewed exact manifest hash.
- PUBLIC_CORPUS_APPROVAL_FILE: a separate publication decision, **outside** that directory.
- PUBLIC_CORPUS_APPROVAL_SHA256: an independently pinned hash of that decision.

No real decision is included or generated. After explicit user approval, an
authorized operator can record a decision with these fields (this is a schema
description, not an approval): purpose=`corpus_publication_only; not legal evidence approval`,
decision=`approved_for_publication`, manifest_sha256, approved_by, timezone-aware
approved_at, substantive rationale, rights_review=`applicable terms and statutory conditions reviewed`,
and safety_review=`exact payload reviewed; no private data`. Review includes the
actual rights conditions, provenance, privacy and intended hosting use, not just
presence of editorial notes. Pin both hashes through deployment configuration.
This is an operator trust boundary, not cryptographic identity authentication or
a legal opinion. The legal-evidence ledger is neither consulted nor modified.

Missing approval, incorrect hashes, corruption, unexpected corpus files, unsafe
paths/characters or stale source bindings fail closed. GET /api/ready returns 503
and chat status available=false when the public index is unavailable. GET
/api/health retains its original response. Tampering after startup invalidates
search and citations. The offline inspection/measurement mode cannot serve through
HTTP, even if accidentally injected into an application instance.

## Manual verification (PowerShell)

```powershell
$candidate = 'backend/data/public-corpus/candidate-v2'
$pin = (Get-FileHash "$candidate/manifest.json" -Algorithm SHA256).Hash.ToLower()
.\.venv\Scripts\python.exe -B -m backend.public_corpus inspect --directory $candidate --sha256 $pin --query 'BNS section 15'
.\.venv\Scripts\python.exe -B -m backend.public_corpus measure --directory $candidate --sha256 $pin
# Preparation always requires a NEW ignored directory; it never overwrites artifacts:
# .\.venv\Scripts\python.exe -B -m backend.public_corpus prepare --output backend/data/public-corpus/<NEW-name>
$run = 'backend/data/test-runs/public-' + [guid]::NewGuid().ToString('N').Substring(0,8)
New-Item -ItemType Directory -Path (Split-Path $run) -Force | Out-Null
.\.venv\Scripts\python.exe -B -m pytest backend/tests -q --basetemp $run -p no:cacheprovider
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

Offline results explicitly say preview_only=true and publication_approved=false.
No publication decision is synthesized for real data. Browser production-path
testing uses backend.tests.public_corpus_e2e_server and frontend/tests/public-runtime.mjs:
these are labelled SYNTHETIC-only fixtures, disable Groq, and require a synthetic
server marker before sending requests. Never deploy that test server.

Measured on local Windows/Python 3.12.10 with all 555 selections: 0.6593 s startup,
62.488 MiB peak resident, 56.258 MiB resident after nine queries; median 134.656 ms,
maximum 163.032 ms for BNS section 15. HTTP dependency imports are included. No
Torch, FAISS, Sentence Transformers, PDF parser, private review/catalogue module or
model download occurs in this public path. This is a single-machine offline
measurement, not Linux, Render Free or a sustained-load guarantee. Corpora are
bounded to six sources, 404 page contexts, 1,000 selections and 4 MiB per data file.

## Deployment preparation only

render.yaml disables automatic deploys and selects the public BM25 runtime.
The minimal source ZIP contains 16 runtime/config files plus its inventory;
it contains neither corpus text nor approval records. backend/requirements-runtime.txt
pins the tested four direct HTTP/Pydantic dependencies, without PDF/ML/test packages.
The version file selects Python 3.12; Render resolves its latest patch, which still
needs a clean Linux/deployment verification. Local tests used 3.12.10, not that
future hosting environment. Free-tier fit is plausible from local footprint,
but **not certified**. No hosting resources were created.

After publication approval, deliver only the approved three corpus files and the
separately reviewed decision using an explicitly approved deployment-artifact step.
The current code package/blueprint will remain unready without them. Do not copy
backend/data wholesale or fetch private files in a build hook. Render's ephemeral
filesystem cannot be used as permanent publication storage; reviewed files must
be supplied reproducibly for each approved build. This delivery/publishing step
is intentionally not automated before approval.

Use one uvicorn worker, port $PORT, health path /api/health, and verify research_ready
on /api/ready separately. KANOON_ACCESS_TOKEN must be a distinct random 32+ character
secret; KANOON_ALLOWED_ORIGINS must list the actual HTTPS frontend origins. Basic
limits remain 30 requests/minute/process, two concurrent chats, 16,000-byte bodies,
10-second body reads and 25-second answer timeout. A shared demo token is not
per-user identity or a distributed quota system.

Vercel project root frontend; frontend/vercel.json configures Vite build/dist.
Set public VITE_API_BASE_URL to the real HTTPS backend origin. Never put bearer
tokens or Groq secrets in VITE_* variables. The demo token is entered at runtime
and held in browser memory. Optional GROQ_API_KEY and GROQ_MODEL stay backend-only;
they are absent locally, so live inference remains unverified. Mocked timeout,
error and evidence-ID validation tests remain in the full suite.

Original V1/V2 reports, hashes and approval state remain untouched. The previous
54-file runtime report describes the historical package, not this minimal runtime.
No claim of comprehensive coverage, legal correctness or legal currentness is made.

Final local verification: 305 backend tests passed (one existing Starlette/HTTPX
deprecation warning), frontend lint/TypeScript/build passed, three provider guard
tests passed, 14 synthetic-voice and 12 unsupported-voice private browser checks
passed, and five synthetic-public production browser checks passed. The isolated
16-file runtime answered synthetic data without private or ML modules and became
unready when its synthetic publication decision was removed. The candidate's
28-case developer regression set retained Recall@5 1.0, MRR 0.9649, nDCG@5 0.9737,
61/61 byte-valid citations and 9/9 abstentions. This was not an independent legal
accuracy benchmark. All 129 baseline protected files and 80 archived V1 files
remain unchanged; both real audit chains and empty allowlists pass. See
[machine-readable verification](public-corpus-verification.json).
