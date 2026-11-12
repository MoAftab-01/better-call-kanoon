import asyncio
from collections import deque
import logging
import os
import secrets
import threading
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .models import ChatRequest, ChatResponse
from .provider import ProviderError
from .service import ChatService

logger = logging.getLogger("kanoon.chat")
ERRORS = {
    "corpus_not_approved": "The public corpus has not been approved for serving.",
    "access_required": "Enter the private demo access token supplied by the operator.",
    "deployment_not_configured": "Public chat is disabled until the operator configures access protection.",
    "service_busy": "Two research requests are already running. Retry shortly.",
    "local_rate_limited": "Local request limit reached. Wait one minute before retrying.",
    "request_too_large": "The request body exceeds the 16,000-byte limit. Shorten the recent history or question.",
    "provider_timeout": "Groq timed out. Retry shortly; no answer was fabricated.",
    "provider_rate_limited": "Groq rate limit reached. Wait before retrying.",
    "provider_configuration_error": "Check the backend Groq key and model configuration.",
    "provider_unavailable": "Groq is unavailable. Retry shortly.",
    "provider_invalid_response": "Groq returned an invalid response.",
    "source_changed": "Source integrity changed during this request. Restart after checking the evidence bundle.",
}


def create_app(service=None):
    app = FastAPI(title="Better Call Kanoon", description="Archival research workspace; public source publication is required. No current-law certification.")
    app.state.chat = service
    lock, arrivals = threading.Lock(), deque()
    environment = os.environ.get("KANOON_ENV", "local")
    if environment not in {"local", "production"}:
        raise ValueError("KANOON_ENV must be local or production")
    production = environment == "production"
    access_token = os.environ.get("KANOON_ACCESS_TOKEN", "")
    auth_ready = len(access_token) >= 32 and access_token != os.environ.get("GROQ_API_KEY", "")
    origins = [s.strip() for s in os.environ.get("KANOON_ALLOWED_ORIGINS", "").split(",") if s.strip()]
    from urllib.parse import urlparse
    if any(urlparse(s).scheme != "https" or not urlparse(s).netloc or urlparse(s).path not in ("", "/") or
           urlparse(s).username or urlparse(s).query or urlparse(s).fragment for s in origins):
        raise ValueError("Production CORS origins must be explicit HTTPS origins")
    origins = [s.rstrip("/") for s in origins]
    active = 0

    def get_service():
        with lock:
            if app.state.chat is None:
                app.state.chat = ChatService()
        return app.state.chat

    def error(code, status, retry=None):
        headers = {"Cache-Control": "no-store"}
        if retry:
            headers["Retry-After"] = str(retry)
        return JSONResponse(status_code=status, content={"error": {"code": code,
            "message": ERRORS.get(code, "Request could not be completed safely.")}}, headers=headers)

    @app.middleware("http")
    async def privacy_headers(request, call_next):
        nonlocal active
        # Bound actual streamed body bytes, including chunked requests, before JSON parsing.
        guarded = request.url.path == "/api/chat" and request.method == "POST"
        if guarded:
            if production:
                if not auth_ready:
                    return error("deployment_not_configured", 503)
                supplied = request.headers.get("Authorization", "")
                if not secrets.compare_digest(supplied.encode(), ("Bearer " + access_token).encode()):
                    return error("access_required", 401)
            with lock:
                if active >= 2:
                    return error("service_busy", 429, 10)
                active += 1
        try:
            return await bounded_request(request, call_next, guarded)
        finally:
            if guarded:
                with lock:
                    active -= 1

    async def bounded_request(request, call_next, guarded):
        if guarded:
            body = bytearray()
            try:
                async with asyncio.timeout(10):
                    async for chunk in request.stream():
                        body.extend(chunk)
                        if len(body) > 16000:
                            return error("request_too_large", 413)
            except TimeoutError:
                return error("request_body_timeout", 408)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _exc):
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_request",
            "message": "Send a nonempty message up to 2,000 characters and at most six recent user/assistant turns (1,200 characters each)."}})

    @app.get("/")
    def welcome():
        return {"message": "Welcome to Better Call Kanoon"}

    @app.get("/api/health")
    def health():
        return {"status": "healthy", "service": "better-call-kanoon"}

    @app.get("/api/ready")
    def ready(chat: ChatService = Depends(get_service)):
        data = chat.status()
        corpus = data["retrieval"]["passages"] > 0
        configured = not production or auth_ready
        ready = configured and (data['available'] or not getattr(chat.index,'public_runtime',False))
        return JSONResponse(status_code=200 if ready else 503, content={
            "status": "ready" if ready else "blocked", "corpus_available": corpus,
            "research_ready": corpus and configured and data['available'], "authentication_required": production,
            "research_state": data['research_state'], "message": data['research_message'],
            "legal_currentness": "unknown"})

    @app.get("/api/chat/status")
    def status(chat: ChatService = Depends(get_service)):
        return dict(**chat.status(), authentication_required=production,
                    deployment_ready=not production or auth_ready)

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest, chat: ChatService = Depends(get_service)):
        now = time.monotonic()
        with lock:
            while arrivals and arrivals[0] < now - 60:
                arrivals.popleft()
            if len(arrivals) >= 30:
                return error("local_rate_limited", 429, 60)
            arrivals.append(now)
        trace, started = str(uuid4()), time.monotonic()
        try:
            async with asyncio.timeout(25):
                # ChatService offloads hash/search work; provider I/O stays async.
                result = await chat.answer(request)
            logger.info("chat_completed request_id=%s evidence=%s citations=%d elapsed_ms=%d",
                trace, result.evidence_status, len(result.citations), (time.monotonic()-started)*1000)
            return result
        except (TimeoutError, ProviderError) as exc:
            code = "provider_timeout" if isinstance(exc, TimeoutError) else exc.code
            status_code = 504 if isinstance(exc, TimeoutError) else exc.status
            logger.warning("chat_failed request_id=%s code=%s", trace, code)
            return error(code, status_code, getattr(exc, "retry_after", None))
        except Exception:
            logger.error("chat_failed request_id=%s code=internal_error", trace)
            return error("internal_error", 500)

    # Outermost CORS also covers early authentication/size-limit failures.
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins,
            allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"],
            allow_credentials=False)
    return app
