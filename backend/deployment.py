"""Package only explicitly reviewed public runtime files. No corpus or model.

This prepares a source artifact locally; it neither deploys nor grants publication
approval to new legal text, embeddings, private archives or review stores.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from backend.app.ingestion.paths import checked_path, source_path

ROOT = Path(__file__).resolve().parents[1]


def package(root, output):
    root = checked_path(root)
    specification = json.loads(source_path(root, "docs/deployment-publication.json").read_bytes())
    paths = specification["runtime_files"]
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("Explicit unique runtime file inventory required")
    records = {}
    payloads = {}
    for name in paths:
        if (name.startswith(("backend/data/", ".git/", ".venv/")) or
                any(part in {"node_modules", "__pycache__"} for part in Path(name).parts) or
                Path(name).suffix.lower() in {".pdf", ".bin", ".faiss", ".npy", ".safetensors", ".env"}):
            raise ValueError("Private or generated deployment path rejected")
        payload = source_path(root, name).read_bytes()
        if len(payload) > 8 * 1024 * 1024:
            raise ValueError("Unexpected large runtime file")
        records[name] = hashlib.sha256(payload).hexdigest()
        payloads[name] = payload
    target = checked_path(output)
    if not target.is_relative_to(checked_path(root / "backend/data/deployment")):
        raise ValueError("Output must stay under ignored backend/data/deployment")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(payloads):
            archive.writestr(name, payloads[name])
        archive.writestr("artifact-inventory.json", json.dumps(dict(files=records,
            corpus_available=False, source_text_publication_approved=False), sort_keys=True, indent=2))
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None or any(hashlib.sha256(archive.read(k)).hexdigest() != v for k,v in records.items()):
            raise ValueError("Deployment archive integrity failed")
    return dict(files=len(records), sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        corpus_available=False, new_legal_text_included=False, published=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(ROOT, args.output), indent=2))


if __name__ == "__main__":
    main()
