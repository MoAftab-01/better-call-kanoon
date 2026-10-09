"""Shared pytest fixtures for the Better Call Kanoon test suite.

The most important job of this module is ordering: the environment is prepared
*before* ``app.main`` is imported for the first time. ``app.config`` builds its
settings object once (behind a cached accessor) and ``app.main`` freezes those
settings into the FastAPI factory at import time, so anything set afterwards
would arrive too late.

Two consequences shape what you see below:

* Every path-like setting except ``STATIC_DIR`` is redirected at a temporary
  directory, so running the suite never reads or writes the real ``data/`` or
  ``logs/`` folders in the working tree.
* ``STATIC_DIR`` deliberately keeps pointing at the real built frontend
  (``<repo>/frontend/dist``), because the suite asserts that the frontend
  really is served. Only the server mounts it; nothing writes to it.

``frontend/dist`` does not exist until the React app is built, so the two
frontend-serving tests skip — loudly and with an actionable reason — rather than
failing, until ``npm run build`` has been run in ``frontend/``. Every other
assertion runs unconditionally.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# --------------------------------------------------------------------------
# 1. Put the backend root on sys.path so `import app` and `import tests` resolve
#    even when pytest is invoked from a different working directory.
# --------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --------------------------------------------------------------------------
# 2. Prepare the environment BEFORE the application is imported anywhere.
# --------------------------------------------------------------------------

# A recognisable fake credential. It must never appear in any HTTP response;
# `tests/test_api.py` asserts exactly that.
SENTINEL_GROQ_API_KEY = "gsk_TEST_SENTINEL_MUST_NEVER_BE_ECHOED_0123456789"

# Temporary home for anything the app might want to write. Using a session-wide
# directory (rather than `tmp_path`) keeps the paths stable for the whole run.
_TMP_DATA_DIR: Path = Path(tempfile.mkdtemp(prefix="bck_test_data_"))
_TMP_INDEX_DIR: Path = Path(tempfile.mkdtemp(prefix="bck_test_index_"))
#: The built React app, at the repo root one level above this backend package.
#: Absent until `npm run build` has run in `frontend/` - hence the skips.
_REAL_STATIC_DIR: Path = PROJECT_ROOT.parent / "frontend" / "dist"

#: Reason shown when the built frontend is absent. Actionable on purpose.
FRONTEND_NOT_BUILT = "frontend/dist not built - run npm run build in frontend/"


def skip_if_frontend_not_built() -> None:
    """Skip the calling test unless the built frontend exists on disk.

    The backend serves ``<repo>/frontend/dist``. Until the React app is built
    that directory simply does not exist, so any assertion about a served
    ``index.html`` has nothing to assert against. Skipping keeps the failure
    signal honest: an absent build is a missing step, not a broken backend.
    """
    if not (_REAL_STATIC_DIR / "index.html").is_file():
        pytest.skip(FRONTEND_NOT_BUILT)


def _seed_test_data_dir() -> None:
    """Copy the read-only data files the app serves into the temp data dir.

    ``DATA_DIR`` is redirected so the suite never writes into the working tree,
    but ``emergency_contacts.json`` is *read* by ``/api/config``. Seeding it
    keeps the redirect total (nothing points at the real ``data/``) while the
    fixture data the tests assert on stays available.
    """
    source = PROJECT_ROOT / "data" / "emergency_contacts.json"
    if source.is_file():
        shutil.copy2(source, _TMP_DATA_DIR)


def _configure_test_environment() -> None:
    """Set every environment override the Stage 1 test-suite relies on.

    Uses plain ``os.environ`` assignments rather than ``setdefault`` so the
    suite is deterministic even when a developer has a populated ``.env`` file
    or exported variables in their shell. Real environment variables take
    precedence over ``.env`` entries in pydantic-settings, so a developer's
    genuine ``GROQ_API_KEY`` can never leak into an assertion here.
    """
    os.environ["APP_NAME"] = "Better Call Kanoon"
    os.environ["APP_TAGLINE"] = "Your AI guide to Indian law."
    os.environ["APP_VERSION"] = "0.1.0"

    os.environ["HOST"] = "127.0.0.1"
    os.environ["PORT"] = "8000"
    os.environ["DEBUG"] = "false"
    os.environ["CORS_ORIGINS"] = "*"

    os.environ["GROQ_API_KEY"] = SENTINEL_GROQ_API_KEY
    os.environ["GROQ_MODEL"] = ""

    os.environ["TOP_K"] = "5"
    os.environ["CANDIDATE_MULTIPLIER"] = "4"
    os.environ["RRF_K"] = "60"
    os.environ["MAX_INPUT_LENGTH"] = "1000"
    os.environ["RATE_LIMIT"] = "20"

    os.environ["DEFAULT_LANGUAGE"] = "en"
    os.environ["SUPPORTED_LANGUAGES"] = "en,hi"

    os.environ["LOG_LEVEL"] = "WARNING"

    # Redirect every writable location into a throwaway directory.
    os.environ["DATA_DIR"] = str(_TMP_DATA_DIR)
    os.environ["INDEX_DIR"] = str(_TMP_INDEX_DIR)
    os.environ["STATIC_DIR"] = str(_REAL_STATIC_DIR)


_seed_test_data_dir()
_configure_test_environment()


# --------------------------------------------------------------------------
# 3. Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Absolute path to the backend package root (``<repo>/backend``)."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def static_dir() -> Path:
    """Absolute path to the built frontend the server is expected to mount.

    Exists only after the React app has been built; the frontend-serving tests
    call :func:`skip_if_frontend_not_built` before relying on it.
    """
    return _REAL_STATIC_DIR


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """Session-scoped ``TestClient`` built from the real ASGI application.

    ``from app.main import app`` happens inside the fixture (not at module
    import time) so the environment above is guaranteed to be in place first.
    The client is used as a context manager so FastAPI's startup and shutdown
    lifespan handlers actually run, exactly as they do under uvicorn.
    """
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as test_client:
        yield test_client
