"""All writable records/decisions are synthetic, isolated software fixtures."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.public_corpus.models import HARD_EXCLUSIONS,canonical,sha
from backend.public_corpus.runtime import PublicIndex,load
from backend.tests.public_corpus_fixtures import fixture,repin


@pytest.fixture
def corpus(tmp_path,monkeypatch):
    from backend.tests.public_corpus_fixtures import test_key
    result=fixture(tmp_path/'SYNTHETIC-CORPUS-NOT-LAW')
    monkeypatch.setenv('PUBLIC_CORPUS_SIGNER_PUBLIC_KEY',test_key(result[0]).public_key().public_bytes_raw().hex())
    return result


def test_exact_manifest_and_provenance(corpus):
    index=PublicIndex(*corpus)
    assert index.status()['publication_approved'] and index.mode=='bm25'
    hit=index.search('BNS section 15')[0];citation=index.citation(hit,1)
    assert citation.quote.startswith('15. SYNTHETIC') and citation.pdf_page==2
    assert citation.text_sha256==sha(citation.quote.encode())
    assert citation.publication_manifest_sha256==corpus[1] and not citation.processed_sha256
    assert not citation.qa_sha256 and not citation.catalog_sha256
    assert 'SYNTHETIC' in citation.publication_commentary and citation.evidence_status=='ARCHIVAL_UNVERIFIED'


def test_candidate_never_auto_approved(corpus):
    root,pin,_,_=corpus
    assert not PublicIndex(root,pin).passages
    preview=PublicIndex(root,pin,preview=True)
    assert preview.passages and not preview.status()['publication_approved']
    assert preview.status()['preview_only']


def test_missing_and_corrupted_fail_closed(corpus):
    root,pin,decision,digest=corpus
    assert not PublicIndex(root/'absent',pin,decision,digest).passages
    assert not PublicIndex(root,'0'*64,decision,digest).passages
    (root/'corpus.json').write_bytes((root/'corpus.json').read_bytes()+b' ')
    assert not PublicIndex(root,pin,decision,digest).passages


def test_post_start_tamper_invalidates_citations(corpus):
    index=PublicIndex(*corpus);hit=index.search('BNS section 15')[0]
    (corpus[0]/'NOTICE.md').write_bytes(b'tamper')
    assert not index.search('BNS section 15') and not index.status()['passages']
    with pytest.raises(ValueError):index.citation(hit,1)


@pytest.mark.parametrize('name',['private.pdf','private.json','extra-directory'])
def test_unauthorized_files_or_directories(corpus,name):
    (corpus[0]/name).write_text('SYNTHETIC UNAUTHORIZED',encoding='utf-8')
    assert not PublicIndex(*corpus).passages


def test_manifest_path_traversal_rejected(corpus):
    root,*_=corpus;m=json.loads((root/'manifest.json').read_bytes());m['files']['../private.json']=m['files']['NOTICE.md']
    (root/'manifest.json').write_bytes(canonical(m))
    with pytest.raises(ValueError):load(root,sha((root/'manifest.json').read_bytes()),preview=True)


def test_duplicate_json_keys_rejected(corpus):
    root,*_=corpus;b=(root/'manifest.json').read_bytes();b=b.replace(b'{',b'{"schema_version":1,',1)
    (root/'manifest.json').write_bytes(b)
    with pytest.raises(ValueError):load(root,sha(b),preview=True)


def test_public_hard_policy_matches_original():
    from backend.review.service import HARD_EXCLUSIONS as original
    assert HARD_EXCLUSIONS==original


@pytest.mark.parametrize('change',['hard_flag','page_range','source','text','unicode'])
def test_invalid_bindings_even_with_new_manifest(corpus,change):
    root,*_=corpus;data=json.loads((root/'corpus.json').read_bytes())
    if change=='hard_flag':data['pages'][0]['qa_flags']=['table_or_form_layout_unverified']
    if change=='page_range':data['sources'][0]['physical_pages']=1
    if change=='source':data['passages'][0]['document_id']='doc_'+'b'*64
    if change=='text':data['pages'][0]['text']+='tamper'
    if change=='unicode':
        data['pages'][0]['text']+='\ufffd';data['pages'][0]['text_sha256']=sha(data['pages'][0]['text'].encode())
    (root/'corpus.json').write_bytes(canonical(data));new=repin(root)
    assert not PublicIndex(*new).passages


def test_public_private_configuration_isolation(corpus,monkeypatch):
    from backend.retrieval.configuration import create_index
    monkeypatch.setenv('CORPUS_KIND','public');monkeypatch.setenv('RETRIEVAL_MODE','bm25')
    monkeypatch.setenv('PRIVATE_CORPUS_ROOT','MUST NEVER BE READ')
    monkeypatch.setenv('KANOON_EMBEDDING_MODEL_PATH','MUST NEVER BE LOADED')
    for key,value in zip(['PUBLIC_CORPUS_DIR','PUBLIC_CORPUS_MANIFEST_SHA256','PUBLIC_CORPUS_APPROVAL_FILE','PUBLIC_CORPUS_APPROVAL_SHA256'],corpus):monkeypatch.setenv(key,str(value))
    assert create_index().search('BNS section 15')
    monkeypatch.setenv('PUBLIC_CORPUS_DIR','missing')
    assert not create_index().passages
    monkeypatch.setenv('CORPUS_KIND','private');monkeypatch.setenv('KANOON_ENV','production')
    with pytest.raises(ValueError):create_index()


def test_public_production_readiness_and_auth(corpus,monkeypatch):
    from backend.chat.api import create_app
    monkeypatch.setenv('KANOON_ENV','production');monkeypatch.setenv('CORPUS_KIND','public')
    monkeypatch.setenv('RETRIEVAL_MODE','bm25');monkeypatch.setenv('KANOON_ACCESS_TOKEN','SYNTHETIC-ACCESS-TOKEN-NOT-REAL-123456789')
    for key,value in zip(['PUBLIC_CORPUS_DIR','PUBLIC_CORPUS_MANIFEST_SHA256','PUBLIC_CORPUS_APPROVAL_FILE','PUBLIC_CORPUS_APPROVAL_SHA256'],corpus):monkeypatch.setenv(key,str(value))
    client=TestClient(create_app());assert client.get('/api/ready').status_code==200
    assert client.post('/api/chat',json={'message':'BNS section 15'}).status_code==401
    result=client.post('/api/chat',headers={'Authorization':'Bearer SYNTHETIC-ACCESS-TOKEN-NOT-REAL-123456789'},json={'message':'BNS section 15'})
    assert result.status_code==200 and result.json()['evidence_status']=='ARCHIVAL_UNVERIFIED'
    assert result.json()['citations'][0]['publication_manifest_sha256']==corpus[1]
    corpus[2].unlink()
    assert client.get('/api/ready').status_code==503


def test_bm25_imports_no_private_or_ml_modules(corpus):
    root,pin,decision,digest=corpus
    script='''import json,sys
from backend.public_corpus.runtime import PublicIndex
x=PublicIndex(*sys.argv[1:]);assert x.search('BNS section 15')
assert not any(n in sys.modules for n in ['torch','faiss','sentence_transformers','pymupdf','backend.review.service','backend.publication.bindings'])
print(json.dumps({'mode':x.mode,'passages':len(x.passages)}))'''
    result=subprocess.run([sys.executable,'-B','-c',script,str(root),pin,str(decision),digest],capture_output=True,check=True)
    assert json.loads(result.stdout)['passages']==1


def test_no_review_store_created(corpus):
    root,*_=corpus;index=PublicIndex(*corpus);index.search('BNS section 15')
    assert not (root/'backend').exists() and not (root/'reviews').exists()


@pytest.mark.parametrize('field',['rights_review','safety_review'])
def test_publication_requires_explicit_rights_and_safety_review(corpus,field):
    root,pin,decision,_=corpus
    data=json.loads(decision.read_bytes());data.pop(field);decision.write_bytes(canonical(data))
    assert not PublicIndex(root,pin,decision,sha(decision.read_bytes())).passages


def test_replaced_publication_decision_fails_closed(corpus):
    index=PublicIndex(*corpus);assert index.passages
    corpus[2].write_bytes(corpus[2].read_bytes()+b' ')
    assert not index.search('BNS section 15')


def test_memory_reporting_and_preview_scope(corpus):
    from backend.public_corpus.measure import memory
    report=memory()
    assert set(report)=={'resident_mib','peak_resident_mib','method'}
    if sys.platform=='win32' or sys.platform.startswith('linux'):
        assert report['resident_mib']>0 and report['peak_resident_mib']>0
    script='''import json,sys
from backend.public_corpus.measure import measure
print(json.dumps(measure(sys.argv[1],sys.argv[2],'BNS section 15',iterations=2)))'''
    result=subprocess.run([sys.executable,'-B','-c',script,str(corpus[0]),corpus[1]],capture_output=True,check=True)
    data=json.loads(result.stdout)
    assert data['mode']=='bm25' and data['preview_only'] and not data['publication_approved']
    assert data['query_hits']==1 and data['startup_seconds']>0 and not data['forbidden_imports']


def test_bm25_private_mode_does_not_initialize_ml(corpus,monkeypatch):
    from backend.retrieval.engine import ArchivalIndex
    class FailIfInitialized:
        def __bool__(self):raise AssertionError('Semantic index should not be inspected')
    # No model exists, but even an injected semantic object must remain untouched.
    index=ArchivalIndex(corpus[0],loader=lambda r: (_ for _ in ()).throw(ValueError('No private fixture')),
        semantic=FailIfInitialized(),retrieval_mode='bm25')
    assert index.semantic is None and index.mode=='bm25'


@pytest.mark.parametrize('component',['record','source','page'])
def test_in_memory_citation_tampering_cannot_escape(corpus,component):
    from dataclasses import replace
    index=PublicIndex(*corpus);hit=index.search('BNS section 15')[0]
    original=getattr(hit,component)
    field='title' if component=='source' else 'text'
    bad=replace(hit,**{component:original.model_copy(update={field:'SYNTHETIC TAMPERING'})})
    index.passages[0]=bad
    with pytest.raises(ValueError):index.citation(bad,1)
    assert not index.search('BNS section 15')


def test_invalid_manifest_configuration_does_not_leak(corpus):
    index=PublicIndex(corpus[0],'SYNTHETIC-SENSITIVE-CONFIG-NOT-REAL')
    assert index.status()['index_version'] is None


def test_offline_preview_cannot_be_exposed_through_http(corpus,monkeypatch):
    from backend.chat.api import create_app
    from backend.chat.service import ChatService
    from backend.chat.provider import Settings
    monkeypatch.setenv('KANOON_ENV','local')
    index=PublicIndex(corpus[0],corpus[1],preview=True)
    assert index.search('BNS section 15')  # Inspection is allowed offline.
    client=TestClient(create_app(ChatService(index,Settings())))
    assert client.get('/api/ready').status_code==503
    assert not client.get('/api/chat/status').json()['available']
    result=client.post('/api/chat',json={'message':'BNS section 15'})
    assert result.status_code==503 and 'citations' not in result.json()


def test_excessive_json_nesting_fails_closed(corpus):
    root,*_=corpus
    blob=b'['*2000+b'0'+b']'*2000
    (root/'manifest.json').write_bytes(blob)
    assert not PublicIndex(root,sha(blob),preview=True).passages
