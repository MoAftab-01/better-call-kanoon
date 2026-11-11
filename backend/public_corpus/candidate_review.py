"""Offline deterministic candidate checks and source-sharded preparation.

No production import, approval, text correction, or legal interpretation. Matching
extraction is a mechanical check, never evidence of visual/legal correctness.
"""
from collections import Counter
import json
from pathlib import Path
import re
import zipfile

from .models import Corpus, HARD_EXCLUSIONS, Manifest, canonical, sha
from .runtime import load


def text_findings(passage, page):
    text = passage.text
    lines = page.text.split('\n')
    findings = []
    if not re.search(r'[.!?][\u201d\u2019"\x27)\]]*\s*$', text):
        findings.append('incomplete_terminal_sentence')
    if text.count('(') != text.count(')'):
        findings.append('unbalanced_passage_parentheses')
    if re.search(r'(?m)^\s*\d{1,3}\.\s', '\n'.join(text.split('\n')[1:])):
        findings.append('multiple_numeric_starts')
    after = '\n'.join(lines[passage.end_line:])
    if re.match(r'^\s*(?:Provided|Explanation|Exception|\(\d+\))', after):
        findings.append('possible_omitted_following_qualification')
    if set(page.qa_flags) & HARD_EXCLUSIONS:
        findings.append('hard_excluded_page')
    return findings


def audit(root, candidate, pin):
    from backend.app.ingestion.extraction import normalize_text
    import pymupdf
    root = Path(root)
    _,corpus = load(candidate,pin,preview=True)
    qa = json.loads((root/'docs/legal-text-quality-stage2e.json').read_bytes())
    documents = {}
    total = 0
    source_results = []
    for item in qa['documents']:
        raw = (root/item['raw_path']).read_bytes()
        processed = (root/item['processed_path']).read_bytes()
        if sha(raw) != item['raw_sha256'] or sha(processed) != item['processed_sha256']:
            raise ValueError('Protected source differs from Stage 2E')
        document = json.loads(processed)
        with pymupdf.open(stream=raw,filetype='pdf') as pdf:
            if len(pdf) != len(document['pages']):
                raise ValueError('PDF/processed page count mismatch')
            for number,page in enumerate(document['pages']):
                if normalize_text(pdf[number].get_text('text',sort=False)) != page['text']:
                    raise ValueError('PDF extraction differs from processed record')
        total += len(document['pages'])
        documents['doc_'+item['raw_sha256']] = document
        source_results.append(dict(document_id='doc_'+item['raw_sha256'],raw_sha256=sha(raw),
            processed_sha256=sha(processed),physical_pages=len(document['pages']),all_page_extractions_match=True))
    pages = {p.page_id:p for p in corpus.pages}
    contexts = []
    for page in corpus.pages:
        original = documents[page.document_id]['pages'][page.physical_page-1]
        if original['text'] != page.text:
            raise ValueError('Candidate context differs from processed page')
        contexts.append(dict(page_id=page.page_id,physical_page=page.physical_page,
            text_sha256=page.text_sha256,qa_flags=page.qa_flags,exact_processed_match=True,
            visually_verified=False))
    passages = []
    for passage in corpus.passages:
        page = pages[passage.page_id]
        findings = text_findings(passage,page)
        passages.append(dict(passage_id=passage.passage_id,document_id=passage.document_id,
            page_id=passage.page_id,physical_page=page.physical_page,
            lines=[passage.start_line,passage.end_line],text_sha256=passage.text_sha256,
            mechanically_bound=True,quarantined=bool(findings),findings=findings,
            page_qa_flags=page.qa_flags,printed_number_unverified=passage.printed_number_unverified,
            visual_review_required=True,legal_currentness='unknown'))
    return dict(schema_version=1,deterministic=True,publication_approved=False,
        physical_pages=total,sources=source_results,page_contexts=contexts,passages=passages,
        selection_count=len(passages),context_count=len(contexts),
        quarantine_count=sum(p['quarantined'] for p in passages),
        page_warning_counts=dict(sorted(Counter(f for p in corpus.pages for f in p.qa_flags).items())),
        limitations=['Same-engine extraction equality is not visual correctness.',
            'No legal completeness, provision attribution, currentness or rights clearance is inferred.',
            'Full-page context can contain continuations and detached headings; only exact selected lines are quoted.',
            'Unflagged passages still require human publication review; no review/approval state changed.'])


def shard_candidate(root, candidate, pin, output):
    from backend.app.ingestion.paths import checked_path
    root = checked_path(root)
    target = checked_path(output)
    if not target.is_relative_to(checked_path(root/'backend/data/public-corpus')):
        raise ValueError('Candidate must stay in ignored preparation area')
    if target.exists() or target.with_suffix('.zip').exists():
        raise ValueError('Refusing existing candidate')
    report = audit(root,candidate,pin)
    _,corpus = load(candidate,pin,preview=True)
    quarantine = {p['passage_id'] for p in report['passages'] if p['quarantined']}
    blobs = {}
    artifacts = []
    for source in sorted(corpus.sources,key=lambda s:s.document_id):
        passages = [p for p in corpus.passages if p.document_id == source.document_id and p.passage_id not in quarantine]
        if not passages:
            continue
        ids = {p.page_id for p in passages}
        shard = Corpus(schema_version=1,sources=[source],pages=[p for p in corpus.pages if p.page_id in ids],
            passages=passages,legal_currentness='unknown',review_approval=corpus.review_approval)
        filename = 'source_'+source.raw_sha256+'.json'
        blobs[filename] = canonical(shard.model_dump(mode='json'))
        artifacts.append(dict(document_id=source.document_id,raw_sha256=source.raw_sha256,
            filename=filename,passage_count=len(passages)))
    notice = (Path(candidate)/'NOTICE.md').read_text(encoding='utf-8').replace('references are in corpus.json.',
        'references are in source-specific JSON files.')
    notice += ('\nThis source-sharded candidate requires an independently trusted Ed25519 signature,\n'
        'an exact receipt pin, and explicit include/exclude/revoke decisions for every\n'
        'source. No authorization or licence is granted by creating these files.\n'
        'Source-specific rights and hosting terms remain subject to human/legal review.\n')
    blobs['NOTICE.md'] = notice.encode('utf-8')
    old = Manifest.model_validate_json((Path(candidate)/'manifest.json').read_bytes())
    updated = old.model_dump(mode='json')
    updated.update(dict(schema_version=2,sources=artifacts,
        files={n:dict(sha256=sha(b),bytes=len(b)) for n,b in blobs.items()},source_count=len(artifacts),
        passage_count=sum(s['passage_count'] for s in artifacts)))
    manifest = Manifest.model_validate(updated)
    blobs['manifest.json'] = canonical(manifest.model_dump(mode='json'))
    # Fail before writing on known private metadata markers.
    for blob in blobs.values():
        if re.search(rb'[A-Z]:[\\/]+(?:Users|placement_personal)|refs/codex|\.codex|git-reconciliation|backend/data|processed_sha256|catalog_sha256',blob):
            raise ValueError('Private metadata in candidate')
    target.mkdir(parents=True,exist_ok=False)
    for name,blob in blobs.items():
        with (target/name).open('xb') as f:
            f.write(blob)
    with zipfile.ZipFile(target.with_suffix('.zip'),'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(blobs):
            info = zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info,blobs[name])
    load(target,sha(blobs['manifest.json']),preview=True)
    return dict(manifest_sha256=sha(blobs['manifest.json']),
        files={n:dict(sha256=sha(b),bytes=len(b)) for n,b in blobs.items()},
        source_count=len(artifacts),passages=manifest.passage_count,quarantined=len(quarantine),
        archive_bytes=target.with_suffix('.zip').stat().st_size,
        archive_sha256=sha(target.with_suffix('.zip').read_bytes()),unpacked_bytes=sum(map(len,blobs.values())),
        publication_approved=False,published=False)
