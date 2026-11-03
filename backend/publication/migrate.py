"""Deterministically derive V2 in a NEW scratch workspace from preserved V1.

The caller publishes returned files explicitly. V1 is read-only, never repinned.
"""
import copy
from pathlib import Path

from backend.app.ingestion.paths import checked_path, source_path
from backend.app.ingestion.pipeline import canonical_json
from backend.review.service import Catalog as V1Catalog, ReviewStore, read_json, sha
from backend.discovery.passages import discover, LABEL
from .bindings import Catalog, PREFIX, SPEC, QA, VERSION, POLICY, V1_MANIFEST, MANIFEST, proposals, validate_mapping

REPORTS = [
    "legal-source-acquisition-stage2c.json", "legal-source-acquisition-stage2c.md",
    "acquired-legal-source-manifest-stage2c.json",
    "legal-document-ingestion-stage2d.json", "legal-document-ingestion-stage2d.md",
    "legal-text-quality-stage2e.json", "legal-text-quality-stage2e.md",
    "legal-passage-review-stage2f.json", "legal-passage-review-stage2f.md",
    "legal-passage-discovery-stage2g.json", "legal-passage-discovery-stage2g.md",
    "legal-evidence-review-stage2h.json", "legal-evidence-review-stage2h.md",
]
IMPLEMENTATION = ["backend/publication/" + n for n in ["__init__.py", "bindings.py", "migrate.py", "__main__.py"]]


def public_path(name):
    return PREFIX + Path(name).name if Path(name).name in REPORTS else name


def sanitize_diagnostics(audit):
    """Only the 14 identified command/output diagnostics, not document metadata."""
    result = copy.deepcopy(audit)
    for run in result["ingestion_runs"]:
        for command in run["commands"]:
            value = command["argv"][8].replace("\\", "/")
            if ":/" not in value or "backend/data/" not in value:
                raise ValueError("Unexpected V1 diagnostic location; review migration plan")
            command["argv"][8] = value[value.index("backend/data/"):]
            for document in command["summary"]["documents"]:
                value = document["output_path"].replace("\\", "/")
                if ":/" not in value or "backend/data/" not in value:
                    raise ValueError("Unexpected diagnostic output path")
                document["output_path"] = value[value.index("backend/data/"):]
    return result


def public_markdown(data, name):
    """The audited MD occurrences are workstation Set-Location examples only."""
    text = data.decode("utf-8")
    lines = text.splitlines()
    for n, line in enumerate(lines):
        if "Set-Location -LiteralPath" in line:
            lines[n] = "# Run from the repository root."
    notice = ("# Publication evidence V2\n\nSanitized derived report; not byte-identical to the private V1 original. "
              "Historical test results/command examples below describe V1 unless explicitly labelled V2. "
              "Use the public migration guide for current V2 commands. No human approval or current-law claim is added.\n\n")
    return (notice + "\n".join(lines).rstrip("\n") + "\n").encode("utf-8")


def build(v1_root, implementation_root, preservation_path, workspace):
    """Return deterministic publication bytes; all working files stay in scratch."""
    v1_root, implementation_root = checked_path(Path(v1_root)), checked_path(Path(implementation_root))
    workspace = checked_path(Path(workspace))
    if workspace.is_relative_to(v1_root) or any(p.casefold() == '.git' for p in workspace.parts):
        raise ValueError("Migration scratch cannot be inside V1 or Git metadata")
    if workspace.exists():
        raise ValueError("Migration scratch destination already exists")
    old = read_json(Path(preservation_path))
    captured = {}
    for name, expected in old["files"].items():
        if any(p.casefold() == '.git' for p in Path(name).parts):
            raise ValueError("Git metadata cannot be an evidence input")
        data = source_path(v1_root, name).read_bytes()
        if sha(data) != expected["sha256"]:
            raise ValueError("V1 preservation mismatch: " + name)
        captured[name] = data
    v1 = V1Catalog(v1_root)
    if v1.digest != old["catalogue_sha256"] or v1.qa_hash != old["qa_sha256"]:
        raise ValueError("V1 preservation catalogue differs")
    if ReviewStore(v1).replay() != ([], {}) or ReviewStore(v1).allowlist()["entries"]:
        raise ValueError("V1 review state unexpectedly nonempty")
    _, originals = discover(v1_root)
    if [p["candidate"] for p in originals] != old["candidates"]:
        raise ValueError("Preserved V1 candidate identities differ")
    workspace.mkdir(parents=True)
    # Complete independent corpus replay sandbox; none of it is auto-published.
    for name in old["files"]:
        p = workspace / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(captured[name])
    for name in IMPLEMENTATION:
        p = workspace / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(source_path(implementation_root, name).read_bytes())
    output = {}

    def put(name, value):
        payload = canonical_json(value) if isinstance(value, dict) else value
        path = workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ValueError("Refusing to overwrite any input: " + name)
        path.write_bytes(payload)
        output[name] = payload
        return sha(payload)

    put(V1_MANIFEST, old)  # Hashes/relationships only; no original diagnostic values.
    for name in REPORTS:
        if name.endswith('.md') and 'stage2h' not in name:
            put(PREFIX + name, public_markdown((v1_root / 'docs' / name).read_bytes(), name))
    for name in ['legal-source-acquisition-stage2c.json', 'acquired-legal-source-manifest-stage2c.json']:
        value = read_json(v1_root / 'docs' / name)
        # The acquired manifest retains Stage 2A's strict schema (no extra fields).
        if name != 'acquired-legal-source-manifest-stage2c.json':
            value['publication_binding_version'] = 'v2'
            value['publication_notice'] = 'Derived publication metadata; source identities/URLs/hashes remain unchanged; not byte-identical to V1.'
            value['acquired_manifest'] = PREFIX + 'acquired-legal-source-manifest-stage2c.json'
        put(PREFIX + name, value)
    d = sanitize_diagnostics(read_json(v1_root / 'docs/legal-document-ingestion-stage2d.json'))
    d.update(manifest_path=PREFIX + 'acquired-legal-source-manifest-stage2c.json',
        manifest_sha256=sha(output[PREFIX + 'acquired-legal-source-manifest-stage2c.json']),
        acquisition_audit_path=PREFIX + 'legal-source-acquisition-stage2c.json',
        acquisition_audit_sha256=sha(output[PREFIX + 'legal-source-acquisition-stage2c.json']),
        publication_binding_version='v2')
    put(PREFIX + 'legal-document-ingestion-stage2d.json', d)
    qa = read_json(v1_root / 'docs/legal-text-quality-stage2e.json')
    old_documents = copy.deepcopy(qa['documents'])
    qa['inputs'] = {public_path(n): sha(output[public_path(n)]) if public_path(n) in output else digest for n,digest in qa['inputs'].items()}
    qa['publication_binding_version'] = 'v2'
    assert qa['documents'] == old_documents  # No findings, exclusions or page text changed.
    put(QA, qa)
    spec = read_json(v1_root / 'docs/legal-passage-review-stage2f.json')
    pins = {public_path(n): sha(output[public_path(n)]) if public_path(n) in output else digest for n,digest in spec['catalog']['input_pins'].items()}
    pins.update({n: sha((implementation_root / n).read_bytes()) for n in IMPLEMENTATION})
    pins[V1_MANIFEST] = sha(output[V1_MANIFEST])
    spec['catalog'] = dict(policy_version=POLICY, input_pins=pins)
    spec['publication_binding_version'] = 'v2'
    spec['default_ledger'] = 'backend/data/reviews/stage2f/v2'
    spec['implementation_files'] += IMPLEMENTATION
    spec['publication_notice'] = 'New catalogue; canonical candidate algorithm and original exclusion rules unchanged. Read-only V2 verifier exposes no event writer.'
    put(SPEC, spec)
    catalog = Catalog(workspace)
    packets = proposals(catalog)
    if len(packets) != len(originals):
        raise ValueError("Migration changed proposal coverage")
    rows, packet_refs = [], []
    for a, b in zip(originals, packets, strict=True):
        if a['exact_passage'] != b['exact_passage'] or a['surrounding_context'] != b['surrounding_context'] or a['qa_pages'] != b['qa_pages']:
            raise ValueError("Migration changed legal text, context, boundaries or QA findings")
        old_c, c = a['candidate'], b['candidate']
        path = PREFIX + 'packets/proposal_' + c['candidate_id'] + '.json'
        packet_refs.append(dict(path=path, sha256=put(path, b), candidate_id=c['candidate_id']))
        rows.append(dict(v1_candidate_id=old_c['candidate_id'],v2_candidate_id=c['candidate_id'],
            document_id=c['document_id'],raw_sha256=c['raw_sha256'],processed_sha256=c['processed_sha256'],
            source_identity=dict(document_id=c['document_id'],official_title=c['source_metadata']['official_title'],
                source_url=c['source_metadata']['source_url'],original_identifiers=c['original_identifiers']),
            passage_identity=dict(spans=c['spans'],context_spans=c['context_spans'],attribution=c['attribution']),
            passage_sha256=c['passage_sha256'],context_sha256=c['context_sha256'],
            exact_text_hashes=[s['text_sha256'] for s in c['spans']],v1_catalogue_sha256=v1.digest,
            v2_catalogue_sha256=catalog.digest,migration_version=VERSION,
            reason='Publication metadata and versioned QA/catalogue pins only; no legal text or review change'))
    mapping = dict(schema_version=1,migration_version=VERSION,human_approval=False,legal_currentness='unknown',
        v1_catalogue_sha256=v1.digest,v2_catalogue_sha256=catalog.digest,v1_qa_sha256=v1.qa_hash,
        v2_qa_sha256=catalog.qa_hash,mappings=rows,packets=packet_refs,
        review_state=dict(submissions=0,events=0,approvals=0,verified_evidence_allowlist=[]))
    validate_mapping(old,catalog,mapping,packets)
    put(MANIFEST,mapping)
    g = dict(schema_version=1,binding_version='v2',catalogue_sha256=catalog.digest,qa_sha256=catalog.qa_hash,
        label=LABEL,proposed_count=len(packets),packet_export=packet_refs,legal_currentness='unknown',
        limitation='Metadata migration is not visual/human review, retrieval approval or proof of current applicability.')
    put(PREFIX+'legal-passage-discovery-stage2g.json',g)
    h = read_json(v1_root/'docs/legal-evidence-review-stage2h.json')
    for name in ['git_preparation','proposed_commit','verification']:
        h.pop(name,None)
    h['stage']='2H publication V2'
    h['source_pins']={n:sha(payload) for n,payload in output.items() if n.endswith('.json') and '/packets/' not in n}
    h['runtime_changes']=['Separate V2 read-only verification namespace; original Stage2F/2G implementation unchanged.']
    h['real_packets']=[dict(candidate_id=p['candidate_id'],packet_path=r['path'],packet_sha256=r['sha256'],
        label=LABEL,submitted=False,approved=False,eligible=False) for p,r in zip(packets,packet_refs,strict=True)]
    put(PREFIX+'legal-evidence-review-stage2h.json',h)
    put(PREFIX+'legal-evidence-review-stage2h.md',
        ('# Stage 2H - publication V2\n\nSanitized derived workflow summary; not byte-identical to V1. '
         'All three packets remain PROPOSED / NOT SUBMITTED / NOT APPROVED. No reviewer, decision, approval or attestation is created. '
         'Use `python -B -m backend.publication metadata` without corpus data and `verify`, `list`, `history`, `allowlist` with the exact corpus bundle. '
         'Inspect one packet using `preview <V2-candidate-id>`. V1 IDs are rejected. '
         'Metadata checks never prove visual correctness or current legal applicability.\n').encode())
    return output
