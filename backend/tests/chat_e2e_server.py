"""EXPLICIT TEST SERVER: real retrieval, mocked Groq, never live inference.

Run only for the documented browser E2E exercise, never as the application entry.
Requires the separate original local evidence bundle for citation scenarios.
"""
import asyncio
import json
import httpx

from backend.chat.api import create_app
from backend.chat.provider import GroqProvider, Settings
from backend.chat.service import ChatService

attempts = {}


async def mock_groq(request):
    payload = json.loads(request.content)
    content = json.loads(payload["messages"][1]["content"])
    question = content["question"]
    await asyncio.sleep(.4)
    if "retry-test" in question:
        attempts[question] = attempts.get(question, 0) + 1
        if attempts[question] == 1:
            return httpx.Response(429)
    return httpx.Response(200, json={"choices": [{"finish_reason": "stop",
        "message": {"content": json.dumps({"source_ids": [content["untrusted_evidence"][0]["id"]]})}}]})


settings = Settings("SYNTHETIC_E2E_KEY_NOT_REAL", "SYNTHETIC_E2E_NOT_LIVE")
app = create_app(ChatService(settings=settings, provider=GroqProvider(settings, httpx.MockTransport(mock_groq))))


@app.middleware("http")
async def synthetic_marker(request, call_next):
    response = await call_next(request)
    response.headers["X-Kanoon-Synthetic-Provider"] = "true"
    return response
