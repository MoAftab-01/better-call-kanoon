"""SYNTHETIC authorization only. No real source publication or reviewer identity."""
import json
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest
from fastapi.testclient import TestClient

from backend.public_corpus.models import canonical,sha
from backend.public_corpus.runtime import PublicIndex,load
from backend.tests.public_corpus_fixtures import fixture,sign_synthetic,test_key as synthetic_key


@pytest.fixture
def bundle(tmp_path,monkeypatch):
    result=fixture(tmp_path/'SYNTHETIC-ONLY')
    monkeypatch.setenv('PUBLIC_CORPUS_SIGNER_PUBLIC_KEY',synthetic_key(result[0]).public_key().public_bytes_raw().hex())
    return result


def rewrite(bundle, change, *, sign=True):
    root,pin,decision,_=bundle
    data=json.loads(decision.read_bytes());change(data)
    if sign:data=sign_synthetic(root,data)
    decision.write_bytes(canonical(data))
    return root,pin,decision,sha(decision.read_bytes())


@pytest.mark.parametrize('change',[
    lambda d:d.pop('signature'),
    lambda d:d.update(signature='0'*128),
    lambda d:d.update(approved_by='SYNTHETIC TAMPERING'),
    lambda d:d.update(signer_key_id='0'*64),
])
def test_unsigned_or_altered_receipt_rejected_even_if_rehashed(bundle,change):
    assert not PublicIndex(*rewrite(bundle,change,sign=False)).passages


def test_independent_signer_required(bundle,monkeypatch):
    monkeypatch.delenv('PUBLIC_CORPUS_SIGNER_PUBLIC_KEY')
    assert not PublicIndex(*bundle).passages
    monkeypatch.setenv('PUBLIC_CORPUS_SIGNER_PUBLIC_KEY',Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex())
    assert not PublicIndex(*bundle).passages


@pytest.mark.parametrize('change',[
    lambda d:d.update(manifest_sha256='0'*64),
    lambda d:d['sources'][0].update(raw_sha256='0'*64),
    lambda d:d['sources'][0].update(artifact_sha256='0'*64),
    lambda d:d['sources'][0].update(document_id='doc_'+'b'*64),
    lambda d:d.update(sources=[]),
    lambda d:d['sources'].append(d['sources'][0].copy()),
    lambda d:d['sources'][0].update(decision='exclude'),
    lambda d:d['sources'][0].update(decision='revoke'),
    lambda d:d.update(decision='revoked'),
])
def test_signed_wrong_or_revoked_binding_fails_closed(bundle,change):
    assert not PublicIndex(*rewrite(bundle,change)).passages


def test_legacy_unsigned_contract_is_preview_only(bundle):
    root,_,_,_=bundle
    data=json.loads((root/'manifest.json').read_bytes());data['schema_version']=1;data.pop('sources')
    (root/'manifest.json').write_bytes(canonical(data));pin=sha((root/'manifest.json').read_bytes())
    assert PublicIndex(root,pin,preview=True).passages
    new=rewrite((root,pin,bundle[2],bundle[3]),lambda d:d.update(manifest_sha256=pin))
    assert not PublicIndex(*new).passages


def two_sources(bundle):
    root,_,decision,_=bundle
    a=json.loads((root/'corpus.json').read_bytes());b=json.loads(canonical(a))
    aid='doc_'+'a'*64;bid='doc_'+'b'*64
    b=json.loads(json.dumps(b).replace(aid,bid))
    b['sources'][0]['raw_sha256']='b'*64
    b['sources'][0]['title']='SYNTHETIC EXCLUDED Bharatiya Nyaya Sanhita - NOT LAW'
    for p in b['passages']:
        p['passage_id']='public_'+sha(canonical({k:v for k,v in p.items() if k!='passage_id'}))
    name='source_'+'b'*64+'.json';(root/name).write_bytes(canonical(b))
    m=json.loads((root/'manifest.json').read_bytes());m['files'][name]=dict(sha256=sha(canonical(b)),bytes=len(canonical(b)))
    m['sources'].append(dict(document_id=bid,raw_sha256='b'*64,filename=name,passage_count=1))
    m.update(source_count=2,passage_count=2);(root/'manifest.json').write_bytes(canonical(m));pin=sha(canonical(m))
    d=json.loads(decision.read_bytes());d['manifest_sha256']=pin
    d['sources'].append(dict(document_id=bid,raw_sha256='b'*64,artifact_sha256=sha(canonical(b)),decision='exclude',
        rationale='SYNTHETIC SOFTWARE EXCLUSION - NOT REAL REVIEW'))
    decision.write_bytes(canonical(sign_synthetic(root,d)))
    return (root,pin,decision,sha(decision.read_bytes())),name


def test_subset_delivery_and_no_runtime_read_of_excluded_source(bundle,monkeypatch):
    from backend.public_corpus.delivery import deliver
    from backend.public_corpus import runtime
    multi,name=two_sources(bundle)
    # A full candidate contains excluded bytes and is forbidden as a runtime directory.
    assert not PublicIndex(*multi).passages
    destination=Path.cwd()/'backend/data/deployment'/('SYNTHETIC-SUBSET-'+uuid4().hex)
    result=deliver(*multi,destination)
    assert result['sources']==1 and result['passages']==1 and not result['published']
    assert {p.name for p in destination.iterdir()}=={'manifest.json','corpus.json','NOTICE.md'}
    original=runtime.read
    def guarded(path,limit):
        assert Path(path).name!=name,'Excluded source must never be opened by runtime'
        return original(path,limit)
    monkeypatch.setattr(runtime,'read',guarded)
    subset=(destination,*multi[1:])
    index=PublicIndex(*subset)
    hit=index.search('BNS section 15')[0]
    assert hit.source.raw_sha256=='a'*64 and len(index.passages)==1
    assert index.citation(hit,1).text_sha256==hit.record.text_sha256
    # Even a corrupt excluded file's presence blocks runtime; its bytes are not read.
    (destination/name).write_bytes(b'CORRUPT SYNTHETIC EXCLUDED FILE')
    assert not PublicIndex(*subset).passages
    monkeypatch.setattr(runtime,'read',original)
    with pytest.raises(ValueError):deliver(*multi,destination)


def test_live_revocation_disables_api_and_old_receipt_cannot_be_rolled_back(bundle,monkeypatch):
    from backend.chat.api import create_app
    from backend.chat.service import ChatService
    from backend.chat.provider import Settings
    monkeypatch.setenv('KANOON_ENV','local')
    old=bundle[2].read_bytes();index=PublicIndex(*bundle)
    client=TestClient(create_app(ChatService(index,Settings())))
    assert client.get('/api/ready').status_code==200
    revoked=rewrite(bundle,lambda d:d.update(decision='revoked'))
    assert client.get('/api/ready').status_code==503
    assert not index.search('BNS section 15')
    assert client.post('/api/chat',json={'message':'BNS section 15'}).status_code==503
    assert not PublicIndex(*revoked).passages
    bundle[2].write_bytes(old)
    assert not PublicIndex(*revoked).passages  # New independent pin rejects the old receipt.


def test_source_revocation_keeps_only_other_explicitly_authorized_source(bundle):
    from backend.public_corpus.delivery import deliver
    multi,_=two_sources(bundle)
    def policy(data):
        data['sources'][0]['decision']='revoke'
        data['sources'][1]['decision']='include'
    revised=rewrite(multi,policy)
    destination=Path.cwd()/'backend/data/deployment'/('SYNTHETIC-REVOCATION-'+uuid4().hex)
    result=deliver(*revised,destination)
    assert result['sources']==1
    index=PublicIndex(destination,*revised[1:])
    assert index.status()['publication_approved']
    assert {h.source.raw_sha256 for h in index.passages}=={'b'*64}
    assert not index.search('BNS section 15',source_ids=['doc_'+'a'*64])


def test_deterministic_ranking_and_safe_abstention(bundle):
    first=PublicIndex(*bundle);second=PublicIndex(*bundle)
    assert [h.identifier for h in first.search('BNS section 15')]==[h.identifier for h in second.search('BNS section 15')]
    assert not first.search('What is the weather?')
    assert first.status()['evidence_status']=='ARCHIVAL_UNVERIFIED'
    assert first.corpus.legal_currentness=='unknown'
    assert first.corpus.review_approval.startswith('none;')


@pytest.mark.parametrize('suffix,code',[
    (' unfinished','incomplete_terminal_sentence'),
    (' (','unbalanced_passage_parentheses'),
    ('\n16. SYNTHETIC EXTRA NUMBER.','multiple_numeric_starts'),
])
def test_candidate_quality_quarantines_ambiguous_text(bundle,suffix,code):
    from backend.public_corpus.candidate_review import text_findings
    _,corpus=load(bundle[0],bundle[1],preview=True)
    p=corpus.passages[0].model_copy(update={'text':corpus.passages[0].text+suffix})
    assert code in text_findings(p,corpus.pages[0])


def test_candidate_quality_catches_following_proviso(bundle):
    from backend.public_corpus.candidate_review import text_findings
    _,corpus=load(bundle[0],bundle[1],preview=True)
    page=corpus.pages[0].model_copy(update={'text':'SYNTHETIC HEADER\n'+corpus.passages[0].text+'\nProvided SYNTHETIC condition.'})
    assert 'possible_omitted_following_qualification' in text_findings(corpus.passages[0],page)
