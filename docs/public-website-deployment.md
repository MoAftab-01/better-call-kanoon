# Public website deployment: research intentionally unavailable

This release prepares a real Vercel/Render website with **no public corpus**.
The interface loads, backend health works, and visitors see source publication
pending. Legal research, citations and provider calls remain blocked. No source
clearance, publication receipt, Git push or cloud deployment is performed here.

## Deployment inventory and build

`docs/deployment-publication.json` lists exactly 41 source/configuration files:
17 backend/runtime files and 24 frontend build files. The ignored local artifact
is `backend/data/deployment/public-no-corpus-website-20261112.zip`, with a separate
artifact-inventory.json inside. It contains no corpus, PDFs, processed records,
private indexes, audit archives, approval files, test servers, secrets or local
diagnostics. SHA-256 and measurements are in [results](public-website-results.json).
The backend packager keeps its existing name, but the explicit inventory now also
includes the independently buildable frontend. Do not copy backend/data wholesale.

`frontend/.vercelignore` excludes dependencies, local screenshots, tests, secrets
and generated assets from source uploads. `.vercel/` metadata is Git-ignored.
Vercel must use the frontend directory as project root and dist as output.
`npm run build:hosted` rejects a missing/unsafe API origin before building.

Local checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m pytest backend/tests -q -p no:cacheprovider
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
node --test frontend/tests/provider-guard.test.mjs frontend/tests/hosted-env.test.mjs
# Use the actual backend HTTPS origin for a deployable frontend build:
$env:VITE_API_BASE_URL = 'https://<actual-backend-host>'
npm.cmd --prefix frontend run build:hosted
```

The placeholder is not a live URL. The local hosted-build check used
https://api.example strictly as test configuration, not a claimed deployment.
No generated frontend bundle is committed.

## Environment checklist

| Location | Variable / setting | Required value |
| --- | --- | --- |
| Render | Python | 3.12, selected by root .python-version |
| Render | KANOON_ENV | production |
| Render | CORPUS_KIND | public |
| Render | RETRIEVAL_MODE | bm25 |
| Render secret | KANOON_ACCESS_TOKEN | Operator-generated random secret of at least 32 characters, distinct from Groq key |
| Render | KANOON_ALLOWED_ORIGINS | Exact actual frontend HTTPS origin(s), comma-separated, no wildcard |
| Render | PUBLIC_CORPUS_DIR | ./public-corpus, intentionally absent |
| Render | PUBLIC_CORPUS_APPROVAL_FILE | ./publication-approval.json, intentionally absent |
| Render | PUBLIC_CORPUS_MANIFEST_SHA256 | Leave absent |
| Render | PUBLIC_CORPUS_APPROVAL_SHA256 | Leave absent |
| Render | PUBLIC_CORPUS_SIGNER_PUBLIC_KEY | Leave absent |
| Render optional secret | GROQ_API_KEY | Real backend-only Groq key; not needed for no-corpus website |
| Render optional config | GROQ_MODEL | Exact enabled model ID from the operator's Groq account |
| Vercel Preview and Production | VITE_API_BASE_URL | Actual backend HTTPS origin only, without /api, credentials, query or fragment |
| Vercel | Root / build / output | frontend / npm run build:hosted / dist |

Never put a bearer token, provider key or signing key in VITE_* variables, Git,
command arguments, build logs or frontend files. Supply secrets through the
hosting dashboard. Leave PRIVATE_CORPUS_ROOT and embedding settings unset. Do
not create placeholder publication pins, signers or receipts to satisfy setup.
The Render Blueprint no longer prompts for these deferred publication values.

## After separate push and cloud authorization

The following are future operator instructions, **not commands executed in this
task**. Account access, a chosen deployment project and separately authorized
source publication are different decisions. This infrastructure release requires
no publication approval because it carries no corpus.

1. Review this commit/artifact and explicitly authorize the intended feature-branch
   push or a separate code-only deployment repository. Do not merge or force-push
   implicitly. Render's connected remote must actually contain the reviewed code.
2. In Render, create a Python Web Service from the reviewed branch using render.yaml.
   Select the exact branch/commit, keep automatic deploys off, and use one worker.
   Set the token and origins above. If the frontend origin is not known, an empty
   origin list safely denies browser CORS until the actual origin is configured.
3. Backend build/start/probe commands are:

```text
python -m pip install -r backend/requirements-runtime.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log
Health probe: /api/health
```

4. Copy the actual Render HTTPS origin into Vercel's VITE_API_BASE_URL for the
   intended Preview and Production environments. Variables are embedded at build
   time; changing an origin requires a new frontend build/deploy.
5. Create/link the Vercel project with frontend as root. If using an already
   authorized CLI, these are the commands after deployment approval (npx may prompt
   to install the CLI; no PowerShell policy change is needed):

```powershell
npx.cmd vercel login
npx.cmd vercel link --cwd frontend
npx.cmd vercel env add VITE_API_BASE_URL production --cwd frontend
npx.cmd vercel env add VITE_API_BASE_URL preview --cwd frontend
npx.cmd vercel deploy --cwd frontend
# Only after the staging/first-deployment checks and production approval:
npx.cmd vercel deploy --cwd frontend --prod
```

The first deployment of a new Vercel project can be production even without
--prod. Use a separate staging project if isolation is required, and treat every
deploy command as a cloud publication action requiring approval. Do not upload
the repository root with the frontend CLI. No CLI/account login was performed here.

6. Update Render CORS to the exact deployed frontend origin. For a known existing
   service, the official Render CLI supports the following explicit deployment:

```powershell
render login
render deploys create <service-id> --commit <reviewed-commit-sha> --wait
```

Do not run this against an unreviewed service or assume a local SHA exists in
the connected remote. Account-aware Blueprint validation and actual target
deployment remain pending; only local configuration/artifact checks ran here.

Official references checked: [Render FastAPI](https://render.com/docs/deploy-fastapi),
[Blueprint fields](https://render.com/docs/blueprint-spec),
[Render CLI](https://render.com/docs/cli-reference),
[Vercel deploy](https://vercel.com/docs/cli/deploy),
[Vercel variables](https://vercel.com/docs/environment-variables).

## Staging smoke checks (Windows PowerShell)

Run after authorized deployment, substituting actual URLs. These use no secret
and submit no legal question. Expected readiness is **503**, not a failed deploy.

```powershell
$backend = 'https://<actual-backend-host>'
$frontend = 'https://<actual-frontend-host>'
$health = Invoke-RestMethod "$backend/api/health" -TimeoutSec 90
if ($health.status -ne 'healthy' -or $health.service -ne 'better-call-kanoon') { throw 'Unexpected health' }
$state = Invoke-RestMethod "$backend/api/chat/status" -TimeoutSec 90
if ($state.available -or $state.retrieval.passages -ne 0 -or $state.retrieval.corpus_kind -ne 'public' -or $state.research_state -ne 'publication_pending') { throw 'Unexpected research activation' }
$readyCode = curl.exe --silent --show-error --max-time 90 --output NUL --write-out '%{http_code}' "$backend/api/ready"
if ($readyCode -ne '503') { throw 'Research should remain blocked' }
$authCode = curl.exe --silent --show-error --max-time 90 --output NUL --write-out '%{http_code}' --request POST "$backend/api/chat"
if ($authCode -ne '401') { throw 'Check production access protection' }
$headers = curl.exe --silent --show-error --max-time 90 --dump-header - --output NUL --header "Origin: $frontend" "$backend/api/health"
if (($headers -join "`n") -notmatch [regex]::Escape("access-control-allow-origin: $frontend")) { throw 'Check exact production CORS origin' }
```

Open the website on desktop and a real mobile browser. Check the pending banner,
no source suggestions/citations, no access-token prompt for unavailable research,
disabled send even after typing/Enter, normal navigation, and connection retry.
In Network tools, typing or dictating must not issue POST /api/chat. Check that
actual account/CDN settings do not expose source directories or private artifacts.

Health is process liveness; readiness represents research capability. Render's
probe must stay /api/health so intentional publication gating does not create a
restart loop. HTTP 200 health is not a claim that legal research is functioning.
Production retains 30 chat requests/minute/process, two concurrent requests,
16,000-byte bodies, bounded history and a 25-second request deadline. Groq has
18-second provider timeout, 5-second connection timeout, bounded output and
limited transient retries; the whole-request deadline still applies.

## Groq and native voice

GROQ_API_KEY and GROQ_MODEL were absent in process, user and machine configuration;
root/backend .env files were absent. No live inference was claimed. Configure both
in the backend hosting environment and select an available model from the
[official Groq model documentation](https://console.groq.com/docs/models).
Do not enable unapproved research to test a provider. A later bounded integration
test can use explicitly synthetic evidence; the provider selects only known IDs
and the server builds exact citations. Existing mocked timeout/error/invalid-ID
tests remain in the passing backend suite.

Browser voice needs HTTPS (or localhost) and browser/device support. Automated
checks exercise consent, denial, start/stop/cancel, draft-only dictation, read-aloud
controls and unavailable-API fallback. They do not verify a real microphone,
transcription quality or audible output. On an actual device, dictate a harmless
test draft, check the words, stop/cancel, deny permission and confirm typing still
works. No dictation auto-submits. Public no-corpus mode intentionally has no answer
to read aloud; use the separately documented local SYNTHETIC test runtime for
manual read-aloud acceptance, never a fabricated public conversation.

## Cold start, dependencies and rollback

Local Windows measurements are in [results](public-website-results.json). They
cover fresh-process HTTP initialization and route checks using minimal runtime
dependencies, not Render/Linux certification. The isolated source package built
without private evidence; the frontend installed from its lockfile and built.

[Render Free](https://render.com/docs/free) documents idle spin-down after 15
minutes, roughly minute-scale platform wake-up and ephemeral storage, and
discourages production reliance. Our five-second UI health attempt may initially
time out; automatic checks retry every 15 seconds. The public status check is
separate and cannot activate research. Verify actual target startup, resource
usage and HTTPS before promoting a deployment. Free preview is not a service SLA.

Dependency audit: production npm dependencies report zero advisories. Full npm
audit reports ten moderate affected development packages from the minimatch DoS
advisory [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249).
These affect ESLint/TypeScript-ESLint tooling, not the served static application;
build only trusted repository/configuration inputs. The tooling risk remains
unresolved. No automatic major downgrade or forced override was applied, and
there is no blanket security-clearance claim.

If smoke tests fail, keep research blocked and stop promotion. With separate
operational approval, roll Vercel back to a known safe no-corpus deployment using
the dashboard, and deploy the corresponding safe Render commit explicitly.
Keep public/bm25, access/CORS configuration and absent publication pins. Never
roll back to private mode, restore obsolete approval pins, rewrite Git history or
copy private evidence. There is no existing cloud deployment to roll back in this
task. [Vercel rollback guidance](https://vercel.com/docs/deployments/rollback-production-deployment).

Corpus activation remains a later, independently authorized operation described
in [the publication dossier](publication-review.md). This website release changes
no candidate bytes, legal-review state, audit chain or publication authorization.
