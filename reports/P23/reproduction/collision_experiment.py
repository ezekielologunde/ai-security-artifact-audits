"""Controlled eight-case matrix against unmodified source and insert-only overlay."""
import hashlib,itertools,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'data/source-code/src'))
from ragtrap.datastore import ProvenanceDatastore
from ragtrap.gate import ingest,verify_record
from ragtrap.hashing import sha256_text
from ragtrap.records import Chunk
from ragtrap.revocation import revoke_source
from ragtrap.signing import Ed25519Signer
from ragtrap.traceback import ragtrap_traceback
from immutable_store import ImmutableIdStore,IndexConsistentUpsertStore
def inconsistencies(store):
    bad_principal=[];bad_hash=[]
    for principal,ids in store.by_principal.items():
        for cid in ids:
            if cid not in store.records or store.records[cid].principal!=principal:bad_principal.append({'principal':principal,'chunk_id':cid})
    for digest,ids in store.by_content_hash.items():
        for cid in ids:
            if cid not in store.records or store.records[cid].content_hash!=digest:bad_hash.append({'hash':digest,'chunk_id':cid})
    return {'principal_index_mismatches':bad_principal,'hash_index_mismatches':bad_hash}
def run_case(cls,same_id,same_principal,same_text):
    signer=Ed25519Signer.generate();store=cls()
    first=Chunk('doc::c0','alpha controlled passage','local://A','source-A',document_id='doc')
    second=Chunk('doc::c0' if same_id else 'doc-v2::c0',first.text if same_text else 'beta changed controlled passage',
                 'local://A' if same_principal else 'local://B','source-A' if same_principal else 'source-B',document_id='doc' if same_id else 'doc-v2')
    ingest([first],signer,datastore=store,detectors={});rejected=False
    try:ingest([second],signer,datastore=store,detectors={})
    except ValueError:rejected=True
    before=inconsistencies(store)
    signatures_valid=all(verify_record(r,signer) for r in store.records.values())
    old_lookup=store.lookup_by_content_hash(sha256_text(first.text))
    old_hash_binds=old_lookup is None or old_lookup.content_hash==sha256_text(first.text)
    attribution=ragtrap_traceback([first],store,signer)
    current_other={cid for cid,r in store.records.items() if r.principal!='source-A'}
    rev=revoke_source(store,'source-A')
    false_purges=sorted(current_other&set(rev.purged_chunk_ids))
    return {'same_id':same_id,'same_principal':same_principal,'same_text':same_text,'second_ingestion_rejected':rejected,
        'live_signatures_valid_before_revocation':signatures_valid,'before_revocation':before,
        'old_content_lookup_hash_matches_or_unknown':old_hash_binds,'old_content_attribution':attribution.attributions[first.chunk_id],
        'signature_verification_failures':attribution.verification_failures,
        'current_other_source_before_revocation':len(current_other),'current_other_source_false_purges':false_purges,
        'after_revocation':inconsistencies(store),'remaining_records':len(store)}
if __name__=='__main__':
    receipts=json.loads((ROOT/'data/code_manifest.json').read_text())
    for r in receipts:assert hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()==r['sha256']
    result={'source_revision':'c11da0ba9e6071773b11113c47a69bf80fcb916a','new_model_calls':0,'original_author_code_modified':False,'variants':{}}
    for name,cls in [('original',ProvenanceDatastore),('immutable_overlay',ImmutableIdStore),('consistent_upsert_posthoc',IndexConsistentUpsertStore)]:
        rows=[run_case(cls,*flags) for flags in itertools.product([False,True],repeat=3)]
        result['variants'][name]={'cases':rows,'summary':{'cases':len(rows),'accepted_second_ingestions':sum(not r['second_ingestion_rejected'] for r in rows),
            'principal_index_failure_cases':sum(bool(r['before_revocation']['principal_index_mismatches']) for r in rows),
            'hash_index_failure_cases':sum(bool(r['before_revocation']['hash_index_mismatches']) for r in rows),
            'old_content_wrong_hash_binding_cases':sum(not r['old_content_lookup_hash_matches_or_unknown'] for r in rows),
            'other_source_false_purge_cases':sum(bool(r['current_other_source_false_purges']) for r in rows),
            'live_signature_failure_cases':sum(not r['live_signatures_valid_before_revocation'] for r in rows)}}
    out=ROOT/'results';out.mkdir(exist_ok=True)
    (out/'collision_matrix.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v['summary'] for k,v in result['variants'].items()},indent=2))
