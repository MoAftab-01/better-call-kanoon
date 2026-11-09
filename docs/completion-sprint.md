# Completion sprint: local archival research

Implemented on the existing feature branch. This is an extractive research demo,
not a lawyer, a current-law service, or unrestricted model-generated legal advice.
No push, cloud deployment, real submission or legal approval is performed.

## Working coverage and safety

The six unchanged original documents account for 404 physical pages. Research
discovery creates 552 Act selections (BNS 204, BNSS 259, BSA 89) and retains the
three original notification paragraphs: 555 archival selections in total.
The original three review proposals, candidate IDs and V1/V2 bindings are unchanged.
The archival research index is in memory, separate from both empty real allowlists.

Selection requires two consecutive printed numeric starts on the same page.
The final section on every page, uncertain subsection requests, cross-page joins,
unbalanced selection delimiters, unfinished punctuation, detected headers and
schedules are omitted. Stage 2F preview/validation and all hard page exclusions
are reused. Hard gates exclude 152 Act pages (BNS 15, BNSS 126, BSA 11); pages
passing them may still yield no complete selection. Full source page context is
hash-bound and displayed separately. Numeric starts are explicitly **unverified**;
attribution remains document-only, not a verified section citation.

Page-level delimiter/continuation heuristics are retained as warnings. They are
not silently removed: local selection boundaries must independently close before
the next numeric start. Sorted-extraction differences remain unresolved. Some
marginal headings appear detached in full-page context. Passing automated checks
does not prove visual fidelity or that the heuristic found every qualification.
No auto-repair is applied to source text.

Agent visual spot checks: BNS physical page 11 (numeric start 15, lines 3-4), BNSS
page 10 (25, lines 27-42), BSA page 33 (109, lines 11-17). Rendered pages agree
with these selected bodies and their illustrations/qualifiers at the inspected
scale. Only three Act pages were inspected visually in this sprint; this is not
approval of all selections. Original notification exception protections remain:
BNS excludes section 106(2); BNSS excludes the First Schedule entry relating to
BNS section 106(2). Neither original Act text nor those notifications proves
present commencement, subsequent amendments or case-specific applicability.

## Local hybrid setup (PowerShell)

Base dependencies still suffice for BM25. The optional stack tested here uses
CPU torch 2.9.1+cpu, sentence-transformers 5.1.2, transformers 4.57.6 and
faiss-cpu 1.13.2. Install into the project environment:

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.9.1+cpu --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-hybrid.txt
# Set an EXISTING, reviewed local all-MiniLM-L6-v2 snapshot directory.
$env:KANOON_EMBEDDING_MODEL_PATH = Read-Host 'Existing local embedding model directory'
.\.venv\Scripts\python.exe -B -m backend.retrieval check
.\.venv\Scripts\python.exe -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 --no-access-log
```

In a second terminal:

```powershell
$env:KANOON_BACKEND_PORT = '8001'
npm.cmd --prefix frontend run dev -- --port 5174
```

Open http://127.0.0.1:5174; backend http://127.0.0.1:8001.
No model is downloaded by application startup. The cached 91 MB MiniLM weights
were reused after checking 117 GiB free storage. CPU torch wheel was 111 MB;
optional installed dependencies use more space. GPU dependencies were avoided.
Missing packages/model or failed initialization keep BM25 working and report the
fallback. Startup can take about 48 seconds on this machine; status UI permits a
90-second cold start and offers retry. This CPU model's hosting memory requirement
has not been proven to fit Render's free tier.

FAISS IndexFlatIP searches normalized Sentence Transformers vectors. Overlapping
tokenizer-sized windows cover long selections; their parent complete selections
are deduplicated and ranked. RRF merges BM25 and semantic top-50 rankings.
Whole legal selections are never shortened to fit an answer budget. Semantic
scores cannot bypass source filters, lexical support checks, exclusions or live
source revalidation. Source-selection version and model-file digest are reported.
Top-k is 1-5; POST /api/chat also accepts source_ids containing exact document IDs.
An empty source filter returns no evidence. No request may select filesystem paths.

Try BNS section 15, BNSS concurrent consecutive sentences several offences,
BSA fact especially knowledge person burden proving, and each notification.
The UI supplies citations, original context, raw/processed/text hashes, warnings
and the archival label. Personalized advice, unsupported domains, ambiguous
requests and exact subsection attribution without reliable boundaries abstain.

## Evaluation and verification

The public benchmark contains questions and expected extraction references, not
new private Act excerpts. It has 19 supported and nine abstention cases. This is
a developer-authored regression set used during implementation, not a held-out,
expert-labelled or independent legal accuracy evaluation. Relevance judgments
are intentionally narrow and not exhaustive. Citation validity means exact byte
bindings and unchanged policy eligibility, not legal correctness. Timings exclude
provider calls and include live source checks; no Groq credits are spent.

```powershell
$run = [guid]::NewGuid().ToString('N').Substring(0,8)
.\.venv\Scripts\python.exe -B -m backend.retrieval.evaluate --output "backend/data/qa/benchmark-$run.json"
.\.venv\Scripts\python.exe -B -m pytest backend/tests -q --basetemp "backend/data/test-runs/$run"
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
node --test frontend/tests/provider-guard.test.mjs
$env:CHAT_E2E_BACKEND_URL = 'http://127.0.0.1:8001'
$env:CHAT_E2E_FRONTEND_URL = 'http://127.0.0.1:5174'
node frontend/tests/browser.mjs --mock-speech
node frontend/tests/browser.mjs --no-speech
.\.venv\Scripts\python.exe -B -m backend.review verify
.\.venv\Scripts\python.exe -B -m backend.review allowlist
.\.venv\Scripts\python.exe -B -m backend.publication verify
.\.venv\Scripts\python.exe -B -m backend.publication allowlist
```

See completion-sprint-results.md for measured scores. Real citation E2E and
benchmarks need the exact private source bundle. Public-only tests use explicitly
synthetic fixtures. The unchanged synthetic demo generates zero events:
`python -B -m backend.review.synthetic_demo --output-dir <NEW-synthetic-directory>`.
Groq key/model remain absent; mocked provider tests cover bounded transport,
timeouts, errors, abstention and invalid outputs. No live success is claimed.

Browser speech is opt-in, English (en-IN), and does not auto-submit transcripts.
Permission denial, unsupported APIs and errors leave typed chat usable. Stop and
cancel controls are available, and read aloud has a stop control. Browser speech
providers may process audio/text online. Headless tests use explicitly synthetic
speech objects; actual microphone quality, native permission prompts and audible
voice quality still require manual browser testing. Telephone calls remain disabled.

## Deployment preparation and publication boundary

Vercel: project root frontend, build `npm run build`, output dist. Set public
VITE_API_BASE_URL to the actual HTTPS Render origin; it is baked into the bundle
and must never contain a secret. Development leaves it blank for the Vite proxy.
Render: Python 3.12 service, repository root, build
`pip install -r backend/requirements.txt`, start
`uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log`.
Health path /api/health. Do not deploy the optional CPU stack by default.

Required backend settings: KANOON_ENV=production, KANOON_ACCESS_TOKEN (a distinct
32+ character private demo token), KANOON_ALLOWED_ORIGINS (actual explicit HTTPS
Vercel origin). Optional GROQ_API_KEY and GROQ_MODEL stay backend-only. No .env is
auto-loaded. Set secrets through hosting controls, never the Git repository.
The user enters the demo token at runtime in a password field; it stays in browser
memory, is not embedded in VITE_* or persisted, and is sent only as a bearer header.
Restrict distribution and rotate it. This is operator-gated demo access, not
per-user authentication. Production chat fails closed if protection is absent.

The service enforces 16,000-byte bodies, a ten-second body-read bound, 25-second
answer timeout, 30 requests/minute and two concurrent chat requests per process.
Use one worker. Internet-wide service still needs gateway authentication, shared
per-user limits, provider spending budgets and operational security review.
CORS is not authentication. /api/ready distinguishes process configuration from
corpus/research availability; /api/health preserves its original response.

The exact allowlist in deployment-publication.json packages public runtime code
and previously published V2 metadata only. backend.deployment refuses private data,
PDFs, model/index binaries and outside output paths; it verifies ZIP contents:

```powershell
.\.venv\Scripts\python.exe -B -m backend.deployment --output "backend/data/deployment/runtime-$run.zip"
```

The artifact intentionally contains **no raw PDFs, processed records, private V1
archive, review store, model or generated corpus index**. Existing published V2
metadata/notification packets are historical public artifacts, not newly published
Act selections. A clean source artifact cannot answer corpus questions; it returns
insufficient evidence. A useful hosted expanded corpus requires a separate,
explicit source-text/index publication review. Never copy the local backend/data
directory to hosting. No deployment or push is authorized by this preparation.

Free-tier cold starts and resource limits remain relevant: Render documents
[inactivity spin-down](https://render.com/docs/free). Vercel documents
[Vite environment variables](https://vercel.com/docs/frameworks/frontend/vite).
Implementation references: [Sentence Transformers local-only loading and encoding](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html),
[FAISS cosine similarity](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances),
[browser speech behavior](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition).

New code and synthetic fixtures can be reproduced publicly. Exact private evidence
verification cannot be reproduced without that bundle. Historical Git metadata
exposure identified in the migration guide remains; no history is rewritten.
