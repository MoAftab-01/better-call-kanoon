"""EXPLICIT SYNTHETIC browser server. Never approves a real corpus or calls Groq."""
import os
from pathlib import Path
from uuid import uuid4

from backend.tests.public_corpus_fixtures import fixture, test_key
from backend.chat.api import create_app
from backend.chat.service import ChatService
from backend.chat.provider import Settings

root=Path(__file__).resolve().parents[2]
parent=root/'backend/data/test-runs'/('public-browser-'+uuid4().hex[:10])
parent.mkdir(parents=True)
corpus=fixture(parent/'SYNTHETIC-NOT-LAW')
os.environ['PUBLIC_CORPUS_SIGNER_PUBLIC_KEY']=test_key(corpus[0]).public_key().public_bytes_raw().hex()
os.environ.update(KANOON_ENV='production',CORPUS_KIND='public',RETRIEVAL_MODE='bm25',
    KANOON_ACCESS_TOKEN='SYNTHETIC_PUBLIC_BROWSER_ACCESS_NOT_REAL_2026')
for key,value in zip(['PUBLIC_CORPUS_DIR','PUBLIC_CORPUS_MANIFEST_SHA256','PUBLIC_CORPUS_APPROVAL_FILE','PUBLIC_CORPUS_APPROVAL_SHA256'],corpus):
    os.environ[key]=str(value)
app=create_app(ChatService(settings=Settings()))


@app.middleware('http')
async def marker(request,call_next):
    response=await call_next(request)
    response.headers['X-Kanoon-Synthetic-Public-Corpus']='true'
    return response
