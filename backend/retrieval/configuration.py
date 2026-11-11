"""Explicit corpus separation. Public mode never consults private evidence."""
import os


def create_index():
    corpus_kind = os.getenv('CORPUS_KIND', 'public' if os.getenv('KANOON_ENV')=='production' else 'private')
    retrieval_mode = os.getenv('RETRIEVAL_MODE', 'bm25' if corpus_kind=='public' else 'auto')
    if corpus_kind not in {'public','private'}:
        raise ValueError('CORPUS_KIND must be public or private')
    if corpus_kind=='public':
        if retrieval_mode!='bm25':
            raise ValueError('Public deployment supports BM25 only')
        from backend.public_corpus.runtime import PublicIndex
        return PublicIndex(os.getenv('PUBLIC_CORPUS_DIR',''),os.getenv('PUBLIC_CORPUS_MANIFEST_SHA256',''),
            os.getenv('PUBLIC_CORPUS_APPROVAL_FILE'),os.getenv('PUBLIC_CORPUS_APPROVAL_SHA256'))
    if os.getenv('KANOON_ENV')=='production':
        raise ValueError('Production cannot load a private research corpus')
    from pathlib import Path
    from .engine import ArchivalIndex, ROOT
    return ArchivalIndex(Path(os.getenv('PRIVATE_CORPUS_ROOT') or str(ROOT)),retrieval_mode=retrieval_mode)
