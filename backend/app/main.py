"""FastAPI application entry point for Better Call Kanoon.

Owns the app factory, lifespan logging, CORS, the ``/api`` routers, the public
``GET /api/config`` route, the built-frontend mount at ``/`` and a single
generic exception handler that never leaks a traceback. The frontend it serves
is the Vite build output at ``<repo>/frontend/dist``, resolved by
``settings.STATIC_DIR``. Routing order matters: the API routers are registered
**before** ``StaticFiles`` is mounted at ``"/"``, otherwise the catch-all mount
shadows every API route and ``/api/health`` 404s.

Disclaimer: this project provides general legal INFORMATION, not legal advice.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.routing import Mount as fastapi_Mount
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match
from starlette.types import Scope

from app.api.health import router as health_router
from app.config import get_emergency_contacts, get_settings, load_emergency_contacts
from app.models import EmergencyContact, PublicConfig, StarterQuestion, SupportedLanguage

logger = logging.getLogger(__name__)

DESCRIPTION = "Voice-powered AI legal information grounded in Indian law."
#: Advertised in ``/api/config`` so the frontend renders the same wording.
DISCLAIMER = (
    "Better Call Kanoon provides general legal information based on its "
    "available legal sources. It is not a lawyer and does not provide legal "
    "advice."
)
SPEECH_RATES: list[float] = [0.75, 1.0, 1.25, 1.5]

#: Machine-readable slugs and default copy for the HTTP statuses this app emits.
_ERROR_CODES: dict[int, str] = {
    400: "bad_request",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_server_error",
    503: "service_unavailable",
}
_DEFAULT_HTTP_MESSAGE: dict[int, str] = {
    404: "The requested resource was not found.",
    405: "That HTTP method is not supported for this endpoint.",
    500: "Something went wrong while processing your request. Please try again.",
}


def _plain_text_response(status_code: int, message: str) -> PlainTextResponse:
    """Build a browser-facing response with no exception text in the body."""
    return PlainTextResponse(
        message or _DEFAULT_HTTP_MESSAGE.get(status_code, "Error"),
        status_code=status_code,
    )


class FrontendStaticFiles(StaticFiles):
    """Serve the built frontend files, with SPA-style ``html=True`` behaviour.

    Deliberately a plain ``StaticFiles`` subclass with no routing logic. The
    ``/api`` namespace is protected one level up, by :class:`ApiAwareMount`,
    because FastAPI's own ``Mount`` re-implements ``matches()`` and would bypass
    an override placed here entirely.
    """


#: Per-language voice metadata: label, native label, STT locale and TTS locale.
LANGUAGE_DETAILS: dict[str, dict[str, str]] = {
    "en": {
        "label": "English",
        "native_label": "English",
        "stt_locale": "en-IN",
        "tts_locale": "en-IN",
    },
    "hi": {
        "label": "Hindi",
        "native_label": "हिन्दी",
        "stt_locale": "hi-IN",
        "tts_locale": "hi-IN",
    },
}

#: One-tap example questions for the empty conversation screen.
STARTER_QUESTIONS: list[dict[str, str]] = [
    {"id": "tenancy_deposit",
     "text_en": "My landlord won't return my deposit",
     "text_hi": "मेरे मकान मालिक ने जमा रकम वापस नहीं की"},
    {"id": "ipc420", "text_en": "What replaced IPC 420?",
     "text_hi": "IPC 420 की जगह कौन सा कानून आया?"},
    {"id": "police_stop", "text_en": "What are my rights if police stop me?",
     "text_hi": "पुलिस ने रोका तो मेरे क्या अधिकार हैं?"},
    {"id": "defective_product", "text_en": "I received a defective product",
     "text_hi": "मुझे टूटा हुआ सामान मिला"},
]


def _supported_languages(codes: list[str]) -> list[SupportedLanguage]:
    """Build the ``supported_languages`` payload for the configured codes."""
    languages: list[SupportedLanguage] = []
    for code in codes:
        detail = LANGUAGE_DETAILS.get(
            code, {"label": code.upper(), "native_label": code,
                   "stt_locale": code, "tts_locale": code})
        languages.append(SupportedLanguage(code=code, **detail))
    return languages


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Log startup information on the way in and a shutdown line on the way out.

    The API key itself is never logged — only whether one is configured.
    """
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    logger.info(
        "Starting %s v%s | environment=%s | host=%s | port=%d",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.environment,
        settings.HOST,
        settings.PORT,
    )
    logger.info(
        "LLM API key configured: %s | knowledge base ready: %s | static dir: %s",
        settings.is_llm_configured,
        settings.knowledge_base_ready,
        settings.STATIC_DIR,
    )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


def _build_config_response() -> PublicConfig:
    """Assemble the browser-safe public configuration payload."""
    settings = get_settings()
    # Re-read per request rather than relying on the import-time cache, so the
    # emergency database can be edited without restarting the service.
    contacts = get_emergency_contacts.cache_clear() or load_emergency_contacts()
    return PublicConfig(
        app_name=settings.APP_NAME,
        tagline=settings.APP_TAGLINE,
        description=settings.APP_DESCRIPTION,
        supported_languages=_supported_languages(settings.SUPPORTED_LANGUAGES),
        default_language=settings.DEFAULT_LANGUAGE,
        llm_configured=settings.is_llm_configured,
        knowledge_base_ready=settings.knowledge_base_ready,
        max_input_length=settings.MAX_INPUT_LENGTH,
        speech_rates=SPEECH_RATES,
        starter_questions=[StarterQuestion(**item) for item in STARTER_QUESTIONS],
        disclaimer=DISCLAIMER,
        emergency_contacts=[EmergencyContact(**contact) for contact in contacts],
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    ``redoc_url`` is disabled deliberately. FastAPI's default ReDoc page pulls
    its bundle from jsdelivr *and* a Montserrat/Roboto stylesheet from Google
    Fonts — a second, undisclosed external origin that broke the project's
    no-CDN / no-external-font rule. ``/docs`` (Swagger UI) is kept because the
    README documents it as the single developer-facing exception, and
    ``/openapi.json`` stays self-hosted and fully offline either way.
    """
    settings = get_settings()
    application = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        lifespan=lifespan,
        redoc_url=None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ORIGINS != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _register_api_routes(application)
    _register_exception_handlers(application)
    _mount_static_frontend(application)
    return application


def _register_api_routes(application: FastAPI) -> None:
    """Register the ``/api`` surface."""

    @application.get("/api/config", response_model=PublicConfig, tags=["config"])
    async def public_config() -> PublicConfig:
        """Return browser-safe frontend configuration."""
        return _build_config_response()

    application.include_router(health_router, prefix="/api")


class ApiAwareMount(fastapi_Mount):
    """Mount the frontend without shadowing the ``/api`` namespace.

    A ``Mount("/")`` returns ``Match.FULL`` for every path, so it outranks the
    ``APIRoute``'s *partial* (wrong-method) match and the router never gets a
    chance to answer. Because ``StaticFiles`` only serves files it would reply
    ``405`` to every non-GET request — including a POST to an ``/api`` path that
    does not exist, which should be an honest ``404``.

    Declining non-GET ``/api`` requests here sends them to the router's default
    handler instead, which raises that ``404``. A correctly implemented POST
    endpoint is matched before this mount is ever consulted, so adding one later
    needs no change here. GET and HEAD — everything this mount actually serves —
    are untouched.

    Note the override lives on the *mount*, not on ``StaticFiles``: FastAPI's
    own ``Mount`` re-implements ``matches()`` and would bypass a subclass of the
    static app entirely.
    """

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        """Decline non-GET ``/api`` requests so the router can answer them."""
        if (
            scope["type"] in ("http", "websocket")
            and scope.get("method") not in ("GET", "HEAD", None)
            and scope["path"].startswith("/api")
        ):
            logger.info("No API route matched %s %s", scope["method"], scope["path"])
            return Match.NONE, {}
        return super().matches(scope)


def _register_exception_handlers(application: FastAPI) -> None:
    """Add handlers that keep raw internals — tracebacks, paths, exception text —
    off the wire for every failure mode the app can produce."""

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Return JSON for API paths and HTML for browser navigation.

        The static mount rejects any non-GET request with ``405``, which would
        otherwise reach a browser as a bare status code with no body. Callers of
        the API always get a ``{"error", "message"}`` document instead.
        """
        detail = exc.detail if isinstance(exc.detail, str) else None
        if request.url.path.startswith("/api"):
            message = detail or _DEFAULT_HTTP_MESSAGE.get(
                exc.status_code, "The request could not be completed."
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": _ERROR_CODES.get(exc.status_code, "error"), "message": message},
            )
        return _plain_text_response(exc.status_code, detail or "")

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Log server-side, return a clean 500 body with no exception text."""
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": (
                    "Something went wrong while processing your request. "
                    "Please try again."
                ),
            },
        )


def _mount_static_frontend(application: FastAPI) -> None:
    """Serve the built frontend from ``STATIC_DIR`` at ``/``.

    Registered last so API routes match before the catch-all mount. A missing
    ``frontend/dist`` directory is tolerated: the API still runs and only the
    site root 404s until the frontend has been built.
    """
    static_dir = get_settings().STATIC_DIR
    if not static_dir.is_dir():
        logger.warning("Static directory %s not found; serving API only.", static_dir)
        return
    application.routes.append(
        ApiAwareMount(
            "/",
            app=FrontendStaticFiles(directory=str(static_dir), html=True),
            name="static",
        )
    )


app = create_app()

__all__ = ["app", "create_app"]
