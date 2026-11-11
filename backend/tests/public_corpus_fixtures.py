"""SYNTHETIC SOFTWARE ONLY. No real corpus/publication or legal approval."""
import json
from pathlib import Path
from backend.public_corpus.models import canonical,sha
from backend.public_corpus.authorization import DOMAIN
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# Ephemeral software-test keys only. Never used for human or real corpus approval.
_keys = {}


def test_key(root):
    return _keys[Path(root).absolute()]


def sign_synthetic(root, data):
    key = test_key(root)
    data = {k:v for k,v in data.items() if k != 'signature'}
    data['signer_key_id'] = sha(key.public_key().public_bytes_raw())
    # Pydantic's datetime serialization is the signed protocol's representation.
    data['approved_at'] = data['approved_at'].replace('+00:00','Z')
    data['signature'] = key.sign(DOMAIN+canonical(data)).hex()
    return data


def fixture(root):
    root=Path(root);root.mkdir()
    document='doc_'+'a'*64;page_id=document+':page:000002'
    body='15. SYNTHETIC SOFTWARE FIXTURE - NOT LAW. A judge acts judicially in this practice example.'
    text='SYNTHETIC PAGE - NOT AN OFFICIAL DOCUMENT\n'+body+'\n16. SYNTHETIC FINAL TEXT - NOT LAW.'
    record=dict(document_id=document,page_id=page_id,start_line=2,end_line=2,text=body,text_sha256=sha(body.encode()),
        printed_number_unverified='15',attribution='document_only',evidence_status='ARCHIVAL_UNVERIFIED')
    record['passage_id']='public_'+sha(canonical(record))
    corpus=dict(schema_version=1,sources=[dict(document_id=document,title='SYNTHETIC Bharatiya Nyaya Sanhita - NOT LAW',
        instrument='SYNTHETIC ACT - NOT LAW',kind='act',
        # Existing official URL is a syntax fixture only; no request or authenticity claim.
        source_url='https://egazette.gov.in/WriteReadData/2023/250883.pdf',raw_sha256='a'*64,
        issuing_authority='SYNTHETIC TEST LABEL - NOT GOVERNMENT',publication_date='2000-01-01',physical_pages=2,
        edition='SYNTHETIC SOFTWARE FIXTURE - NOT LAW',commentary='SYNTHETIC SOFTWARE TEST COMMENTARY. This fixture is not real legal text or a publication approval. '*2,
        provenance='official_gazette_identity_checked_at_preparation',legal_currentness='unknown')],
        pages=[dict(document_id=document,page_id=page_id,physical_page=2,text=text,text_sha256=sha(text.encode()),
                    qa_flags=[],automatic_checks_passed=True)],passages=[record],legal_currentness='unknown',
        review_approval='none; publication permission is not legal evidence approval')
    (root/'corpus.json').write_bytes(canonical(corpus))
    (root/'NOTICE.md').write_text('SYNTHETIC TEST NOTICE - NOT LAW. No real approvals.',encoding='utf-8')
    return repin(root)


def repin(root):
    root=Path(root)
    if root.absolute() not in _keys:
        _keys[root.absolute()] = Ed25519PrivateKey.generate()
    (root.parent/(root.name+'-SYNTHETIC-public-key.txt')).write_text(test_key(root).public_key().public_bytes_raw().hex(),encoding='ascii')
    data=json.loads((root/'corpus.json').read_bytes())
    source=data['sources'][0]
    manifest=dict(schema_version=2,status='candidate; publication requires a separate operator decision',
        files={n:dict(sha256=sha((root/n).read_bytes()),bytes=(root/n).stat().st_size) for n in ['corpus.json','NOTICE.md']},
        sources=[dict(document_id=source['document_id'],raw_sha256=source['raw_sha256'],filename='corpus.json',passage_count=1)],
        source_count=1,passage_count=1,policy='single-page-archival-public-v1',
        rights_basis='Copyright Act 1957 section 52(1)(q)(i)-(ii); conditional, not public domain',
        rights_assessment='conditional; applicable terms and statutory conditions require human review',
        exclusions=['SYNTHETIC TEST ONLY'],legal_currentness='unknown')
    (root/'manifest.json').write_bytes(canonical(manifest));digest=sha((root/'manifest.json').read_bytes())
    approval=root.parent/(root.name+'-synthetic-publication-decision.json')
    approval.write_bytes(canonical(sign_synthetic(root,dict(schema_version=2,purpose='corpus_publication_only; not legal evidence approval',
        decision='approved_for_publication',manifest_sha256=digest,approved_by='SYNTHETIC TEST ACTOR - NOT A REAL APPROVAL',
        approved_at='2000-01-01T00:00:00Z',rationale='SYNTHETIC SOFTWARE TEST - not approval to publish any legal corpus.',
        rights_review='applicable terms and statutory conditions reviewed',
        safety_review='exact payload reviewed; no private data',sources=[dict(document_id=source['document_id'],
        raw_sha256=source['raw_sha256'],artifact_sha256=sha((root/'corpus.json').read_bytes()),decision='include',
        rationale='SYNTHETIC SOFTWARE TEST ONLY - NOT REAL APPROVAL')]))))
    return root,digest,approval,sha(approval.read_bytes())
