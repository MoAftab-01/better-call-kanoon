# Publication evidence V2

Sanitized derived report; not byte-identical to the private V1 original. Historical test results/command examples below describe V1 unless explicitly labelled V2. Use the public migration guide for current V2 commands. No human approval or current-law claim is added.

# Stage 2E — legal text QA and retrieval-readiness assessment

**Overall: PARTIAL.** Integrity and deterministic extraction-consistency checks
PASS for six documents / 404 physical pages. **Using this corpus as verified
retrieval evidence is BLOCKED pending approved passage-level review and
legal-status controls.** No retrieval implementation was built.

Raw PDFs and Stage 2D JSON were not modified. Their recorded SHA-256 values,
source read-only attributes and modification times still match Stage 2D.

## Scope and reproducibility

Inputs: approved Stage 2C report/audit, acquired manifest, Stage 2D report/audit,
six original PDFs and six processed JSON records.
The [machine-readable report](legal-text-quality-stage2e.json) records input hashes,
checker/runtime versions, per-document invariants, all 404 per-page findings,
exact normalized line ranges/evidence and distinct visual-review observations.

The standalone [QA command](../backend/qa/legal_text.py) is separate from production
ingestion/API behavior. Its canonical JSON output excludes wall-clock timestamps.
Generation followed by --check produced identical bytes. No network, OCR,
correction, chunking, index, embeddings, RAG or LLM is involved.

| Document | Hash/schema/metadata | Nonempty / pages | Rendered page samples | Readiness |
| --- | --- | ---: | --- | --- |
| BNS act | PASS | 102/102 | 3 scoped samples | **PARTIAL** |
| BNSS act | PASS | 249/249 | 4 scoped samples | **PARTIAL** |
| BSA act | PASS | 47/47 | 4 scoped samples | **PARTIAL** |
| BNS notification | PASS | 2/2 | 2 scoped samples | **PARTIAL** |
| BNSS notification | PASS | 2/2 | 2 scoped samples | **PARTIAL** |
| BSA notification | PASS | 2/2 | 2 scoped samples | **PARTIAL** |

**1,440,219 extracted characters; no empty pages or exact duplicate page texts.**
All source hashes match the Stage 2C audit, Stage 2D audit, acquired manifest and
normalized source_file. All processed hashes match Stage 2D. Metadata equality,
content-derived IDs, page IDs/physical order and section-line coverage pass.

A matching PyMuPDF text layer is only a **same-engine consistency check**. It
does not prove that extracted characters match visible glyphs, preserve reading
order, include graphical form symbols, or express valid/current law.

## Deterministic automatic checks

Each page was checked for text-layer equality, physical ordinal/reference,
section-fragment line coverage, empty text, suspicious Unicode categories,
replacement/control/format characters, mojibake patterns, unusual whitespace,
duplicate pages, repeated lines, page-end continuation, delimiter balance,
margin folio candidates, printed-number observations and schedule/form context.
Alternative sorted extraction was compared without replacing stored text.

No replacement characters, unexpected controls, private/unassigned/surrogate
Unicode, invisible/directional format characters or mojibake pattern matches
were found. This does not establish faithful Hindi or complete extraction.

Findings count physical pages carrying a signal, not proven defects:

- devanagari_mapping_unverified: **6 pages**.
- legacy_hindi_glyph_codes: **3 pages**.
- marginal_citation_association_unverified: **55 pages**.
- possible_page_boundary_continuation: **245 pages**.
- possible_printed_page_order_mismatch: **3 pages**.
- repeated_line_candidate: **395 pages**.
- sorted_extraction_differs: **404 pages**.
- table_or_form_layout_unverified: **94 pages**.
- unbalanced_delimiters_candidate: **400 pages**.
- unusual_whitespace_candidate: **23 pages**.
- within_page_repetition_candidate: **82 pages**.

Interpretation:

- All 404 pages differ under sorted extraction. This demonstrates sensitivity to
  ordering, not that one ordering is correct. Marginal headings/citations and
  page furniture are observed examples.
- Repeated headers, separator lines and legal phrases are expected. No text was
  deleted or deduplicated. The two marginal 1 of 1872 citations on BSA page 45
  are both visible, legitimate occurrences.
- Unbalanced delimiters often reflect Gazette headers such as an open PART II
  bracket, or a continuation across pages. They are not proof of truncated law.
- Page-end continuation signals are heuristic. BNS pages 34–35 demonstrate
  ordinary cross-page provision context. No actual truncation was established.
- Notifications' page-1 folio signals are false positives on visual review:
  (1) is visible; printing/issue numbers confused the heuristic. No page-order
  mismatch was established. Passing page order does not certify textual continuity.
- BNSS pages 158–189 contain the First Schedule table; 190–249 contain Second
  Schedule forms. BSA pages 46–47 contain Schedule certificate forms.
  Their rows/cells/fields are not encoded as reliable structures.

## Automatic versus visual evidence

Exactly **17 physical pages** received scoped agent visual comparison during this
stage. These are not 17 wholly verified pages. The remaining 387 pages received
automatic checks only. Source-hash-bound observations are kept separately in
[the review ledger](../backend/qa/stage2e_visual_review.json), including render
settings, inspected scope, exact extracted evidence and approval limitations.
Images were rendered in memory; no source or processed text was repaired.

| Document | PDF page | Normalized lines sampled | Scope | Visual observation |
| --- | ---: | --- | --- | --- |
| BNS act | 1 | 18–23 | Bilingual Gazette header only; English Act body below crop not visually checked here. | observed_glyph_mismatch: Rendered Hindi words appear as Latin glyph codes in extracted header; bilingual header and Gazette PART II are publication furniture, not a validated Act hierarchy. |
| BNS act | 34 | 33–36 | Printed section 106(2), numbering, and margin citation placement. | sample_matches_with_layout_limitation: Sampled subsection wording matches the rendered body. Marginal headings and 30 of 2019 are positioned beside relevant body text visually but appended separately in extracted reading order. The enacted subsection text alone does not establish commencement. |
| BNS act | 35 | 1–3 | Top continuation and bottom page-boundary continuation only. | context_dependency: Top (2) continues previous physical page; the bottom ends mid-provision. Both are expected page breaks, not demonstrated data truncation. Standalone fragments require adjacent-page/subsection context. |
| BNSS act | 1 | 1–6 | Bilingual Gazette header only; English Act body below crop not visually checked here. | observed_glyph_mismatch: Rendered Hindi words appear as Latin glyph codes in extracted header; bilingual header and Gazette PART II are publication furniture, not a validated Act hierarchy. |
| BNSS act | 158 | 1–27 | Schedule heading/table or form sample only. | layout_limitation: First Schedule heading/explanatory notes and six column headings are visible. Flattened extraction does not preserve tabular geometry; no whole-table verification. |
| BNSS act | 163 | 147–156 | Schedule heading/table or form sample only. | layout_limitation: Printed First Schedule row 106(2) is visible with six columns. Its text is present, but JSON contains no reliable row/cell binding. Keep associated commencement exception from S.O. 848(E); do not assert this entry commenced from the table alone. |
| BNSS act | 190 | 1–5 | Schedule heading/table or form sample only. | layout_limitation: Second Schedule Form No. 1 is visible; spatial blanks/field associations are not represented as a form structure. |
| BSA act | 1 | 17–22 | Bilingual Gazette header only; English Act body below crop not visually checked here. | observed_glyph_mismatch: Rendered Hindi words appear as Latin glyph codes in extracted header; bilingual header and Gazette PART II are publication furniture, not a validated Act hierarchy. |
| BSA act | 45 | 10–15 | Savings/marginal citations or Schedule certificate option fields only. | sample_matches_with_layout_limitation: Section 170 sample and two separate 1 of 1872 marginal citations are visible. Their repetition is legitimate source content; do not deduplicate them or infer a missing footnote. The marginal associations are not encoded. |
| BSA act | 46 | 11–18 | Savings/marginal citations or Schedule certificate option fields only. | observed_layout_omission: Schedule Part A shows square checkboxes beside device/hash options; these graphics are absent from the extracted plain-text option labels. JSON is not a faithful form facsimile; no checkbox text was invented. |
| BSA act | 47 | 11–18 | Savings/marginal citations or Schedule certificate option fields only. | observed_layout_omission: Schedule Part B shows square checkboxes beside device/hash options; these graphics are absent from the extracted plain-text option labels. JSON is not a faithful form facsimile; no checkbox text was invented. |
| BNS notification | 1 | 1–41 | Hindi heading and operative paragraph; Gazette cover and folio. | observed_glyph_mismatch: Rendered Hindi heading/words differ from extracted Devanagari glyph mapping. Folio (1) is visible; automatic margin-number mismatch is a false positive caused by printing/issue numbers, not observed page reordering. |
| BNS notification | 2 | 8–11 | English heading, instrument number/date and complete operative paragraph only. | sample_matches: Compared rendered English paragraph to JSON; appointed date and the instrument-specific exception (where present) are preserved. This verifies the sampled text, not subsequent legal status or the footer/signature. |
| BNSS notification | 1 | 1–41 | Hindi heading and operative paragraph; Gazette cover and folio. | observed_glyph_mismatch: Rendered Hindi heading/words differ from extracted Devanagari glyph mapping. Folio (1) is visible; automatic margin-number mismatch is a false positive caused by printing/issue numbers, not observed page reordering. |
| BNSS notification | 2 | 8–11 | English heading, instrument number/date and complete operative paragraph only. | sample_matches: Compared rendered English paragraph to JSON; appointed date and the instrument-specific exception (where present) are preserved. This verifies the sampled text, not subsequent legal status or the footer/signature. |
| BSA notification | 1 | 1–41 | Hindi heading and operative paragraph; Gazette cover and folio. | observed_glyph_mismatch: Rendered Hindi heading/words differ from extracted Devanagari glyph mapping. Folio (1) is visible; automatic margin-number mismatch is a false positive caused by printing/issue numbers, not observed page reordering. |
| BSA notification | 2 | 8–10 | English heading, instrument number/date and complete operative paragraph only. | sample_matches: Compared rendered English paragraph to JSON; appointed date and the instrument-specific exception (where present) are preserved. This verifies the sampled text, not subsequent legal status or the footer/signature. |

Important findings requiring manual review:

1. **All six PDF page-1 Hindi regions:** Act mastheads use legacy glyph codes
   (for example vlk/kkj.k); notification headings/body contain Devanagari with
   mismatched glyph mapping. Do not present them as verified Hindi evidence.
2. **BNS page 34:** section 106(2) wording was spot-checked. Marginal headings and
   the 30 of 2019 citation are detached in extracted reading order. Review exact
   subsection boundaries before future provision citations.
3. **BNS pages 34–35:** check the continuation context of section 109 and the next
   page's initial (2). Do not label an isolated (2) using a previous guessed ID.
4. **BNSS pages 158–189, especially 163 row 106(2):** text is present, but column
   association is not encoded. A complete row/cell comparison is still required.
5. **BNSS pages 190–249:** forms need field/layout review; page 190 was sampled.
6. **BSA pages 45–47:** preserve marginal citations/savings context. On pages
   46–47, visible checkbox graphics are absent from extracted option labels.
   Plain text is not a faithful certificate-form facsimile.
7. **All notification page-2 operative paragraphs:** positive English spot checks
   must not be expanded to a whole-document, signature or currentness claim.

Additional exact page queues follow. The JSON supplies individual line ranges,
page IDs and original evidence for every signal; heuristic candidates remain
unresolved until compared to the relevant rendered page and adjacent context.

- **BNS act**: marginal citation candidates on PDF pages **3, 5–6, 24, 28, 34, 38, 50, 52, 77, 84, 94–95, 102**; page-end continuation candidates on **1–4, 7, 9, 12–14, 16, 18–19, 22–31, 33–37, 39–41, 43–48, 50, 52–59, 63–64, 66–69, 71–74, 76–77, 82–83, 85, 89–90, 92, 97–98, 100, 102**. Pages without any rendered spot check: **2–33, 36–102**.
- **BNSS act**: marginal citation candidates on PDF pages **3, 18, 20, 25, 27–28, 35, 37–38, 51, 62, 70, 74, 89, 92–93, 100–102, 112, 114, 116–117, 120, 123–126, 134, 138, 155–157**; page-end continuation candidates on **1, 3–4, 6, 9–10, 12–17, 19, 23–26, 28–31, 33, 36–37, 39–40, 43–50, 52, 54–55, 59–61, 63–65, 67–68, 70–72, 74–81, 83–84, 86–87, 89–90, 92, 96–98, 101, 105, 108, 111, 116–117, 119–124, 128–132, 135, 137–139, 141, 143–149, 153, 155–156, 158–168, 170–173, 175, 178–179, 182–186, 190, 194, 199–202, 205, 207–209, 214, 217, 219, 221, 223–225, 231, 233, 235–236, 240–241, 243, 245–246, 248–249**. Pages without any rendered spot check: **2–157, 159–162, 164–189, 191–249**.
- **BSA act**: marginal citation candidates on PDF pages **3–4, 17–18, 24, 28, 31, 45**; page-end continuation candidates on **1, 3–6, 10, 13–14, 16, 21–22, 25–26, 29–30, 32, 34–37, 41, 44, 47**. Pages without any rendered spot check: **2–44**.
- **BNS notification**: marginal citation candidates on PDF pages **none**; page-end continuation candidates on **1–2**. Pages without any rendered spot check: **none**.
- **BNSS notification**: marginal citation candidates on PDF pages **none**; page-end continuation candidates on **1–2**. Pages without any rendered spot check: **none**.
- **BSA notification**: marginal citation candidates on PDF pages **none**; page-end continuation candidates on **1–2**. Pages without any rendered spot check: **none**.

No correction text is proposed or authorized. If corrections are later needed,
record original hash, page/coordinates, original extraction, proposed correction,
reviewer and rationale separately, then request approval before creating a new
derived version. Never edit the raw or Stage 2D files.

## Commencement exceptions

The English operative paragraphs on page 2 of all three notifications match the
acquisition evidence and the sampled rendered images.

- S.O. 850(E): BNS exception for sub-section (2) of section 106 remains intact.
- S.O. 848(E): the exception is the **First Schedule entry relating to BNS
  section 106(2)**, not BNSS section 106(2).
- S.O. 849(E): the sampled paragraph has no provision-specific carve-out.

BNS page 34 contains the enacted subsection; BNSS page 163 contains its Schedule
entry. Presence in an enacted text/table does not establish commencement.
BNS/BNSS scalar effective_date values remain null. Later commencement,
amendments, corrigenda and applicability remain **unverified**. No new legal
sources were downloaded or currentness research represented as complete.

## Citation metadata readiness

**PASS for traceable archival page references**, using the companion catalogue:
document ID, source byte hash, physical PDF page, page ID, source URL, official
title, authority, original-artifact version and provenance limitations exist.
Act/notification identifiers and acquisition details are retained in source
text/provenance and the acquisition/ingestion catalogues.

**PARTIAL for standalone citations:** all notifications have the title NOTIFICATION.
Citations must include the S.O. number/date from the hash-bound catalogue; title
alone is ambiguous. Physical PDF page numbers must be labelled as physical pages
unless printed folios are separately confirmed.

**BLOCKED for verified provision/current-law citations:** legal section/subsection
boundaries are not validated IDs; Chapter/Part labels remain candidates, including
Gazette mastheads. Schedule rows/cells and cross-page associations need approval.
Keep user_supplied / not_independently_verified status visible. A government URL,
hash match or successful parse does not upgrade authenticity or legal currentness.

## Proposed future inclusion/exclusion rules

These are a proposal, not implemented retrieval logic.

- Default-deny promotion to **verified evidence**. Require an explicit approved
  review keyed by raw/processed hashes, document/page IDs and exact passage lines
  or coordinates. Agent spot checks in this report do not constitute user approval.
- Include English passages only after their boundaries, qualifiers, adjacent
  continuation and marginal associations are checked. Pin original edition and
  provenance; describe original artifacts as such.
- Keep Acts, commencement notifications and consolidated editions separate.
  Any commencement statement must carry its operative notification and exception.
- Quarantine all unresolved Hindi/glyph mappings and suspicious Unicode.
- Exclude schedule rows, cell values, form fields and checkbox meanings until
  layout-aware manual comparison establishes their associations.
- Never treat a heuristic heading, bare number or page continuation as a verified
  legal section. Never remove repeated legal phrases automatically.
- Exclude publication furniture, colophons and signature appearances as substantive
  legal evidence. Do not confuse extraction fidelity with signature validation.
- Do not answer current-applicability questions from this corpus alone. Later
  amendments, commencement, State scope, savings and case context need separate
  reviewed evidence. Do not assert BNS 106(2) or the BNSS entry commenced.

All 404 pages currently have verified_evidence_eligible=false; no inclusion
allowlist, chunks or retrieval endpoint has been created.

## Manual QA checklist

- [ ] Run the deterministic report comparison and confirm all six integrity rows.
- [ ] Compare all six first-page Hindi regions; retain exclusions for mismatches.
- [ ] Compare each notification's complete English operative paragraph, dates,
      instrument number and exceptions on page 2.
- [ ] Review BNS 34–35, BNSS 158/163/190 and BSA 45–47 against the listed scopes.
- [ ] Review remaining Schedule tables/forms and all selected page/line signals.
      Preserve true repeated legal text and document false-positive signals.
- [ ] For any future allowed passage, record full subsection/row/context boundaries,
      physical page/coordinates, reviewer approval and source hashes.
- [ ] Keep currentness/applicability/signature limitations explicit; approve no
      repaired text or verified-evidence promotion through this checklist alone.

## Manual Windows PowerShell commands

Read-only deterministic scan (about 15–25 seconds on this machine):

~~~powershell
# Run from the repository root.
& '.\.venv\Scripts\python.exe' -B -m backend.qa.legal_text --check
if ($LASTEXITCODE -ne 0) { throw 'QA report mismatch or validation failure.' }
$qa = Get-Content -LiteralPath '.\docs\legal-text-quality-stage2e.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$qa | Select-Object readiness,verified_evidence_readiness
$qa.documents | Select-Object document,readiness,pdf_pages,nonempty_pages,characters | Format-Table -AutoSize
foreach ($d in $qa.documents) {
    if ((Get-FileHash -LiteralPath $d.raw_path -Algorithm SHA256).Hash -ine $d.raw_sha256) { throw 'Raw hash mismatch.' }
    if ((Get-FileHash -LiteralPath $d.processed_path -Algorithm SHA256).Hash -ine $d.processed_sha256) { throw 'Processed hash mismatch.' }
}
~~~

Exact findings and visual scopes:

~~~powershell
foreach ($d in $qa.documents) {
    foreach ($p in $d.pages) {
        foreach ($f in $p.findings | Where-Object { $_.code -in @('legacy_hindi_glyph_codes','devanagari_mapping_unverified','marginal_citation_association_unverified','table_or_form_layout_unverified') }) {
            [pscustomobject]@{Document=$d.document;PDFPage=$p.pdf_page;StartLine=$f.start_line;EndLine=$f.end_line;Code=$f.code;Evidence=($f.evidence | ConvertTo-Json -Depth 6 -Compress)}
        }
        if ($p.visual_reviews.Count -gt 0) {
            $p.visual_reviews | Select-Object document,pdf_page,scope,status,observation | Format-List
        }
    }
}
# Display the preserved English notification exceptions:
$qa.documents | Where-Object { $_.notification_exception_check } |
    ForEach-Object { $_.notification_exception_check | ConvertTo-Json -Depth 8 }
~~~

Render selected originals to a NEW scratch directory; this writes PNGs only,
without altering sources or processed JSON:

~~~powershell
$reviewDir = Join-Path '.\backend\data\qa\stage2e' ([guid]::NewGuid().ToString('N'))
@'
from pathlib import Path
import json, sys
import pymupdf
folder = Path(sys.argv[1])
folder.mkdir(parents=True, exist_ok=False)
qa = json.loads(Path("docs/legal-text-quality-stage2e.json").read_text(encoding="utf-8"))
selected = {"BNS act": [1, 34, 35], "BNSS act": [1, 158, 163, 190],
            "BSA act": [1, 45, 46, 47], "BNS notification": [1, 2],
            "BNSS notification": [1, 2], "BSA notification": [1, 2]}
for document in qa["documents"]:
    with pymupdf.open(document["raw_path"]) as pdf:
        for number in selected[document["document"]]:
            image = pdf[number - 1].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
            name = document["document"].replace(" ", "-") + "-page-" + str(number) + ".png"
            with (folder / name).open("xb") as target:
                target.write(image.tobytes("png"))
print(folder.resolve())
'@ | & '.\.venv\Scripts\python.exe' -B - $reviewDir
if ($LASTEXITCODE -ne 0) { throw 'Rendering failed.' }
# Open images and compare with the JSON line ranges:
# Invoke-Item -LiteralPath $reviewDir
~~~

Backend tests, using a fresh scratch directory:

~~~powershell
$testScratch = '.\backend\data\test-runs\manual-stage2e-' + [guid]::NewGuid().ToString('N')
& '.\.venv\Scripts\python.exe' -B -m pytest backend/tests -v --basetemp $testScratch -p no:cacheprovider
~~~

## Tests, artifacts and stop point

**101 passed, 0 failed, 0 skipped, 1 warning in 5.09 seconds.**
This includes 17 new QA test cases and the existing 84 backend cases.
The existing Starlette TestClient/HTTPX deprecation warning remains.
Synthetic QA fixtures test corruption signals, repeated headers versus duplicate
pages, page swapping, hash mismatch, section gaps, deterministic checks and
prevention of automatic/foreign-byte visual approval.

Created the two requested reports, backend/qa standalone tooling/review ledger,
and backend/tests/test_legal_text_quality.py. No dependency changes. Production
ingestion/API/frontend, raw PDFs, processed JSON and approved prior reports remain
unchanged. Tests used isolated synthetic temporary data under backend/data/test-runs/.

No new legal downloads, corrections, chunks, index, retrieval, embeddings,
LLM/voice integration, commits or pushes.

**Stage 2E stops here for manual review and approval.**
