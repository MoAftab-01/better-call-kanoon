"""Private, explicit candidate preparation. Never publishes or approves anything."""
import json
from pathlib import Path
import re
import zipfile

from .models import Corpus, Manifest, canonical, sha

EXCLUSIONS = ['raw PDFs','private processed records','review events and approval stores',
    'private catalogue hashes and candidate IDs','workstation paths and diagnostic metadata',
    'user conversations','embeddings and private indexes','hard-excluded pages and uncertain cross-page joins']
NOTICE = '''# Better Call AI: candidate archival research corpus

NOT APPROVED FOR PUBLICATION. Preparing this package is not a legal evidence review.
No passage has been promoted to a verified-evidence allowlist. Legal currentness,
subsequent amendments and case-specific applicability remain unknown.

Source: Government of India, official e-Gazette original publications. Individual
source URLs, original PDF SHA-256, titles, issuing authorities and physical-page
references are in corpus.json. Text remains unreviewed archival extraction.
Source identity does not prove visual correctness, legal validity or currentness.

Redistribution assessment: the official Copyright Office publication of the
Copyright Act, 1957, section 52(1)(q)(i), addresses Gazette matter other than Acts.
Subclause (ii) conditions Act reproduction on accompanying commentary or other
original matter. This candidate accompanies each source with original editorial
commentary, delivered alongside every citation. Attribution, this notice and that
commentary must remain with the excerpts. No blanket public-domain or open-license
claim is made, and no third-party commentary or scanned signature is republished.
Editorial commentary alone is not proof that every applicable copyright,
website-use, redistribution or publication condition has been satisfied. This
assessment remains conditional: an identified human must review the applicable
terms, statutory conditions and exact payload before approving publication.

Rights evidence inspected using certificate-verified HTTPS:
https://copyright.gov.in/Documents/Notification/Copyright_Act_1957.pdf
SHA-256 ac3ec4fd5e04cb4cb87cc10e2568f027c1dd9ede572dccf617a34fb1f6feb8c9
This is a conditional statutory-basis assessment, not an independent legal opinion
or proof of the absence of later legal changes. Operator publication review must
confirm the assessment and exact manifest before deployment. A government domain
or free online access alone was not treated as redistribution permission.

Only automatically eligible English single-page selections are proposed. Existing
extraction warnings remain. Hindi mapping, tables/forms, uncertain associations
and incomplete page-boundary qualifications are excluded. Printed numeric starts
are unverified; attribution remains document-only. These excerpts do not replace
the complete original PDFs or qualified legal advice.
'''


def prepare(root, destination):
    # Heavy/private dependencies are preparation-only, never runtime imports.
    from backend.retrieval.engine import ArchivalIndex
    from backend.review.service import validate_candidate, exclusion_reasons, span_text
    root = Path(root).resolve()
    target = Path(destination).absolute()
    from backend.app.ingestion.paths import checked_path
    target = checked_path(target)
    if not target.is_relative_to(checked_path(root/'backend/data/public-corpus')):
        raise ValueError('Candidates must stay under ignored backend/data/public-corpus')
    if target.exists() or target.with_suffix('.zip').exists():
        raise ValueError('Refusing existing candidate destination')
    index = ArchivalIndex(root,retrieval_mode='bm25')
    if not index.catalog or len(index.passages)!=555:
        raise ValueError('Expected complete 555-selection private source bundle')
    sources,pages,passages = {},{},[]
    for hit in index.passages:
        c = hit.candidate
        item,doc = validate_candidate(index.catalog,c)
        if exclusion_reasons(item,c) or span_text(doc,c.spans[0])!=hit.text:
            raise ValueError('Source selection failed existing review gates')
        s = c.spans[0]
        identifier = 'doc_'+c.raw_sha256
        page_id = f'{identifier}:page:{s.physical_page:06d}'
        original = c.original_identifiers
        title = str(original.get('official_title') or c.source_metadata.official_title)
        count = sum(p.candidate.document_id==c.document_id for p in index.passages)
        commentary = (f'Editorial archival note for {hit.instrument}: this collection selects {count} '
            f'single-page English passages from the original publication of {title}. '
            'The numeric starts and page context are extraction references, not verified provision '
            'attribution. Marginal-heading order, omitted pages and external cross-references limit '
            'interpretation. This collection is not a consolidated or amended edition and does not '
            'establish present legal applicability. Consult the linked original and later official instruments.')
        if c.source_metadata.instrument_type=='notification':
            commentary += (' The operative paragraph is reproduced in full; read its exception exactly as written. '
                'The BNS provision exception and BNSS First Schedule entry exception are different subjects.')
        sources[identifier] = dict(document_id=identifier,title=title,instrument=hit.instrument,
            kind=c.source_metadata.instrument_type,source_url=c.source_metadata.source_url,
            raw_sha256=c.raw_sha256,issuing_authority=c.source_metadata.issuing_authority,
            publication_date=str(c.source_metadata.publication_date),physical_pages=len(doc.pages),
            edition=str(original['version']),commentary=commentary,
            provenance='official_gazette_identity_checked_at_preparation',legal_currentness='unknown')
        page = doc.pages[s.physical_page-1]
        qa = item['pages'][s.physical_page-1]
        pages[page_id] = dict(document_id=identifier,page_id=page_id,physical_page=s.physical_page,
            text=page.text,text_sha256=sha(page.text.encode()),
            qa_flags=sorted({f['code'] for f in qa['findings']}),automatic_checks_passed=all(qa['automatic_checks'].values()))
        entry = dict(document_id=identifier,page_id=page_id,start_line=s.start_line,end_line=s.end_line,
            text=hit.text,text_sha256=s.text_sha256,printed_number_unverified=hit.printed_number,
            attribution='document_only',evidence_status='ARCHIVAL_UNVERIFIED')
        entry['passage_id'] = 'public_'+sha(canonical(entry))
        passages.append(entry)
    data = dict(schema_version=1,sources=sorted(sources.values(),key=lambda x:x['document_id']),
        pages=sorted(pages.values(),key=lambda x:x['page_id']),passages=sorted(passages,key=lambda x:x['passage_id']),
        legal_currentness='unknown',review_approval='none; publication permission is not legal evidence approval')
    corpus = Corpus.model_validate(data)
    blobs = {'corpus.json':canonical(corpus.model_dump(mode='json')),'NOTICE.md':NOTICE.encode('utf-8')}
    for blob in blobs.values():
        if re.search(rb'[A-Z]:[\\/](?:Users|placement_personal)|refs/codex|\.codex|git-reconciliation|backend/data|processed_sha256|catalog_sha256',blob):
            raise ValueError('Private metadata in publication candidate')
    manifest = Manifest(schema_version=1,status='candidate; publication requires a separate operator decision',
        files={n:dict(sha256=sha(b),bytes=len(b)) for n,b in blobs.items()},source_count=len(sources),
        passage_count=len(passages),policy='single-page-archival-public-v1',
        rights_basis='Copyright Act 1957 section 52(1)(q)(i)-(ii); conditional, not public domain',
        rights_assessment='conditional; applicable terms and statutory conditions require human review',
        exclusions=EXCLUSIONS,legal_currentness='unknown')
    blobs['manifest.json'] = canonical(manifest.model_dump(mode='json'))
    target.mkdir(parents=True,exist_ok=False)
    for n,b in blobs.items():
        with (target/n).open('xb') as f:f.write(b)
    archive = target.with_suffix('.zip')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for n in sorted(blobs):z.writestr(n,blobs[n])
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and all(z.read(n)==b for n,b in blobs.items())
    return dict(manifest_sha256=sha(blobs['manifest.json']),files=manifest.model_dump(mode='json')['files'],
        source_count=len(sources),page_count=len(pages),passage_count=len(passages),
        archive_bytes=archive.stat().st_size,archive_sha256=sha(archive.read_bytes()),
        unpacked_bytes=sum(map(len,blobs.values())),publication_approved=False,
        sources=[{k:v for k,v in s.items() if k not in {'commentary'}} for s in data['sources']],
        exclusions=EXCLUSIONS)
