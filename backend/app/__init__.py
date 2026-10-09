"""Better Call Kanoon — voice-powered AI legal information assistant for Indian law.

This package exposes application metadata only. Sub-packages are intentionally
NOT imported here so that importing :mod:`app` never triggers heavy or optional
dependencies (FastAPI, pydantic-settings, retrieval libraries) and can never
create a circular import between ``app.config`` and ``app.main``.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

__all__ = ["__version__", "__app_name__"]

__version__: str = "0.1.0"
__app_name__: str = "Better Call Kanoon"
