"""API contract tests for Better Call Kanoon - Stage 1.

Stage 1 exposes exactly two API routes (``/api/health`` and ``/api/config``),
serves the built frontend from ``frontend/dist``, and ships OpenAPI docs. These
tests pin that contract down so later stages cannot break it silently.

Anything asserted here must keep working with **no** ``.env`` file, **no** API
key and **no** built retrieval index - that resilience is a hard requirement of
the health endpoint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.conftest import SENTINEL_GROQ_API_KEY, skip_if_frontend_not_built

# The exact string the health endpoint must report. Asserted literally.
EXPECTED_HEALTH_STATUS = "healthy"
EXPECTED_APP_NAME = "Better Call Kanoon"
EXPECTED_TAGLINE = "Your AI guide to Indian law."


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------


def test_health_returns_200(client: Any) -> None:
    """The health endpoint responds successfully to an unauthenticated GET."""
    response = client.get("/api/health")

    assert response.status_code == 200, response.text


def test_health_status_is_exactly_healthy(client: Any) -> None:
    """``status`` must be the literal string ``healthy`` - not a truthy stand-in."""
    response = client.get("/api/health")
    data: dict[str, Any] = response.json()

    assert data["status"] == EXPECTED_HEALTH_STATUS
    assert isinstance(data["status"], str)
    assert data["status"].strip().lower() == EXPECTED_HEALTH_STATUS


def test_health_reports_service_identity_and_version(client: Any) -> None:
    """Health output identifies the service and its version for monitoring."""
    data: dict[str, Any] = client.get("/api/health").json()

    assert data["service"] == EXPECTED_APP_NAME
    assert isinstance(data["version"], str)
    assert data["version"], "version must not be empty"
    assert data["environment"] in {"local", "production"}


def test_health_reports_knowledge_base_state(client: Any) -> None:
    """Knowledge-base block is present and honest about an unbuilt index.

    No index has been built at Stage 1, so ``ready`` is false and ``chunks`` is
    zero. The test asserts the *shape* strictly and the *values* leniently, so
    it keeps passing once an index exists.
    """
    knowledge_base: dict[str, Any] = client.get("/api/health").json()["knowledge_base"]

    assert isinstance(knowledge_base, dict)
    assert set(knowledge_base) >= {"ready", "chunks", "source"}
    assert isinstance(knowledge_base["ready"], bool)
    assert isinstance(knowledge_base["chunks"], int)
    assert isinstance(knowledge_base["source"], str)
    assert knowledge_base["chunks"] >= 0

    if knowledge_base["ready"] is False:
        assert knowledge_base["chunks"] == 0
        assert "not built" in knowledge_base["source"].lower()


def test_health_works_with_no_api_key_configured(client: Any, monkeypatch: Any) -> None:
    """Health stays healthy when the model provider key is absent.

    ``tests/conftest.py`` deliberately configures a sentinel key so the
    secret-leak test has something to look for. Here the key is blanked out and
    the endpoint is checked again - a missing credential must not turn the
    health probe red, otherwise every container restart loop would be pointless.
    """
    import app.config as config_module

    settings_object = getattr(config_module, "settings", None)
    if settings_object is None:  # pragma: no cover - depends on the accessor shape
        settings_object = config_module.get_settings()

    assert settings_object.GROQ_API_KEY == SENTINEL_GROQ_API_KEY, "sentinel key should be set"

    monkeypatch.setattr(settings_object, "GROQ_API_KEY", "")

    response = client.get("/api/health")
    data: dict[str, Any] = response.json()

    assert settings_object.GROQ_API_KEY == ""
    assert response.status_code == 200
    assert data["status"] == EXPECTED_HEALTH_STATUS
    assert data["service"] == EXPECTED_APP_NAME


def test_health_is_stable_across_repeated_calls(client: Any) -> None:
    """Repeated health probes return an identical body (no per-call drift)."""
    first = client.get("/api/health").json()
    second = client.get("/api/health").json()

    assert first == second


# ---------------------------------------------------------------------------
# GET /api/config
# ---------------------------------------------------------------------------


def test_config_returns_200(client: Any) -> None:
    """The frontend config endpoint responds successfully."""
    response = client.get("/api/config")

    assert response.status_code == 200, response.text


def test_config_contains_expected_top_level_keys(client: Any) -> None:
    """Every key the frontend bootstrap depends on is present."""
    data: dict[str, Any] = client.get("/api/config").json()

    expected_keys = {
        "app_name",
        "tagline",
        "description",
        "supported_languages",
        "default_language",
        "llm_configured",
        "knowledge_base_ready",
        "max_input_length",
        "speech_rates",
        "starter_questions",
        "disclaimer",
        "emergency_contacts",
    }
    assert expected_keys <= set(data), f"missing keys: {sorted(expected_keys - set(data))}"


def test_config_contains_branding_verbatim(client: Any) -> None:
    """Branding strings match the project contract character for character."""
    data: dict[str, Any] = client.get("/api/config").json()

    assert data["app_name"] == EXPECTED_APP_NAME
    assert data["tagline"] == EXPECTED_TAGLINE
    assert isinstance(data["description"], str) and data["description"].strip()


def test_config_never_leaks_the_api_key(client: Any) -> None:
    """No response body may echo the configured provider credential.

    ``tests/conftest.py`` sets a sentinel key in the environment. If any layer
    of the app ever serialised settings into the frontend payload, the sentinel
    would appear verbatim in the raw response text.
    """
    for path in ("/api/config", "/api/health", "/openapi.json"):
        raw = client.get(path).text
        assert SENTINEL_GROQ_API_KEY not in raw, f"{path} leaked the configured API key"
        assert "GROQ_API_KEY" not in raw, f"{path} exposed the API key setting name"


def test_config_never_leaks_secrets_or_exception_text(client: Any, project_root: Path) -> None:
    """The config payload contains no credentials, filesystem paths or traceback text."""
    data: dict[str, Any] = client.get("/api/config").json()

    assert "llm_configured" in data
    assert isinstance(data["llm_configured"], bool)
    # A configured key is summarised as a single boolean - never as its value.
    # `tests/conftest.py` sets a sentinel key for the whole session.
    assert data["llm_configured"] is True

    serialised = repr(data)
    forbidden = [
        "Traceback",
        'File "',
        "site-packages",
        str(project_root),                # absolute path to this checkout
        "data/index",                     # an index path has no place in the UI payload
        "\\",                             # nor Windows-style filesystem separators
    ]
    # The checkout directory name is usually identical to APP_NAME, which is
    # *supposed* to appear in the payload — so only assert against it when it
    # cannot collide with the branding.
    if project_root.name != data["app_name"]:
        forbidden.append(project_root.name)

    for token in forbidden:
        assert token not in serialised, f"/api/config leaked {token!r}"


def test_config_supported_languages_shape(client: Any) -> None:
    """Each supported language carries the fields the voice UI binds to."""
    data: dict[str, Any] = client.get("/api/config").json()
    languages = data["supported_languages"]

    assert isinstance(languages, list) and languages, "supported_languages must be a non-empty list"

    for language in languages:
        assert isinstance(language, dict)
        assert set(language) >= {
            "code",
            "label",
            "native_label",
            "stt_locale",
            "tts_locale",
        }
        for key in ("code", "label", "native_label", "stt_locale", "tts_locale"):
            value = language[key]
            assert isinstance(value, str) and value.strip(), f"{key} must be a string"
        # Speech-recognition and speech-synthesis locales are BCP 47 tags.
        for key in ("stt_locale", "tts_locale"):
            assert "-" in language[key], f"{key} must be a BCP 47 tag such as en-IN"
        assert language["code"] == language["code"].lower()

    codes = [language["code"] for language in languages]
    assert len(codes) == len(set(codes)), "language codes must be unique"
    assert data["default_language"] in codes


def test_config_starter_questions_shape(client: Any) -> None:
    """Starter questions are bilingual prompts the landing screen offers."""
    data: dict[str, Any] = client.get("/api/config").json()
    questions = data["starter_questions"]

    assert isinstance(questions, list) and questions, "starter_questions must be a non-empty list"

    identifiers: list[str] = []
    for question in questions:
        assert isinstance(question, dict)
        assert set(question) >= {"id", "text_en", "text_hi"}
        for key in ("id", "text_en", "text_hi"):
            value = question[key]
            assert isinstance(value, str) and value.strip(), f"{key} must be a string"
        identifiers.append(question["id"])

    assert len(identifiers) == len(set(identifiers)), "starter question ids must be unique"


def test_config_emergency_contacts_are_well_formed(client: Any) -> None:
    """Emergency helpline entries are complete and the numbers are digits."""
    data: dict[str, Any] = client.get("/api/config").json()
    contacts = data["emergency_contacts"]

    assert isinstance(contacts, list) and contacts, "emergency_contacts must be a non-empty list"

    seen_numbers: set[str] = set()
    for contact in contacts:
        assert isinstance(contact, dict)
        assert "id" in contact and str(contact["id"]).strip(), "each contact needs an id"
        assert "label" in contact and str(contact["label"]).strip(), "each contact needs a label"
        assert "number" in contact and str(contact["number"]).strip(), "each contact needs a number"

        number = str(contact["number"])
        assert number.isdigit(), f"helpline number {number!r} must contain digits only"
        assert number not in seen_numbers, f"duplicate helpline number {number}"
        seen_numbers.add(number)

        assert "note" in contact
        assert isinstance(contact["source"], str) and contact["source"].strip()
        assert isinstance(contact["verified"], bool)


def test_config_speech_rates_shape(client: Any) -> None:
    """Speech-rate choices are positive floats, as the audio player expects."""
    rates: list[Any] = client.get("/api/config").json()["speech_rates"]

    assert isinstance(rates, list) and rates
    for rate in rates:
        assert isinstance(rate, (int, float))
        assert not isinstance(rate, bool)
        assert 0.1 < rate < 5.0


def test_config_max_input_length_is_a_positive_int(client: Any) -> None:
    """The input-length cap the frontend enforces is a sane positive integer."""
    max_input_length: Any = client.get("/api/config").json()["max_input_length"]

    assert isinstance(max_input_length, int)
    assert not isinstance(max_input_length, bool)
    assert max_input_length > 0


def test_config_disclaimer_avoids_lawyer_claims(client: Any) -> None:
    """The disclaimer states plainly that this is information, not advice."""
    disclaimer: str = client.get("/api/config").json()["disclaimer"]

    assert isinstance(disclaimer, str) and disclaimer.strip()
    assert "not a lawyer" in disclaimer.lower()


@pytest.mark.parametrize(
    "forbidden_phrase",
    ["ai lawyer", "your lawyer", "virtual lawyer", "i am your lawyer"],
)
def test_config_contains_no_lawyer_branding(client: Any, forbidden_phrase: str) -> None:
    """Contract guardrail: the app never presents itself as a lawyer."""
    raw = client.get("/api/config").text.lower()

    assert forbidden_phrase not in raw, f"/api/config must not contain {forbidden_phrase!r}"


# ---------------------------------------------------------------------------
# Frontend static mount
# ---------------------------------------------------------------------------


def test_frontend_index_is_served_at_root(client: Any) -> None:
    """The built frontend is mounted at ``/`` and serves the index page."""
    skip_if_frontend_not_built()

    response = client.get("/")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    assert EXPECTED_APP_NAME in response.text


def test_frontend_unknown_path_does_not_return_a_traceback(client: Any) -> None:
    """An unknown *page* route never dumps a Python traceback at the browser."""
    skip_if_frontend_not_built()

    response = client.get("/this-page-does-not-exist")

    assert "Traceback" not in response.text
    assert "File \"" not in response.text


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_unknown_api_path_returns_json_not_html(client: Any) -> None:
    """An unknown API path yields a JSON body, never an HTML error page."""
    response = client.get("/api/definitely-not-a-real-endpoint")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert "Traceback" not in response.text

    body: dict[str, Any] = response.json()
    assert "detail" in body or "error" in body


def test_wrong_method_on_api_route_returns_json(client: Any) -> None:
    """A correct 405 is fine; what matters is that it stays JSON."""
    response = client.post("/api/health")

    assert response.status_code == 405
    assert "Traceback" not in response.text
    assert response.headers["content-type"].startswith("application/json")


# ---------------------------------------------------------------------------
# OpenAPI documentation
# ---------------------------------------------------------------------------


def test_openapi_schema_is_served(client: Any) -> None:
    """FastAPI's generated OpenAPI schema is reachable and self-describing."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    schema: dict[str, Any] = response.json()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == EXPECTED_APP_NAME
    assert "/api/health" in schema["paths"]
    assert "/api/config" in schema["paths"]


def test_docs_page_is_served(client: Any) -> None:
    """The interactive API documentation page loads."""
    response = client.get("/docs")

    assert response.status_code == 200


def test_redoc_page_is_disabled(client: Any) -> None:
    """``/redoc`` must not be served - it leaks a Google Fonts stylesheet.

    FastAPI's default ReDoc page pulls its bundle from jsdelivr and a
    Montserrat/Roboto stylesheet from fonts.googleapis.com. The second origin
    was never disclosed, and it breaks the project's no-CDN / no-external-font
    rule outright. ``create_app`` therefore sets ``redoc_url=None``.

    This is a contract test, not a style preference: if a future FastAPI
    upgrade or a well-meaning edit re-enables the page, this fails loudly rather
    than silently restoring the external font fetch.
    """
    response = client.get("/redoc")

    assert response.status_code == 404, (
        "/redoc must stay disabled: it loads a stylesheet from fonts.googleapis.com, "
        "which violates the no-external-font rule. /docs and /openapi.json remain "
        "available and are the documented developer surface."
    )


def test_no_page_references_an_external_font_origin(client: Any) -> None:
    """No served HTML page may reference Google Fonts or a remote stylesheet.

    ``/docs`` is the one documented exception, and it is allowed to reference
    jsdelivr for the Swagger UI bundle. Google Fonts is never acceptable, on
    any page, because the product ships its own local typography.
    """
    for path in ("/", "/docs", "/openapi.json"):
        body = client.get(path).text
        assert "fonts.googleapis.com" not in body, f"{path} loads an external font stylesheet"
        assert "fonts.gstatic.com" not in body, f"{path} loads external font files"


# ---------------------------------------------------------------------------
# Stage gating
# ---------------------------------------------------------------------------


def test_chat_endpoint_is_not_implemented_yet(client: Any) -> None:
    """No ``/api/chat`` route exists at Stage 1 - and that is deliberate.

    The chat endpoint arrives in a later stage, once the retrieval pipeline and
    the model client exist. A stub that returned a fabricated answer would be
    worse than no endpoint at all, so the contract here is a clean 404 until the
    real implementation lands. When it ships, DELETE this test.
    """
    assert "/api/chat" not in client.get("/openapi.json").json()["paths"]

    response = client.post("/api/chat", json={"query": "What is IPC 420?"})

    assert response.status_code == 404, (
        "/api/chat must not exist in Stage 1; it is introduced in a later stage "
        "with a real retrieval-backed implementation."
    )
