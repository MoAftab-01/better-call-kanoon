"""Opt-in CPU semantic search. Local safetensors only; no downloads or disk index.

Tokenizer-sized windows cover all selection text, rather than silently truncating
long legal provisions. Windows rank their complete parent source selection.
"""
import hashlib
import json
from pathlib import Path
import threading


class LocalSemantic:
    def __init__(self, model_path, passages):
        path = Path(model_path).resolve(strict=True)
        if not path.is_dir() or not (path / "model.safetensors").is_file():
            raise ValueError("Explicit local safetensors model directory required")
        files = sorted(p for p in path.rglob("*") if p.is_file())
        if any(p.suffix in {".py", ".bin", ".pkl", ".pickle"} for p in files):
            raise ValueError("Only data-only safetensors model directories are accepted")
        modules = json.loads((path / "modules.json").read_bytes())
        supported = {"sentence_transformers.models.Transformer", "sentence_transformers.models.Pooling", "sentence_transformers.models.Normalize"}
        if not modules or any(m.get("type") not in supported for m in modules):
            raise ValueError("Only standard Transformer/Pooling/Normalize modules are supported")
        import faiss
        import numpy as np
        import torch
        from sentence_transformers import SentenceTransformer
        fingerprint = hashlib.sha256()
        for p in files:
            fingerprint.update(p.relative_to(path).as_posix().encode())
            fingerprint.update(hashlib.sha256(p.read_bytes()).digest())
        self.version = fingerprint.hexdigest()
        torch.set_num_threads(2)
        faiss.omp_set_num_threads(2)
        self.model = SentenceTransformer(str(path), device="cpu", local_files_only=True,
            trust_remote_code=False, model_kwargs={"use_safetensors": True})
        self.lock = threading.Lock()
        self.np, self.faiss = np, faiss
        windows, self.parents = [], []
        width = min(self.model.max_seq_length - 2, 240)
        if width < 32:
            raise ValueError("Unsupported model sequence length")
        for number, passage in enumerate(passages):
            ids = self.model.tokenizer.encode(passage.search_text, add_special_tokens=False, verbose=False)
            for start in range(0, len(ids), width - 24):
                windows.append(self.model.tokenizer.decode(ids[start:start + width]))
                self.parents.append(number)
        vectors = np.asarray(self.model.encode(windows, batch_size=16,
            normalize_embeddings=True, show_progress_bar=False), dtype="float32")
        if not np.isfinite(vectors).all():
            raise ValueError("Nonfinite embeddings")
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)

    def rank(self, question, limit):
        with self.lock:
            ids = self.model.tokenizer.encode(question, add_special_tokens=False, verbose=False)
            width = min(self.model.max_seq_length - 2, 240)
            windows = [self.model.tokenizer.decode(ids[i:i+width]) for i in range(0, len(ids), width)] or [""]
            query = self.np.asarray(self.model.encode(windows, normalize_embeddings=True,
                show_progress_bar=False), dtype="float32").mean(axis=0, keepdims=True)
            self.faiss.normalize_L2(query)
            scores, indices = self.index.search(query, min(len(self.parents), limit * 4))
        ranked = []
        for score, number in zip(scores[0], indices[0], strict=True):
            if number >= 0 and score >= .2 and self.parents[number] not in ranked:
                ranked.append(self.parents[number])
        return ranked[:limit]
