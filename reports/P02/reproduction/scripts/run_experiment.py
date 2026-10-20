"""Reproduce descriptive observations and a small controlled conformance benchmark."""
import collections, copy, csv, dataclasses, hashlib, importlib.metadata, json, pickle, pickletools, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from model_consistency.core import analyze, normalize_model_id
from picklescan.scanner import scan_file_path
OUT=ROOT/'results'; OUT.mkdir(exist_ok=True)

def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')

def static_format(payload):
    try:
        ops=list(pickletools.genops(payload))
        if ops and ops[-1][0].name=='STOP' and ops[-1][2]+1==len(payload):return 'pickle'
    except Exception:pass
    # Structural fixture validation only. Tensor content has no execution semantics.
    if len(payload)>=8:
        size=int.from_bytes(payload[:8],'little')
        if 2<=size<=len(payload)-8:
            try:
                header=json.loads(payload[8:8+size])
                if isinstance(header,dict) and all(k=='__metadata__' or isinstance(v,dict) and {'dtype','shape','data_offsets'}<=v.keys() for k,v in header.items()):return 'safetensors'
            except Exception:pass
    return 'unknown'

def fixtures():
    folder=ROOT/'experiment/fixtures';folder.mkdir(parents=True,exist_ok=True)
    header=json.dumps({'x':{'dtype':'F32','shape':[1],'data_offsets':[0,4]}},separators=(',',':')).encode()
    header+=b' '*((-len(header))%8)
    payloads={'benign.pkl':pickle.dumps({'weights':[1,2,3]},protocol=4),
              'suspicious.pkl':b'cbuiltins\neval\n.',
              'model.safetensors':len(header).to_bytes(8,'little')+header+b'\0'*4,
              'opaque.bin':b'This is plain text, not a pickle artifact.',
              'modeling_custom.py':b'class CustomModel: pass\n'}
    records={}
    for name,payload in payloads.items():
        path=folder/name;path.write_bytes(payload)
        records[name]={'path':name,'sha256':hashlib.sha256(payload).hexdigest(),'format':static_format(payload),'bytes':len(payload)}
        if name.endswith('.pkl'):
            scan=scan_file_path(str(path))
            dump(OUT/'scanner'/f'{name}.json',{'scanner':'PickleScan','version':importlib.metadata.version('picklescan'),'artifact_sha256':records[name]['sha256'],'original_result':dataclasses.asdict(scan)})
    dump(OUT/'fixture_manifest.json',records)
    return records

def observational():
    records=json.loads((ROOT/'data/experiment/manifest.json').read_text())
    rows=[];snapshots=[]
    for r in records:
        if r['status']!='collected':continue
        folder=ROOT/r['folder'];meta=json.loads((folder/'metadata.json').read_text())
        def read_json(name):
            path=folder/name
            return json.loads(path.read_text()) if path.exists() else {}
        readme=(folder/'README.md').read_text(encoding='utf-8',errors='replace') if (folder/'README.md').exists() else ''
        cfg=read_json('config.json');adapter=read_json('adapter_config.json')
        declared=meta.get('cardData',{}).get('base_model',[])
        if isinstance(declared,str):declared=[declared]
        if not isinstance(declared,list):declared=[]
        bases=[normalize_model_id(x) for x in declared if isinstance(x,str)]
        target=adapter.get('base_model_name_or_path');category='no-adapter-config'
        if adapter:
            if not target:category='adapter-base-missing'
            elif not bases:category='card-base-missing'
            elif '/' not in target or target.startswith(('/', '.', 'C:')):category='unresolved-local-base'
            elif normalize_model_id(target) in bases:category='declarations-agree'
            else:category='candidate-declaration-disagreement'
        names=[x['rfilename'] for x in meta.get('siblings',[])]
        snap={'model_id':r['model_id'],'revision':r['revision'],'readme':readme,'card_data':meta.get('cardData',{}),'config':cfg,'adapter_config':adapter,
              'artifacts':[{'path':p,'format':'unknown'} for p in names], 'loading_path':{}}
        report=analyze(snap)
        dump(OUT/'real_reports'/f'{folder.name}.json',report)
        dump(ROOT/'data/experiment/snapshots'/f'{folder.name}.json',snap)
        rows.append({'model_id':r['model_id'],'revision':r['revision'],'folder':r['folder'],'card_bases':bases,'adapter_base':target,
                     'comparison':category,'card_present':bool(readme),'adapter_config_present':bool(adapter),'config_present':bool(cfg),
                     'pickle_named':any(p.endswith(('.bin','.pt','.pth','.pkl','.pickle')) for p in names),
                     'safetensors_named':any(p.endswith('.safetensors') for p in names),'auto_map_present':bool(cfg.get('auto_map')),
                     'explicit_supported_claims':len(report['overlay']['claim_assessments']),
                     'contradicted_claims':sum(x['consistency']=='contradicted' for x in report['overlay']['claim_assessments'])})
        snapshots.append(snap)
    summary={'frame_size':len(json.loads((ROOT/'data/experiment/peft_top100_frame.json').read_text())),
             'sample_requested':len(records),'collected':len(rows),'unavailable':len(records)-len(rows),
             'card_present':sum(x['card_present'] for x in rows),'adapter_config_present':sum(x['adapter_config_present'] for x in rows),
             'config_present':sum(x['config_present'] for x in rows),'card_base_present':sum(bool(x['card_bases']) for x in rows),
             'comparisons':dict(collections.Counter(x['comparison'] for x in rows)),
             'pickle_named':sum(x['pickle_named'] for x in rows),'safetensors_named':sum(x['safetensors_named'] for x in rows),
             'both_named':sum(x['pickle_named'] and x['safetensors_named'] for x in rows),
             'auto_map_present':sum(x['auto_map_present'] for x in rows),'supported_claims':sum(x['explicit_supported_claims'] for x in rows),
             'contradicted_supported_claims':sum(x['contradicted_claims'] for x in rows),
             'scope':'observations in a sampled top-download PEFT-tagged frame; no confirmed-malware or true-lineage labels'}
    dump(OUT/'observational_rows.json',rows);dump(OUT/'observational_summary.json',summary)
    return snapshots

def make_cases(artifacts,sources):
    cases=[]
    def add(name,text,kind,expected,files=None,base=None,selected=None,code=False,trust=False,report_mode=None,exposure=False):
        snapshot={'model_id':'controlled/'+name,'revision':'a'*40,
                  'readme':f'# Controlled case {name}\n\n{text}\n','config':{'model_type':'bert'},'adapter_config':{},
                  'artifacts':[copy.deepcopy(artifacts[f]) for f in (files or [])],
                  'loading_path':{'artifacts':selected or [],'auto_class':'AutoModel'}}
        if base:snapshot['adapter_config']={'base_model_name_or_path':base}
        if code:snapshot['config']['auto_map']={'AutoModel':'modeling_custom.CustomModel'}
        if trust:snapshot['readme']+='\n```python\nAutoModel.from_pretrained(repo, trust_remote_code=True)\n```\n'
        report=None
        if report_mode:
            raw=json.loads((OUT/'scanner/benign.pkl.json').read_text())
            report={'scanner':raw['scanner'],'version':raw['version'],'target':{'model_id':snapshot['model_id'],'revision':snapshot['revision']},
                    'artifact_sha256':{'benign.pkl':artifacts['benign.pkl']['sha256']},'verified_formats':{'benign.pkl':'pickle'},
                    'original_result':raw['original_result']}
            for a in snapshot['artifacts']:
                if a['path']=='benign.pkl':a['format']='unknown'
            if report_mode=='stale':report['target']['revision']='b'*40
            if report_mode=='wrong-hash':report['artifact_sha256']['benign.pkl']='0'*64
        cases.append({'case_id':name,'family':kind,'expected_contradiction':expected,'expected_exposure':exposure,'snapshot':snapshot,'scanner_report':report})
    # Fourteen serialization cases, including deliberate grammar challenges.
    add('exclusive-pickle','Weights are only Safetensors.','serialization',True,['benign.pkl'],selected=['benign.pkl'],exposure=True)
    add('exclusive-safe','Weights are exclusively Safetensors.','serialization',False,['model.safetensors'],selected=['model.safetensors'])
    add('no-pickle-opaque','There are no pickle files in this repository.','serialization',False,['opaque.bin'],selected=['opaque.bin'])
    add('path-mixed','The selected loading path is pickle-free.','serialization',False,['benign.pkl','model.safetensors'],selected=['model.safetensors'])
    add('repository-mixed','This repository is pickle-free.','serialization',True,['benign.pkl','model.safetensors'],selected=['model.safetensors'])
    add('availability','Safetensors weights are available.','serialization',False,['benign.pkl','model.safetensors'],selected=['model.safetensors'])
    add('not-only','Weights are not only Safetensors; a legacy pickle is available.','serialization',False,['benign.pkl','model.safetensors'],selected=['model.safetensors'])
    add('quoted','> Example: only Safetensors weights.','serialization',False,['benign.pkl'],selected=['benign.pkl'],exposure=True)
    add('stale-scanner','There are no pickle weights.','serialization',False,['benign.pkl'],selected=['benign.pkl'],report_mode='stale')
    add('bound-scanner','There are no pickle weights.','serialization',True,['benign.pkl'],selected=['benign.pkl'],report_mode='bound',exposure=True)
    add('bad-hash','There are no pickle artifacts.','serialization',False,['benign.pkl'],selected=['benign.pkl'],report_mode='wrong-hash')
    add('suspicious-global','This repository is pickle-free.','serialization',True,['suspicious.pkl'],selected=['suspicious.pkl'],exposure=True)
    add('unrecognized-format-paraphrase','All checkpoints use the safe tensor format, with no Python serialization.','serialization',True,['benign.pkl'],selected=['benign.pkl'],exposure=True)
    add('unknown-format','Weights are only Safetensors.','serialization',False,['opaque.bin'])
    # Ten adapter cases. Training ancestry is intentionally outside this relationship.
    add('base-disagrees','Adapter requires base model `org/A`.','adapter-base',True,base='org/B')
    add('base-agrees','Adapter requires base model `org/A`.','adapter-base',False,base='org/A')
    add('base-url','Adapter loads https://huggingface.co/org/A.','adapter-base',False,base='org/A')
    add('base-missing','Adapter uses org/A.','adapter-base',False)
    add('base-local','Adapter base: org/A.','adapter-base',False,base='./checkpoint')
    add('ancestral','Fine-tuned from org/A; adapter deployment uses a later checkpoint.','adapter-base',False,base='org/B')
    add('merge-input','Merge inputs include org/A and org/C.','adapter-base',False,base='org/B')
    add('case-sensitive','Adapter requires base model org/A.','adapter-base',True,base='org/a')
    add('unrecognized-base-paraphrase','The adapter must be attached to org/A at inference time.','adapter-base',True,base='org/B')
    add('base-hyphen','Adapter base model: org/Model-A.','adapter-base',False,base='org/Model-A')
    # Twelve code/loading cases. Present source alone is not proof of execution.
    add('code-required','No custom Python code is required.','custom-code',True,['model.safetensors','modeling_custom.py'],selected=['model.safetensors'],code=True,trust=True,exposure=True)
    add('code-present-only','No custom code is required.','custom-code',False,['model.safetensors','modeling_custom.py'],selected=['model.safetensors'])
    add('trust-without-mapping','No custom code is required.','custom-code',False,['model.safetensors'],selected=['model.safetensors'],trust=True)
    add('mapping-without-trust','No custom code is required.','custom-code',False,['model.safetensors','modeling_custom.py'],selected=['model.safetensors'],code=True)
    add('disclosed-code','Custom Python code is required; review it before loading.','custom-code',False,['model.safetensors','modeling_custom.py'],selected=['model.safetensors'],code=True,trust=True,exposure=True)
    add('source-missing','No custom code is required.','custom-code',False,['model.safetensors'],selected=['model.safetensors'],code=True,trust=True)
    add('no-code-negation','This model does not require custom code.','custom-code',True,['modeling_custom.py'],code=True,trust=True,exposure=True)
    add('unrecognized-code-paraphrase','Loading executes exclusively the standard library implementation.','custom-code',True,['modeling_custom.py'],code=True,trust=True,exposure=True)
    add('safe-weights-code','Weights are only Safetensors.','custom-code',False,['model.safetensors','modeling_custom.py'],selected=['model.safetensors'],code=True,trust=True,exposure=True)
    add('legacy-unused','No custom code is required.','custom-code',False,['benign.pkl','model.safetensors'],selected=['model.safetensors'])
    add('legacy-selected','No custom code is required.','custom-code',False,['benign.pkl','model.safetensors'],selected=['benign.pkl'],exposure=True)
    add('no-artifacts','No custom code is required.','custom-code',False)
    assert len(cases)==36
    dump(ROOT/'experiment/controlled_cases.json',cases)
    return cases

def score(labels,preds):
    tp=sum(a and b for a,b in zip(labels,preds));fp=sum(not a and b for a,b in zip(labels,preds))
    fn=sum(a and not b for a,b in zip(labels,preds));tn=sum(not a and not b for a,b in zip(labels,preds))
    precision=tp/(tp+fp) if tp+fp else None;recall=tp/(tp+fn) if tp+fn else None
    return {'TP':tp,'FP':fp,'FN':fn,'TN':tn,'precision':precision,'recall':recall,'F1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}

def controlled(cases):
    predictions=[];systems={}
    for mode in ['documentation_only','filename_rule','overlay','overlay_without_scope','overlay_without_revision_binding']:
        cp=[];ep=[];missing=0;unknown=0;preserved=0
        started=time.perf_counter()
        for case in cases:
            result=analyze(case['snapshot'],case['scanner_report'],mode)
            findings=result['overlay']['claim_assessments']
            contradiction=any(x['consistency']=='contradicted' for x in findings)
            exposure=result['overlay']['loading_exposure']=='observed-loading-exposure'
            cp.append(contradiction);ep.append(exposure)
            missing+=not findings;unknown+=sum(x['consistency']=='unverifiable' for x in findings)
            preserved+=result['upstream_report']==case['scanner_report']
            predictions.append({'case_id':case['case_id'],'mode':mode,'expected_contradiction':case['expected_contradiction'],'predicted_contradiction':contradiction,
                                'expected_exposure':case['expected_exposure'],'predicted_exposure':exposure,'result':result})
        systems[mode]={'contradiction':score([x['expected_contradiction'] for x in cases],cp),
                       'exposure':score([x['expected_exposure'] for x in cases],ep),'cases_without_extracted_claim':missing,
                       'unverifiable_claims':unknown,'upstream_reports_preserved':preserved,'runtime_seconds':time.perf_counter()-started}
    summary={'cases':len(cases),'positive_contradictions':sum(x['expected_contradiction'] for x in cases),'positive_exposures':sum(x['expected_exposure'] for x in cases),
             'families':dict(collections.Counter(x['family'] for x in cases)),'systems':systems,
             'evaluation_boundary':'developer-authored controlled conformance cases, no independent annotation, no real-world precision claim'}
    dump(OUT/'controlled_predictions.json',predictions);dump(OUT/'controlled_summary.json',summary)
    errors=[x for x in predictions if x['mode']=='overlay' and (x['expected_contradiction']!=x['predicted_contradiction'] or x['expected_exposure']!=x['predicted_exposure'])]
    dump(OUT/'error_analysis.json',errors)
    return summary

def verify_receipts():
    receipts=[json.loads(p.read_text()) for p in (ROOT/'data/experiment').rglob('*.receipt.json')]
    failures=[]
    for r in receipts:
        payload=(ROOT/r['path']).read_bytes()
        if hashlib.sha256(payload).hexdigest()!=r['sha256'] or len(payload)!=r['bytes']:failures.append(r['path'])
    dump(OUT/'receipt_verification.json',{'verified_files':len(receipts),'downloaded_bytes':sum(r['bytes'] for r in receipts),'failures':failures})
    if failures:raise RuntimeError('Receipt validation failed')

def main():
    verify_receipts(); art=fixtures(); sources=observational();summary=controlled(make_cases(art,sources))
    dump(OUT/'environment.json',{'python':sys.version,'picklescan':importlib.metadata.version('picklescan'),'pyyaml':importlib.metadata.version('PyYAML'),
                              'completed_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'protocol_sha256':hashlib.sha256((ROOT/'experiment/protocol.json').read_bytes()).hexdigest()})
    print(json.dumps({'observational':json.loads((OUT/'observational_summary.json').read_text()),'controlled':summary},indent=2))

if __name__=='__main__':main()
