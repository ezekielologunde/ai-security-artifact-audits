"""Replay constructed evidence-route conformance. No model/example execution."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases',type=Path,default=ROOT/'cases.json')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Refusing overwrite')
    expected=json.loads((ROOT/'expected.json').read_text(encoding='utf-8'))
    assert sha(args.cases)==expected['dataset_sha256']
    assert sha(ROOT/'core.py')==expected['implementation_sha256']
    spec=importlib.util.spec_from_file_location('authored_sensitivity_core',ROOT/'core.py')
    core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    cases=json.loads(args.cases.read_text(encoding='utf-8'))
    counts={m:Counter({'tp':0,'fp':0,'fn':0,'tn':0}) for m in ['overlay','overlay_bound_loader']}
    paired=Counter();outputs=[]
    for case in cases:
        predictions={mode:core.analyze(case['snapshot'],mode=mode) for mode in counts}
        outputs.append({case['case_id']:predictions})
        firing={mode:predictions[mode]['overlay']['loading_exposure']=='observed-loading-exposure' for mode in counts}
        truth=case['reference']['enabled_declared_custom_route']
        for mode in counts:
            value=firing[mode];counts[mode]['tp' if truth and value else 'fn' if truth else 'fp' if value else 'tn']+=1
        paired[f"default={firing['overlay']},strict={firing['overlay_bound_loader']}"]+=1
    assert counts==expected['counts'] and paired==expected['paired_firings']
    digest=hashlib.sha256(json.dumps(outputs,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert digest==expected['outputs_sha256']
    assert sha(args.cases)==expected['dataset_sha256'] and sha(ROOT/'core.py')==expected['implementation_sha256']
    result={'case_count':len(cases),'counts':{k:dict(v) for k,v in counts.items()},
            'paired_firings':dict(paired),'all_144_outputs_match':True,
            'outputs_sha256':digest,'model_calls':0,'example_executions':0,
            'scope':'Authored evidence-route conformance, not natural accuracy or runtime security'}
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
