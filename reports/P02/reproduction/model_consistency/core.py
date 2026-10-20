"""Conservative claim checks. No model imports, deserialization, or universal safety score."""
import copy, hashlib, json, re

CONTRADICTED='contradicted'
CONSISTENT='consistent-with-observed-evidence'
UNKNOWN='unverifiable'

def normalize_model_id(value):
    value=str(value).strip().strip('`\"\'').rstrip('/.')
    value=re.sub(r'^https?://huggingface\.co/', '', value)
    return value  # Hub IDs are case-sensitive; do not collapse arbitrary aliases.

def extract_claims(readme):
    claims=[]; in_code=False
    for number,line in enumerate(readme.splitlines(),1):
        text=line.strip()
        if text.startswith('```'): in_code=not in_code; continue
        if in_code or text.startswith('>'): continue
        kind=None; value=None; scope='repository'
        lower=text.lower()
        if re.search(r'\b(only|exclusively)\s+(?:in\s+)?safetensors\b|\bno\s+pickle(?:[- ]based)?\s+(?:files|weights|artifacts)\b|\bpickle[- ]free\b',lower):
            # "not only" and quoted recommendations are not exclusivity assertions.
            if 'not only' in lower or re.search(r'\b(should|recommend|example)\b',lower): continue
            kind='serialization'; value='no-pickle'
            if re.search(r'\b(selected|recommended|this)\s+(?:loading\s+)?path\b',lower):scope='loading-path'
        elif re.search(r'\bno\s+custom\s+(?:python\s+)?code\b|\bdoes not require\s+custom\s+(?:python\s+)?code\b',lower):
            if re.search(r'\b(should|recommend|example)\b',lower):continue
            kind='custom-code';value='no-custom-code';scope='loading-path'
        else:
            match=re.search(r'\b(?:adapter\s+(?:requires|loads|uses)(?:\s+base\s+model)?|adapter\s+base(?:\s+model)?\s*:)\s+[`\"]?((?:https?://huggingface\.co/)?[\w.-]+/[\w.-]+)',text,re.I)
            if match:kind='adapter-base';value=normalize_model_id(match.group(1));scope='adapter-load-dependency'
        if kind:
            claims.append({'claim_type':kind,'claim_value':value,'claim_quote':line,'claim_scope':scope,
                           'source':{'file':'README.md','line':number}})
    return claims

def bind_report(snapshot,report):
    if not report:return 'absent'
    target=report.get('target',{})
    if target.get('model_id')!=snapshot['model_id'] or target.get('revision')!=snapshot['revision']:return 'mismatched-target-or-revision'
    expected={x['path']:x.get('sha256') for x in snapshot.get('artifacts',[]) if x.get('sha256')}
    scanned=report.get('artifact_sha256',{})
    if not scanned:return 'unknown-artifact-identity'
    if any(expected.get(path)!=digest for path,digest in scanned.items()):return 'mismatched-artifact-hash'
    if any(path not in scanned for path in report.get('verified_formats',{})):return 'unbound-format-evidence'
    return 'matched'

def analyze(snapshot,report=None,mode='overlay'):
    snapshot=copy.deepcopy(snapshot)
    binding=bind_report(snapshot,report)
    allow_stale=mode=='overlay_without_revision_binding'
    scope_enabled=mode!='overlay_without_scope'
    docs_only=mode=='documentation_only'
    findings=[]
    artifacts=[] if docs_only else snapshot.get('artifacts',[])
    weight_artifacts=[a for a in artifacts if a.get('format') in ('pickle','safetensors') or a['path'].lower().endswith(('.bin','.pt','.pth','.pkl','.pickle','.safetensors'))]
    formats={a['path']:a.get('format','unknown') for a in weight_artifacts}
    if mode=='filename_rule':
        formats={a['path']:('pickle' if a['path'].lower().endswith(('.bin','.pt','.pth','.pkl','.pickle')) else a.get('format','unknown')) for a in weight_artifacts}
    if report and (binding=='matched' or allow_stale) and not docs_only:
        formats.update({p:v for p,v in report.get('verified_formats',{}).items() if p in {a['path'] for a in artifacts}})
    selected=snapshot.get('loading_path',{}).get('artifacts')
    config={} if docs_only else snapshot.get('config',{})
    adapter={} if docs_only else snapshot.get('adapter_config',{})
    trust=bool(re.search(r'trust_remote_code\s*=\s*True',snapshot.get('readme','')))
    local_py={a['path'][:-3].replace('/','.') for a in artifacts if a['path'].endswith('.py')}
    auto=config.get('auto_map',{})
    references=[]
    for entry in auto.values():
        references.extend(entry if isinstance(entry,list) else [entry])
    # External auto_map modules and unselected loader paths remain indeterminate.
    selected_class=snapshot.get('loading_path',{}).get('auto_class')
    selected_refs=auto.get(selected_class) if selected_class else None
    if isinstance(selected_refs,str):selected_refs=[selected_refs]
    code_used=bool(trust and selected_refs and any(isinstance(r,str) and '--' not in r and r.rsplit('.',1)[0] in local_py for r in selected_refs))
    for claim in extract_claims(snapshot.get('readme','')):
        claim['source']['revision']=snapshot['revision']
        status=UNKNOWN; evidence=[]; reason='Required evidence is unavailable or outside the implemented grammar.'
        if claim['claim_type']=='serialization':
            paths=list(formats)
            if claim['claim_scope']=='loading-path' and scope_enabled:
                paths=selected or []
            inspected=[{'path':p,'format':formats.get(p,'unknown')} for p in paths]
            evidence=inspected
            if any(x['format']=='pickle' for x in inspected):status=CONTRADICTED;reason='Confirmed pickle-format evidence conflicts with the stated scope.'
            elif inspected and all(x['format']=='safetensors' for x in inspected):status=CONSISTENT;reason='All inspected artifacts in the stated scope have Safetensors structure.'
        elif claim['claim_type']=='adapter-base':
            observed=adapter.get('base_model_name_or_path')
            if observed:
                evidence=[{'file':'adapter_config.json','base_model_name_or_path':observed}]
                if '/' not in str(observed) or str(observed).startswith(('/', '.', 'C:', 'D:')):reason='A local path cannot be resolved to a Hub model identity.'
                else:
                    status=CONSISTENT if normalize_model_id(observed)==claim['claim_value'] else CONTRADICTED
                    reason='Compared declarations of the same adapter loading dependency; this does not authenticate training lineage.'
        elif claim['claim_type']=='custom-code':
            evidence=[{'documented_trust_remote_code':trust,'selected_auto_class':selected_class,'selected_auto_map':selected_refs}]
            if code_used:status=CONTRADICTED;reason='The documented selected loader enables a referenced custom module present at this revision.'
            elif selected_class and selected_class not in auto and config and not docs_only:
                status=CONSISTENT;reason='No custom mapping exists for the selected loader in the inspected configuration.'
        findings.append({**claim,'consistency':status,'reason':reason,'evidence':evidence})
    load_paths=list(formats) if not scope_enabled or mode=='filename_rule' else (selected or [])
    confirmed_pickle=any(formats.get(p)=='pickle' for p in load_paths)
    exposure='observed-loading-exposure' if confirmed_pickle or code_used else 'indeterminate'
    if not confirmed_pickle and not code_used and load_paths and all(formats.get(p)=='safetensors' for p in load_paths) and selected_class and selected_class not in auto and config:
        exposure='no-exposure-observed-within-inspected-scope'
    declared=snapshot.get('card_data',{}).get('base_model',[])
    if isinstance(declared,str):declared=[declared]
    declared=[normalize_model_id(x) for x in declared if isinstance(x,str)] if isinstance(declared,list) else []
    observed=adapter.get('base_model_name_or_path')
    provenance={'card_bases':declared,'adapter_load_dependency':observed,'consistency':UNKNOWN,'candidate_disagreement':False,
                'reason':'A comparable card declaration or adapter dependency is absent.'}
    if observed and declared:
        if str(observed).startswith(('/', '.', 'C:', 'D:')) or '/' not in str(observed):
            provenance['reason']='The adapter records an unresolved local path.'
        elif normalize_model_id(observed) in declared:
            provenance.update(consistency=CONSISTENT,reason='The adapter loading dependency appears among the declared card bases; training provenance remains unauthenticated.')
        else:
            provenance.update(candidate_disagreement=True,reason='Different published IDs require review of relationship semantics, aliases and intermediate transformations; false lineage is not established.')
    return {'schema_version':'0.1','target':{'model_id':snapshot['model_id'],'revision':snapshot['revision']},
            'upstream_report':copy.deepcopy(report),
            'overlay':{'mode':mode,'scanner_binding':binding,'claim_assessments':findings,'provenance_comparison':provenance,'loading_exposure':exposure,
                       'limitations':['Only the implemented explicit-claim grammar is assessed.','Agreement does not authenticate provenance or establish safety.','No model code or weight deserialization was executed.']}}
