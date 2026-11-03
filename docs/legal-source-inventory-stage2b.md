# Better Call Kanoon: Stage 2B official-source inventory

Research checked **26 October 2026, Asia/Kolkata**. This is a source-discovery
record and an acquisition proposal, not a statement that these texts are current
for every provision, State, date, or proceeding. No legal PDF was saved to the
workspace, downloaded by a shell command, hashed, or ingested. Remote web views
and official search-index text were used for research only. Application code,
the approved ingestion implementation, and the frontend were not changed.

## Verification vocabulary

- **R — remotely inspected:** the research viewer returned the official-hosted
  document text. The identified facts were observed in that text. This does not
  verify a future local file's bytes, digital signature, completeness, or currency.
- **I — official indexed evidence:** indexed text from an official URL corroborates
  the stated fact, but the live URL failed through the research viewer. The exact
  future file remains **unverified** until recovered and checked.
- **U — unresolved:** the evidence does not establish the particular claim.
  A discovered URL is not proof of its contents. No status is inferred from a
  filename, government-looking hostname, search-result publication age, or absence
  of search results.

Every proposed manifest entry remains `verification_claim: "unverified"`.
No local legal-document retrieval date or SHA-256 is available: both are `null`.
The research check date above is deliberately separate from file acquisition.

## 1. Original enactment publications: proposed primary corpus

The Act identity and dates below are corroborated by the Gazette headers indexed
at the linked MHA copies and by the India Code Act texts in section 2. The issuing
publication authority is the **Ministry of Law and Justice, Legislative
Department**; the enacting legislature is **Parliament of India**. MHA is the
administering ministry, not the legislature or original Gazette publisher.

| ID | Official title / Act number | Assent/enactment date | Gazette publication date and identity | Direct primary URL | Status |
| --- | --- | --- | --- | --- | --- |
| G-BNS | The Bharatiya Nyaya Sanhita, 2023 — **45 of 2023** | 2023-12-25 | 2023-12-25; Part II, Section 1; No. 53; CG-DL-E-25122023-250883 | [Original Gazette PDF](https://egazette.gov.in/WriteReadData/2023/250883.pdf) | **I**: official indexed header available; live fetch returned 502. |
| G-BNSS | The Bharatiya Nagarik Suraksha Sanhita, 2023 — **46 of 2023** | 2023-12-25 | 2023-12-25; Part II, Section 1; No. 54; CG-DL-E-25122023-250884 | [Original Gazette PDF](https://egazette.gov.in/WriteReadData/2023/250884.pdf) | Identity/date **I**, direct-file contents **U**: live fetch timed out. |
| G-BSA | The Bharatiya Sakshya Adhiniyam, 2023 — **47 of 2023** | 2023-12-25 | 2023-12-25; Part II, Section 1; No. 55; CG-DL-E-25122023-250882 | [Original Gazette PDF](https://egazette.gov.in/WriteReadData/2023/250882.pdf) | **I**: official indexed header available; live fetch returned 502. |

Evidence: each original Gazette header identifies the Act, its number, the
Legislative Department, and presidential assent/publication on 25 December 2023.
These are **original enactment publications**, not claims of consolidation through
2026. All subsequent changes, corrections, and commencement instruments must be
handled separately.

Official MHA counterparts discovered in the index, with the same Gazette headers:

| Reference | Official URL | Evidence location / access result |
| --- | --- | --- |
| M-BNS | [MHA original BNS copy](https://www.mha.gov.in/sites/default/files/250883_english_01042024.pdf) | Opening Gazette header: 45 of 2023, 25 December 2023, Gazette 250883; **I**, live 404. |
| M-BNSS | [MHA original BNSS copy](https://www.mha.gov.in/sites/default/files/250884_2_english_01042024.pdf) | Opening Gazette header: 46 of 2023, 25 December 2023, Gazette 250884; **I**, live 404. |
| M-BSA | [MHA original BSA copy](https://www.mha.gov.in/sites/default/files/250882_english_01042024.pdf) | Opening Gazette header: 47 of 2023, 25 December 2023, Gazette 250882; **I**, live 404. |

The G-BNSS and N-BNSS e-Gazette links were also discovered as explicit official
outbound links in a third-party Gazette index. That index was a **link-discovery
aid only**: it is not accepted as legal verification evidence. The corresponding
Act/notification facts above and below are corroborated with official material.

## 2. India Code reference copies: distinguish edition from original text

| ID | Direct official document URL | Remotely observed evidence | Version/currentness status |
| --- | --- | --- | --- |
| IC-BNS | [India Code BNS PDF](https://www.indiacode.nic.in/indiacode/bitstream/123456789/20062/1/a202345.pdf) | **R**: 112 PDF pages. Cover identifies Act 45 and an edition date of **6 October 2025**. Act heading and section 1 commencement footnote are on physical PDF page 16. | Official dated reference/reprint, **not** the original Gazette artifact. Currentness after 2025-10-06 **U**. The cover date alone does not establish an exhaustive amendment trail. |
| IC-BNSS | [India Code BNSS PDF](https://www.indiacode.nic.in/indiacode/bitstream/123456789/20335/1/a2023-46.pdf) | **R**: 279 PDF pages. Physical page 16 identifies Act 46, its date, section 1 extent, and the commencement footnote. No `As on` label was found in the searchable text. | Editorial/reference copy with a post-enactment commencement footnote; not the original Gazette artifact. Revision cutoff and parent catalogue record/jurisdiction **U**. Do not assign the other PDFs' 2025 cutoff to this copy. |
| IC-BSA | [India Code BSA PDF](https://www.indiacode.nic.in/indiacode/bitstream/123456789/20063/1/aa202347.pdf) | **R**: 54 PDF pages. Cover identifies Act 47 and an edition date of **6 October 2025**. Act heading and commencement footnote are on physical page 10. | Official dated reference/reprint, **not** the original Gazette artifact. Currentness after 2025-10-06 **U**; complete amendment incorporation is not established by the label. |

Catalogue discoveries, whose live pages timed out during research:

- [Central BNS candidate catalogue record](https://www.indiacode.nic.in/indiacode/handle/123456789/20062?view_type=browse).
- [BNSS catalogue record](https://www.indiacode.nic.in/indiacode/handle/123456789/20099?view_type=browse): indexed details list Act 46, 2023-12-25, MHA/Internal Security, and an enforcement date of 1 July 2024. That catalogue-wide date must not erase the notification's exception.
- [BSA catalogue record](https://www.indiacode.nic.in/indiacode/handle/123456789/20063?col=123456789%2F1362&view_type=search): indexed details corroborate Act 47, 2023-12-25 and the administering ministry.

Do not substitute similarly named State catalogue records or third-party
`indiacode.ecourtsindia.com` pages for a checked central official source.
The superficially plausible BNS URL ending in
`/bitstream/123456789/20062/1/a2023-45.pdf` returned an India Code error page;
the inspected reference copy is the distinct **`a202345.pdf`** URL linked above.

## 3. Commencement notifications and provision-specific qualifications

These are **commencement instruments**, not amendment Acts. All three are MHA
notifications dated **23 February 2024**, under F. No. 1/3/2023-Judicial Cell-I.
The Gazette issue date is **24 February 2024**, distinct from the notification date.
Their printed English instrument heading is `NOTIFICATION`; the labels below
identify them by notification number rather than inventing a formal long title.

| ID | Notification / statutory power | Appointed date and exact scope qualification | Official Gazette URL | Supporting official evidence and status |
| --- | --- | --- | --- | --- |
| N-BNS | **S.O. 850(E)**, 2024-02-23; BNS section 1(2) | 2024-07-01, **excluding BNS section 106(2)**. This proves what that notification appointed; later commencement of the exclusion remains **U**. | [Gazette 252353](https://egazette.gov.in/WriteReadData/2024/252353.pdf); No. 811; CG-DL-E-24022024-252353 | **I**: indexed official Gazette cover and [MHA operative text](https://www.mha.gov.in/sites/default/files/BhartiyaNyayaSanhita_24022024.pdf); also IC-BNS page 16 footnote. Gazette live timeout; MHA live 404. |
| N-BNSS | **S.O. 848(E)**, 2024-02-23; BNSS section 1(3) | 2024-07-01, **excluding the First Schedule entry relating to BNS section 106(2)**. This is **not** an exclusion of BNSS section 106(2). Later changes remain **U**. | [Gazette 252354](https://egazette.gov.in/WriteReadData/2024/252354.pdf); No. 809; CG-DL-E-24022024-252354 | **I**: [MHA operative text](https://www.mha.gov.in/sites/default/files/BharatiyaNagarikSurakshaSanhita_24022024.pdf), IC-BNSS page 16 footnote, and the official government reproduction noted below. Gazette live 502; MHA live 404. |
| N-BSA | **S.O. 849(E)**, 2024-02-23; BSA section 1(3) | 2024-07-01, **no provision-specific exclusion stated in this notification**. This does not decide the Act's application to every proceeding. | [Gazette 252352](https://egazette.gov.in/WriteReadData/2024/252352.pdf); No. 810; CG-DL-E-24022024-252352 | **I**: indexed official Gazette cover and [MHA operative text](https://www.mha.gov.in/sites/default/files/BharatiyaSakshyaAdhiniyam_24022024.pdf); also IC-BSA page 10 footnote. Gazette live 502; MHA live 404. |

Additional official corroboration for N-BNSS's publication identity/date:
[Kerala Forest Department government reproduction](https://forest.kerala.gov.in/forestapp/public/documents/announcements/announcement3101202609%3A13%3A21.pdf).
Its indexed Gazette cover states No. 809, CG-DL-E-24022024-252354, publication
24 February 2024 and notification 23 February 2024. This is a supporting scanned
reproduction, **not a byte-verified substitute** for the original e-Gazette PDF.

Further cross-check: [MHA report indexed at this official URL](https://www.mha.gov.in/sites/default/files/AREnglish_24032026.pdf),
paragraphs **11.38–11.39**, repeats the enactment date and both commencement
exceptions. It returned 404 live; treat this as **I**, not as proof that nothing
changed subsequently or as a substitute for the notification.

## 4. Applicability and transition are not the same as commencement

These review points come from the inspected India Code copies, not from mappings
between old/new codes:

- **BNS:** inspect section **358**, physical PDF page 110, for repeal/savings.
- **BNSS:** inspect section **1(2)**, page 16, for Nagaland/defined tribal-area
  qualifications and the Chapters IX, XI and XII exception; local extension
  notifications require separate verification. Inspect section **531**, page 172,
  for savings affecting pending matters.
- **BSA:** inspect section **1(2)**, page 10, for application exclusions, including
  affidavits and arbitration; inspect section **170**, page 51, for pending-matter
  savings.

These are review pointers, not a case-specific applicability determination.
All proposed `legal_applicability` fields remain `null`. No automatic IPC→BNS,
CrPC→BNSS, or Evidence Act→BSA provision mapping is asserted.

## 5. Amendments and unresolved currentness

**No complete, verified amendment register through 2026-10-26 was established.**
No positive claim is made that any Act is unamended. In particular, the absence
of an amendment found by this bounded web search is not evidence of its absence.
The dated BNS/BSA reference covers leave a material post-2025-10-06 gap; the BNSS
copy has an unknown revision cutoff. State changes, corrigenda, commencement
changes, court orders, and rules/notifications can require additional checks.

Relevant amendment-related records found, **excluded from the binding corpus**:

| Record | Observed evidence | Verification consequence |
| --- | --- | --- |
| [BNS (Amendment) Bill, 2026](https://sansad.in/getFile/BillsTexts/RSBillTexts/Asintroduced/8e3192026103107AM.pdf?source=legislation) | **R**: cover says introduced in Rajya Sabha on 13 March 2026; Bill No. I of 2026. | Verified as an introduced Bill artifact, **not** verified as an enacted amendment. Later passage, assent, Act number and commencement **U**. The clause beginning with the proposed Act name is not proof of enactment. |
| [BNSS (Amendment) Bill, 2025](https://sansad.in/getFile/BillsTexts/RSBillTexts/Asintroduced/421211202550452PM.pdf?source=legislation) | **R**: cover says introduced in Rajya Sabha on 5 December 2025; Bill No. XXXVII of 2025. | Introduced Bill artifact only; later enactment/commencement **U**. Do not merge its proposed provisions into BNSS. |
| [Tamil Nadu Gazette, 10 January 2025](https://www.stationeryprinting.tn.gov.in/extraordinary/2025/21_Ex_IV_1_E_2025.pdf) | **R**: Part IV, Section 1, explicitly **Bills**; L.A. Bill No. 2 of 2025 proposes changes to BNS and BNSS in Tamil Nadu. | State amendment watch item only. This artifact does not prove assent, a final State Act, or commencement; later status **U**. Do not present the proposal as applicable law. |

Current official [MHA Acts](https://www.mha.gov.in/acts-rules) and
[MHA Notifications](https://www.mha.gov.in/notifications) indexes were reachable,
but their visible first pages were not exhaustive registers. Their website
update dates do **not** certify currentness of an individual Act. A manual
Gazette/Legislative Department/Parliament follow-up is required before calling
any edition current through the research date. A search hit mentioning BNS/BSA
inside another Act is not proof that it amends them.

## 6. Proposed metadata manifest

[proposed-legal-source-manifest-stage2b.json](proposed-legal-source-manifest-stage2b.json)
contains **six proposed entries**: the three original Gazette Acts and the three
commencement notifications. It uses the existing Stage 2A schema unchanged.

- The relative `file_path` values are proposed names; those PDFs do not exist here.
- `retrieval_date` and `expected_sha256` remain `null` pending actual acquisition.
- Act numbers, notification numbers/dates, qualifications and evidence URLs live
  in provenance text because Stage 2A has no separate structured fields for them.
- `effective_date` stays `null` for BNS/BNSS and their notifications to avoid
  flattening qualified commencement into an all-provisions claim. Notes record
  the qualified appointed date. BSA records 2024-07-01 with the scope caveats.
- `amendment_version` describes a proposed original artifact, not a currentness
  certification. `legal_applicability` stays `null` throughout.
- Notification language is `mul` for the indexed Hindi/English instrument; confirm
  the complete file at acquisition. Act body language is `en`.
- The schema accepts only a user-supplied verification claim. Keep it `unverified`
  now. Even after manual review, Stage 2A would preserve a `user_claimed_verified`
  claim separately and still output `not_independently_verified`. A research
  observation is not an independent-verification subsystem or a signature check.

**Schema validation alone does not check URLs, legal facts, source availability,
or local bytes. Do not invoke ingestion against this proposal in Stage 2B.**

## 7. Acquisition plan — requires the next approval

Acquire **G-BNS, G-BNSS, G-BSA, N-BNS, N-BNSS and N-BSA** from their actual official
Gazette records after resolving the access failures. Keep each original file
unchanged and separate. If an official mirror is necessary, record the URL
actually used; do not silently claim the bytes were retrieved from e-Gazette.
Stop if an official file cannot be recovered and identified confidently.

Proposed future source root: `backend/data/legal-sources/`, with the manifest's
`acts/` and `notifications/` relative paths beneath it. At the later approved
step, either place the finalized manifest beside those directories or explicitly
configure that source root in Stage 2A. These paths are a plan only; this stage
does not create source directories or PDF files.

The three IC reference copies can be acquired separately for comparison, with
their actual edition/cutoff limitations recorded. They are not silently substituted
for the six proposed originals and are not included as duplicate primary records
in this manifest. Do not acquire/ingest the introduced amendment Bills as law.

Only after approval, acquisition, hash calculation, and manual review should a
finalized manifest be passed to the existing Stage 2A CLI. Do not run a download
or ingestion command as part of this source-discovery stage.

## 8. Manual verification checklist

1. Open each official record through the publishing portal. Check final redirect
   destination and that the response is the intended PDF, not a portal/error page.
2. Check printed title, Act number, Gazette ID, Part/Section/issue, publishing
   authority, presidential assent date and publication date against section 1.
3. For notifications, compare the cover and English operative text: S.O. number,
   notification date **23 February**, publication date **24 February**, power,
   appointed date, and each provision-specific exception. Do not conflate BNSS's
   First Schedule entry with a BNSS subsection.
4. Resolve the later status of BNS 106(2) and the corresponding schedule entry
   through subsequent official notifications; a 2024 exclusion alone cannot prove
   their status on 26 October 2026.
5. Search official amendment Acts, corrigenda, commencement instruments, and
   jurisdiction-specific amendments through the intended cutoff. For the Bills
   above, require a distinct assented Act publication and applicable commencement
   evidence before considering their proposed changes operative.
6. Check any reference copy's printed edition date and amendment footnotes against
   original instruments. Do not derive currentness from upload dates or file names.
7. Review section 1 extent/application, savings and transition provisions, and any
   relevant State extension/rules or court orders for the intended use. Mark unresolved
   applicability unknown; the three Acts are not complete Indian legal coverage.
8. After download approval only: verify completeness, digital-signature result if
   available, file format, text readability and PDF page boundaries; record the
   actual acquisition date, actual URL, exact SHA-256 and immutable local path.
9. Update the proposed provenance with reviewer identity, precise evidence and
   unresolved points. Never upgrade status on domain matching alone. Preserve
   failed access attempts and distinguish research, acquisition and review dates.
10. Review the finalized manifest before authorizing ingestion. No application
    changes, embeddings, retrieval, AI answers, voice, commit or push belong here.

**Stop point:** inventory and proposed metadata only. Acquisition and ingestion
remain unapproved and have not been performed.
