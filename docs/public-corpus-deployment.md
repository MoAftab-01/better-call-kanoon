# Public BM25 deployment preparation

Status: READY_FOR_HUMAN_PUBLICATION_REVIEW; no actual corpus publication, push or deployment.
The source-specific rights assessment and A-L approval dossier are in
[publication-review.md](publication-review.md), with metadata in
[publication-review.json](publication-review.json). Older unsigned decisions are
no longer accepted in production. Candidate-v2 remains immutable offline input.

## Runtime boundaries

Private local research: CORPUS_KIND=private, optional PRIVATE_CORPUS_ROOT,
RETRIEVAL_MODE=auto/hybrid/bm25. Public production never imports that private path.
Public: KANOON_ENV=production, CORPUS_KIND=public, RETRIEVAL_MODE=bm25. No model,
FAISS, Sentence Transformers, PDF parser, review ledger or download is needed.

Public production requires all of the following, supplied separately after review:

- PUBLIC_CORPUS_DIR: exact delivered subset, not the full unreviewed candidate.
- PUBLIC_CORPUS_MANIFEST_SHA256: independently reviewed schema-2 manifest hash.
- PUBLIC_CORPUS_APPROVAL_FILE: external signed decision outside the corpus folder.
- PUBLIC_CORPUS_APPROVAL_SHA256: independently retained latest authorized receipt hash.
- PUBLIC_CORPUS_SIGNER_PUBLIC_KEY: independently provisioned reviewer's raw Ed25519
  public key, 64 lowercase hex characters. It is not read from the candidate/receipt.
- KANOON_ACCESS_TOKEN: distinct 32+ character secret, never the Groq key.
- KANOON_ALLOWED_ORIGINS: explicit HTTPS frontend origins; no wildcard/credentials.

The signed receipt covers the exact manifest and every original PDF/shard hash,
with one include/exclude/revoke decision per source. Unsigned, unauthorized,
missing, revoked, corrupted, stale or extra-file inputs fail closed. Excluded
shards must be absent, and are never opened by the runtime. The manifest itself
retains excluded-source identity/hash metadata, but no excluded text.

Schema 1 is inspection-only. An offline preview cannot be exposed through HTTP.
GET /api/health preserves its original contract. GET /api/ready returns 503 and
research_ready=false for unapproved/missing/invalid inputs; chat returns 503.
Tampering/revocation after startup invalidates search and citations. Legal-evidence
approval is separate and remains empty. No legal currentness inference is made.

## Offline PowerShell review (does not approve)

```powershell
$candidate = 'backend/data/public-corpus/candidate-v3'
$pin = (Get-FileHash "$candidate/manifest.json" -Algorithm SHA256).Hash.ToLower()
Get-ChildItem $candidate -File | Get-FileHash -Algorithm SHA256
.\.venv\Scripts\python.exe -B -m backend.public_corpus inspect --directory $candidate --sha256 $pin --query 'BNS section 15'
.\.venv\Scripts\python.exe -B -m backend.public_corpus review-candidate --directory $candidate --sha256 $pin
.\.venv\Scripts\python.exe -B -m backend.public_corpus measure --directory $candidate --sha256 $pin
# Compare the proposed public metadata manifest to the candidate, byte-for-byte:
(Get-FileHash docs/publication-candidate-manifest.json).Hash -eq (Get-FileHash "$candidate/manifest.json").Hash
# New source-sharded version only; refuses any existing destination:
# .\.venv\Scripts\python.exe -B -m backend.public_corpus shard-candidate --directory backend/data/public-corpus/candidate-v2 --sha256 bbbc799f2583145c0ac704c518cfe2f5d0049d490994d7e0cbabf19df47c1fa6 --output backend/data/public-corpus/<NEW-name>
.\.venv\Scripts\python.exe -B -m backend.review verify
.\.venv\Scripts\python.exe -B -m backend.review allowlist
.\.venv\Scripts\python.exe -B -m backend.publication verify
.\.venv\Scripts\python.exe -B -m pytest backend/tests -q -p no:cacheprovider
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

The review command emits a large JSON report: 555 passage checks and 194 context
checks. It verifies all 404 source pages but makes no visual-correctness claim.
Review the 12 sampled pages and the remaining 543 selections using the original
local PDFs; filenames/hashes are in the source inventory. Open originals locally
with a trusted PDF viewer; do not upload private artifacts to an online viewer.

## Authorized delivery, only AFTER human permission

No real receipt or signing credential has been created. An authorized human must
resolve rights questions and sign externally using their own existing key. The
protocol and receipt schema are in the dossier. This is not a signing CLI.
The following is a future delivery procedure, not authorization to execute it:

```powershell
# Provision trusted values through an independent operator channel, not candidate files:
# $env:PUBLIC_CORPUS_SIGNER_PUBLIC_KEY = '<reviewed raw public key hex>'
# $receipt = '<externally supplied signed publication decision>'
# $receiptPin = '<independently retained latest decision SHA256>'
# .\.venv\Scripts\python.exe -B -m backend.public_corpus deliver --directory $candidate --sha256 $pin --decision $receipt --decision-sha256 $receiptPin --output backend/data/deployment/<NEW-approved-subset>
```

Delivery verifies the entire local candidate, authenticates the receipt and copies
only manifest.json, NOTICE.md and included source shards into a NEW ignored local
directory. It never overwrites or uploads. Revalidation catches concurrent changes.
No private PDF, processed record, audit or index is needed in the delivered runtime.
Keep the signed receipt separate. Hash pins are independent control-plane inputs,
not values automatically trusted from files. Failed preparation can leave an
unpublished partial destination: inspect it; do not serve or overwrite it.

Revocation/rollback requires a new authorized decision and independently updated
latest receipt pin, a new subset directory and explicit restart. Removing/changing
the live receipt fails closed without waiting for re-indexing. This mechanism is
not a global revocation registry and cannot protect against an operator deliberately
reverting both files and trusted pins. Never restore old pins automatically.

## Hosting configuration (not deployed)

render.yaml: single Uvicorn worker, $PORT, minimal pinned runtime requirements,
public BM25, automatic deployment off, secret/trust values sync:false. The backend uses 17 runtime/configuration files. The current combined website
ZIP adds 24 frontend build files (41 total), plus artifact-inventory.json;
no corpus, receipt, signing key, private source, model or diagnostic is included.
The separate frontend uses frontend/vercel.json: Vite build, dist output, frontend
project root. Set VITE_API_BASE_URL to the approved backend HTTPS origin. Secrets
must never use VITE_*; demo access is entered interactively and held in memory.

After separately approved deployment, approved artifact files must be supplied
reproducibly on every build. Do not copy backend/data wholesale or put private
acquisition in a build hook. The corpus location and external receipt location
must match the explicitly configured paths. No public download URL or deployment
artifact publication was created in this task. The ignored local code ZIP is an
inspectable source artifact, not an autonomous installer or deployed service.

[Render Free documentation](https://render.com/docs/free) states idle spin-down
and ephemeral filesystem limitations, and discourages production use. Free is a
preview target, not a verified production SLA or capacity claim. Cold-start time
on the provider includes platform spin-up beyond our Python timing. The local
Windows measurements in [results](publication-release-results.json) do not prove
Linux/Render capacity; verify a clean target build, memory, readiness and limits
before any release. [Render Blueprint reference](https://render.com/docs/blueprint-spec)
and [Vercel Vite guidance](https://vercel.com/docs/frameworks/frontend/vite) were
checked; no hosting API, account or deployment mutation was used.

Production controls: 30 research requests/minute/process, two concurrent requests,
16,000-byte body, bounded history/question, 25-second request deadline, Groq timeout
from backend settings, server-only source-ID selection and exact server citations.
The shared demo token is an access barrier, not per-user identity or distributed
rate limiting. Scaling workers needs a separately designed shared limit policy.

GROQ_API_KEY and GROQ_MODEL are optional backend-only environment variables.
Both are absent in process/user/machine configuration in this review. Extraction
works without them; live Groq and real browser audio remain unverified. Do not
fabricate a live answer or treat mock provider/voice tests as hardware checks.

## Browser verification

backend.tests.public_corpus_e2e_server is SYNTHETIC-only, generates ephemeral
software-test keys, disables Groq and advertises a synthetic marker. Never deploy
it or its receipt. frontend/tests/public-runtime.mjs verifies authorized public
citations, provenance, access protection and mobile rendering against it.
backend.tests.chat_e2e_server uses a marked mock provider and real local archival
retrieval for broader browser checks. Neither test writes real review events.
See measured results for exact check counts and limitations.

For the no-corpus website release, follow [the public website deployment guide](public-website-deployment.md). It supersedes hosting steps here while research remains unavailable.
