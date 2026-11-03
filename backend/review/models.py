"""Strict, hash-bound review records; no field defaults to an approval."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from backend.app.ingestion.models import LegalMetadata
from backend.app.ingestion.paths import validate_relative_path

Hash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
CandidateID = Annotated[str, StringConstraints(pattern=r"^passage_[0-9a-f]{64}$")]
DocumentID = Annotated[str, StringConstraints(pattern=r"^doc_[0-9a-f]{64}$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
DecisionName = Literal["pending", "approved", "rejected", "needs_correction"]


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @field_validator("schema_version", mode="before", check_fields=False)
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("schema_version must be integer 1")
        return value


class Span(StrictRecord):
    page_id: Text
    physical_page: int = Field(ge=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    text_sha256: Hash

    @model_validator(mode="after")
    def ordered_lines(self):
        if self.end_line < self.start_line:
            raise ValueError("Reversed line boundaries")
        return self


class Attribution(StrictRecord):
    kind: Literal["document_only", "printed_label"]
    label: Text | None = None
    anchor: Span | None = None

    @model_validator(mode="after")
    def explicit_or_unknown(self):
        if self.kind == "document_only" and (self.label is not None or self.anchor is not None):
            raise ValueError("Document-only attribution cannot assert a section label")
        if self.kind == "printed_label" and (self.label is None or self.anchor is None):
            raise ValueError("A printed label requires exact source evidence")
        return self


class Candidate(StrictRecord):
    schema_version: Literal[1] = 1
    candidate_id: CandidateID
    catalog_sha256: Hash
    qa_sha256: Hash
    document_id: DocumentID
    raw_path: Text
    raw_sha256: Hash
    processed_path: Text
    processed_sha256: Hash
    source_metadata: LegalMetadata
    original_identifiers: dict
    scope: Literal["archival_text_only"] = "archival_text_only"
    provenance_status: Literal["user_supplied"] = "user_supplied"
    verification_status: Literal["not_independently_verified"] = "not_independently_verified"
    legal_currentness: Literal["unknown"] = "unknown"
    spans: list[Span] = Field(min_length=1, max_length=3)
    context_spans: list[Span] = Field(min_length=1, max_length=6)
    passage_sha256: Hash
    context_sha256: Hash
    context_rationale: Text
    cross_page_context: Text | None = None
    attribution: Attribution

    @field_validator("raw_path", "processed_path")
    @classmethod
    def relative_paths(cls, value):
        validate_relative_path(value)
        return value


class EvidenceReference(StrictRecord):
    kind: Literal["rendered_pdf_page", "qa_report", "context_review"]
    file_path: Text
    sha256: Hash
    physical_pages: list[int] = Field(min_length=1, max_length=6)
    note: Text

    @field_validator("file_path")
    @classmethod
    def relative_path(cls, value):
        validate_relative_path(value)
        return value

    @field_validator("physical_pages")
    @classmethod
    def positive_pages(cls, value):
        if any(n < 1 for n in value) or len(set(value)) != len(value):
            raise ValueError("Evidence pages must be positive and unique")
        return value


class Attestations(StrictRecord):
    visual_comparison_performed: bool = False
    boundaries_and_attribution_verified: bool = False
    qualifiers_and_exceptions_preserved: bool = False
    archival_scope_only: bool = False
    cross_page_context_verified: bool = False


class Decision(StrictRecord):
    decision: DecisionName
    reviewer_id: Text
    decision_time: AwareDatetime
    rationale: Text
    evidence: list[EvidenceReference] = Field(min_length=1, max_length=12)
    attestations: Attestations = Field(default_factory=Attestations)

    @field_validator("decision_time", mode="before")
    @classmethod
    def absolute_utc_time(cls, value):
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Decision time must include an explicit timezone")
        return value.astimezone(timezone.utc)


class Event(StrictRecord):
    schema_version: Literal[1] = 1
    sequence: int = Field(ge=1)
    previous_sha256: Hash
    candidate_id: CandidateID
    candidate: Candidate | None
    review: Decision
    event_sha256: Hash
