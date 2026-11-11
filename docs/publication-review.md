# Public corpus publication dossier

Review date: 2026-11-12. **READY_FOR_HUMAN_PUBLICATION_REVIEW** is a handoff,
not permission to publish. No real publication signature, reviewer identity,
legal-evidence approval, push or deployment was created. Rights and source
limitations still block release. This document concerns the exact local candidate,
not a general licence for Indian government documents.

## A. Source-specific rights matrix

| Source | Issuer / publication | Proposed selections | Recommendation |
| --- | --- | ---: | --- |
| BNS, Act 45/2023 | Law and Justice, Legislative Department / 2023-12-25 | 204 | REQUIRES_LEGAL_REVIEW |
| BNSS, Act 46/2023 | Law and Justice, Legislative Department / 2023-12-25 | 259 | REQUIRES_LEGAL_REVIEW |
| BSA, Act 47/2023 | Law and Justice, Legislative Department / 2023-12-25 | 89 | REQUIRES_LEGAL_REVIEW |
| BNS, S.O. 850(E) | Home Affairs / Gazette publication 2024-02-24 | 1 | ELIGIBLE_FOR_HUMAN_APPROVAL |
| BNSS, S.O. 848(E) | Home Affairs / Gazette publication 2024-02-24 | 1 | ELIGIBLE_FOR_HUMAN_APPROVAL |
| BSA, S.O. 849(E) | Home Affairs / Gazette publication 2024-02-24 | 1 | ELIGIBLE_FOR_HUMAN_APPROVAL |

Notification headings are dated 2024-02-23; publication is a different date.
ELIGIBLE means sufficiently identified for a human publication decision, subject
to the questions below. It does not mean licensed, approved, legally current or
visually approved evidence. None is presently authorized for public release.
No entire source is categorically excluded on an established rights prohibition;
the operator may exclude any source, and must exclude it if rights cannot be
established. Excluded content must not be delivered to the runtime.

[The machine-readable matrix](publication-review.json) gives each official title,
authority, exact source URL, original SHA-256, identifier, date, individual counts,
statutory route, conditions, commercial/web/cache/download uncertainty and evidence.

## B. Primary evidence and its limits

All access dates below are 2026-11-12. Local research used certificate-verifying
truststore/HTTPX, trust_env=False, bounded timeouts and official hosts. Browser
research failures are not treated as contrary legal evidence.

- [Copyright Office, Chapter XI](https://copyright.gov.in/Copyright_Act_1957/chapter_xi.html):
  directly read with TLS, HTTP 200; SHA-256
  `94c8cdc5633c50cfb1e56e4b8e5b7ead3aed18a4d23d5e293063e654f4522cbd`.
  Section 52(1)(q)(i) concerns Gazette matter excluding Acts. Subclause (ii)
  concerns Acts with accompanying commentary or other original matter. These are
  distinct statutory exceptions, not an open licence or a public-domain finding.
- [Official Copyright Act PDF](https://copyright.gov.in/Documents/Notification/Copyright_Act_1957.pdf):
  HTTP 200, 1,730,543 bytes, SHA-256
  `ac3ec4fd5e04cb4cb87cc10e2568f027c1dd9ede572dccf617a34fb1f6feb8c9`.
  Physical page 25 contains those two reproduction/publication clauses. This is
  historical Gazette text, not a verified-current consolidation: other wording
  and institutions in this scan are visibly historical. Do not rely on it alone
  for the present complete statute or copyright term.
- [Copyright Office handbook](https://copyright.gov.in/documents/handbook.html):
  HTTP 200; SHA-256
  `a3b044fc32fb58011c5d59bd0a76236f8ca1dac40135fa89cd2018db0461f935`.
  It explains government work and government first ownership absent contrary
  agreement, and directs readers to the Act and Rules. Sections 2(k), 17(d), 28
  and the economic rights in section 14 must be considered alongside section 52;
  government authorship does not imply no copyright. The handbook is guidance,
  not a licence or assurance of complete current law.
- [eGazette About Us](https://egazette.gov.in/Aboutus.aspx): HTTP 200;
  SHA-256 `8621ee690f41c6546c5ce79091d49f49838e991986e21e646f9bfd8f3bed938a`.
  It describes free public access alongside Controller copyright and an
  infringement warning. Its use of public-access language is not treated as a
  copyright dedication. No blanket reuse permission was established. The homepage
  links About Us; no separate applicable reuse policy was established. A guessed
  WebsitePolicy.aspx returned 500 and is not cited as an existing policy.
- [India Code migration notice](https://www.indiacode.nic.in/) was read and points
  to [indiacode.gov.in](https://indiacode.gov.in/), which returned 200. The old
  Copyright Act bitstreams timed out. No India Code reuse licence was established;
  another portal's terms would not automatically govern our eGazette bytes.

The three notification PDFs are Gazette matter other than Acts; the Act-specific
original-matter condition cannot simply be imported into their statutory route.
For each Act, accompanying editorial notes are present, but their adequacy, the
meaning of reproduction together with original matter, and the actual distribution
arrangement require legal review. Notes alone do not prove compliance. No third-party
publisher's edition, annotation or copyright policy was used as clearance.

## C–D. Inventory and exact artifacts

Candidate-v2 remains unchanged: 555 selections / 194 contexts / six sources;
ZIP 378,552 bytes, SHA-256
`5ca56186069798608b85413d85aa288bd32d59a1d3e7c2ab591f5d4fcdb58ed0`.

Candidate-v3 is justified by source-level delivery: the same unaltered selections,
public passage IDs and contexts are split into six source files, with a manifest
and NOTICE. No source text was repaired or newly approved. New manifest schema 2
supports exclusions before any source bytes are loaded by production.

- Local directory: `backend/data/public-corpus/candidate-v3/` (ignored).
- ZIP: 377,414 bytes; unpacked total: 1,534,660 bytes.
- ZIP SHA-256: `a6ae506e1d388da35f0a66400399728f3903016c5fdc8498a00c2c698b8556ba`.
- Manifest SHA-256: `b3adbfb0230fa86aac586604be73b91ebcb7a3f9d91ec65082aa6a1f6c1ba740`.
- [Exact proposed manifest](publication-candidate-manifest.json) and
  [metadata inventory](publication-review.json) contain every file's SHA-256/size.
  They contain no source text and grant no approval. A disposable regeneration
  matched every file and the complete ZIP byte-for-byte.

## E. Text/context quality and quarantine

All six raw and processed hashes match Stage 2E. All 404 pages were re-extracted
and compared with processed records. All 194 context texts, 555 exact line ranges,
page IDs and text hashes match. Same-engine equality is not visual correctness.

The new deterministic checker quarantines incomplete terminal sentences,
unbalanced passage parentheses, extra numeric starts, following unselected
provisos/subsections and hard-excluded pages. **Zero** of the 555 triggered these
specific rules. All are mechanically inspectable; **zero** are release-usable
without authorization. This does not prove that all substantive qualifications
or external references are present. Attribution remains document-only and printed
numbers remain unverified. New flagged inputs are excluded by the sharder, never
silently corrected. Raw, processed and candidate-v2 bytes are immutable inputs.

Existing context warnings remain: sorted reading order differs (194 pages),
repeated-line candidate (191), delimiter candidate (191), page continuation (129),
within-page repetition (34), unusual whitespace (4). These page-wide warnings
are not silently cleared by a passing selected-span check. Full context may
include detached marginal headings or an adjacent incomplete provision; it must
not be quoted as a verified complete provision. Original hard exclusions retain
152 pages outside the private selection pool.

Agent visual sampling inspected **12 selected passages on 12 rendered pages**:
first, middle (floor n/2), last selection in page/line order for each Act, and every
notification operative paragraph. BNS: pages 8/53/99 (printed starts 4/185/354);
BNSS: 4/83/154 (4/253/516); BSA: 6/33/44 (7/110/167); notifications: page 2 each.
Selected wording, illustrations and qualifiers had no observed omissions in this
sample. Bold/italic styles and spatial layout are not retained in normalized text.
The remaining **543 selections are not visually certified**. These are agent
observations, not human approval or audit events. Page-wide contexts have not
received exhaustive visual review.

Notification checks preserve the complete English operative paragraphs:
BNS page 2 lines 8–11 excludes the provision in section 106(2); BNSS page 2
lines 8–11 excludes the First Schedule entry relating to that provision; BSA
page 2 lines 8–10 contains no corresponding exception. Each names 1 July 2024
in the original paragraph. Neither those paragraphs nor Act text prove the
present commencement position. Later instruments remain unresolved.

## F–G. Hosting, privacy and exclusions

Full original PDFs, Hindi glyph mappings, signature images, tables/forms,
uncertain marginal associations, cross-page joins and unselected text are not
proposed as selected evidence. Full English page contexts can include official
names/addresses and detached text: reviewers must consider those too. No user
conversations or private personal metadata were found in the candidate. Metadata
scanning is not a guarantee against all possible disclosure.

Raw PDFs, private processed records, QA/audit archives, V1/V2 catalogue/candidate
identifiers, private indexes/models, workstation paths, access tokens and provider
credentials are excluded from candidate/runtime artifacts. The deployment code ZIP
contains **no corpus at all**. A public manifest discloses original-source hashes
and file inventory, including excluded-source identity metadata, but no excluded
source text. It must not be confused with the private evidence catalogue.

The statutory route is not an automatic licence for commercial use, persistent
caching, hosting or downloadable redistribution. None of those uses has been
separately cleared against all applicable website/contract conditions. Keep the
ZIP local; no public download endpoint exists. If the reviewer cannot establish
the intended use's legal basis, exclude that source or seek permission. This
dossier offers no legal opinion and makes no claim that no other conditions exist.

## H–I. Disclaimers and authorization

Show archival/unreviewed status, source title/authority, original URL/hash,
physical page/lines, edition and source-specific commentary with citations.
Warn that amendments, currentness, commencement changes and applicability are
unknown; excerpts are not legal advice, a consolidated edition or comprehensive
coverage. The frontend already renders these fields; public browser checks use
synthetic data only.

[PublicationDecision schema](publication-decision.schema.json) specifies a
separate publication-only receipt. Schema 2 requires a signature, signer key ID,
exact manifest hash, identified reviewer/time/rationale, rights/safety attestations
and a unique include/exclude/revoke decision binding every source's raw PDF and
shard hash. No real receipt or approval credential was created.

Ed25519 verification uses an independently configured raw public key. Receipt
signatures cover `DOMAIN + canonical(validated_record_without_signature)`:
DOMAIN is ASCII `better-call-kanoon:publication-decision:v2` followed by one NUL;
canonical JSON is UTF-8, sorted keys, compact separators, no NaN, normalized UTC
timestamp as `Z` (use the Pydantic model's JSON representation). Signature is 128
lowercase hexadecimal characters; signer_key_id is SHA-256 of the 32-byte public
key. The runtime contains verification only, not signing or key generation.
The reviewer retains their own existing private key outside this repository;
do not generate or delegate a reviewer credential through this application.
Cryptographic identity authentication is not proof of rights or legal accuracy.

## J. Human decision checklist

1. Open each original linked PDF and check its title, identifier, exact local
   hash, publication date and intended edition. Do not infer currentness.
2. Review each matrix row and the actual statutory/portal evidence. Resolve
   commentary sufficiency and intended hosting/cache/commercial/download use;
   seek legal review or permission where necessary.
3. Inspect selected text and full context, all QA warnings, omissions,
   illustrations, exceptions and unresolved page associations. Exclude a source
   if any proposed payload is unacceptable; do not edit this pinned candidate.
4. Review exact manifest/file hashes and privacy exclusions. Keep attribution,
   commentary and limitations. A changed payload requires a new candidate.
5. Only an explicitly authorized human may produce an external signed receipt
   using their own credential, with substantive reasons for every source.
   Provision its exact SHA-256 and the trusted public key independently through
   deployment configuration. No unsigned template is deployable approval.
6. Verify the local authorized subset using the delivery command below, inspect
   its exact inventory and citations, then request separate deployment approval.
   Do not copy the full candidate when any source is excluded.

## K. Revocation and controlled rollback

Remove/replace the live receipt to fail closed on the next validation; research,
citations and readiness recheck hashes. For a source-level change, the human
issues a new signed decision marking it revoke/exclude, explicitly includes any
remaining sources, independently updates the trusted latest receipt pin, builds
a NEW delivery directory, and restarts with that directory. Excluded source files
must be absent. The old running configuration fails closed when its receipt bytes
change; it cannot silently accept a newer receipt under an older pin.

A controlled rollback similarly requires explicit authorization for the old
candidate, a new reviewed receipt/latest pin, and a new delivery directory. Do not
restore obsolete approval pins automatically. The independently administered
latest receipt hash is the anti-rollback anchor; this is not a global revocation
registry, WORM ledger or defence against an administrator deliberately reverting
both configuration and files. Disabling the service and purging hosted/CDN copies
would require a separately approved operational action. No deployment exists now.

Publication receipts never write to the legal-evidence ledger. Both V1/V2 chains
remain PASS with zero submissions/events/approvals/allowlist entries. Neither the
555 private selections nor any real review decision was changed.

## L. Outstanding questions / acceptance criteria

Legal review must resolve the complete current statutory position, applicable
portal conditions, commentary sufficiency, persistent hosting/cache/download and
commercial-use obligations. Human visual review remains incomplete. Groq key and
model are absent; live inference is unverified. Real microphone/synthesis hardware
checks remain manual. Local Windows footprint is not Render/Linux certification.

Release requires source-specific signed human publication authorization,
independently provisioned trust anchors, an exact delivered subset, clean target
environment checks, live-provider verification if enabled, privacy review and
separate deployment approval. No public corpus release is authorized by this work.

See [deployment and manual verification](public-corpus-deployment.md) and
[measured release results](publication-release-results.json).
