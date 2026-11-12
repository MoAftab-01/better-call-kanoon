"""Explicit no-corpus browser test server. No approvals, private sources or Groq."""
import os
from pathlib import Path

from backend.chat.api import create_app
from backend.chat.service import ChatService
from backend.chat.provider import Settings

missing=Path(__file__).resolve().parents[2]/'backend/data/test-runs/NO-CORPUS-WEBSITE-DO-NOT-CREATE'
assert not missing.exists()
os.environ.update(KANOON_ENV='production',CORPUS_KIND='public',RETRIEVAL_MODE='bm25',
    PUBLIC_CORPUS_DIR=str(missing),KANOON_ACCESS_TOKEN='SYNTHETIC_PUBLIC_WEBSITE_ACCESS_NOT_REAL_2026')
for name in ['PUBLIC_CORPUS_MANIFEST_SHA256','PUBLIC_CORPUS_APPROVAL_FILE',
        'PUBLIC_CORPUS_APPROVAL_SHA256','PUBLIC_CORPUS_SIGNER_PUBLIC_KEY']:
    os.environ.pop(name,None)
app=create_app(ChatService(settings=Settings()))


@app.middleware('http')
async def marker(request,call_next):
    response=await call_next(request)
    response.headers['X-Kanoon-Public-Website-Test']='no-corpus'
    return response
