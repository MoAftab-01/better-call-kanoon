# Better Call AI rebrand and compatibility

Product: **Better Call AI**. Repository name: **better-call-ai**.
Intended local directory name: **Better Call AI**. The active branch remains
feat/working-legal-chat-mvp; main is not merged or rewritten. GitHub and filesystem
rename operations are verified separately after the rebrand commit is pushed;
the code/documents do not grant deployment or corpus-publication permission.

The current UI, HTML title/description, welcome endpoint, API documentation title,
application docstrings, frontend package/lockfile metadata, future candidate
notice template and Render service name use the new product name. No Python
package/module path or API route is renamed. Existing local/private research and
the public no-corpus experience are preserved.

## Deliberately preserved compatibility names

- `KANOON_ENV`, `KANOON_ACCESS_TOKEN`, `KANOON_ALLOWED_ORIGINS`,
  `KANOON_EMBEDDING_MODEL_PATH`, `KANOON_BACKEND_PORT`: existing configuration
  keys remain authoritative. Do not rename or rotate secrets for this rebrand.
- `/api/health` still returns `service: better-call-kanoon`. This machine-facing
  service identifier is preserved for existing health checks; the human welcome
  message and OpenAPI title use Better Call AI. The frontend checks this legacy
  identifier without displaying it as the product brand.
- The `kanoon.chat` logger and `X-Kanoon-*` synthetic test markers remain stable.
  Keeping these names does not relax the mock-provider guard or authentication.
- The Ed25519 signature domain `better-call-kanoon:publication-decision:v2` plus
  one NUL is an immutable protocol identifier. Neither its bytes, decision schema,
  signature validation, independent trust anchor nor hash pins are migrated.

No environment-variable, module/import or signed-decision migration is required.
The health endpoint's status/service contract remains compatible. Only the
human-facing GET / welcome message changes to Welcome to Better Call AI.

## Historical and evidence boundaries

Former names inside Stage 2B source provenance, immutable V1/V2 records/packets,
original synthetic provenance fixtures, publication manifests, previous release
reports and the existing candidate notices remain byte-exact. They describe the
product at the time those records were made. They are not current UI branding.
All 179 captured protected files are checked before and after the rebrand.

The future candidate-preparation notice template uses Better Call AI. A newly
prepared candidate would therefore have different notice/manifest hashes and
must use a new output version with its own independent publication review.
Existing candidate-v2/v3 directories, ZIPs, manifests, IDs and notices are not
rewritten, repinned, regenerated or approved for this branding change.

[The rebrand report](rebrand-report.json) lists every remaining tracked old-name
occurrence by file, line and reason. Generated caches, virtual environments and
ignored private historical artifacts are outside the tracked branding search.
No raw PDF, processed legal text, review event or publication approval is changed.

## GitHub rename

After tests, push only the verified feature-branch commit to the existing origin.
Rename the same GitHub repository to better-call-ai; do not delete/recreate it or
merge main. Verify its repository ID, feature-branch SHA and default branch remain
the same. Update origin to https://github.com/MoAftab-01/better-call-ai.git only
after that URL is verified. Repo and folder rename results belong in the final
operational report; they are not assumed by this document.

If the authenticated rename operation is unavailable or lacks administration
permission, use the existing repository's GitHub **Settings > General > Repository
name**, enter **better-call-ai**, then click **Rename**. Keep the existing history,
branches, visibility and settings. Afterwards verify the new feature-branch URL
and update origin. Do not reuse the former repository name for a new repository;
that would interfere with GitHub's redirects. See
[GitHub's rename guidance](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository).

## Local directory rename

Stop the project development servers and close terminals/editors that hold the
directory open, after saving work. Do not terminate unrelated processes. Perform
one same-parent directory rename, with an absent destination, preserving .git,
.venv, node_modules and ignored private data in place. No copying, cleanup,
deletion, environment recreation or dependency installation is needed.

If an active workspace or terminal locks the folder, keep the original directory
intact. From a **new terminal in the containing Projects directory**, after closing
the old project workspace, run:

```powershell
if (Test-Path -LiteralPath '.\Better Call AI') { throw 'Destination already exists; stop.' }
Rename-Item -LiteralPath '.\Better Call Kanoon' -NewName 'Better Call AI' -ErrorAction Stop
Set-Location -LiteralPath '.\Better Call AI'
# Only after the GitHub repository rename has been verified:
git remote set-url origin https://github.com/MoAftab-01/better-call-ai.git
git status --short
git log -1 --oneline
git remote -v
.\.venv\Scripts\python.exe -B -m pytest backend/tests -q -p no:cacheprovider
npm.cmd --prefix frontend run typecheck
```

Reopen the new folder in the editor/agent. On Windows, existing .venv console
launchers can embed the original absolute directory. Preserve the environment
and use `.\.venv\Scripts\python.exe -m pytest`, `-m uvicorn`, or `-m pip` as the
setup guide does; do not recreate the environment as part of this rebrand.
Historical creation paths inside generated environment files remain historical.

## Deployment

The new Render blueprint service name is better-call-ai-api; existing hosted
resources, if any, are not renamed or redeployed by this task. No Vercel project
identifier is invented. The hosted frontend still requires its actual backend
HTTPS origin and exact production CORS settings. Authentication, request limits,
public BM25-only mode, pending-publication UI and fail-closed source gates remain
unchanged. The corpus remains unpublished and real approval state remains empty.
