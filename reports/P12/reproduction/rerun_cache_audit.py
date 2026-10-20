"""Execute original inspected cache audit with output-root override only."""
import hashlib,importlib.util,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parent
SOURCE=ROOT/'outputs'
if __name__=='__main__':
    original=SOURCE/'behavioral-experiment/cache_audit.py';overlay=SOURCE/'experiment/overlay.py'
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [original,overlay,SOURCE/'behavioral-experiment/cache-audit-results.json']}
    manifest=json.loads((SOURCE/'behavioral-experiment/results/run-manifest.json').read_text())
    assert before[str(original)]==manifest['source_sha256']['cache_audit.py']
    assert before[str(overlay)]==manifest['v1_source_sha256']['overlay.py']
    sandbox=(ROOT/'work/cache-rerun/outputs').resolve();assert sandbox.is_relative_to(ROOT.resolve())
    assert not sandbox.exists(),'Use a fresh uniquely named audit sandbox rather than reusing previous cases'
    (sandbox/'behavioral-experiment').mkdir(parents=True)
    spec=importlib.util.spec_from_file_location('original_memory_cache_audit',original);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.ROOT=sandbox
    module.main()
    path=sandbox/'behavioral-experiment/cache-audit-results.json';fresh=json.loads(path.read_text());prior=json.loads((SOURCE/'behavioral-experiment/cache-audit-results.json').read_text())
    assert fresh['trials']==prior['trials'],'Fresh cache outcomes differ from saved reference'
    for name,sha in before.items():assert hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==sha
    rows=fresh['trials'];assert len(rows)==len({(r['backend'],r['episode'],r['arm']) for r in rows})==96
    result={'date':'2026-10-20','fresh_cache_cases':len(rows),'original_outcome_vectors_match':True,'runtime_output_root_override':str(sandbox),
      'source_modified':False,'original_reference_results_modified':False,'original_source_sha256':before,'python':sys.version,
      'original_v1_key_recovery':sum(r['cache_key_recovery'] for r in rows if r['arm']=='v1_full'),
      'clearing_key_recovery':sum(r['cache_key_recovery'] for r in rows if r['arm']=='cache_clearing_full'),
      'active_file_recovery':sum(r['active_byte_recovery'] for r in rows),'scope':'direct reachable CPython cache string keys; not physical heap zeroization','new_model_calls':0}
    out=ROOT/'results';out.mkdir(exist_ok=True);(out/'fresh_cache_reproduction.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
