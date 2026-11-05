from uuid import uuid4
from starlette.concurrency import run_in_threadpool

from backend.retrieval.engine import ArchivalIndex, ROOT
from .models import ChatResponse, Citation, ProviderStatus
from .provider import GroqProvider, ProviderError, Settings

LIMITATIONS = ["Archival source text only; not human-approved legal evidence.",
    "Current amendments, commencement changes and case-specific applicability are unknown.",
    "English operative paragraphs only; Hindi extraction and table/form associations remain unresolved."]


class ChatService:
    def __init__(self, index=None, settings=None, provider=None):
        self.index = index if index is not None else ArchivalIndex(ROOT)
        self.settings = settings if settings is not None else Settings.from_environment()
        self.provider = provider if provider is not None else GroqProvider(self.settings)

    def status(self):
        return dict(available=True, retrieval=self.index.status(),
            provider_configured=self.settings.configured,
            answer_mode="Groq selects bounded evidence; server quotes exact sources" if self.settings.configured else "Extractive archival mode; Groq key/model not configured",
            privacy="Questions, bounded history and cited paragraphs go to Groq only when configured. No server conversation persistence.")

    @staticmethod
    def citation(passage, number):
        c = passage.candidate
        s = c.spans[0]
        return Citation(id="E" + str(number), candidate_id=c.candidate_id,
            document_id=c.document_id, title=passage.title, instrument=passage.instrument,
            source_url=c.source_metadata.source_url, issuing_authority=c.source_metadata.issuing_authority,
            publication_date=str(c.source_metadata.publication_date) if c.source_metadata.publication_date else None,
            pdf_page=s.physical_page, page_id=s.page_id, start_line=s.start_line, end_line=s.end_line,
            quote=passage.text, raw_sha256=c.raw_sha256, processed_sha256=c.processed_sha256,
            text_sha256=s.text_sha256, catalog_sha256=c.catalog_sha256, qa_sha256=c.qa_sha256)

    async def answer(self, request):
        identifier = request.conversation_id or uuid4()
        hits = await run_in_threadpool(self.index.search, request.message)
        provider = ProviderStatus(model=self.settings.model or None, status="not_called", generation_mode="extractive")
        warnings = list(LIMITATIONS)
        if not hits:
            return ChatResponse(answer="I do not have adequate validated source support for that question. "
                "This demo covers archival BNS, BNSS and BSA commencement notifications only. "
                "Ask what one of those notifications states; I cannot determine your current rights or obligations.",
                conversation_id=identifier, evidence_status="INSUFFICIENT_EVIDENCE", citations=[], provider=provider, warnings=warnings)
        citations = [self.citation(p, i) for i, p in enumerate(hits, 1)]
        if self.settings.configured:
            selected = await self.provider.select(request.message, request.history, citations)
            if selected is None:
                provider.status = "rejected_output"
                warnings.append("The model output failed validation; only deterministic source quotations are shown.")
            else:
                provider.status = "completed"
                provider.generation_mode = "extractive_model_selection"
                citations = [c for c in citations if c.id in selected]
        else:
            provider.status = "not_configured"
            warnings.append("Groq is not configured; this is deterministic extraction, not live model inference.")
        # Source edits during the model call invalidate even an already-ranked hit.
        fresh = {p.candidate.candidate_id for p in await run_in_threadpool(self.index.search, request.message)}
        if any(c.candidate_id not in fresh for c in citations):
            raise ProviderError("source_changed", 409)
        if not citations:
            return ChatResponse(answer="The available archival paragraphs do not adequately support an answer. Please name the notification you want to inspect.",
                conversation_id=identifier, evidence_status="INSUFFICIENT_EVIDENCE", citations=[], provider=provider, warnings=warnings)
        answer = "The following is what the archived source document states; this is not a current-law determination.\n\n"
        answer += "\n\n".join(f"[{c.id}] {c.instrument or c.title} (physical PDF page {c.pdf_page}):\n{c.quote}" for c in citations)
        answer += "\n\nThese original notifications alone do not establish present commencement, applicability or your legal rights."
        return ChatResponse(answer=answer, conversation_id=identifier, evidence_status="ARCHIVAL_UNVERIFIED",
            citations=citations, provider=provider, warnings=warnings)
