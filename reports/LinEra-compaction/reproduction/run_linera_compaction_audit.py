"""Frozen three-case, single-process-exit boundary audit; synthetic data only."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,platform
ROOT=Path(__file__).resolve().parent
WORK=ROOT/'work/linera-compaction-v1'
SOURCE=ROOT/'data/linera-qualification-20261121'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def child(folder,mode):
    sys.path.insert(0,str(WORK/'source'))
    from lf.store import LineageStore
    folder=Path(folder)
    store=LineageStore(str(folder/'objects.db'),str(folder/'state.json'))
    a=store.put('FORGOTTEN_SYNTHETIC_A');b=store.put('RETAINED_SYNTHETIC_B')
    c=store.put('DERIVED_SYNTHETIC_A','derived',[a]);d=store.put('DERIVED_SYNTHETIC_B','derived',[b])
    (folder/'tags.json').write_text(json.dumps({'forgotten_source':a,'retained_source':b,'forgotten_derived':c,'retained_derived':d}))
    store.forget(a,delete_rows=False)
    if mode=='interrupted_rotation':
        def interrupt():
            (folder/'boundary.json').write_text(json.dumps({'boundary':'rotate _save_state entry after db.commit','injected_exit':73}))
            os._exit(73)
        store._save_state=interrupt
    if mode!='forget_only':store.rotate()
    store.close()
def main():
    if len(sys.argv)>1:
        child(sys.argv[1],sys.argv[2]);return
    assert not WORK.exists(),'Refuse to overwrite experiment'
    protocol=ROOT/'LINERA_COMPACTION_PROTOCOL_20261121.json'
    assert sha(protocol)=='41b0387359aa77de110bd1ac6296cc58a0cf951422acdc5e3e61655ceeac4759'
    (WORK/'source/lf').mkdir(parents=True)
    hashes={}
    for n in ['__init__.py','pprf.py','keydag.py','store.py']:
        src=SOURCE/'lf'/n;dst=WORK/'source/lf'/n;shutil.copyfile(src,dst);assert sha(src)==sha(dst);hashes[n]=sha(src)
    sys.path.insert(0,str(WORK/'source'))
    from lf.store import LineageStore
    import cryptography
    results=[]
    for mode in ['forget_only','completed_rotation','interrupted_rotation']:
        folder=WORK/mode;folder.mkdir()
        command=[sys.executable,'-B',str(Path(__file__).resolve()),str(folder),mode]
        p=subprocess.run(command,capture_output=True,text=True,timeout=30)
        assert p.returncode==(73 if mode=='interrupted_rotation' else 0),(mode,p.stderr)
        tags=json.loads((folder/'tags.json').read_text());store=LineageStore(str(folder/'objects.db'),str(folder/'state.json'))
        outcomes={}
        for name,tag in tags.items():
            try:outcomes[name]={'readable':True,'plaintext':store.get(tag)}
            except Exception as exc:outcomes[name]={'readable':False,'exception_type':type(exc).__name__}
        store.close()
        results.append({'case':mode,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'outcomes':outcomes,'boundary':json.loads((folder/'boundary.json').read_text()) if (folder/'boundary.json').exists() else None})
    for n,h in hashes.items():assert sha(SOURCE/'lf'/n)==sha(WORK/'source/lf'/n)==h
    result={'date':'2026-11-21','protocol_sha256':sha(protocol),'harness_sha256':sha(Path(__file__)),'source_hashes':hashes,'python':sys.version,'platform':platform.platform(),'cryptography':cryptography.__version__,'cases':results,'new_model_calls':0,'upstream_inputs_unchanged':True,'independent_review':False,'scope':'One synthetic fixture per case; process exit at named boundary, not arbitrary power loss or LC-FS proof validation.'}
    (ROOT/'results/linera_compaction_audit_20261121.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))
if __name__=='__main__':main()
