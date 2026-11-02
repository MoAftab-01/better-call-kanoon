"""Explicit input claims and inspectable extraction records."""

import re
from datetime import date
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
InstrumentType = Literal[
    "act", "rule", "regulation", "notification", "judgment", "order",
    "circular", "constitution", "ordinance", "other", "unknown",
]
SourceType = Literal[
    "official_portal", "official_gazette", "official_court", "government_portal",
    "user_supplied", "secondary", "synthetic", "unknown",
]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class SuppliedProvenance(Record):
    supplied_by: NonEmpty
    verification_claim: Literal["unverified", "user_claimed_verified"] = "unverified"
    verification_evidence: NonEmpty | None = None
    notes: NonEmpty | None = None

    @model_validator(mode="after")
    def require_claim_evidence(self):
        if self.verification_claim == "user_claimed_verified" and not self.verification_evidence:
            raise ValueError("A user verification claim requires user-supplied evidence or notes.")
        return self


class LegalMetadata(Record):
    official_title: NonEmpty
    instrument_type: InstrumentType
    jurisdiction: NonEmpty | None
    state: NonEmpty | None = None
    issuing_authority: NonEmpty | None
    source_url: str | None
    source_type: SourceType
    retrieval_date: date | None = None
    enactment_date: date | None = None
    publication_date: date | None = None
    effective_date: date | None = None
    amendment_version: NonEmpty | None = None
    legal_applicability: NonEmpty | None = None
    language: Annotated[str, StringConstraints(pattern=r"^(?:[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*|unknown)$")]
    provenance: SuppliedProvenance

    @field_validator("source_url")
    @classmethod
    def preserve_valid_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value or len(value) > 8192 or any(c.isspace() or ord(c) < 32 for c in value):
            raise ValueError("source_url must be an HTTP(S) URL without whitespace or controls.")
        try:
            parsed = urlsplit(value)
            valid = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            valid = valid and parsed.username is None and parsed.password is None
            _ = parsed.port
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("source_url must be an HTTP(S) URL without embedded credentials.")
        return value  # Deliberately do not canonicalize the original URL.

    @field_validator("retrieval_date", "enactment_date", "publication_date", "effective_date", mode="before")
    @classmethod
    def require_calendar_date(cls, value):
        if value is None or type(value) is date:
            return value
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Dates must be YYYY-MM-DD or null; no inferred or numeric dates.")
        return value


class ManifestEntry(Record):
    file_path: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    metadata: LegalMetadata
    expected_sha256: Sha256 | None = None

    @field_validator("file_path")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        from .paths import validate_relative_path

        validate_relative_path(value)
        return value


class DocumentManifest(Record):
    schema_version: Literal[1]
    documents: list[ManifestEntry] = Field(min_length=1, max_length=100)

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("schema_version must be the integer 1.")
        return value


class SourceFile(Record):
    sha256: Sha256
    media_type: Literal["application/pdf", "text/plain"]
    size_bytes: int = Field(gt=0)


class ExtractedPage(Record):
    page_id: str
    ordinal: int = Field(ge=1)
    page_number: int | None = Field(default=None, ge=1)
    text: str
    warnings: list[str] = Field(default_factory=list)


class ExtractedSection(Record):
    section_id: str
    page_id: str
    page_number: int | None = Field(default=None, ge=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    identifier: str | None = None
    heading: str | None = None
    text: str
    structure_status: Literal["candidate", "unidentified"]
    uncertainties: list[str]


class ExtractionInfo(Record):
    engine: str
    engine_version: str
    pipeline_version: Literal["stage2a-v1"] = "stage2a-v1"
    normalization: Literal["line-endings-and-trailing-horizontal-whitespace-only"] = (
        "line-endings-and-trailing-horizontal-whitespace-only"
    )


class LegalDocument(Record):
    schema_version: Literal[1] = 1
    document_id: Annotated[str, StringConstraints(pattern=r"^doc_[0-9a-f]{64}$")]
    metadata: LegalMetadata
    source_file: SourceFile
    ingested_at: AwareDatetime
    provenance_status: Literal["user_supplied"] = "user_supplied"
    verification_status: Literal["not_independently_verified"] = "not_independently_verified"
    extraction: ExtractionInfo
    pages: list[ExtractedPage]
    sections: list[ExtractedSection]
    warnings: list[str]
