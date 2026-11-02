# Better Call Kanoon

**Your AI Guide to Indian Law**

Stage 1A provides a minimal FastAPI backend. Stage 1B adds a responsive
React + TypeScript + Vite workspace with plain CSS and Lucide icons.

The frontend is a preview: AI answers, legal retrieval, citations, microphone
input, and voice calls are unavailable. You can draft a question or choose a
starter topic, but sending is disabled. Drafts stay in memory in the current tab;
they are not sent or saved and disappear on reload.

## Backend endpoints

| Method | Path | JSON response |
| --- | --- | --- |
| GET | `/` | `{"message":"Welcome to Better Call Kanoon"}` |
| GET | `/api/health` | `{"status":"healthy","service":"better-call-kanoon"}` |

## Windows PowerShell setup

Prerequisites: Python 3.12 and Node.js 24 with npm (verified with Python 3.12.10,
Node.js 24.14.0, and npm 11.9.0). Use `npm.cmd` in PowerShell so the commands work
without changing script execution policy.

Run these commands from the repository root. Reuse the root `.venv` when it
already exists; otherwise create it with the installed Python 3.12 interpreter.
Activation is unnecessary because the commands use the virtual environment's
Python executable directly.

```powershell
# Run from the repository root.

if (-not (Test-Path -LiteralPath '.\.venv')) {
    python -m venv .venv
}

if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
    throw 'The root .venv does not contain a Python executable.'
}

& '.\.venv\Scripts\python.exe' --version
& '.\.venv\Scripts\python.exe' -m pip install -r .\backend\requirements.txt
npm.cmd --prefix .\frontend ci
```

## Run the backend — terminal 1

From the repository root:

```powershell
# Run from the repository root.
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

The server listens at `http://127.0.0.1:8000`. Press `Ctrl+C` to stop it.

## Run the frontend — terminal 2

```powershell
# Run from the repository root.
npm.cmd --prefix .\frontend run dev
```

Open `http://127.0.0.1:5173`. Vite forwards `/api` requests to
`http://127.0.0.1:8000`, so the existing backend needs no CORS or API changes.
Port 5173 is fixed: if it is occupied, stop your previous frontend server rather
than silently switching ports. Press `Ctrl+C` to stop the frontend.

The status indicator validates the real `/api/health` response. It checks on
page load, every 15 seconds, and when you select Refresh or Retry. Requests time
out after 5 seconds. Backend connectivity does not enable AI answers.

## Manual endpoint checks

With the server running, open another PowerShell window and run:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/' | ConvertTo-Json -Compress
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' | ConvertTo-Json -Compress
```

The results should match the JSON responses in the table above.

## Verification commands

From the repository root:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest backend/tests -v
npm.cmd --prefix .\frontend run typecheck
npm.cmd --prefix .\frontend run build
npm.cmd --prefix .\frontend run lint
```

The two health tests use FastAPI's `TestClient` to check HTTP 200 responses and the
exact JSON payloads. No running server is required.

The production build is written to `frontend/dist`. Production hosting and API
routing are outside this stage; the configured proxy is for Vite development.
No API keys or other credentials belong in frontend code or `VITE_` variables.

## Manual browser checklist

- With both servers running, confirm **Backend connected** and the welcome,
  conversation, source, voice, and disclaimer sections.
- Refresh the connection and observe its checking state. Stop your backend
  server: within 15 seconds plus the request timeout, the status should become
  **Backend disconnected** without crashing. Restart it and select **Retry**.
- Type a question or select a topic. Only the draft should change. Sending,
  microphone input, and voice calls stay disabled, even with a connected backend.
- Confirm there are no generated answers, conversations, or citations. The
  sources panel explicitly says legal retrieval is unavailable.
- Reload: the draft should clear. In browser Network tools, question drafts
  should never produce an API request; the only application API call is health.
- Test desktop, tablet, and narrow mobile widths (including 320px). Sections
  should reflow without horizontal scrolling.
- Use Tab and Shift+Tab to reach the skip link, navigation, connection refresh,
  topic buttons, and text area. Check visible focus outlines and anchor links.

Better Call Kanoon is a legal-information guide, not a licensed lawyer. Consult
a qualified legal professional for advice about your specific situation.

## Stage 2A: offline document ingestion

The backend now includes a separate local CLI for user-supplied PDF/TXT documents
and explicit metadata manifests. It preserves provenance, unknown dates, source
hashes, physical PDF pages, and extraction uncertainty. It does not download or
verify documents, determine applicable law, or connect ingestion to the frontend.

See the [manual ingestion guide](docs/ingestion-manual.md) for the synthetic
fixture, exact PowerShell commands, metadata contract, output format, and limits.

## Versioned evidence publication

The [architecture](docs/architecture.md) and [V1-to-V2 migration guide](docs/evidence-migration.md)
explain the publication integration scope. Public metadata and synthetic tests
are independently checkable; real-corpus verification requires the exact separate
PDF/processed bundle. No legal passage is approved and current applicability is
unknown. Sanitized reports under `docs/evidence/v2/` have new bindings and IDs;
original V1 evidence is preserved privately, not overwritten.
