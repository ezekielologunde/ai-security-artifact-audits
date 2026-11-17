"""Standard-library regression; optional hash-checked text acquisition, never weights."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def strip_context(value):
    result=copy.deepcopy(value)
    result['overlay'].pop('loader_context')
    for claim in result['overlay']['claim_assessments']:
        claim.pop('nearby_loader_context_lines')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path,help='New directory; refuses overwrite')
    parser.add_argument('--acquire',action='store_true',help='Fetch seven pinned README/config files with curl')
    args=parser.parse_args()
    if args.output.exists():
        raise SystemExit('Output already exists; choose a fresh directory')
    args.output.mkdir(parents=True)
    authored=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts
              and '.pytest_cache' not in p.parts and not p.is_relative_to(args.output.resolve())]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in authored}
    before=load(ROOT/'core_before.py','before')
    after=load(ROOT/'model_consistency/core.py','after')
    cases=json.loads((ROOT/'experiment/controlled_cases.json').read_text(encoding='utf-8'))
    modes=['documentation_only','filename_rule','overlay','overlay_without_scope','overlay_without_revision_binding']
    checked=0
    for case in cases:
        for mode in modes:
            snap=copy.deepcopy(case['snapshot']); report=copy.deepcopy(case['scanner_report'])
            old=before.analyze(snap,report,mode)
            new=after.analyze(snap,report,mode)
            assert strip_context(new)==old,(case['case_id'],mode)
            assert snap==case['snapshot'] and report==case['scanner_report']
            checked+=1
    discoveries=[]; downloaded=[]
    if args.acquire:
        expected=json.loads((ROOT/'expected_observations.json').read_text(encoding='utf-8'))
        candidates=json.loads((ROOT/'candidates.json').read_text(encoding='utf-8'))
        for case in candidates:
            folder=args.output/case['case_id'];folder.mkdir()
            for item in case['files']:
                assert item['name'] in {'README.md','config.json','adapter_config.json'}
                target=folder/item['name']
                result=subprocess.run(['curl.exe' if sys.platform=='win32' else 'curl',
                    '--location','--fail','--silent','--show-error','--max-time','35',
                    '--max-filesize','4194304','--output',str(target),item['url']],
                    capture_output=True,text=True,timeout=45)
                if result.returncode:
                    raise RuntimeError(f"Acquisition failed for {case['case_id']}/{item['name']}: {result.stderr}")
                assert target.stat().st_size==item['bytes']
                assert hashlib.sha256(target.read_bytes()).hexdigest()==item['sha256']
                downloaded.append({'case_id':case['case_id'],**item})
            cfg=folder/'config.json'
            snap={'model_id':case['model_id'],'revision':case['revision'],
                  'readme':(folder/'README.md').read_text(encoding='utf-8'),
                  'config':json.loads(cfg.read_text(encoding='utf-8')) if cfg.exists() else {},
                  'artifacts':[{'path':n,'format':'unknown'} for n in case['inventory']],
                  'loading_path':{}}
            new=after.analyze(snap)
            assert strip_context(new)==before.analyze(snap)
            overlay=new['overlay']
            observed={'claims':len(overlay['claim_assessments']),
                      'dispositions':[x['consistency'] for x in overlay['claim_assessments']],
                      'loader_observations':len(overlay['loader_context']['observations']),
                      'nearby_context_lines':[x['nearby_loader_context_lines'] for x in overlay['claim_assessments']]}
            assert observed==expected[case['case_id']]
            discoveries.append({'case_id':case['case_id'],'observed':observed})
            (folder/'augmented.json').write_text(json.dumps(new,indent=2)+'\n',encoding='utf-8')
    assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
    receipt={'controlled_comparisons':checked,'discoveries':discoveries,'downloaded_files':downloaded,
             'input_sha256':hashes,'input_bytes_unchanged':True,'previous_fields_unchanged':True,
             'independent_annotations':0,'model_calls':0,'scanner_runs':0,
             'scope':'source-informed regression and observability, not natural accuracy'}
    (args.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'controlled_comparisons':checked,'discovery_cases':len(discoveries),
                      'pinned_files_reacquired':len(downloaded),'previous_fields_unchanged':True}))


if __name__=='__main__':
    main()
