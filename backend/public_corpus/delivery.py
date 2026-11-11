"""Create a new local authorized subset. Never uploads or creates approvals."""
from pathlib import Path

from .runtime import load, metadata, read
from .models import sha


def deliver(candidate, pin, decision, decision_pin, output, *, trusted_key=None):
    # Verify the complete candidate before copying; validate authorization separately.
    load(candidate,pin,preview=True)
    root,manifest,names,included = metadata(candidate,pin,decision,decision_pin,trusted_key=trusted_key)
    destination = Path(output).absolute()
    if destination.exists() or destination.with_suffix('.zip').exists():
        raise ValueError('Delivery destination must be new')
    # Standalone delivery is constrained to the existing ignored deployment area.
    from backend.app.ingestion.paths import checked_path
    destination = checked_path(destination)
    workspace = Path(__file__).resolve().parents[2]
    if not destination.is_relative_to(checked_path(workspace/'backend/data/deployment')):
        raise ValueError('Delivery must stay under ignored backend/data/deployment')
    blobs = {'manifest.json': read(root/'manifest.json',128*1024)}
    if sha(blobs['manifest.json']) != pin:
        raise ValueError('Manifest changed during delivery')
    for name in sorted(names):
        blob = read(root/name,4*1024*1024)
        if sha(blob) != manifest.files[name].sha256 or len(blob) != manifest.files[name].bytes:
            raise ValueError('Artifact changed during delivery')
        blobs[name] = blob
    destination.mkdir(parents=True,exist_ok=False)
    for name,blob in blobs.items():
        with (destination/name).open('xb') as f:
            f.write(blob)
    # Revalidate exact subset and still-live authorization after copying.
    _,corpus = load(destination,pin,decision,decision_pin,trusted_key=trusted_key)
    return dict(files={n:sha(b) for n,b in blobs.items()},sources=len(included),
        passages=len(corpus.passages),published=False,approval_created=False)
