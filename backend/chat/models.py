from typing import Literal
from uuid import UUID
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Turn(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1200, strict=True)


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=2000, strict=True)
    conversation_id: UUID | None = None
    history: list[Turn] = Field(default_factory=list, max_length=6)
    top_k: int = Field(default=3, ge=1, le=5, strict=True)
    source_ids: list[str] | None = Field(default=None, max_length=6)

    @field_validator("source_ids")
    @classmethod
    def source_id_shape(cls, value):
        if value is not None and (len(value) != len(set(value)) or
                any(not re.fullmatch(r"doc_[0-9a-f]{64}", s) for s in value)):
            raise ValueError("Use unique source document IDs")
        return value

    @field_validator("message")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("A question is required")
        return value.strip()


class Citation(StrictModel):
    id: str
    candidate_id: str
    document_id: str
    title: str
    instrument: str
    source_url: str | None
    issuing_authority: str | None
    publication_date: str | None
    pdf_page: int
    page_id: str
    start_line: int
    end_line: int
    quote: str
    raw_sha256: str
    processed_sha256: str
    text_sha256: str
    catalog_sha256: str
    qa_sha256: str
    evidence_status: Literal["ARCHIVAL_UNVERIFIED"] = "ARCHIVAL_UNVERIFIED"
    attribution: Literal["document_only", "printed_label"] = "document_only"
    printed_number_unverified: str | None = None
    qa_flags: list[str] = Field(default_factory=list)
    context_text: str = ""
    context_text_sha256: str = ""
    version_description: str = "original archival source; currentness unknown"


class ProviderStatus(StrictModel):
    provider: Literal["groq"] = "groq"
    model: str | None
    status: Literal["not_configured", "completed", "not_called", "rejected_output"]
    generation_mode: Literal["extractive", "extractive_model_selection"]


class ChatResponse(StrictModel):
    answer: str
    conversation_id: UUID
    evidence_status: Literal["VERIFIED_REVIEWED", "ARCHIVAL_UNVERIFIED", "INSUFFICIENT_EVIDENCE"]
    citations: list[Citation]
    provider: ProviderStatus
    retrieval_mode: Literal["bm25", "hybrid"] = "bm25"
    warnings: list[str]
    legal_currentness: Literal["unknown"] = "unknown"


class Selection(StrictModel):
    source_ids: list[str] = Field(max_length=3)
