# Working archival-chat MVP

Historical initial chat slice. The [completion sprint](completion-sprint.md)
supersedes the three-paragraph, BM25-only and unavailable-voice limits below.
The original evidence bindings and review restrictions remain unchanged.

The current architecture adds backend/retrieval and backend/chat without changing
Stage 2A/2E/2F/2G or V2 schemas, algorithms, policies, reports or source files.

1. The existing V2 verifier loads the explicit metadata/candidate bindings.
2. Each document is checked against its raw PDF and processed JSON hash.
3. Stage 2F validation and hard exclusions are reused, including full notification
   paragraphs and enclosing context. Uncertain Hindi, schedules/forms, ambiguous
   marginal associations and unsafe boundaries are excluded.
4. Eligible archival paragraphs form a deterministic BM25 index, with exact
   whole-paragraph context limits and deduplication.
5. A conservative question scope gate abstains on unsupported domains, current
   rights/applicability, instruction-like requests or missing/stale evidence.
6. If configured, Groq chooses a JSON list of retrieved source IDs. Unsupported
   fields, IDs, duplicates, malformed/truncated output or invented prose are
   rejected. The response falls back to exact extractive source quotations with
   an explicit rejected-output warning. Empty selection abstains.
7. The server validates sources again and assembles the answer and citations.
   Frontend text rendering does not execute HTML or Markdown supplied by a model.

This is an intentionally extractive AI-assisted research slice, not unrestricted
legal-answer generation. Prompts alone cannot verify an arbitrary model claim.
The server therefore never publishes free-form model claims as a grounded answer.
No real review event or approval is created. VERIFIED_REVIEWED is reserved and
never emitted by this release. Even an existing future approval would require
separate trusted-checkpoint integration before being used as reviewed evidence.

BM25 works without third-party search dependencies. No embedding model or FAISS
is installed/configured. A rank-fusion utility is tested, but hybrid retrieval is
not claimed. Retrieval scope expansion needs separate source/quality work.

## Files to inspect

- [Search and quarantine](../backend/retrieval/engine.py)
- [Existing exclusion policy](../backend/review/service.py)
- [Existing QA implementation](../backend/qa/legal_text.py)
- [Preserved visual observations](../backend/qa/stage2e_visual_review.json)
- [Chat models](../backend/chat/models.py)
- [Bounded Groq transport](../backend/chat/provider.py)
- [API and error handling](../backend/chat/api.py)
- [Browser conversation](../frontend/src/components/ConversationWorkspace.tsx)
- [Evidence migration](evidence-migration.md)

Existing derived V2 reports retain historical links and original hashes. The
links above provide working public source references without modifying pinned
reports. The original publication manifest describes the migration commit only.

## Installed-browser E2E

No test package or browser download is required. Use installed Chrome and Node
24. Set CHROME_BINARY if using Edge or a non-default installation.

Start the real backend and Vite as described in the README. Then:

```powershell
node frontend/tests/browser.mjs
```

The browser suite refuses a genuinely configured provider before sending chat
requests. Mocked mode additionally requires the test server's synthetic-transport
response marker. The guard can be tested without any server or API calls:

```powershell
node --test frontend/tests/provider-guard.test.mjs
```

This citation exercise requires the separate exact local source bundle. It tests
real browser requests, BNS/BNSS qualifiers, server quote hashes, source links,
source selection, Enter/Shift+Enter, clear, mobile layout and connection recovery.
Screenshots/results go only to ignored frontend/.qa/. The script launches its own
temporary headless browser profile, not the user's normal profile, and closes it.

For external-inference mocking, start this EXPLICIT TEST SERVER instead of the
real backend (never confuse it with live inference):

```powershell
.\.venv\Scripts\python.exe -B -m uvicorn backend.tests.chat_e2e_server:app --host 127.0.0.1 --port 8000 --no-access-log
# Vite in a separate terminal, then a third terminal:
node frontend/tests/browser.mjs --mock-provider
```

The synthetic test key/model are not real credentials. Actual source retrieval,
hash verification, API and browser rendering still run. The mock transport
returns only a supplied evidence ID and simulates a rate limit once. Additional
browser assertions cover loading, duplicate-send prevention, clear during an
in-flight request, and safe retry without duplicate user turns. Do not use this
test server for normal work.

When required ports are busy, do not terminate unrelated services:

```powershell
# Backend/test-backend terminal:
.\.venv\Scripts\python.exe -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 --no-access-log
# Frontend terminal:
$env:KANOON_BACKEND_PORT='8001'
npm.cmd --prefix frontend run dev -- --port 5174
# Browser-test terminal:
$env:CHAT_E2E_BACKEND_URL='http://127.0.0.1:8001'
$env:CHAT_E2E_FRONTEND_URL='http://127.0.0.1:5174'
node frontend/tests/browser.mjs
```

For the mock exercise on alternate ports, substitute backend.tests.chat_e2e_server
and add --mock-provider to the Node command. These browser tests are local
integration checks, not live Groq verification and not a complete accessibility
audit. Backend tests run entirely on labelled synthetic mutable evidence and
mock all external model calls.

## Manual checks

Ask supported questions, then inspect the complete quote, original PDF link,
physical page, line range and hashes. Ensure the BNS 106(2) exception is distinct
from the BNSS First Schedule entry. Do not infer subsequent commencement from
either source. Ask a consumer/tenancy/current-rights question and confirm no
citation is invented. Clear or reload and confirm local history disappears.

Missing Groq configuration must be labelled extractive mode. With a genuinely
configured available model, verify the provider status separately. A model
selection response does not certify legal correctness or currentness. Rate limits,
downtime and timeouts show safe errors and retry controls. Missing or changed
source bytes must produce quarantine/abstention, never new approvals.

The MVP test run does not download new legal sources, embeddings or models.
Public clones support synthetic tests and honest insufficient-evidence responses;
exact original-source verification requires the private bundle.
