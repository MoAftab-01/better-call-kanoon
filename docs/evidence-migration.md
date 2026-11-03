# Publication V2: metadata migration, unchanged legal evidence

V1 is the original approved Stage 2F/2G binding set. Its complete source and report
bytes, six PDFs, six processed records and three proposal packets are retained in
a restricted, read-only local archive. Original identities are not reassigned.
No archived original containing workstation diagnostics is published here.

V2 uses new paths under `docs/evidence/v2/`. Its copied reports replace the audited
workstation directory examples and fourteen ingestion command/output paths with
relative diagnostics. Historical Git diagnostics are omitted from the new Stage
2H summary. Reports identify themselves as derived publication artifacts; they
are not byte-identical to unpublished V1 reports.

The acquired manifest still obeys the strict Stage 2A schema. Official URLs,
document titles/numbers/dates, provenance, PDF/processed hashes, all 404 pages,
QA findings/exclusions, passage text and surrounding context remain unchanged.
The BNS section 106(2) exception remains distinct from the BNSS First Schedule
entry relating to that BNS subsection. The BSA notification has no stated
provision-specific exception. These historical notifications do not establish
current applicability or account for later amendments/commencement.

Only catalogue and QA bindings, and therefore content-derived candidate IDs,
change in paired records. The existing canonical JSON/SHA-256 algorithm is reused.
`migration.json` records both IDs, exact text/context/source hashes, old/new
catalogue digests and the reason. Verification rejects any other candidate-field
change. The V1 preservation manifest records hashes and relationships, not the
private diagnostic values. Hashes alone do not authenticate a publisher or certify
legal correctness.

V2 has a separate review namespace. No V1 event is imported. V2 exposes read-only
verification only: no submit, approval or bulk-promotion operation. No reviewer,
decision time, rationale or attestation is manufactured. Both real histories are
empty, and all three V2 packets say PROPOSED / NOT SUBMITTED / NOT APPROVED.

## Fresh public checkout

After installing the existing requirements, these checks need no private corpus:

```powershell
python -B -m backend.publication metadata
$scratch = '.\backend\data\test-runs\public-' + [guid]::NewGuid().ToString('N').Substring(0,8)
python -B -m pytest backend/tests -q --basetemp $scratch -p no:cacheprovider
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

`metadata` validates public pins, the declared version mapping and proposal
text/boundary hashes. Its output explicitly says source bytes were not verified.
Tests use labelled synthetic fixtures, including any simulated approvals. A
public test badge must not imply real-corpus verification or human legal review.

The public presentation contract is `docs/review-presentation-contract.json`;
it is a test/interface contract, not a substitute historical evidence report.

## Exact source/processed bundle required

Place the separately acquired six original PDFs and six original processed JSONs
at their manifest-recorded paths under ignored `backend/data/`. No automatic
download, ingestion or repinning occurs. Then run:

```powershell
python -B -m backend.publication verify
python -B -m backend.publication list
python -B -m backend.publication history
python -B -m backend.publication allowlist
# Inspect ONE actual V2 ID from docs/evidence/v2/migration.json:
# python -B -m backend.publication preview <V2-candidate-id>
```

Missing or changed corpus bytes return a nonzero result; they are never treated
as an empty successful source verification. Even a successful check is archival
text verification, not legal-currentness certification. The exact processed
bundle is not promised reproducible merely by ingesting the same PDFs again.

V1 replay requires the independent archived V1 workspace, including its original
code, reports and source bundle. Use the unchanged `backend.review` CLI there.
Without that workspace a public clone cannot independently inspect every private
V1 diagnostic byte. It can check the public preservation/mapping consistency.

## Deterministic regeneration and Git review

The existing dependency order remains baseline through Stage 2A, then 2B-2H.
Those public scope snapshots contain source, synthetic tests and explicitly
unbound stage summaries. A separate ninth integration scope introduces V2
bindings, packets, verifier and migration tests together, avoiding incomplete
catalogues whose implementation or input pins are in later commits.

`backend.publication.migrate.build` accepts a preserved V1 workspace, its manifest,
the implementation root and a NEW scratch directory. It never overwrites V1 or an
existing scratch destination. Its returned publication bytes are deterministic;
publication is a separate explicit operation. Full V1-to-V2 regeneration requires
the original archive, and is not claimed as a public-only metadata check.

The byte-preservation attributes retain existing LF/CRLF inputs. Publication uses
an explicit file/hash manifest, excludes legacy reports and all corpus/review data,
and requires staged-blob/export checks with both autocrlf settings in disposable
repositories. Existing reachable history still contains legacy README path and
author-email metadata; this migration does not rewrite that history.
