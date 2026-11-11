"""Verify publication decisions. Contains no key generation or signing operation.

The operator must configure a reviewer's public key independently of the payload.
The separately configured receipt hash anchors the latest authorized decision.
"""
import os
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .models import PublicationDecision, canonical, sha

DOMAIN = b'better-call-kanoon:publication-decision:v2\x00'


def authorize(data, manifest, manifest_sha256, trusted_key=None):
    record = PublicationDecision.model_validate(data)
    key = trusted_key if trusted_key is not None else os.getenv('PUBLIC_CORPUS_SIGNER_PUBLIC_KEY', '')
    if not re.fullmatch(r'[0-9a-f]{64}', key or ''):
        raise ValueError('Independently configured Ed25519 public key required')
    raw = bytes.fromhex(key)
    if sha(raw) != record.signer_key_id:
        raise ValueError('Unauthorized publication signer')
    try:
        Ed25519PublicKey.from_public_bytes(raw).verify(bytes.fromhex(record.signature),
            DOMAIN + canonical(record.model_dump(mode='json', exclude={'signature'})))
    except InvalidSignature:
        raise ValueError('Invalid publication signature') from None
    if record.manifest_sha256 != manifest_sha256 or manifest.schema_version != 2:
        raise ValueError('Publication decision covers another or legacy candidate')
    sources = {s.document_id:s for s in record.sources}
    if len(sources) != len(record.sources) or set(sources) != {s.document_id for s in manifest.sources}:
        raise ValueError('Every source requires an explicit unique decision')
    for source in manifest.sources:
        decision = sources[source.document_id]
        if (source.raw_sha256 != decision.raw_sha256 or
                manifest.files[source.filename].sha256 != decision.artifact_sha256):
            raise ValueError('Source authorization hash mismatch')
    included = {k for k,v in sources.items() if v.decision == 'include'}
    if record.decision == 'revoked' or not included:
        raise ValueError('Publication revoked or no sources authorized')
    return included
