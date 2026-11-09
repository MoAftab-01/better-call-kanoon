# Completion sprint verification results

2026-11-10. Local feature branch only; no push or deployment.

| Measured retrieval metric | BM25 | Hybrid |
| --- | ---: | ---: |
| Recall@5 | 1.0000 | 1.0000 |
| MRR | 0.9649 | 0.9737 |
| nDCG@5 | 0.9737 | 0.9806 |
| Byte-bound citation validity | 61/61 | 61/61 |
| Unsupported/unsafe abstention | 9/9 | 9/9 |
| Median retrieval latency | 424 ms | 477 ms |
| p95 retrieval latency | 920 ms | 938 ms |

28 developer-authored cases: 19 supported, nine abstention. Expected references
identify printed numeric starts or original notification identifiers. They are
not legal approvals. This set was used during implementation and is not held out.
An initial run missed the abduction example because a generic `force` keyword was
incorrectly routed to commencement. The routing fix distinguishes coming into
force from use of force; the table reports the subsequent regression run.
No model-provider call is included in these scores or timings. Broader relevance,
legal correctness and legal currentness were not measured. The modest ranking
gain does not establish that hybrid is better for every question.

Coverage: 555 unapproved selections on 194 physical source pages, from six
unchanged original PDFs/processed records accounting for 404 pages overall.
BNS 204 selections, BNSS 259, BSA 89, plus three commencement paragraphs.
152 Act pages fail the unchanged hard QA gates. Other passages may be omitted
because single-page boundaries cannot safely be bounded by the heuristic.
Three rendered Act pages were visually spot-checked by the agent. All remaining
selections lack a new visual comparison; no human approval was created.

Verification completed:

- Full backend suite: **275 passed**, one existing Starlette/HTTPX deprecation warning.
- Disposable public-only export: **275 passed**, same warning, with no real corpus.
- Frontend ESLint, TypeScript and Vite production build: PASS.
- Provider test guard: **3 Node tests passed**, preventing accidental paid E2E calls.
- Normal hybrid browser flow with synthetic speech: **14 checks**, five source bindings.
- Browser flow with speech APIs absent: **12 checks**, five source bindings.
- Explicit mocked-Groq browser flow: **16 checks**, five source bindings; includes
  rate-limit retry, no duplicate user turn, cancellation and late-response guard.
- Runtime ZIP: **54 explicit public files**; CRC/hash validation PASS. Disposable
  artifact health/readiness/chat smoke PASS; no corpus gives INSUFFICIENT_EVIDENCE.
- Before/after preservation: **129 protected files unchanged**, including six PDFs,
  six processed records, V1 archive, original packets and published evidence files.
- V1 and V2 source/binding verification and both audit chains: PASS; zero real
  submissions, events, approvals and allowlist entries. Original proposals remain
  PROPOSED / NOT SUBMITTED / NOT APPROVED.
- Publication checks: no new credentials, personal absolute paths, corpus files,
  private archive, review store, environment, model weights or private index in
  proposed commit paths. Historical author/path metadata remains in Git history.

The first test invocation hit Windows default temp-directory permissions; tests
passed with explicit workspace basetemp. The first public export test invocation
needed its absent backend/data parent created for basetemp. These were verification
setup errors, not hidden application passes. FAISS imports emit upstream SWIG
deprecation warnings when exercised; missing-model fallback now checks the path
before importing the optional stack. No TLS validation was disabled.
The repeated mocked browser run also exposed shared retry-test state in its test
server. A unique per-run request now receives its own initial 429 and successful
retry, keeping that test repeatable without weakening its assertions.

Live Groq remains **NOT VERIFIED**: key/model absent. Provider success/failure
paths are mocked only. Native microphone permission, spoken transcription and
audible TTS quality require manual browser testing. No telephony is implemented.

Deployment source preparation is finished; actual deployment is **NOT PERFORMED**.
A public clone/artifact intentionally has no real corpus. Expanded source text or
derived indexes need separate publication approval before hosting. Free-tier ML
memory capacity is unverified. Shared demo access protection is not a substitute
for production per-user authentication, shared quotas or provider spending caps.

See [reproduction commands and deployment boundary](completion-sprint.md) and
[machine-readable aggregate metrics](completion-sprint-results.json).
