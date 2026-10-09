"""Application settings for Better Call Kanoon — the single source of truth for
every environment variable used by the backend.

Path-like settings resolve against the absolute backend root
(``<repo>/backend/app/config.py`` -> ``<repo>/backend``) so behaviour does not
depend on the process working directory. ``STATIC_DIR`` is the one exception:
it defaults to ``<repo>/frontend/dist``, the Vite build output the backend
serves. This module imports nothing from FastAPI and nothing from
``app.api`` / ``app.rag`` / ``app.llm``, so any module may import it first
without creating a circular import.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

#: Absolute backend root — the directory containing the ``app`` package.
#:
#: Resolves to ``<repo>/backend``. ``DATA_DIR`` and ``INDEX_DIR`` hang off it;
#: the built frontend lives one level up, in ``<repo>/frontend/dist``.
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

#: Emergency contact database filename, relative to ``DATA_DIR``.
EMERGENCY_CONTACTS_FILENAME: str = "emergency_contacts.json"

#: Index artefacts that must all exist for the knowledge base to count as built.
INDEX_ARTEFACTS: tuple[str, ...] = ("chunks.json", "embeddings.npy", "index_metadata.json")

_TRUE_VALUES: frozenset[str] = frozenset({"true", "1", "yes", "y", "on", "t"})
_FALSE_VALUES: frozenset[str] = frozenset({"false", "0", "no", "n", "off", "f"})

#: A ``list[str]`` read from a plain comma-separated env var.
#:
#: pydantic-settings JSON-decodes any complex field before a ``mode="before"``
#: validator runs, so a bare ``CORS_ORIGINS="*"`` would die inside ``json.loads``
#: and ``Settings()`` could not be constructed at all. ``Annotated[..., NoDecode]``
#: opts the field out of that step and hands the raw string to ``_parse_str_list``.
#: JSON input such as ``CORS_ORIGINS='["http://a", "http://b"]'`` still works:
#: a string that starts with ``[`` is parsed as JSON, everything else as CSV.
CommaSeparatedList = Annotated[list[str], NoDecode]
_CSV_JSON_PREFIXES: tuple[str, ...] = ("[",)


def _parse_bool(value: Any) -> bool:
    """Parse an env string as a bool; accepts true/1/yes and false/0/no, any case."""
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    raise ValueError(f"Cannot interpret {value!r} as a boolean value.")


def _parse_str_list(value: Any) -> list[str]:
    """Parse a comma-separated env string into a list of strings.

    ``"en,hi"`` becomes ``["en", "hi"]`` and an empty string becomes ``[]``.
    A JSON array literal is also accepted so a value such as
    ``CORS_ORIGINS='["http://localhost:5173"]'`` works too.
    """
    if isinstance(value, (list, tuple, set)):
        parts: list[Any] = list(value)
    else:
        text = str(value or "").strip()
        if text.startswith(_CSV_JSON_PREFIXES):
            try:
                decoded = json.loads(text)
            except ValueError:
                decoded = None
            parts = decoded if isinstance(decoded, list) else text.split(",")
        else:
            parts = text.split(",")
    return [item for item in (str(part).strip() for part in parts) if item]


class Settings(BaseSettings):
    """Typed settings read from the environment and ``.env``.

    No field is mandatory and every default works, so the service starts and
    ``/api/health`` reports healthy with no ``.env``, no API key and no index.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # Branding
    APP_NAME: str = "Better Call Kanoon"
    APP_TAGLINE: str = "Your AI guide to Indian law."
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "Voice-powered AI legal information grounded in Indian law."
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    # Networking
    #: Browser origins allowed to call this API.
    #:
    #: Defaults to the local Vite dev server only. In production the built
    #: frontend is served by this same process, so the browser sees one origin
    #: and CORS never applies. The wildcard ``["*"]`` is deliberately NOT the
    #: default: it would let any website on the internet read this API's
    #: responses from a user's browser. Set it explicitly if you truly need it.
    CORS_ORIGINS: CommaSeparatedList = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    # Large language model (optional — never required to start)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = ""
    # Retrieval
    TOP_K: int = 5
    #: How many candidates to pull from each retriever before fusing.
    #: Fusion can only rerank what it is given, so this multiplies ``TOP_K``.
    #: **Not validated** - no recall measurement stands behind the value.
    CANDIDATE_MULTIPLIER: int = 4
    #: Reciprocal-rank-fusion damping constant. 60 is the value from the
    #: original RRF paper; it is **not** tuned for this corpus.
    RRF_K: float = 60.0
    #: The embedding model is read from here and never hardcoded in source, so
    #: a model that is withdrawn can be swapped without a code change. The
    #: backend that consumes it is **not installed**, so nothing reads this
    #: yet - see the Stage 3 note in the README.
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Request limits
    MAX_INPUT_LENGTH: int = 1000
    #: Requests allowed per window per client. **Not enforced yet** - the
    #: middleware that will read this arrives with the chat endpoint in a
    #: later stage. Declared now so the value is configurable from the start
    #: rather than hardcoded when the limiter lands.
    RATE_LIMIT: int = 20
    # Localisation
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: CommaSeparatedList = Field(default_factory=lambda: ["en", "hi"])
    # Filesystem
    DATA_DIR: Path = Field(default_factory=lambda: PROJECT_ROOT / "data")
    #: Built frontend. Defaults to the Vite build output in the sibling
    #: ``frontend/`` package at the repo root, NOT a folder inside ``backend/``.
    STATIC_DIR: Path = Field(default_factory=lambda: PROJECT_ROOT.parent / "frontend" / "dist")
    INDEX_DIR: Path = Field(default_factory=lambda: PROJECT_ROOT / "data" / "index")

    _coerce_debug = field_validator("DEBUG", mode="before")(_parse_bool)
    _coerce_cors = field_validator("CORS_ORIGINS", mode="before")(_parse_str_list)
    _coerce_langs = field_validator("SUPPORTED_LANGUAGES", mode="before")(_parse_str_list)

    @field_validator("DATA_DIR", "STATIC_DIR", "INDEX_DIR", mode="after")
    @classmethod
    def _absolutise_paths(cls, value: Path) -> Path:
        """Resolve a directory field to an absolute path under the project root."""
        path = Path(value).expanduser()
        return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()

    @property
    def is_llm_configured(self) -> bool:
        """Whether an LLM API key is available on the server."""
        return bool(self.GROQ_API_KEY.strip())

    @property
    def knowledge_base_ready(self) -> bool:
        """Whether ``INDEX_DIR`` holds every artefact of a built index."""
        if not self.INDEX_DIR.is_dir():
            return False
        return all((self.INDEX_DIR / name).is_file() for name in INDEX_ARTEFACTS)

    @property
    def environment(self) -> str:
        """``"local"`` when ``DEBUG`` is on, otherwise ``"production"``."""
        return "local" if self.DEBUG else "production"

    @property
    def emergency_contacts_path(self) -> Path:
        """Absolute path of the emergency contact JSON file."""
        return self.DATA_DIR / EMERGENCY_CONTACTS_FILENAME


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached :class:`Settings` instance.

    Built once so every module sees the same configuration; call
    ``get_settings.cache_clear()`` after mutating the environment in a test.
    """
    return Settings()


def load_emergency_contacts() -> list[dict[str, Any]]:
    """Load the emergency contact database as a list of dicts.

    The file is data, not code, and stays editable without touching the LLM.
    Any read or parse failure yields ``[]``, so a missing helpline file can
    never stop the service from starting.
    """
    try:
        path = get_settings().emergency_contacts_path
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return []

    raw = payload.get("contacts") if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        return []
    return [
        {
            "id": str(item.get("id", "")),
            "label": str(item.get("label", "")),
            "number": str(item.get("number", "")),
            "note": str(item.get("note", "")),
            "source": str(item.get("source", "")),
            "verified": bool(item.get("verified", False)),
        }
        for item in raw
        if isinstance(item, dict)
    ]


@lru_cache(maxsize=1)
def get_emergency_contacts() -> tuple[dict[str, Any], ...]:
    """Return the emergency contacts, read from disk at most once per process."""
    return tuple(load_emergency_contacts())


__all__ = [
    "PROJECT_ROOT",
    "Settings",
    "get_emergency_contacts",
    "get_settings",
    "load_emergency_contacts",
]
