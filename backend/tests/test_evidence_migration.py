"""All mutated evidence, actors and audit events here are SYNTHETIC, NOT LAW."""
import copy
import json
from pathlib import Path

import pytest

from backend.app.ingestion.pipeline import canonical_json
from backend.publication.bindings import (
    Catalog, ReadOnlyReview, POLICY, QA, SPEC, VERSION, LEDGER, MANIFEST, V1_MANIFEST, validate_mapping,
)
from backend.publication.migrate import build, REPORTS, sanitize_diagnostics
from backend.review.models import Candidate, Decision, Event
from backend.review.service import (
    Catalog as V1Catalog, ReviewStore, preview, sha, model_hash, validate_candidate,
)
from backend.review.synthetic_demo import create_demo


@pytest.fixture
def fixture(tmp_path):
    root = tmp_path / 'SYNTHETIC-NOT-LAW'
    create_demo(root)
    old_catalog = V1Catalog(root)
    a = Candidate.model_validate_json((root / 'candidate.json').read_bytes())
    qa = copy.deepcopy(old_catalog.qa)
    qa['publication_binding_version'] = 'v2'
    (root / QA).parent.mkdir(parents=True)
    (root / QA).write_bytes(canonical_json(qa))
    (root / SPEC).write_bytes(canonical_json(dict(catalog=dict(policy_version=POLICY,input_pins={QA:sha((root/QA).read_bytes())}))))
    catalog = Catalog(root)
    b = preview(catalog,a.document_id,[(1,2,4)],[(1,1,4)],a.context_rationale)
    inspected = ReviewStore(catalog).inspect(b)
    packet = dict(candidate_id=b.candidate_id,candidate=b.model_dump(mode='json'),
        exact_passage=inspected['selected'],surrounding_context=inspected['context'],qa_pages=inspected['qa_pages'],
        label='PROPOSED / NOT SUBMITTED / NOT APPROVED',submitted=False,approved=False,eligible=False)
    old = dict(catalog=old_catalog.config,catalogue_sha256=old_catalog.digest,qa_sha256=old_catalog.qa_hash,candidates=[a.model_dump(mode='json')])
    row = dict(v1_candidate_id=a.candidate_id,v2_candidate_id=b.candidate_id,document_id=b.document_id,
        source_identity=dict(document_id=b.document_id,official_title=b.source_metadata.official_title,
            source_url=b.source_metadata.source_url,original_identifiers=b.original_identifiers),
        passage_identity=dict(spans=[s.model_dump() for s in b.spans],context_spans=[s.model_dump() for s in b.context_spans],attribution=b.attribution.model_dump()),
        raw_sha256=b.raw_sha256,processed_sha256=b.processed_sha256,passage_sha256=b.passage_sha256,
        context_sha256=b.context_sha256,exact_text_hashes=[s.text_sha256 for s in b.spans],
        v1_catalogue_sha256=old_catalog.digest,v2_catalogue_sha256=catalog.digest,migration_version=VERSION,
        reason='Publication metadata and versioned QA/catalogue pins only; no legal text or review change')
    mapping = dict(migration_version=VERSION,human_approval=False,v2_catalogue_sha256=catalog.digest,mappings=[row])
    return root,old_catalog,catalog,a,b,old,mapping,[packet]


def test_only_qa_catalogue_and_candidate_identity_change(fixture):
    root,_,catalog,a,b,old,mapping,packets=fixture
    assert a.candidate_id!=b.candidate_id
    assert validate_mapping(old,catalog,mapping,packets)
    assert not ReadOnlyReview(catalog).store.path.exists()
    assert ReadOnlyReview(catalog).allowlist()['entries']==[]
    assert not hasattr(ReadOnlyReview(catalog),'append')


@pytest.mark.parametrize('direction',['old_to_new','new_to_old'])
def test_cross_version_candidates_are_rejected(fixture,direction):
    _,old,new,a,b,*_=fixture
    with pytest.raises(ValueError,match='Stale'):
        validate_candidate(new,a) if direction=='old_to_new' else validate_candidate(old,b)


@pytest.mark.parametrize('change',['missing_raw','modified_raw','modified_processed','stale_catalogue','qa_pin'])
def test_missing_modified_stale_inputs_fail_closed(fixture,change):
    root,_,catalog,_,b,*_=fixture
    if change=='stale_catalogue':
        data=json.loads((root/SPEC).read_bytes());data['catalog']['input_pins'][QA]='0'*64
        (root/SPEC).write_bytes(canonical_json(data))
    elif change=='qa_pin':
        (root/QA).write_bytes((root/QA).read_bytes()+b' ')
    else:
        path=root/(b.processed_path if change=='modified_processed' else b.raw_path)
        path.chmod(0o600)
        if change=='missing_raw':path.rename(path.with_suffix('.missing'))
        else:path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError):validate_candidate(catalog,b)


def test_candidate_qa_binding_mismatch(fixture):
    _,_,catalog,_,b,*_=fixture
    with pytest.raises(ValueError):validate_candidate(catalog,b.model_copy(update={'qa_sha256':'0'*64}))


@pytest.mark.parametrize('field',['raw_sha256','processed_sha256','passage_sha256','context_sha256','exact_text_hashes','v1_catalogue_sha256','migration_version','reason','source_identity','passage_identity'])
def test_mapping_fields_are_validated(fixture,field):
    _,_,catalog,_,_,old,mapping,packets=fixture
    changed=copy.deepcopy(mapping);changed['mappings'][0][field]=[] if field=='exact_text_hashes' else 'invalid'
    with pytest.raises(ValueError):validate_mapping(old,catalog,changed,packets)


@pytest.mark.parametrize('change',['duplicate','approval','text','boundary','candidate_source','qa_flags'])
def test_mapping_cannot_hide_legal_changes_or_promotion(fixture,change):
    _,_,catalog,_,_,old,mapping,packets=fixture
    mapping,packets=copy.deepcopy(mapping),copy.deepcopy(packets)
    if change=='duplicate':mapping['mappings']*=2
    elif change=='approval':packets[0]['approved']=True
    elif change=='text':packets[0]['exact_passage'][0]['text']+=' altered'
    elif change=='boundary':packets[0]['exact_passage'][0]['start_line']+=1
    elif change=='qa_flags':packets[0]['qa_pages']=[]
    else:
        c=Candidate.model_validate(packets[0]['candidate']).model_copy(update={'raw_sha256':'0'*64})
        c=c.model_copy(update={'candidate_id':'passage_'+model_hash(c,{'candidate_id'})})
        packets[0].update(candidate_id=c.candidate_id,candidate=c.model_dump(mode='json'))
        mapping['mappings'][0]['v2_candidate_id']=c.candidate_id
    with pytest.raises(ValueError):validate_mapping(old,catalog,mapping,packets)


def synthetic_decision(root,state,day):
    d=json.loads((root/'pending-request.json').read_bytes())
    d.update(decision=state,reviewer_id='SYNTHETIC TEST ACTOR - NOT HUMAN APPROVAL',
        decision_time=f'2026-01-{day:02}T00:00:00Z',rationale='SYNTHETIC state-isolation exercise only')
    if state=='approved':
        for key in ['visual_comparison_performed','boundaries_and_attribution_verified','qualifiers_and_exceptions_preserved','archival_scope_only']:d['attestations'][key]=True
    return Decision.model_validate(d)


def test_v1_approval_never_transfers_to_v2(fixture):
    root,old,catalog,a,*_=fixture
    store=ReviewStore(old)
    store.append(a,synthetic_decision(root,'pending',1),a.candidate_id,submit=True)
    approved=store.append(a,synthetic_decision(root,'approved',2),a.candidate_id,approve_one=True)
    assert len(store.allowlist((approved.sequence,approved.event_sha256))['entries'])==1
    target=ReadOnlyReview(catalog)
    assert target.allowlist()['entries']==[]
    target.store.path.mkdir(parents=True)
    for p in store.path.iterdir():(target.store.path/p.name).write_bytes(p.read_bytes())
    with pytest.raises(ValueError,match='Stale'):target.allowlist()


def test_audit_tampering_is_detected_and_checkpoints_fail_closed(fixture):
    root,_,catalog,_,b,*_=fixture
    review=ReadOnlyReview(catalog)
    assert review.allowlist((0,'0'*64))['entries']==[]
    with pytest.raises(ValueError,match='checkpoint'):review.allowlist((1,'0'*64))
    request=synthetic_decision(root,'pending',1)
    event=Event(sequence=1,previous_sha256='0'*64,candidate_id=b.candidate_id,candidate=b,review=request,event_sha256='0'*64)
    event=event.model_copy(update={'event_sha256':model_hash(event,{'event_sha256'})})
    review.store.path.mkdir(parents=True)
    p=review.store.path/f'00000001_{event.event_sha256}.json';data=event.model_dump(mode='json')
    data['review']['rationale']='SYNTHETIC TAMPERING'
    p.write_bytes(canonical_json(data))
    with pytest.raises(ValueError,match='tampering'):review.replay()


@pytest.mark.parametrize('mode',['valid','false_attestation','v1_qa_reference'])
def test_v2_approval_readback_requires_v2_evidence_and_checkpoint(fixture,mode):
    root,_,catalog,_,b,*_=fixture
    review=ReadOnlyReview(catalog);review.store.path.mkdir(parents=True)
    previous='0'*64
    for number,state in [(1,'pending'),(2,'approved')]:
        value=synthetic_decision(root,state,number).model_dump(mode='json')
        if mode!='v1_qa_reference':
            for ref in value['evidence']:
                if ref['kind']=='qa_report':ref.update(file_path=QA,sha256=catalog.qa_hash)
        if mode=='false_attestation':value['attestations']['visual_comparison_performed']=False
        event=Event(sequence=number,previous_sha256=previous,candidate_id=b.candidate_id,
            candidate=b if number==1 else None,review=Decision.model_validate(value),event_sha256='0'*64)
        event=event.model_copy(update={'event_sha256':model_hash(event,{'event_sha256'})})
        (review.store.path/f'{number:08}_{event.event_sha256}.json').write_bytes(canonical_json(event.model_dump(mode='json')))
        previous=event.event_sha256
    assert review.allowlist()['entries']==[]
    result=review.allowlist((2,previous))
    assert len(result['entries'])==(1 if mode=='valid' else 0)
    assert bool(result['blocked'])==(mode!='valid')


def test_public_metadata_succeeds_but_missing_corpus_cli_fails_closed(fixture,monkeypatch,capsys):
    from backend.publication import __main__ as cli
    root,_,catalog,_,b,old,mapping,packets=fixture
    (root/V1_MANIFEST).parent.mkdir(exist_ok=True)
    (root/V1_MANIFEST).write_bytes(canonical_json(old))
    packet_path=Path(SPEC).parent/'SYNTHETIC-packet.json'
    (root/packet_path).write_bytes(canonical_json(packets[0]))
    mapping['packets']=[dict(path=packet_path.as_posix(),sha256=sha((root/packet_path).read_bytes()))]
    (root/MANIFEST).write_bytes(canonical_json(mapping))
    raw=root/b.raw_path;raw.chmod(0o600);raw.rename(raw.with_suffix('.missing'))
    monkeypatch.setattr(cli,'__file__',str(root/'backend/publication/__main__.py'))
    assert cli.main(['metadata'])==0
    assert json.loads(capsys.readouterr().out)['source_bytes_verified'] is False
    assert cli.main(['verify'])==2
    assert json.loads(capsys.readouterr().out)['verified'] is False
    assert not (root/LEDGER).exists()


def test_diagnostics_sanitization_is_scoped_and_keeps_source_metadata():
    audit=dict(documents=[dict(source_sha256='a'*64,official_url='https://example.invalid/SYNTHETIC')],
        ingestion_runs=[dict(commands=[dict(argv=['synthetic']*8+['C:/SYNTHETIC-NOT-LAW/backend/data/output'],
            summary=dict(documents=[dict(output_path='C:/SYNTHETIC-NOT-LAW/backend/data/output/fixture.json')]))])])
    result=sanitize_diagnostics(audit)
    assert result['documents']==audit['documents']
    assert result['ingestion_runs'][0]['commands'][0]['argv'][8]=='backend/data/output'
    assert audit['ingestion_runs'][0]['commands'][0]['argv'][8].startswith('C:')


def test_deterministic_builder_and_no_overwriting(tmp_path):
    root=tmp_path/'SYNTHETIC-MIGRATION-NOT-LAW';create_demo(root)
    for name in REPORTS:
        p=root/'docs'/name
        if p.exists():continue
        p.write_bytes(canonical_json({}) if name.endswith('.json') else b'# SYNTHETIC NOT LAW\n')
    d=dict(ingestion_runs=[],documents=[],manifest_path='docs/acquired-legal-source-manifest-stage2c.json')
    (root/'docs/legal-document-ingestion-stage2d.json').write_bytes(canonical_json(d))
    q=root/'docs/legal-text-quality-stage2e.json';qa=json.loads(q.read_bytes());qa['inputs']={};q.write_bytes(canonical_json(qa))
    f=root/'docs/legal-passage-review-stage2f.json';spec=json.loads(f.read_bytes());spec['catalog']['input_pins']={str(q.relative_to(root)).replace('\\','/'):sha(q.read_bytes())};spec['implementation_files']=[];f.write_bytes(canonical_json(spec))
    c=V1Catalog(root)
    files={p.relative_to(root).as_posix():dict(sha256=sha(p.read_bytes())) for p in root.rglob('*') if p.is_file()}
    manifest=dict(files=files,catalog=c.config,catalogue_sha256=c.digest,qa_sha256=c.qa_hash,candidates=[])
    preserved=tmp_path/'preservation.json';preserved.write_bytes(canonical_json(manifest))
    implementation=Path(__file__).resolve().parents[2]
    first=build(root,implementation,preserved,tmp_path/'first')
    assert first==build(root,implementation,preserved,tmp_path/'second')
    with pytest.raises(ValueError,match='already exists'):build(root,implementation,preserved,tmp_path/'first')


@pytest.mark.parametrize('unsafe',['../outside.txt','.git/config','.GIT/config'])
def test_builder_rejects_unsafe_preservation_paths_before_writing(tmp_path,unsafe):
    root=tmp_path/'SYNTHETIC-ROOT';root.mkdir()
    preservation=tmp_path/'SYNTHETIC-manifest.json'
    preservation.write_bytes(canonical_json(dict(files={unsafe:dict(sha256='0'*64)})))
    destination=tmp_path/'must-not-exist'
    with pytest.raises(ValueError):build(root,tmp_path,preservation,destination)
    assert not destination.exists()


@pytest.mark.parametrize('inside',['v1','git'])
def test_builder_cannot_write_inside_preserved_v1_or_git_metadata(tmp_path,inside):
    root=tmp_path/'SYNTHETIC-V1';root.mkdir()
    destination=root/'new' if inside=='v1' else tmp_path/'.git/new'
    with pytest.raises(ValueError,match='inside V1 or Git'):
        build(root,tmp_path,tmp_path/'unused.json',destination)
    assert not destination.exists()
