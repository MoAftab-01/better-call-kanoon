"""Pydantic v2 response models for the Stage 1 HTTP API.

Only the models this stage actually serves — health and public configuration.
Chat, retrieval and citation models arrive in a later stage.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from typing import Any

#: Reported by ``/api/health`` when the knowledge base is not ready.
#:
#: A text index alone does not make it ready - Stage 2 writes
#: ``chunks.json`` and ``index_metadata.json`` but not ``embeddings.npy``, and
#: ``settings.knowledge_base_ready`` requires all three. So this is what a
#: correctly-built Stage 2 index still reports, and it names the command rather
#: than a stage number that has already passed.
#:
#: ``"not built"`` leads deliberately: a test asserts on it, and it is the
#: honest summary in every case where this is served.
NOT_BUILT_SOURCE = (
    "not built — run scripts/ingest_laws.py, then build embeddings (Stage 3)"
)
DEFAULT_DISCLAIMER = (
    "Better Call Kanoon provides general legal information based on its "
    "available legal sources. It is not a lawyer and does not provide legal "
    "advice."
)


class KnowledgeBaseStatus(BaseModel):
    """Readiness of the local retrieval index that grounds answers."""

    ready: bool = Field(
        default=False, description="True when a built index is on disk."
    )
    chunks: int = Field(
        default=0, description="Indexed law chunks, or 0 when not built."
    )
    source: str = Field(
        default=NOT_BUILT_SOURCE, description="Origin of the knowledge base."
    )


class SupportedLanguage(BaseModel):
    """A language the voice interface can listen and speak in."""

    code: str = Field(description="ISO-style language code.", examples=["en"])
    label: str = Field(description="English name.", examples=["English"])
    native_label: str = Field(
        description="Name written in that language.", examples=["हिन्दी"]
    )
    stt_locale: str = Field(description="Speech-recognition locale.", examples=["en-IN"])
    tts_locale: str = Field(description="Speech-synthesis locale.", examples=["en-IN"])


class StarterQuestion(BaseModel):
    """A one-tap example question for the empty conversation screen."""

    id: str = Field(description="Stable identifier.", examples=["ipc420"])
    text_en: str = Field(
        description="English text.", examples=["What replaced IPC 420?"]
    )
    text_hi: str = Field(
        description="Hindi text.", examples=["IPC 420 की जगह कौन सा कानून आया?"]
    )


class EmergencyContact(BaseModel):
    """A widely published national helpline number for India.

    Informational only; verify against official Government of India sources
    before any production deployment.
    """

    id: str = Field(description="Stable identifier.", examples=["police"])
    label: str = Field(description="Short label.", examples=["Police"])
    number: str = Field(description="Dialable number.", examples=["100"])
    note: str = Field(
        default="", description="When to use this number.", examples=["Emergencies."]
    )
    source: str = Field(
        default="",
        description="Official programme behind it.",
        examples=["National Police Helpline, Ministry of Home Affairs"],
    )
    verified: bool = Field(
        default=False, description="Checked against an official source."
    )


class ChatResponse(BaseModel):
    """Response body of ``POST /api/chat`` — honest at Stage 1."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "not_available",
                "message": "Answering is not available yet. The backend answering endpoint arrives in a later stage, so nothing has been sent.",
                "question": "What replaced IPC 420?",
            }
        }
    )

    status: str = Field(
        default="not_available",
        description="Always 'not_available' at Stage 1; the endpoint cannot answer questions.",
    )
    message: str = Field(
        default="Answering is not available yet. The backend answering endpoint arrives in a later stage, so nothing has been sent.",
        description="Honest explanation delivered to the user.",
    )
    question: str = Field(
        default="",
        description="The user's question, echoed back so the caller knows it was received.",
    )


    sources: list[str] = Field(
        default_factory=list,
        description="Source file names for chunks used to answer.",
    )


class HealthResponse(BaseModel):
    """Response body of ``GET /api/health``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "service": "Better Call Kanoon",
                "version": "0.1.0",
                "environment": "production",
                "knowledge_base": {
                    "ready": False,
                    "chunks": 0,
                    "source": NOT_BUILT_SOURCE,
                },
            }
        }
    )

    status: str = Field(
        description="Exactly 'healthy' while the service is up.",
        examples=["healthy"],
    )
    service: str = Field(
        description="Service name.", examples=["Better Call Kanoon"]
    )
    version: str = Field(description="Running version.", examples=["0.1.0"])
    environment: str = Field(
        description="'local' in debug mode, otherwise 'production'.",
        examples=["production"],
    )
    knowledge_base: KnowledgeBaseStatus = Field(
        default_factory=KnowledgeBaseStatus, description="Retrieval index status."
    )


class PublicConfig(BaseModel):
    """Response body of ``GET /api/config``.

    Browser-safe: never contains an API key, a secret, an absolute filesystem
    path or any exception text.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "app_name": "Better Call Kanoon",
                "tagline": "Your AI guide to Indian law.",
                "description": (
                    "Voice-powered AI legal information grounded in Indian law."
                ),
                "default_language": "en",
                "llm_configured": False,
                "knowledge_base_ready": False,
                "max_input_length": 1000,
                "speech_rates": [0.75, 1.0, 1.25, 1.5],
            }
        }
    )

    app_name: str = Field(default="Better Call Kanoon", description="Product name.")
    tagline: str = Field(
        default="Your AI guide to Indian law.", description="One-line tagline."
    )
    description: str = Field(
        default="Voice-powered AI legal information grounded in Indian law.",
        description="One-line product description.",
    )
    supported_languages: list[SupportedLanguage] = Field(
        default_factory=list, description="Languages available for speech and text."
    )
    default_language: str = Field(
        default="en", description="Language selected on first load."
    )
    llm_configured: bool = Field(
        default=False, description="Whether the server has an LLM API key."
    )
    knowledge_base_ready: bool = Field(
        default=False, description="Whether the retrieval index is built."
    )
    max_input_length: int = Field(
        default=1000, description="Maximum accepted length of a user question."
    )
    speech_rates: list[float] = Field(
        default_factory=lambda: [0.75, 1.0, 1.25, 1.5],
        description="Playback rate multipliers for the speech controls.",
    )
    starter_questions: list[StarterQuestion] = Field(
        default_factory=list, description="One-tap example questions."
    )
    disclaimer: str = Field(
        default=DEFAULT_DISCLAIMER, description="Legal-information disclaimer."
    )
    emergency_contacts: list[EmergencyContact] = Field(
        default_factory=list, description="National helpline numbers for India."
    )


__all__ = [
    "ChatResponse",
    "EmergencyContact",
    "HealthResponse",
    "KnowledgeBaseStatus",
    "NOT_BUILT_SOURCE",
    "PublicConfig",
    "StarterQuestion",
    "SupportedLanguage",
]
