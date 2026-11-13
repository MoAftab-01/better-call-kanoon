"""No corpus or real approval is needed to verify a public infrastructure release."""
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from backend.chat.api import create_app
from backend.chat.provider import Settings
from backend.chat.service import ChatService
from backend.retrieval.configuration import create_index

TOKEN = 'SYNTHETIC_PUBLIC_WEBSITE_ACCESS_NOT_REAL_2026'


@pytest.fixture
def website(tmp_path,monkeypatch):
    monkeypatch.setenv('KANOON_ENV','production')
    monkeypatch.setenv('CORPUS_KIND','public')
    monkeypatch.setenv('RETRIEVAL_MODE','bm25')
    monkeypatch.setenv('PUBLIC_CORPUS_DIR',str(tmp_path/'NO-APPROVED-CORPUS'))
    monkeypatch.setenv('PRIVATE_CORPUS_ROOT','MUST-NOT-BE-READ')
    monkeypatch.setenv('KANOON_ACCESS_TOKEN',TOKEN)
    monkeypatch.setenv('KANOON_ALLOWED_ORIGINS','https://website.example')
    for key in ['PUBLIC_CORPUS_MANIFEST_SHA256','PUBLIC_CORPUS_APPROVAL_FILE',
            'PUBLIC_CORPUS_APPROVAL_SHA256','PUBLIC_CORPUS_SIGNER_PUBLIC_KEY']:
        monkeypatch.delenv(key,raising=False)
    class NeverCallProvider:
        async def select(self,*args):raise AssertionError('Missing corpus must never call Groq')
    index=create_index()
    # Simulate configured credentials without a network call or real key.
    service=ChatService(index,Settings('SYNTHETIC_NOT_REAL','SYNTHETIC_MODEL'),NeverCallProvider())
    return TestClient(create_app(service))


def test_healthy_website_reports_research_publication_pending(website):
    assert website.get('/').status_code==200
    assert website.get('/').json()=={'message':'Welcome to Better Call AI'}
    assert website.get('/openapi.json').json()['info']['title']=='Better Call AI'
    assert website.get('/api/health').json()=={'status':'healthy','service':'better-call-kanoon'}
    ready=website.get('/api/ready');assert ready.status_code==503
    assert ready.json()['research_ready'] is False and ready.json()['corpus_available'] is False
    assert ready.json()['research_state']=='publication_pending'
    assert 'publication is pending' in ready.json()['message']
    status=website.get('/api/chat/status').json()
    assert not status['available'] and status['retrieval']['passages']==0
    assert status['retrieval']['corpus_kind']=='public'
    assert status['research_state']=='publication_pending'
    assert status['provider_configured']  # A provider key cannot activate research.


def test_public_website_enforces_auth_then_corpus_gate_without_provider(website,caplog):
    question={'message':'BNS commencement notification'}
    assert website.post('/api/chat',json=question).status_code==401
    assert website.post('/api/chat',headers={'Authorization':'Bearer wrong'},json=question).status_code==401
    response=website.post('/api/chat',headers={'Authorization':'Bearer '+TOKEN},json=question)
    assert response.status_code==503 and response.json()['error']['code']=='corpus_not_approved'
    assert 'citations' not in response.json() and 'answer' not in response.json()
    assert TOKEN not in caplog.text and 'SYNTHETIC_NOT_REAL' not in caplog.text


def test_pending_website_cors_and_privacy_headers(website):
    good=website.get('/api/health',headers={'Origin':'https://website.example'})
    assert good.headers['access-control-allow-origin']=='https://website.example'
    bad=website.get('/api/health',headers={'Origin':'https://untrusted.example'})
    assert 'access-control-allow-origin' not in bad.headers
    pending=website.get('/api/ready',headers={'Origin':'https://website.example'})
    assert pending.headers['cache-control']=='no-store'
    assert pending.headers['x-content-type-options']=='nosniff'


def test_public_website_without_access_configuration_stays_blocked(website,monkeypatch):
    monkeypatch.delenv('KANOON_ACCESS_TOKEN')
    client=TestClient(create_app())
    assert client.get('/api/health').status_code==200
    assert client.get('/api/ready').status_code==503
    assert client.post('/api/chat',json={'message':'BNS notification'}).json()['error']['code']=='deployment_not_configured'


def test_no_corpus_startup_never_imports_private_or_ml_dependencies(website):
    script='''import sys
from backend.chat.api import create_app
from backend.retrieval.configuration import create_index
index=create_index();assert not index.passages
assert index.public_runtime and index.mode=='bm25'
assert not any(n in sys.modules for n in ['torch','faiss','sentence_transformers','pymupdf','backend.review.service','backend.publication.bindings','backend.retrieval.engine'])
print('PASS: public no-corpus startup without private or ML imports')'''
    result=subprocess.run([sys.executable,'-B','-c',script],capture_output=True,check=True)
    assert b'PASS:' in result.stdout
