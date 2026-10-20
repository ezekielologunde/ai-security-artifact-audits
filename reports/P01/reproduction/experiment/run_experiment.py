"""Freeze and run the finite, AgentTrap-informed local microbenchmark."""
import argparse,hashlib,json,platform,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from runtime import ARMS,initialize,retire
from adapter import bundle
from score import ground_truth

ROOT=Path(__file__).resolve().parent.parent
NODE=Path(r'C:\Users\Ezekiel\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
IDS=[1,5,23,39,43,203,207,209,5005,5010,5204,5205]
KINDS=['credential-copy','shell-hook','webhook-registration','oauth-cache','memory-metadata','cron-entry','heartbeat-entry','memory-upload-registration','terminal-hook','credential-heartbeat','monitor-enrollment','callback-token-cache']

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def curate():
    source=ROOT/'datasets/upstream/agenttrap/hf_dataset/data/tasks.jsonl'
    records={int(x['case_id']):x for x in map(json.loads,source.read_text(encoding='utf-8').splitlines())}
    cases=[]
    for i,ident in enumerate(IDS):
        r=records[ident]
        for failed in [False,True]:
            cases.append({'scenario_id':f'AT{ident}-'+('residual' if failed else 'clean'),
              'source_case_id':ident,'source_skill':r['skill_name'],'source_dimension':r['dim'],
              'source_summary':r['brief_plan'],'source_record_sha256':hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest(),
              'artifact_kind':KINDS[i],'auth_mode':['issuer_recheck','cached_token','local_uncredentialed'][i%3],
              'route':'foreground' if i%3==0 else 'background','failed_cleanup':failed,
              'stale_adapter':failed and i in [1,3,7,9],
              'missing_source':i in [4,10],
              'adaptation':'Inert synthetic residual record and explicit local replay; original task/skill is not executed.'})
    return cases,digest(source)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repeats',type=int,default=5);ap.add_argument('--name',default='measured-v1');args=ap.parse_args()
    out=ROOT/'experiment/results'/args.name
    out.mkdir(parents=True,exist_ok=False)
    cases,source_hash=curate()
    code={p.name:digest(p) for p in Path(__file__).parent.iterdir() if p.suffix in ['.py','.mjs']}
    frozen={'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'design':'Finite paired local microbenchmark, not original AgentTrap execution','repeats':args.repeats,'arms':ARMS,'cases':cases,'source_sha256':source_hash,'code_sha256':code,'python':sys.version,'platform':platform.platform(),'node':subprocess.check_output([str(NODE),'--version'],text=True).strip(),'limitations':['No LLM/provider calls','Synthetic credentials and residual objects','Sequential retirement then replay; no concurrent-cut race or distributed delay experiment','Logical evidence stamps are not elapsed time','Purpose-selected cases; no population inference']}
    (out/'frozen_design.json').write_text(json.dumps(frozen,indent=2),encoding='utf-8')
    (out/'frozen_design.sha256').write_text(digest(out/'frozen_design.json'),encoding='ascii')
    derived=ROOT/'datasets/derived';derived.mkdir(exist_ok=True)
    (derived/'agenttrap_offboarding_adaptations.jsonl').write_text(''.join(json.dumps(c)+'\n' for c in cases),encoding='utf-8')
    rows=[];bundles=[]
    for repeat in range(args.repeats):
      for case in cases:
       for arm in ARMS:
        ident=f"r{repeat}-{case['scenario_id']}-{arm}";run_dir=out/'runs'/ident
        initialize(run_dir,case,arm)
        before=json.loads(subprocess.check_output([sys.executable,str(Path(__file__).parent/'worker.py'),str(run_dir),'pre'],text=True))
        if not all(x['allowed'] for x in before.values()):raise RuntimeError('positive calibration failed')
        ack=retire(run_dir,case,arm)
        t=time.perf_counter();after=json.loads(subprocess.check_output([sys.executable,str(Path(__file__).parent/'worker.py'),str(run_dir),'post'],text=True));worker_ms=(time.perf_counter()-t)*1000
        truth=ground_truth(run_dir)
        row={'run_id':ident,'repeat':repeat,'scenario_id':case['scenario_id'],'arm':arm,'case':case,'ack':ack,'worker_ms':worker_ms,'post':after,'truth':truth,'administrative_verdict':'CLOSED'}
        rows.append(row)
        for feed in ['snapshot','probe']:
            bundles.append({'run_id':ident,'feed':feed,'bundle':bundle(run_dir,case,feed)})
    (out/'runs.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    (out/'evidence_bundles.json').write_text(json.dumps(bundles,indent=2),encoding='utf-8')
    subprocess.run([str(NODE),str(Path(__file__).parent/'verify_batch.mjs'),str(out/'evidence_bundles.json'),str(out/'verifier_receipts.json')],check=True)
    print(json.dumps({'runs':len(rows),'output':str(out),'frozen_design_sha256':digest(out/'frozen_design.json')}))

if __name__=='__main__':main()
