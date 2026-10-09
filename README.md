# Better Call Kanoon

> **Your AI guide to Indian law.**

Voice-powered AI legal information grounded in Indian law.

> **This is a legal INFORMATION tool. It is not a lawyer and it does not
> provide legal advice.** Nothing it shows you is a substitute for a qualified
> advocate. See [Honest limitations](#honest-limitations) before you rely on
> anything here.

---

## Contents

- [What this is](#what-this-is)
- [Repository layout](#repository-layout)
- [Architecture — and why the API contract is the boundary](#architecture--and-why-the-api-contract-is-the-boundary)
- [Quick start](#quick-start)
  - [Dev workflow (two processes, hot reload)](#dev-workflow-two-processes-hot-reload)
  - [Prod / single-origin workflow (build, then serve from one origin)](#prod--single-origin-workflow-build-then-serve-from-one-origin)
  - [Docker](#docker)
- [Environment variables](#environment-variables)
- [Tests and linting](#tests-and-linting)
- [API surface](#api-surface)
- [Roadmap — 15 stages](#roadmap--15-stages)
- [Honest limitations](#honest-limitations)
- [Security and privacy properties](#security-and-privacy-properties)
- [Responsible use](#responsible-use)
- [License](#license)

---

## What this is

Better Call Kanoon is a voice-first web application that will answer ordinary
questions about Indian law in plain language, in English or Hindi, and read the
answer back to you. It is being built so that every answer is grounded in
statute text the application itself retrieved from official sources, carries
citations, and is delivered next to a clear disclaimer.

**It is Stage 1 of 15.** What exists today is the application shell, the
configuration layer, two API endpoints, and the full React interface. There is
**no question answering yet** — there is no `/api/chat` route. The composer
accepts a question and then tells you, honestly, that answering arrives in a
later stage. It cannot invent a legal answer, because the code path that would
have to do that does not exist.

## Repository layout

Two folders, one per side of the API contract, plus the root files:

```
Better Call Kanoon/
├── backend/                  Python — FastAPI application
│   ├── app/
│   │   ├── main.py           App factory, CORS, static mount, error handlers
│   │   ├── config.py         Settings: the only place env vars are read
│   │   ├── models.py         Pydantic response models (the API contract)
│   │   ├── api/health.py     GET /api/health
│   │   ├── rag/              Ingestion + hybrid retrieval   (Stage 2–3)
│   │   ├── llm/              Grounded generation           (Stage 4)
│   │   ├── voice/            Speech helpers                 (Stage 5)
│   │   ├── legal/            IPC/BNS crosswalks             (Stage 5)
│   │   └── evaluation/       Quality measurement            (Stage 7)
│   ├── tests/                pytest suite (contract + leak guards)
│   ├── data/                 Ingested laws, index, helpline data
│   │   ├── emergency_contacts.json
│   │   ├── laws/             ← you put statute PDFs here (git-ignored)
│   │   ├── mappings/
│   │   └── index/            Generated retrieval index (git-ignored)
│   ├── logs/                 Runtime logs (git-ignored)
│   ├── requirements.txt
│   ├── pyproject.toml        ruff + pytest configuration
│   └── .env.example          The only tracked environment file
│
├── frontend/                 TypeScript — Vite + React 19
│   ├── src/
│   │   ├── main.tsx          Entry point
│   │   ├── App.tsx           Application shell
│   │   ├── i18n.ts           EN + HI string table (48 keys each)
│   │   ├── types.ts          Wire types
│   │   ├── api/              client.ts, mappers.ts — the boundary
│   │   ├── hooks/            useAppConfig, useHealth, useLanguage, useSpeech
│   │   ├── components/       11 components
│   │   ├── lib/              messages, starter questions, storage
│   │   └── index.css         The whole stylesheet, no CSS framework
│   ├── index.html
│   ├── vite.config.ts        Build output dir + dev proxy
│   ├── package.json
│   └── dist/                 Vite build output — served by the backend
│       └── index.html
│
├── Dockerfile                Multi-stage: node build → python runtime
├── docker-compose.yml        Single-container deployment
├── .gitignore                Covers both sides
└── README.md                 This file
```

## Architecture — and why the API contract is the boundary

```
┌────────────────────────────────────────────────────────────────┐
│  Browser — React 19 + TypeScript, built by Vite                │
│  frontend/src                                                  │
│    • Renders from GET /api/config (branding, languages,        │
│      starter questions, disclaimer, emergency contacts)        │
│    • Polls GET /api/health for the status bar                  │
│    • Web Speech API for voice (no server dependency)           │
│    • Zero CDN, zero remote fonts, zero remote images           │
└───────────────────────────┬────────────────────────────────────┘
                            │  HTTP / JSON, same origin
                            ▼
┌────────────────────────────────────────────────────────────────┐
│  backend/ — FastAPI                                           │
│    /api/health   liveness + knowledge-base state               │
│    /api/config   browser-safe settings (never a secret)        │
│    /             StaticFiles mount of frontend/dist            │
│                                                                │
│    rag/ (2–3) → llm/ (4) → legal/ (5) → evaluation/ (7)        │
│    data/laws → data/index        Groq (optional, key from env) │
└────────────────────────────────────────────────────────────────┘
```

**The API contract is the boundary, and it is the only thing the two folders
share.** `backend/app/models.py` defines the response shapes; `frontend/src/api/`
is the only place in the frontend that knows about HTTP, and
`frontend/src/api/mappers.ts` is the single place where the snake_case wire
format becomes camelCase for React components.

This matters for four reasons:

1. **The backend can be replaced.** Nothing in `frontend/src` imports Python,
   reaches into the filesystem, or knows where the server runs. The contract is
   the interface, not the implementation.
2. **The two sides deploy independently.** The frontend is a static bundle; the
   backend is a Python service. In production they share an origin and one
   process, but that is a deployment choice, not a coupling.
3. **Secrets stay server-side by construction.** The frontend cannot read
   `GROQ_API_KEY` because the key never crosses the boundary. The backend tells
   the browser `llm_configured: true|false` and nothing more.
4. **It is testable.** The suite asserts the contract directly, in-process, with
   no browser and no running server.

### Where the frontend build output goes

`frontend/dist` is the contract between the two halves:

- Vite writes to `frontend/dist` (`build.outDir` in `vite.config.ts`). Rename it
  and the deployed site breaks silently.
- `backend/app/config.py` sets `STATIC_DIR` to `<repo>/frontend/dist` — a path in
  the *sibling* folder, not inside `backend/`.
- `backend/app/main.py` mounts that directory at `/`, **after** the API routers
  are registered, so the catch-all mount cannot shadow `/api/*`.

## Quick start

### Prerequisites

| Tool | Version | Needed for |
| --- | --- | --- |
| Python | 3.11 or newer (3.12 works) | Backend |
| Node.js | 20 or newer (22 LTS recommended) | Frontend |

Both are free and open source. No account, no API key and no paid service is
required to run this repository.

### One-time setup

<details open>
<summary><b>Windows PowerShell</b></summary>

```powershell
cd "E:\placement_personal\Projects\Better Call Kanoon"

# Python virtual environment at the repo root
python -m venv .venv

# Backend dependencies
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# Frontend dependencies
cd frontend
npm install
cd ..

# Environment file (optional - the app runs without it)
Copy-Item backend\.env.example backend\.env
```

</details>

<details>
<summary><b>macOS / Linux (bash)</b></summary>

```bash
cd "Better Call Kanoon"

# Python virtual environment at the repo root
python3 -m venv .venv

# Backend dependencies
./.venv/bin/python -m pip install -r backend/requirements.txt

# Frontend dependencies
cd frontend
npm install
cd ..

# Environment file (optional - the app runs without it)
cp backend/.env.example backend/.env
```

</details>

The `.env` file is optional on purpose. With no `.env`, no API key and no built
index, the service starts and `/api/health` reports `"status": "healthy"`.

### Dev workflow (two processes, hot reload)

In development you run the backend and the frontend as two separate processes.
Each one reloads on save.

**Terminal 1 — the API on port 8000**

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd backend
../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — the UI on port 5173**

```powershell
cd frontend
npm run dev
```

```bash
cd frontend
npm run dev
```

**Then open <http://localhost:5173>.** Not port 8000 — that is only the API.

#### Why the URL is 5173, and what the `/api` proxy does

Vite's dev server runs on `5173` with hot module replacement. It cannot serve the
Python backend, so `frontend/vite.config.ts` declares a dev proxy:

```ts
server: {
  port: 5173,
  strictPort: true,
  proxy: {
    '/api':          { target: 'http://127.0.0.1:8000' },
    '/docs':         { target: 'http://127.0.0.1:8000' },

    '/openapi.json': { target: 'http://127.0.0.1:8000' },
  },
},
```

So when the React app calls `fetch('/api/config')`, the request goes to the
browser at `localhost:5173/api/config`, Vite forwards it to
`127.0.0.1:8000/api/config`, and returns the response to the app unchanged.

**This means the browser only ever makes same-origin requests during
development.** CORS is therefore never actually exercised in dev — if the app
works with the proxy on, it will work in production, where the SPA and the API
share one origin. That is why the default `CORS_ORIGINS` lists only the local Vite
dev server, and why it does not matter in production at all.

The default is deliberately **not** `*`. With the wildcard, any website on the
internet can read this API's responses from a user's browser. Add your own
domain explicitly if you ever need it.

Two consequences worth knowing:

- The backend **must** be running on `127.0.0.1:8000` or the proxy returns a
  connection error. The app handles that honestly: the status bar reports
  "Service unavailable" rather than showing a broken screen.
- `/api/config` is also reachable directly at <http://127.0.0.1:8000/api/config>
  if you want to inspect the payload the frontend is binding to.

### Prod / single-origin workflow (build, then serve from one origin)

Build the frontend once, and the same FastAPI process serves both the compiled
UI and the API from a single origin. No second server, no proxy, no CORS.

**Step 1 — build the frontend**

```powershell
cd frontend
npm run build
```

```bash
cd frontend
npm run build
```

This runs `tsc --noEmit` twice before `vite build`, so a type error fails the
build. Output lands in `frontend/dist/`:

```
dist/index.html                   1.11 kB │ gzip:  0.65 kB
dist/assets/index-DexzXpo_.css   13.52 kB │ gzip:  3.65 kB
dist/assets/index-DUQPLhO0.js   254.04 kB │ gzip: 79.25 kB
```

**Step 2 — serve it from the backend**

```powershell
cd ..\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
cd ../backend
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Step 3 — open <http://127.0.0.1:8000>.** That single origin serves:

| Path | Served by |
| --- | --- |
| `/` | `frontend/dist/index.html` — the React app |
| `/assets/*` | the hashed JS and CSS bundles |
| `/api/health` | FastAPI |
| `/api/config` | FastAPI |
| `/docs` | FastAPI's OpenAPI UI — see the CDN note in [Security and privacy properties](#security-and-privacy-properties) |

`vite.config.ts` sets `base: './'`, so every asset reference in the built HTML is
relative. The bundle therefore also works if it is ever served from a sub-path.

If you have not run `npm run build`, the backend logs
`Static directory ... not found; serving API only.` and the API keeps working
while `/` 404s. That is deliberate: a missing frontend build must not take the
API down with it.

### Docker

The root `Dockerfile` is a two-stage build:

- **Stage 1 (`node:22-slim`)** runs `npm ci` and `npm run build` in
  `frontend/`, producing `frontend/dist`.
- **Stage 2 (`python:3.11-slim`)** installs `backend/requirements.txt`, copies
  `backend/app/`, the data placeholders, and **only** the built `frontend/dist`
  from stage 1.

The final image contains **no `node_modules` and no `frontend/src`** — only the
compiled, minified, self-hosted assets. It runs as the unprivileged user
`kanoon` (uid 1001), exposes port 8000, and has a `HEALTHCHECK` that calls
`/api/health`. Only official base images (`python`, `node`) are used; there is
no paid registry and no paid base image.

```bash
cp backend/.env.example backend/.env     # optional; Compose starts without it

docker compose up --build
docker compose logs -f web
docker compose down
```

Then open <http://localhost:8000>.

Or without Compose:

```bash
docker build -t better-call-kanoon .
docker run --rm -p 8000:8000 --env-file backend/.env better-call-kanoon
```

`docker-compose.yml` bind-mounts `./backend/data` and `./backend/logs` so the
statute PDFs you download and the retrieval index generated from them survive a
container rebuild, and passes `backend/.env` through as the container's
environment. The bind mount is also what lets you edit
`backend/data/emergency_contacts.json` on the host and see the change on the next
`/api/config` request.

## Environment variables

Every variable is optional. Copy `backend/.env.example` to `backend/.env` to set
any of them — the app reads `.env` relative to the `backend/` directory it runs
from.

| Variable | Type | Default | Purpose |
| --- | --- | --- | --- |
| `APP_NAME` | str | `Better Call Kanoon` | Name shown in the UI and in the health payload |
| `APP_TAGLINE` | str | `Your AI guide to Indian law.` | Tagline under the app name |
| `APP_VERSION` | str | `0.1.0` | Reported by `/api/health` and the OpenAPI schema |
| `HOST` | str | `0.0.0.0` | Bind address |
| `PORT` | int | `8000` | Bind port |
| `DEBUG` | bool | `false` | Debug mode. Accepts `true/false/1/0/yes/no`, case-insensitively |
| `LOG_LEVEL` | str | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` |
| `CORS_ORIGINS` | list[str] | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed origins. Defaults to the Vite dev server only, never `*`. Irrelevant in production: the SPA and API share one origin |
| `GROQ_API_KEY` | str | *(empty)* | **Optional.** Model provider credential, read from the environment and never returned to the browser. Never commit a real key. An empty value means the model-backed features stay switched off and `/api/config` reports `llm_configured: false` |
| `GROQ_MODEL` | str | *(empty)* | Optional model id. Left empty so no model id is hardcoded; the provider default is used |
| `TOP_K` | int | `5` | Chunks retrieved per question (Stage 3) |
| `CANDIDATE_MULTIPLIER` | int | `4` | Candidates pulled from each retriever before fusion reranks them. **Not validated** — no recall measurement stands behind the value |
| `RRF_K` | float | `60` | Reciprocal-rank-fusion damping constant. The RRF paper's value, **not** tuned for this corpus |
| `EMBEDDING_MODEL` | str | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model id. Read from config and never hardcoded in source. **The backend that would consume it is not installed**, so nothing reads this yet |
| `MAX_INPUT_LENGTH` | int | `1000` | Maximum accepted question length, in characters |
| `RATE_LIMIT` | int | `20` | Requests allowed per window, per client. **Not enforced yet** — the limiter middleware arrives with the chat endpoint in a later stage |
| `DEFAULT_LANGUAGE` | str | `en` | Language selected on first load |
| `SUPPORTED_LANGUAGES` | list[str] | `en,hi` | Comma-separated language codes |
| `DATA_DIR` | Path | `data` | Data root, relative to `backend/` |
| `INDEX_DIR` | Path | `data/index` | Where the generated retrieval index is written |
| `STATIC_DIR` | Path | `../frontend/dist` | Built React app served at `/`. The default already points at the sibling `frontend/` package; set it only if you move `dist` |

## Tests and linting

**Backend** — run from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m pytest -q -rs
..\.venv\Scripts\python.exe -m ruff check .
```

```bash
../.venv/bin/python -m pytest -q
../.venv/bin/python -m pytest -q -rs
../.venv/bin/python -m ruff check .
```

The suite runs in-process — no server needs to be started, and it never touches
the real `backend/data/` directory (every writable path is redirected to a
temporary one). It covers the health and config contracts, the frontend mount,
JSON error handling, the OpenAPI schema, and the leak guards below.

`-rs` is worth running once: two tests skip when `frontend/dist` has not been
built, and they say so with an actionable reason rather than failing.

```powershell
..\.venv\Scripts\python.exe -m pytest -q -rs
```

```bash
../.venv/bin/python -m pytest -q -rs
```

**Frontend** — run from `frontend/`:

```powershell
npm run typecheck
npm run lint
npm run build
```

```bash
npm run typecheck
npm run lint
npm run build
```

`npm run build` runs `tsc --noEmit` against both tsconfigs before bundling, so
the type check is part of the build. `npm run lint` runs ESLint with the
`typescript-eslint` and React Hooks rulesets.

## Stage 3 — retrieval (in progress)

Stage 3 is the retrieval layer. **Half of it has landed.** This section states
exactly what works, because the difference matters: a project that implies a
working hybrid retriever when it has a working lexical one is describing
itself inaccurately.

**What is built and tested** — `backend/app/rag/`:

| Module | What it does |
| --- | --- |
| `tokenizer.py` | Lowercase, split on non-letters, drop short noise tokens. **No stemming, deliberately** — see below |
| `lexical.py` | BM25 over an in-memory index, pure standard library, no dependencies |
| `scoring.py` | Cosine similarity and reciprocal-rank fusion of the two retrievers |
| `npy.py` | Minimal `.npy` reader/writer for the embedding matrix |

**The dense half is not built.** No embedding backend is installed, so
`embeddings.npy` is never written and `knowledge_base_ready` correctly reports
`False`. `hybrid_search` reports `retriever_used="lexical_only"` in that state
rather than returning a hybrid-looking score that silently ignored half its
inputs. Fusion is exercised by tests with synthetic scores only.

### Three decisions that were measured, not assumed

Every number below came from executed code, and each one replaced a default
that had been shown to be wrong.

**1. Lucene's IDF, not the textbook Okapi form.** The naive
`log((N - df + 0.5) / (df + 0.5))` goes *negative* once a term appears in more
than half the corpus. Measured at N = 20000, df = 18000, through the full BM25
denominator: a chunk saying the term ten times scores **−4.3155** while a chunk
saying it once scores **−2.1970** — the term repeated ten times ranks *below*
the one repeated once. The Lucene form `log(1 + x)` is non-negative
everywhere, and is what ships.

**2. Fusion by rank, not by score.** `0.65 * cosine + 0.35 * bm25` does not
apply those weights: cosine lives in `[-1, 1]` and BM25 is unbounded above, so
the lexical share of that sum measured **77.8% / 76.0% / 44.4%** at corpus
sizes 50 / 500 / 5000 instead of 35%. Three repairs were tried and rejected
first — max-normalisation (which makes a chunk scoring exactly 0.0 beat the
best real match), a cosine floor (which never fires, because off-topic queries
produce a flat *positive* cosine band, not a negative one), and
dispersion normalisation (whose denominator collapses — see below).
Reciprocal-rank fusion combines *positions*, which carry no scale at all, so
none of those failures can arise.

**3. A retriever is weighted by how far it narrowed.** Vanilla RRF gives a
retriever's rank-1 item the same score whether that retriever narrowed 20,000
chunks to **one** or to **fifty near-identical scores**. Measured, those tie
*exactly* at k = 0, 10 and 60. Since a list that is 50 long with scores inside
a 0.005-wide band has expressed no opinion, each retriever is weighted by
`1 / (1 + n / k)` — 0.98 at one candidate, 0.55 at fifty, 0.003 at 20,000.

### Two settings that were removed rather than documented

`SEMANTIC_WEIGHT` and `BM25_WEIGHT` were configurable from `.env` for the
weighted sum that measurement ruled out. They were **deleted**, not kept with a
comment explaining they were unused. A knob that appears to control retrieval
behaviour but does not is worse than no knob: anyone tuning it would see no
change and have no way to tell whether the setting was ignored, the corpus was
insensitive, or the feature was broken.

The same reasoning removed `DEFAULT_DENSE_WEIGHT` and `DEFAULT_LEXICAL_WEIGHT`
from `scoring.py`, which had been kept with a comment marking them unused. What
remains — `TOP_K`, `CANDIDATE_MULTIPLIER`, `RRF_K` — is read by real code.
Tests assert the removed names stay removed.

### The result kind that keeps a number from masquerading as an answer

`SearchResult.kind` is the module's honesty device, and it has four values.
Because the IDF floor is a positive constant, a query built only out of
ubiquitous terms scores **every** document above zero — measured 20,000 of
20,000 over synthetic chunks, with the values differing only by ~1e-13 of float
noise. For a statute corpus `section`, `shall` and `act` are exactly such terms,
so this is the *common* query, not a corner case. Reporting it as a confident
match would be the worst failure this project could have.

| `kind` | Means |
| --- | --- |
| `matches` | At least one matched term can discriminate between documents |
| `low_information` | Every matched term was already pinned at `IDF_FLOOR` — the ranking is real but rests only on boilerplate |
| `out_of_vocabulary` | The corpus has never seen those words. **Not** the same as "no provision matches" |
| `empty_index` | Nothing has been ingested |

The `low_information` threshold is **derived from the existing constant**, not
invented: the floor first binds at N = 10 documents (at N = 9 a universal term
weighs 0.051293; at N = 10, 0.050000). A separate tuned cut-off was rejected
precisely because no evaluation has been run that could tune one.

### What is not claimed

**No retrieval-quality number appears anywhere in this project, because none
has been measured.** There is no precision, no recall, no MRR and no nDCG, and
none will be invented. Stage 7 builds the evaluation harness that would produce
them; until it runs, the constants in `lexical.py` and `scoring.py` are
documented defaults with reasoning attached, not tuned values.

The distinction between `low_information` and `out_of_vocabulary` is
**structural, not statistical**: it reports what the index contains, not how
likely a match is to be correct.

## API surface

Stage 1 exposes exactly two routes. Both are read-only, public, and answer with
no `.env`, no API key and no built index.

| Route | Purpose |
| --- | --- |
| `GET /api/health` | Liveness plus knowledge-base state |
| `GET /api/config` | Browser-safe configuration: branding, languages, speech rates, starter questions, the disclaimer, and the emergency helpline directory |

Interactive documentation is at `/docs`, the schema at `/openapi.json`.

`POST /api/chat` **does not exist** and returns a JSON `404`. A stub that
returned a fabricated answer would be worse than no endpoint at all, so the
contract is a clean `404` until the real retrieval-backed implementation lands.
A test pins this (`test_chat_endpoint_is_not_implemented_yet`) and is deleted
when the endpoint ships.

## Roadmap — 15 stages

Stages 1 and 2 are complete. Stage 3 is **in progress** — its lexical half has
landed, its dense half has not. Stages 4 onward are planned and **not started**.

| # | Stage | Status |
| --- | --- | --- |
| 1 | Scaffolding, settings layer, `/api/health`, `/api/config`, React UI, Docker, test suite | **Complete** |
| 2 | Statute PDF ingestion — text extraction and chunking | **Complete** |
| 3 | Hybrid retrieval — dense embeddings + BM25, weighted fusion, `TOP_K` selection | **In progress** — BM25 + fusion done, dense embeddings not |
| 4 | Grounded answer generation with per-chunk citations, strict refusal when retrieval finds nothing | Pending |
| 5 | `POST /api/chat` — the first endpoint that answers a question | Pending |
| 6 | Voice input/output wiring, speech-rate control, read-aloud answers | Pending |
| 7 | Evaluation harness over a curated question set — retrieval and answer-quality measurement | Pending |
| 8 | IPC / BNS crosswalks and section-number normalisation | Pending |
| 9 | IPC → BNS transition guidance for the user | Pending |
| 10 | Rate limiting and per-client abuse guardrails | Pending |
| 11 | Hindi-first rendering pass: Devanagari typography, RTL-safe layout, terminology review | Pending |
| 12 | Offline / low-connectivity operation — service worker, reduced payload | Pending |
| 13 | Accessibility audit — keyboard-only, screen reader, contrast, motor | Pending |
| 14 | Emergency-content sourcing and verification against official Government of India sources | Pending |
| 15 | Deployment hardening — TLS termination, secret management, observability | Pending |

Stage 5 in this table is the chat endpoint; the earlier "voice" wording in some
older notes referred to a different split. The numbering above is the plan of
record.

## Honest limitations

This section is the point of the README, not a disclaimer bolted onto the end.

- **This is legal INFORMATION, not legal advice.** The application explains what
  statute text says. It cannot tell you what to do in your case, cannot predict
  the outcome of any matter, and cannot assess whether a provision applies to
  your facts. Consult a qualified advocate.

- **It is not a lawyer, and it is not presented as one.** The string "AI
  Lawyer", "Your Lawyer" and "Virtual Lawyer" appear nowhere in this
  repository, and a test (`test_config_contains_no_lawyer_branding`) fails the
  build if one is ever introduced. The visible disclaimer contains the words
  "not a lawyer" and "does not provide legal advice", and it is served from
  `/api/config` so the frontend and the API can never disagree about it.

- **The emergency helplines ship UNVERIFIED.** All nine numbers in
  `backend/data/emergency_contacts.json` carry `verified: false`. They are
  widely published national numbers, but this project has **not** checked them
  against official Government of India sources. The UI surfaces that honestly:
  every entry is labelled "Unverified" and the panel carries an explanation. They
  must be verified against official sources — and the flag flipped to `true`
  only when they have been — before any production deployment. Do not rely on
  them as they stand.

- **No accuracy or performance number in this README is real, because none has
  been measured.** There is no retrieval benchmark, no answer-quality score, no
  latency figure and no percentage of any kind anywhere in this repository.
  Stage 7 exists precisely to measure these. Until then, any such figure would
  be invented, so none is quoted.

- **The Hindi needs a native speaker.** All 48 Hindi strings in
  `frontend/src/i18n.ts` were written without native-speaker review. They are
  *plausible*, not *approved*, and the following are the ones most likely to need
  correction:

  | Key | English | Why it needs review |
  | --- | --- | --- |
  | `heroSub` | "Information only — not legal advice." | Carries the central legal disclaimer. Wording must be exact. |
  | `footerNote` | "Information only — not a lawyer and not legal advice." | Same, on a second surface |
  | `composerPending` | "Answering is not available yet…" | Explains why nothing was sent |
  | `stageNote` | "Stage 1 — interface only." | Stage framing; "चरण" vs "स्टेज" is a register choice |
  | `unverifiedExplain` | "Not yet verified against an official Government of India source." | Must match the tone of the `verified` flag |
  | `configDown` | "Cannot reach the server…" | Error copy; needs to read as calm, not alarming |
  | `statusBarUnavailableBody` | "The backend is not responding…" | Error copy; same |
  | `sectionAsk`, `composerLabel` | "Ask your question", "Type your legal question" | "प्रश्न" (question) vs "सवाल" (colloquial) is a deliberate formality choice that should be confirmed |
  | `micLabel`, `micHint` | "Tap to speak — voice input" | Voice is not shipped yet; phrasing may change when it is |
  | `readAloud`, `speakAgain` | Both "Read aloud" in English | These are two *different* keys rendering identical English. They must not stay identical in Hindi. |

  `starter_questions[].text_hi` and `supported_languages[].native_label` are
  also Hindi and also unreviewed; the starter questions are served by
  `/api/config` from `backend/app/main.py`, not from the frontend.

- **Statute text is never shipped in this repository.** `backend/data/laws/` is
  empty on a fresh clone and its `*.pdf` files are git-ignored. You download
  PDFs yourself from official sources — **India Code**
  (<https://www.indiacode.nic.in/>), the official repository of Indian laws
  maintained by the Legislative Department — and save them as
  `backend/data/laws/bns_2023.pdf`, `ipc_1860.pdf`, and so on. Do not use
  scraped third-party mirrors. Stage 2 reads those PDFs into a text index
  (`backend/scripts/ingest_laws.py`), but until you both supply the PDFs and run
  that command the application still has **no legal content at all** — the
  directory ships with only a `.gitkeep`.

  Ingestion is deliberately conservative in six ways that are worth knowing
  before you point it at a corpus:

  - **A chunk never spans two statutory provisions.** Where a section heading
    is detected, the boundary outranks the `min_chars` floor, so a statute of
    many short sections yields many small chunks rather than fewer large ones
    that would file one provision's text under another's section number.
  - **A run that produces no chunks will not overwrite a working index.** If
    every file fails to extract, the existing `chunks.json` is left exactly as
    it was and the command exits `3`.
  - **A scan is reported, not indexed.** A PDF with no text layer is recorded
    as a failure with a neutral reason; nothing is guessed from it.
  - **The scan test asks for a *word*, not for a character count.** A scanned
    page does not extract to nothing — it extracts its page furniture. A
    four-page image-only scan yields `"- 1 -\n- 2 -\n- 3 -\n- 4 -"`: twenty
    characters, and no words. No character threshold can separate that from a
    genuine one-page amendment, because lowering the bar to admit short
    statutes admits page numbers too. So the extractor requires one run of two
    or more word-forming characters, which admits `"Ab."` and rejects
    `"- 1 -"` on a categorical property rather than a tuned number. The
    direction of the error matters: under-reporting a short statute is a
    visible annoyance an operator can fix, while filing `"- 1 -"` in the index
    under a real `law_id` is fabrication.
  - **Word-forming means any script, and that includes combining marks.** In
    Devanagari a syllable is a consonant plus its matra, and the matra *is* the
    vowel — `न` alone is `na`, `नि` is `ni`. Counting letters alone scores
    ordinary Hindi prose at a longest run of *one* character, which is below
    the threshold, so a fully typed Hindi statute would be reported as a scan.
    Marks are therefore counted as part of a word, while digits are not, so a
    page folio like `"- 2023 -"` stays furniture. A Hindi statute's filename
    reaches the terminal as Devanagari rather than mojibake, which is what
    makes it worth keeping the name intact in the first place.
  - **Roman folios count as furniture too.** Excluding digits rejects
    `"- 12 -"`, but a Roman-paginated Act prints the same furniture as
    `"- iii -"`, and `iii` is a three-character *word* — so the word test alone
    would index an image-only scan of a Roman-paginated Act as statute text.
    A run is treated as a page number only if it is a *canonical* Roman
    numeral, which is why **civil** survives: every character of it is in the
    set `IVXLCDM`, and a naive character-set test would classify "civil court"
    as a folio and discard the commonest phrase in Indian legal prose. Because
    a statute may legitimately quote its own divisions, the rule counts *pages*
    that are entirely numerals rather than testing any single run, so one Roman
    numeral inside a typed Act cannot reach the threshold a wholly scanned
    document does.

  The command's exit codes are distinct on purpose, because each calls for a
  different operator response:

  | Code | Meaning | What to do |
  | --- | --- | --- |
  | `0` | Every document was indexed. | Nothing. |
  | `1` | Some documents failed; the rest were indexed. | Re-fetch the files named under `FAILED`. |
  | `2` | No laws directory, or it holds no PDFs. | Check `--laws-dir`. |
  | `3` | Nothing was indexed, and an existing index was left untouched. | Your corpus is unreadable. The old index is still intact. |
  | `4` | The index could not be written at all. | Fix the filesystem — unwritable directory, full disk, revoked permission — then re-run. |

  `3` and `4` are the same symptom with opposite meanings, and collapsing them
  would hide one: in `3` there was nothing to write and your working index is
  safe; in `4` there *was* something to write and the filesystem refused it.

- **Statutes are amended.** A republished PDF may differ from an older one.
  Always confirm a provision against the current official text.

- **Voice input depends on the browser.** Recognition uses the Web Speech API,
  which is feature-detected: Firefox and several other browsers do not support
  it. The UI degrades honestly to a typed composer rather than pretending.

- **Nothing has been tested under load.** No concurrency, memory or long-run
  stability testing has been done.

## Security and privacy properties

These are enforced by tests, not just by convention:

- **No API key is ever hardcoded, committed or returned.** `GROQ_API_KEY` is read
  from the environment. `/api/config` reports `llm_configured` as a **boolean
  only**. A sentinel key is injected by the test suite and asserted absent from
  `/api/config`, `/api/health` and `/openapi.json` — including the literal
  string `GROQ_API_KEY`.
- **No traceback, exception text, filesystem path or `site-packages` string ever
  reaches the browser.** A single catch-all handler logs server-side and returns a
  fixed message. Unknown API paths return JSON `404`, not an HTML error page.
- **No conversations are stored.** Question text lives in React component state
  and is gone on reload. Nothing is logged, persisted, or sent anywhere but the
  backend, and the backend does not write it to disk. The only persisted
  preference is the language and speech-rate choice in `localStorage`.
- **Zero third-party network egress from the application UI.** The served app at
  `/` loads exactly three things, all same-origin: `index.html`, one hashed JS
  bundle and one hashed CSS file. The favicon is an inline SVG data URI, the
  stylesheet is a single local file with no `@import`, and the bundle makes no
  remote request. The only host the app may contact is the Groq API, and only
  when a key is configured.

  **One documented exception:** FastAPI's auto-generated interactive docs page at
  `/docs` loads Swagger UI from `https://cdn.jsdelivr.net` and a favicon from
  `https://fastapi.tiangolo.com`. That page is developer documentation, not the
  product UI, and it is the one place a third-party CDN is contacted. Removing
  it means replacing FastAPI's bundled docs with a self-hosted viewer, which is
  tracked as Stage 15 hardening work. Until then, **do not expose `/docs` to
  end users** — and note that `GET /openapi.json`, the machine-readable schema,
  is fully self-hosted.

  **`/redoc` is disabled on purpose.** FastAPI's second bundled docs page pulls a
  Montserrat/Roboto stylesheet from `https://fonts.googleapis.com` in addition to
  its jsdelivr bundle. That is an external *font* fetch, which this project
  rules out everywhere, so `create_app()` sets `redoc_url=None` and the page
  returns 404. `backend/tests/test_api.py` pins both halves of this: `/redoc`
  stays 404, and no served page references a Google Fonts origin. Use `/docs`
  plus `/openapi.json` instead.
- **No paid services.** Everything here — Python, FastAPI, React, Vite, TypeScript,
  ESLint, pytest, Ruff — is free and open source. Groq's free tier is used when
  you configure a key; a paid Groq tier is *not* required and is not assumed.
  Building the retrieval index uses open-source models that run locally on CPU.
  *(This is what is free today. It is a statement about the tools currently
  chosen, not a guarantee about your hosting bill — an always-on server with
  public traffic is never free.)*

## Responsible use

Better Call Kanoon shares general legal information drawn from the statute text it
has ingested. It is not a lawyer, it does not provide legal advice, and it cannot
predict the outcome of any case.

If you are dealing with an urgent situation, contact the relevant national
helpline or a qualified advocate. The emergency directory in
`backend/data/emergency_contacts.json` is surfaced by the application, and — as
stated above — **those numbers are unverified**.

## License

This project's own source is released under the MIT License. Statute text
remains the property of the Government of India and is not distributed by this
repository.

**One dependency is copyleft, and it changes what you may do with a build.**
Stage 2 ingests statute PDFs with [PyMuPDF](https://pymupdf.readthedocs.io/),
which is licensed **AGPL-3.0** — a strong copyleft licence, not a permissive
one. It is used here as an ordinary, unmodified library installed from PyPI and
called at ingest time; none of its source is vendored into this repository.

That is sufficient for running the project yourself, and for a demo, but it is
**not** a legal opinion, and the practical line is this: AGPL's network clause
means that if you modify PyMuPDF and then let other users interact with it over
a network, you must offer them your modified source. Shipping a modified copy
inside a larger product carries separate obligations too. Anyone intending to
distribute a build of this project should get real advice before doing so.

If AGPL turns out to be incompatible with how you intend to deploy, the
alternative is a different PDF text layer (for example `pdfminer.six`, which is
MIT-licensed) behind the small interface in `backend/app/rag/extraction.py` —
that module is the only place that would need to change.