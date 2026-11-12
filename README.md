# Better Call Kanoon
**Your AI Guide to Indian Law**

**Public website deployment:** the application is prepared to run with no public
corpus. Visitors see "Source publication pending"; legal research and citations
stay unavailable until separate signed authorization. The private local research
capability below is not the public site's availability claim. See the
[hosted website deployment guide](docs/public-website-deployment.md) for the exact
environment, deployment commands, smoke tests and rollback procedure. No cloud
deployment or source publication has been performed.

A locally hosted English legal research workspace built with FastAPI, React,
TypeScript and Vite. It now supports end-to-end chat over a small, explicitly
bounded archival corpus. It describes source documents; it does not determine
current law or provide personalized legal advice.

## What works

- BM25 and optional local Sentence Transformers/FAISS/RRF search over 555
  unapproved archival selections: BNS 204, BNSS 259, BSA 89, and three complete
  commencement paragraphs, when the separate exact source bundle is present.
- Original PDF/processed-record hashes, page IDs, normalized line ranges, QA
  exclusions and V1/V2 candidate bindings are checked before sources are used.
- Optional Groq inference selects relevant evidence IDs. The server constructs
  answers from exact complete source quotations and validates citations.
  Unconstrained model prose is deliberately not published as a legal answer.
- Without Groq configuration, deterministic extractive chat still works.
  Without adequate evidence, the assistant abstains instead of inventing law.
- Browser-only bounded conversation history, loading/error/retry controls,
  Enter/Shift+Enter, clear conversation and answer-specific source cards.
- Existing health APIs, ingestion and evidence-review contracts remain intact.

Optional browser dictation and read aloud have consent, stop/error controls and
typed fallbacks. Speech may use the browser provider's online service. Telephony,
multilingual answering, comprehensive coverage and current-law certification are
unavailable. All real evidence remains unapproved. See the
[completion sprint guide](docs/completion-sprint.md) for hybrid setup, measured
evaluation, deployment preparation and honest remaining blockers.

## Windows PowerShell setup

For the separate, approval-gated public BM25 runtime, candidate inventory and
deployment configuration, see [public corpus deployment](docs/public-corpus-deployment.md).
Candidate preparation is complete; real corpus publication and deployment still
require explicit approval and applicable-rights review. No private evidence is
bundled into that runtime, and it fails closed without a separately pinned decision.

Use Python 3.12, Node.js 24 and npm. Run from the repository root:

```powershell
if (-not (Test-Path '.\.venv\Scripts\python.exe')) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm.cmd --prefix frontend ci
```

Base chat works without optional ML packages. The browser tests use installed
Chrome/Edge and Node's built-in WebSocket client. Backend requirements are not
fully locked; verification uses the installed environment, not a promise that
all future dependency resolutions will behave identically.

## Backend - terminal 1

Groq is optional. Set these **only in the backend terminal** if desired:

```powershell
$env:GROQ_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'Groq API key' -AsSecureString)).Password
$env:GROQ_MODEL = Read-Host 'An available Groq chat model ID supporting JSON object mode'
.\.venv\Scripts\python.exe -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

To run without Groq, omit the two environment assignments. There is no hardcoded
model default. A missing/invalid model or key selects extractive mode; an
unsupported configured model returns a safe configuration error. See
[Groq's API reference](https://console.groq.com/docs/api-reference) and your
account's available models. The tracked [.env.example](.env.example) is a
placeholder template, **not automatically loaded**. Never put a key in VITE_*
variables, source code, a committed file or browser storage.

## Frontend - terminal 2

```powershell
npm.cmd --prefix frontend run dev
```

Open **http://127.0.0.1:5173**. Backend: **http://127.0.0.1:8000**.
Vite proxies /api locally. Both servers bind to loopback.

If either port belongs to another application, leave that application alone.
Choose free alternate ports in separate terminals:

```powershell
# Backend terminal:
.\.venv\Scripts\python.exe -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 --no-access-log
# Frontend terminal:
$env:KANOON_BACKEND_PORT = '8001'
npm.cmd --prefix frontend run dev -- --port 5174
```

KANOON_BACKEND_PORT is a Vite development-server setting, not an API key or a
client-controlled source path. For separate production hosts, configure the
public HTTPS backend origin in frontend VITE_API_BASE_URL and explicit production
CORS/access protection as described in the completion guide. No deployment was performed.

## Evidence and index

A public clone contains source, tests, QA/provenance metadata and unapproved
proposal packets. It does **not** contain the six original PDFs or six processed
records. Place the separate original bundle at its recorded paths under ignored
backend/data/; consult [the evidence migration guide](docs/evidence-migration.md).
Re-ingesting a PDF does not guarantee the same processed hash because extraction
versions and ingestion timestamps matter.

```powershell
.\.venv\Scripts\python.exe -B -m backend.publication metadata
# Requires exact source bundle; fails closed if absent or stale:
.\.venv\Scripts\python.exe -B -m backend.publication verify
.\.venv\Scripts\python.exe -B -m backend.retrieval check
.\.venv\Scripts\python.exe -B -m backend.retrieval build --output backend/data/chat-index/local-v1.json
```

The last command writes a NEW hash-only manifest, refusing overwrite. The research
index is built in memory at the first chat/status request. Restart after
adding the bundle. Every search rechecks live source bindings, including after a
model call. Malformed, mismatched, excluded or instruction-like passages are
quarantined. No HTTP request can choose source paths. No indexing operation
writes approvals or review events.

## API and supported questions

- GET / and GET /api/health retain their existing response contracts.
- GET /api/chat/status reports corpus, retrieval and configuration readiness.
- POST /api/chat accepts message (1-2,000 characters), optional conversation_id,
  at most six recent user/assistant turns (1,200 characters each), optional top_k
  (1-5, default 3) and source_ids (up to six exact document IDs).
- GET /api/ready distinguishes runtime readiness from actual corpus availability.
- Responses include answer, conversation ID, evidence status, citations, source
  hashes/page/line metadata, provider/generation status and uncertainty.
- /docs exposes OpenAPI schemas. Request body cap: 16,000 bytes. Local rate cap:
  30 chat requests/minute per server process. Whole request timeout: 25 seconds.

Try: 'What does the BNS commencement notification state?', 'What exception appears
in S.O. 850(E)?', 'What does the BNSS notification say about the First Schedule?',
or 'What is stated in the BSA commencement notification?'
Also try 'BNS section 15', 'BNSS concurrent consecutive sentences several offences',
or 'BSA fact especially knowledge person burden proving'. These return unreviewed
original text with page context and unresolved QA flags, not verified provisions.

Consumer, tenancy, employment, current applicability and personalized-rights
questions are unsupported. Unclear follow-ups should repeat the notification
name; history is untrusted context, not an authority source.
ARCHIVAL_UNVERIFIED means identifiable archival bytes, not legal correctness.
INSUFFICIENT_EVIDENCE means abstention. This release never emits VERIFIED_REVIEWED:
indexing and model selection cannot promote a proposed passage to approval.

## Privacy and local-only security

Messages remain in browser memory (40 messages); six recent turns are sent with
each request. Questions reach the backend and, when Groq is configured and
evidence exists, the question, history and selected evidence are sent to Groq.
The backend does not persist conversations. Provider handling/retention is
governed separately by Groq; no zero-retention claim is made. Clear/reload removes
local history but cannot undo an external transmission already made.

Logs record request IDs, status codes, citation counts and durations, not prompts
or credentials. Responses use no-store caching. Groq uses certificate validation,
fixed HTTPS destinations, trust_env=False, bounded output and limited transient
retries. The model selects only server-issued IDs; it cannot supply source URLs
or legal claims. This does not prove legal truth or solve every injection attack.

**Restricted demo:** production mode requires a separate private access token,
limits chat to 30 requests/minute and two concurrent requests per server process.
Use one worker; broader public service requires authenticated per-user quotas,
shared limits and provider spending controls. Speak to a
qualified legal professional about your circumstances.

## Tests

```powershell
$run = 'backend/data/test-runs/mvp-' + [guid]::NewGuid().ToString('N').Substring(0,8)
.\.venv\Scripts\python.exe -B -m pytest backend/tests -q --basetemp $run -p no:cacheprovider
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

All automated provider calls are mocked; tests never spend Groq credits.
See [the MVP architecture and browser verification guide](docs/working-mvp.md)
for installed-Chrome E2E tests and exact mocked-provider setup.
See [the ingestion manual](docs/ingestion-manual.md) for synthetic PDF/TXT use.

Original V1/V2 reports, identities and the migration publication manifest remain
unchanged historical artifacts from commit b08da7a. That manifest describes the
migration snapshot, not a current full-file manifest after these MVP changes.
Historical stage documents can describe earlier unavailable features; this
README and the MVP guide describe current application behavior.
The completion guide supersedes the initial MVP guide where features expanded.
