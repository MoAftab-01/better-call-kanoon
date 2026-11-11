"""Small public-only data contract. No private paths, ledgers or processed records."""
from datetime import date, datetime
import hashlib
import re
import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Hash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
DocumentID = Annotated[str, StringConstraints(pattern=r"^doc_[0-9a-f]{64}$")]
HARD_EXCLUSIONS = {"devanagari_mapping_unverified", "legacy_hindi_glyph_codes",
    "table_or_form_layout_unverified", "marginal_citation_association_unverified",
    "replacement_character", "unexpected_control", "possible_mojibake",
    "private_surrogate_or_unassigned_unicode", "invisible_or_directional_format_character",
    "duplicate_page_text", "empty_page"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return __import__('json').dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(Record):
    document_id: DocumentID
    title: str = Field(min_length=1, max_length=250)
    instrument: str = Field(min_length=1, max_length=100)
    kind: Literal['act', 'notification']
    source_url: str = Field(pattern=r'^https://egazette\.gov\.in/WriteReadData/20(?:23|24)/[0-9]+\.pdf$')
    raw_sha256: Hash
    issuing_authority: str = Field(min_length=1, max_length=250)
    publication_date: date
    physical_pages: int = Field(ge=1, le=1000, strict=True)
    edition: str = Field(min_length=1, max_length=250)
    commentary: str = Field(min_length=80, max_length=2000)
    provenance: Literal['official_gazette_identity_checked_at_preparation']
    legal_currentness: Literal['unknown'] = 'unknown'


class Page(Record):
    document_id: DocumentID
    page_id: str = Field(min_length=1, max_length=100)
    physical_page: int = Field(ge=1, le=1000, strict=True)
    text: str = Field(min_length=1, max_length=18000)
    text_sha256: Hash
    qa_flags: list[str] = Field(max_length=30)
    automatic_checks_passed: Literal[True]

    @model_validator(mode='after')
    def exact_page(self):
        if self.page_id != f'{self.document_id}:page:{self.physical_page:06d}':
            raise ValueError('Page identity mismatch')
        if sha(self.text.encode('utf-8')) != self.text_sha256 or not self.text.strip():
            raise ValueError('Page text hash mismatch')
        if set(self.qa_flags) & HARD_EXCLUSIONS:
            raise ValueError('Hard-excluded page cannot enter public research')
        if any((unicodedata.category(ch) in {'Cc','Cf','Co','Cs','Cn'} and ch not in '\n\t') or ch=='\ufffd' or '\u0900'<=ch<='\u097f' for ch in self.text):
            raise ValueError('Unsafe or unresolved character mapping')
        return self


class Passage(Record):
    passage_id: Annotated[str, StringConstraints(pattern=r'^public_[0-9a-f]{64}$')]
    document_id: DocumentID
    page_id: str = Field(min_length=1, max_length=100)
    start_line: int = Field(ge=1, le=4000, strict=True)
    end_line: int = Field(ge=1, le=4000, strict=True)
    text: str = Field(min_length=1, max_length=12000)
    text_sha256: Hash
    printed_number_unverified: str | None = Field(default=None, pattern=r'^\d{1,3}$')
    attribution: Literal['document_only'] = 'document_only'
    evidence_status: Literal['ARCHIVAL_UNVERIFIED'] = 'ARCHIVAL_UNVERIFIED'

    @model_validator(mode='after')
    def exact_identity(self):
        identity = self.model_dump(mode='json', exclude={'passage_id'})
        if self.passage_id != 'public_' + sha(canonical(identity)):
            raise ValueError('Public passage identity mismatch')
        if self.end_line < self.start_line or sha(self.text.encode()) != self.text_sha256:
            raise ValueError('Passage text or range mismatch')
        return self


class Corpus(Record):
    schema_version: Literal[1]
    sources: list[Source] = Field(min_length=1, max_length=6)
    pages: list[Page] = Field(min_length=1, max_length=404)
    passages: list[Passage] = Field(min_length=1, max_length=1000)
    legal_currentness: Literal['unknown']
    review_approval: Literal['none; publication permission is not legal evidence approval']

    @model_validator(mode='after')
    def source_bindings(self):
        sources = {s.document_id:s for s in self.sources}
        pages = {p.page_id:p for p in self.pages}
        if len(sources) != len(self.sources) or len(pages) != len(self.pages) or len({p.passage_id for p in self.passages}) != len(self.passages):
            raise ValueError('Duplicate public identity')
        for page in self.pages:
            source = sources.get(page.document_id)
            if not source or page.physical_page > source.physical_pages:
                raise ValueError('Page outside source')
        for p in self.passages:
            page = pages.get(p.page_id)
            if not page or page.document_id != p.document_id:
                raise ValueError('Passage source association mismatch')
            lines = page.text.split('\n')
            if p.end_line > len(lines) or '\n'.join(lines[p.start_line-1:p.end_line]) != p.text:
                raise ValueError('Exact page/line text differs')
            if p.printed_number_unverified and not re.match(r'^'+p.printed_number_unverified+r'\.\s',p.text):
                raise ValueError('Printed numeric start differs')
        return self


class File(Record):
    sha256: Hash
    bytes: int = Field(ge=1, le=4*1024*1024, strict=True)


class Manifest(Record):
    schema_version: Literal[1]
    status: Literal['candidate; publication requires a separate operator decision']
    files: dict[Literal['corpus.json', 'NOTICE.md'], File]
    source_count: int = Field(ge=1, le=6, strict=True)
    passage_count: int = Field(ge=1, le=1000, strict=True)
    policy: Literal['single-page-archival-public-v1']
    rights_basis: Literal['Copyright Act 1957 section 52(1)(q)(i)-(ii); conditional, not public domain']
    rights_assessment: Literal['conditional; applicable terms and statutory conditions require human review']
    exclusions: list[str] = Field(min_length=1, max_length=30)
    legal_currentness: Literal['unknown']


class PublicationDecision(Record):
    purpose: Literal['corpus_publication_only; not legal evidence approval']
    decision: Literal['approved_for_publication']
    manifest_sha256: Hash
    approved_by: str = Field(min_length=1, max_length=150)
    approved_at: datetime
    rationale: str = Field(min_length=20, max_length=2000)
    rights_review: Literal['applicable terms and statutory conditions reviewed']
    safety_review: Literal['exact payload reviewed; no private data']

    @model_validator(mode='after')
    def aware_time(self):
        if self.approved_at.tzinfo is None:
            raise ValueError('Publication decision time requires timezone')
        return self
