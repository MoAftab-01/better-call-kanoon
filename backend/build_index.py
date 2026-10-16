import json, pathlib, numpy as np
from sentence_transformers import SentenceTransformer
laws_dir = pathlib.Path(__file__).resolve().parent / "data" / "laws"
index_dir = pathlib.Path(__file__).resolve().parent / "data" / "index"
index_dir.mkdir(exist_ok=True)
chunks = []
for f in laws_dir.glob("*.txt"):
    text = f.read_text(encoding="utf-8")
    for i, p in enumerate(text.split("\n\n"), 1):
        p = p.strip()
        if len(p) < 40: continue
        chunks.append({"id": f"{f.stem}.{i}", "source": f.name, "text": p,
                       "heading": p.split("\n")[0][:120] if "\n" in p else ""})
with open(index_dir / "chunks.json", "w", encoding="utf-8") as out:
    json.dump(chunks, out, ensure_ascii=False)
model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode([c["text"] for c in chunks])
np.save(index_dir / "embeddings.npy", embeddings)
with open(index_dir / "index_metadata.json", "w", encoding="utf-8") as out:
    json.dump({"version":"0.1","chunks_file":"chunks.json","embedding_file":"embeddings.npy","count":len(chunks)}, out)
print("Index built:", len(chunks), "chunks")
