"""Source-informed repair validation; no model calls or upstream source mutation."""
from pathlib import Path
import sys,os,json,subprocess,hashlib,shutil,sqlite3
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'work/linera-compaction-v1/source'
WORK=ROOT/'work/linera-journal-comparator-v1'
sys.path.insert(0,str(SOURCE))
from journaled_linera import JournaledStore

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def child(folder,phase):
    folder=Path(folder);s=JournaledStore(str(folder/'objects.db'),str(folder/'state.json'))
    a=s.put('FORGOTTEN_SYNTHETIC_A');b=s.put('RETAINED_SYNTHETIC_B')
    c=s.put('DERIVED_SYNTHETIC_A','derived',[a]);d=s.put('DERIVED_SYNTHETIC_B','derived',[b])
    (folder/'tags.json').write_text(json.dumps({'forgotten_source':a,'retained_source':b,'forgotten_derived':c,'retained_derived':d}))
    s.forget(a,delete_rows=False)
    def hook(point):
        if point==phase:
            (folder/'boundary.json').write_text(json.dumps({'phase':point,'exit':73}))
            os._exit(73)
    s.phase_hook=hook
    if phase!='forget_only':s.rotate()
    s.close()
def main():
    if len(sys.argv)>1:child(sys.argv[1],sys.argv[2]);return
    assert not WORK.exists();WORK.mkdir()
    protocol=ROOT/'LINERA_COMPACTION_REPAIR_PROTOCOL_20261121.json'
    source_hashes={p.name:sha(p) for p in (SOURCE/'lf').glob('*.py')}
    results=[]
    expected={'retained_source':'RETAINED_SYNTHETIC_B','retained_derived':'DERIVED_SYNTHETIC_B'}
    for phase in ['forget_only','completed_rotation','before_db_commit','after_db_commit','after_state_publication']:
        folder=WORK/phase;folder.mkdir()
        p=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),str(folder),phase],capture_output=True,text=True,timeout=30)
        assert p.returncode==(73 if phase.startswith(('before_','after_')) else 0),(phase,p.stderr)
        tags=json.loads((folder/'tags.json').read_text());pending=(folder/'state.json.rotation-journal').exists()
        s=JournaledStore(str(folder/'objects.db'),str(folder/'state.json'));outcomes={}
        for name,tag in tags.items():
            try:outcomes[name]={'readable':True,'plaintext':s.get(tag)}
            except Exception as exc:outcomes[name]={'readable':False,'exception':type(exc).__name__}
        for name,text in expected.items():assert outcomes[name]=={'readable':True,'plaintext':text},(phase,name,outcomes[name])
        assert not outcomes['forgotten_source']['readable'] and not outcomes['forgotten_derived']['readable']
        assert not (folder/'state.json.rotation-journal').exists()
        generation=s.db.execute('SELECT generation FROM rotation_meta WHERE id=1').fetchone()[0];s.close()
        results.append({'phase':phase,'exit_code':p.returncode,'journal_pending_before_restart':pending,'outcomes':outcomes,'generation_after_restart':generation,'stderr':p.stderr})
    # Separate malformed metadata control, never modifying prior fixtures.
    folder=WORK/'mismatched_generation';shutil.copytree(WORK/'completed_rotation',folder)
    state=folder/'state.json';d=json.loads(state.read_text());d['journal_generation']='mismatch';state.write_text(json.dumps(d))
    try:JournaledStore(str(folder/'objects.db'),str(state))
    except RuntimeError as exc:control={'rejected':True,'reason':str(exc)}
    else:raise AssertionError('Mismatch was accepted')
    assert source_hashes=={p.name:sha(p) for p in (SOURCE/'lf').glob('*.py')}
    receipt={'date':'2026-11-21','protocol_sha256':sha(protocol),'harness_sha256':sha(Path(__file__)),'comparator_sha256':sha(ROOT/'journaled_linera.py'),'source_hashes':source_hashes,'cases':results,'mismatched_metadata_control':control,'upstream_source_unchanged':True,'new_model_calls':0,'scope':'Five synthetic cases plus one malformed control; single writer, instrumented process exit only. Known journal technique, not new cryptography, power-loss proof or independent external review.'}
    (ROOT/'results/linera_journal_comparator_20261121.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({'cases_passed':len(results),'mismatch_control':control,'retained_objects_readable_per_case':2,'forgotten_objects_readable_per_case':0},indent=2))
if __name__=='__main__':main()
