"""Health-check router: ``GET /api/health``.

Reports that the process is alive along with the state of the local retrieval
index. It must answer successfully with no ``.env`` file, no API key and no
built knowledge base, so nothing in here may raise.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.models import NOT_BUILT_SOURCE, HealthResponse, KnowledgeBaseStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

#: Index metadata files that carry the chunk count, in preference order.
_CHUNK_COUNT_SOURCES: tuple[str, ...] = ("index_metadata.json", "metadata.json")


def _count_chunks(index_dir: Path) -> int:
    """Best-effort chunk count for a built index.

    Reads the index metadata written by the ingestion script. Any missing or
    malformed file simply yields ``0`` — health must never fail because of it.

    Args:
        index_dir: Absolute path of the built index directory.

    Returns:
        The number of indexed chunks, or ``0`` when unknown.
    """
    for filename in _CHUNK_COUNT_SOURCES:
        candidate = index_dir / filename
        try:
            with candidate.open("r", encoding="utf-8") as handle:
                payload: Any = json.load(handle)
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict):
            value = payload.get("chunk_count", payload.get("chunks"))
            if isinstance(value, int) and value >= 0:
                return value
    return 0


def _knowledge_base_status() -> dict[str, Any]:
    """Build the ``knowledge_base`` block of the health response.

    Returns:
        A dict with ``ready``, ``chunks`` and ``source`` keys.
    """
    settings = get_settings()
    ready = settings.knowledge_base_ready
    if not ready:
        return {"ready": False, "chunks": 0, "source": NOT_BUILT_SOURCE}
    chunks = _count_chunks(settings.INDEX_DIR)
    source = f"built index at {settings.INDEX_DIR.name}/ ({chunks} chunks)"
    return {"ready": True, "chunks": chunks, "source": source}


@router.get("/health", response_model=HealthResponse, summary="Service health")
async def health() -> HealthResponse:
    """Report that the service is running.

    Returns:
        A :class:`~app.models.HealthResponse` whose ``status`` is exactly the
        string ``"healthy"``.
    """
    settings = get_settings()
    logger.debug("Health check served; knowledge base ready=%s", settings.knowledge_base_ready)
    return HealthResponse(
        status="healthy",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.environment,
        knowledge_base=KnowledgeBaseStatus(**_knowledge_base_status()),
    )


__all__ = ["NOT_BUILT_SOURCE", "router"]
