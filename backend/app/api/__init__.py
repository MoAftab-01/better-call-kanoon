"""HTTP routers for the Better Call Kanoon API.

This module intentionally exposes no routers at import time. ``app.main``
imports the individual router modules (``app.api.health``) directly, which keeps
the dependency direction one-way — ``main -> health -> config/models`` — and
makes a circular import impossible.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

__all__: list[str] = []
