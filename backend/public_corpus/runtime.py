"""Bounded BM25 runtime: only manifest files, with an external publication pin.

No ingestion, private evidence catalogue, PDF parser or ML library is imported.
An offline preview is explicit and never used by the HTTP application factory.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import re
import time

from backend.retrieval.scoring import BM25, query_policy, tokens
from .models import Corpus, Manifest, PublicationDecision, sha


def unique(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def read(path, limit):
    p = Path(path).absolute()
    if any(q.is_symlink() or (hasattr(q, 'is_junction') and q.is_junction()) for q in [p,*p.parents]):
        raise ValueError('Reparse paths are not allowed')
    if not p.is_file() or p.stat().st_size > limit:
        raise ValueError('Missing or oversized corpus file')
    with p.open('rb') as f:
        data = f.read(limit+1)
    if len(data)>limit:
        raise ValueError('Corpus size changed')
    return data


def parse(data):
    try:
        return json.loads(data.decode('utf-8'),object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON number')))
    except RecursionError:
        raise ValueError('Public JSON exceeds supported nesting') from None


def load(directory, expected_sha256, decision_file=None, decision_sha256=None, *, preview=False):
    if not re.fullmatch(r'[0-9a-f]{64}',expected_sha256 or ''):
        raise ValueError('Explicit publication manifest pin required')
    root = Path(directory)
    payload = read(root/'manifest.json', 128*1024)
    if sha(payload) != expected_sha256:
        raise ValueError('Publication manifest hash mismatch')
    manifest = Manifest.model_validate(parse(payload))
    if set(manifest.files) != {'corpus.json','NOTICE.md'}:
        raise ValueError('Complete publication inventory required')
    if {p.name for p in root.iterdir()} != {'manifest.json',*manifest.files}:
        raise ValueError('Unauthorized corpus files')
    if not preview:
        if not decision_file or not re.fullmatch(r'[0-9a-f]{64}',decision_sha256 or ''):
            raise ValueError('Explicit separately pinned publication decision required')
        decision = read(decision_file, 8192)
        if sha(decision) != decision_sha256:
            raise ValueError('Publication decision hash mismatch')
        record = PublicationDecision.model_validate(parse(decision))
        if record.manifest_sha256 != expected_sha256:
            raise ValueError('Publication decision covers another corpus')
    blobs = {}
    for name,entry in manifest.files.items():
        blob = read(root/name,4*1024*1024)
        if len(blob) != entry.bytes or sha(blob) != entry.sha256:
            raise ValueError('Corpus file hash/size mismatch')
        blobs[name] = blob
    if not blobs['NOTICE.md'].strip():
        raise ValueError('Publication commentary/notice required')
    corpus = Corpus.model_validate(parse(blobs['corpus.json']))
    if len(corpus.sources) != manifest.source_count or len(corpus.passages) != manifest.passage_count:
        raise ValueError('Publication inventory count differs')
    return manifest,corpus


@dataclass(frozen=True)
class PublicHit:
    record: object
    source: object
    page: object

    @property
    def identifier(self):
        return self.record.passage_id


class PublicIndex:
    mode = 'bm25'
    public_runtime = True

    def __init__(self, directory, manifest_sha256, decision_file=None, decision_sha256=None, *, preview=False):
        self.directory,self.manifest_sha256 = directory,manifest_sha256
        self.decision_file,self.decision_sha256,self.preview = decision_file,decision_sha256,preview
        self.passages = []
        self.corpus = None
        self.reason = 'Public corpus is missing, invalid, or lacks a separately pinned publication decision.'
        started = time.perf_counter()
        try:
            _,self.corpus = load(directory,manifest_sha256,decision_file,decision_sha256,preview=preview)
            sources = {s.document_id:s for s in self.corpus.sources}
            pages = {p.page_id:p for p in self.corpus.pages}
            self.passages = [PublicHit(r,sources[r.document_id],pages[r.page_id]) for r in self.corpus.passages]
            self.reason = 'Unreviewed archival source text; currentness unknown.'
        except (ValueError,OSError,TypeError):
            self.passages = []
        self.bm25 = BM25([p.record.text+' '+p.source.title+' '+p.source.instrument for p in self.passages])
        self.startup_seconds = time.perf_counter()-started

    def valid(self):
        if not self.passages:
            return False
        try:
            # Revalidate exact bytes and the publication decision, including after inference.
            _,live = load(self.directory,self.manifest_sha256,self.decision_file,self.decision_sha256,preview=self.preview)
            return live == self.corpus
        except (ValueError,OSError,TypeError):
            return False

    def search(self, question, limit=3, max_characters=12000, *, source_ids=None, mode=None):
        if type(limit) is not int or not 1 <= limit <= 5:
            raise ValueError('top-k must be 1-5')
        policy = query_policy(question)
        if not policy or not self.valid():
            return []
        specific,requested,printed,notification = policy
        ranked = sorted(enumerate(self.bm25.scores(question)),key=lambda pair:(-pair[1],self.passages[pair[0]].identifier))
        found,total = [],0
        for number,score in ranked:
            p = self.passages[number];r,s = p.record,p.source
            topic = {'S.O. 850(E)':'topic_bns','S.O. 848(E)':'topic_bnss','S.O. 849(E)':'topic_bsa'}.get(s.instrument)
            topic = topic or next((t for t in tokens(s.title) if t.startswith('topic_')),None)
            if score<=0 or (requested and topic not in requested) or (source_ids is not None and s.document_id not in source_ids):
                continue
            if notification != (s.kind=='notification'):
                continue
            if printed and not notification and (r.printed_number_unverified!=printed[1] or printed[2]):
                continue
            if not notification and not printed and len(specific.intersection(tokens(r.text))-{'punishment','provisions','document'})<2:
                continue
            if total+len(r.text)>max_characters:
                continue
            if not self.bound(p):
                continue
            found.append(p);total+=len(r.text)
            if len(found)==limit:
                break
        return found

    def bound(self,hit):
        return (self.corpus is not None and hit.record in self.corpus.passages
                and hit.source in self.corpus.sources and hit.page in self.corpus.pages)

    def citation(self, hit, number):
        from backend.chat.models import Citation
        r,s,p = hit.record,hit.source,hit.page
        if not self.valid() or hit not in self.passages or not self.bound(hit):
            raise ValueError('Stale public citation')
        return Citation(id='E'+str(number),candidate_id=r.passage_id,document_id=s.document_id,
            title=s.title,instrument=s.instrument,source_url=s.source_url,issuing_authority=s.issuing_authority,
            publication_date=str(s.publication_date),pdf_page=p.physical_page,page_id=p.page_id,
            start_line=r.start_line,end_line=r.end_line,quote=r.text,raw_sha256=s.raw_sha256,
            processed_sha256=None,text_sha256=r.text_sha256,catalog_sha256=None,qa_sha256=None,
            qa_flags=p.qa_flags,printed_number_unverified=r.printed_number_unverified,
            context_text=p.text,context_text_sha256=p.text_sha256,version_description=s.edition,
            publication_manifest_sha256=self.manifest_sha256,publication_commentary=s.commentary)

    def status(self):
        available = self.valid()
        return dict(mode='bm25',passages=len(self.passages) if available else 0,
            corpus_kind='public',publication_approved=available and not self.preview,
            preview_only=self.preview,index_version=self.manifest_sha256 if re.fullmatch(r'[0-9a-f]{64}',self.manifest_sha256 or '') else None,
            startup_seconds=round(self.startup_seconds,4),semantic_status='disabled; no ML imports or downloads',
            evidence_status='ARCHIVAL_UNVERIFIED' if available else 'INSUFFICIENT_EVIDENCE',detail=self.reason)
