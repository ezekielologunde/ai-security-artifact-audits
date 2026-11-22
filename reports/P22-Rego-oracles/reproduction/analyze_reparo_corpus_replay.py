"""Summarize all native outcomes and conservatively inventory typed assertion candidates."""
from collections import Counter, defaultdict
from pathlib import Path
import gzip
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parent
WORK=ROOT/'work/reparo-corpus-replay-v2'
SOURCE=ROOT/'data/reparo-archive-20261121/selected/Final Policy with Test oracle/rego'
inventory=json.loads((WORK/'inventory.json').read_text(encoding='utf-8'))
paths=sorted((WORK/'records').glob('*.json.gz'))
assert len(paths)==1050
summaries={};policy_meta={};test_paths={}
def ref(term):
    if not isinstance(term,dict):return None
    if term.get('type')=='var':return (term['value'],)
    if term.get('type')=='ref' and all(t.get('type') in ('var','string') for t in term['value']):return tuple(t['value'] for t in term['value'])
    return None
def package(ast):return tuple(p['value'] for p in ast.get('package',{}).get('path',[]))
def outcome(test):
    if test.get('error'):return 'error'
    if test.get('skip'):return 'skip'
    return 'fail' if test.get('fail') else 'pass'
def base_name(name):return re.sub(r'#\d+$','',str(name))
for path in paths:
    row=json.loads(gzip.decompress(path.read_bytes()))
    key=(row['kind'],row['identity']);assert key not in summaries
    parsed=row.get('parsed')
    stats=Counter()
    native_names=[]
    if row['kind']=='test' and isinstance(parsed,list):
        for t in parsed:
            native_names.append(dict(name=t['name'],base_name=base_name(t['name']),outcome=outcome(t),location=t.get('location')))
            stats[outcome(t)]+=1
    errors=parsed.get('errors',[]) if isinstance(parsed,dict) else []
    summaries[key]=dict(kind=row['kind'],identity=row['identity'],exit_code=row.get('exit_code'),timeout=row.get('timeout',False),native_result_type=type(parsed).__name__,tests=len(native_names),outcomes=dict(stats),native_tests=native_names,error_messages=[e.get('message') for e in errors],stderr_head=row.get('stderr','')[:1000],record=path.relative_to(ROOT).as_posix())
    if row['kind']=='parse-policy' and row['exit_code']==0 and isinstance(parsed,dict):
        heads=[r.get('head',{}) for r in parsed.get('rules',[]) if r.get('head',{}).get('name')=='deny']
        policy_meta[row['identity']]=dict(package=package(parsed),deny_partial_set=bool(heads) and all('key' in h and 'value' not in h for h in heads),deny_heads=len(heads))
    if row['kind']=='parse-tests' and row['exit_code']==0:test_paths[row['identity']]=path
assert len(summaries)==1050
saved={s['identity']:s for s in inventory['saved_csv']}
comparisons=[]
for identity,csv in saved.items():
    native=summaries[('test',identity)]
    original=Counter(str(r.get('opa_result','')).lower() for r in csv['rows'])
    expected=Counter((str(r.get('test_id','')),str(r.get('opa_result','')).lower()) for r in csv['rows'])
    actual=Counter((r['base_name'],r['outcome']) for r in native['native_tests'])
    recognized=all(status in ('pass','fail','error','skip') for _,status in expected)
    comparable=recognized and native['native_result_type']=='list'
    comparisons.append(dict(identity=identity,saved_rows=len(csv['rows']),saved_outcomes=dict(original),native_tests=native['tests'],native_outcomes=native['outcomes'],native_exit_code=native['exit_code'],native_assertions_executed=native['native_result_type']=='list',recognized_csv_statuses=recognized,name_outcome_multiset_equal=(actual==expected) if comparable else None,count_outcomes_equal=(Counter(native['outcomes'])==original) if comparable else None,comparison_scope='Name/outcome multisets after native duplicate-name suffix normalization; not exact source-occurrence correspondence'))
def literal(term):
    kind=term.get('type');value=term.get('value')
    if kind in ('string','number','boolean','null'):return value
    if kind=='array':return [literal(x) for x in value]
    if kind=='object':
        result={}
        for k,v in value:
            key=literal(k)
            if not isinstance(key,str) or key in result:raise ValueError('non-string/duplicate key')
            result[key]=literal(v)
        return result
    raise ValueError('nonliteral '+str(kind))
candidates=[];total_test_rules=0;ast_failed=325-len(test_paths)
for identity,path in sorted(test_paths.items()):
    row=json.loads(gzip.decompress(path.read_bytes()))
    ast=row['parsed']
    policy_id=identity.rsplit('/',1)[0]
    meta=policy_meta.get(policy_id)
    csv_rows=saved[identity]['rows']
    rules=ast.get('rules',[])
    for ordinal,rule in enumerate(rules):
        name=rule.get('head',{}).get('name','')
        if not name.startswith('test_'):continue
        total_test_rules+=1
        body=rule.get('body',[])
        if len(body)!=1 or body[0].get('negated'):continue
        term=ref(body[0].get('terms'))
        if term not in (('deny',),package(ast)+('deny',)):continue
        labels={str(r.get('expected_outcome','')).lower() for r in csv_rows if r.get('test_id')==name}
        binding=body[0].get('with',[])
        request=None;binding_issue=None
        try:
            assert len(binding)==1 and ref(binding[0]['target'])==('input',)
            request=literal(binding[0]['value'])
            assert isinstance(request,dict)
        except (AssertionError,ValueError,KeyError,TypeError) as exc:binding_issue=type(exc).__name__+': '+str(exc)
        original_native=summaries[('test',identity)]
        typed=bool(meta and meta['deny_partial_set'] and tuple(meta['package'])==package(ast))
        record=dict(suite=identity,policy_id=policy_id,test_name=name,ast_rule_ordinal=ordinal,policy_package=list(meta['package']) if meta else None,matching_csv_expected_labels=sorted(labels),deny_rule_is_partial_set_in_same_package=typed,native_policy_check_exit_code=summaries[('check',policy_id)]['exit_code'],native_suite_assertions_executed=original_native['native_result_type']=='list',literal_input=request,input_binding_issue=binding_issue,status='Candidate assertion; not a confirmed per-request verdict/mutation witness')
        record['eligible_for_semantic_followup']=typed and labels=={'deny'} and request is not None and record['native_policy_check_exit_code']==0 and record['native_suite_assertions_executed']
        record['candidate_id']=hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()[:20]
        candidates.append(record)
eligible=[r for r in candidates if r['eligible_for_semantic_followup']]
unique={json.dumps([r['suite'],r['test_name'],r['literal_input']],sort_keys=True) for r in eligible}
counts_by_kind={kind:dict(Counter(str(s['exit_code']) for (k,_),s in summaries.items() if k==kind)) for kind in ('check','parse-policy','parse-tests','test')}
result=dict(date='2026-11-21',policies=200,oracle_suites_present=325,possible_suites=400,missing_suites=75,logical_commands=1050,native_exit_codes=counts_by_kind,saved_csv_rows=sum(c['saved_rows'] for c in comparisons),native_named_test_instances=sum(c['native_tests'] for c in comparisons),native_suites_with_assertions=sum(c['native_assertions_executed'] for c in comparisons),csv_comparison_eligible=sum(c['name_outcome_multiset_equal'] is not None for c in comparisons),csv_name_outcome_multisets_equal=sum(c['name_outcome_multiset_equal'] is True for c in comparisons),csv_name_outcome_multisets_different=sum(c['name_outcome_multiset_equal'] is False for c in comparisons),test_ast_parse_failures=ast_failed,parsed_test_rule_occurrences=total_test_rules,bare_deny_single_expression_candidates=len(candidates),typed_expected_deny_literal_candidates=len(eligible),unique_suite_name_input_candidates=len(unique),candidate_suites=len({r['suite'] for r in eligible}),candidate_policy_variants=len({r['policy_id'] for r in eligible}),candidate_repositories=len({r['policy_id'].split('/')[0] for r in eligible}),new_model_calls=0,scope='Pinned modern-runtime replay and conservative AST candidate inventory; no prevalence of real intent errors, per-request confirmation, paper-score correction or field-wide priority inferred.')
(ROOT/'results/reparo_corpus_analysis_20261121.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
(ROOT/'results/reparo_csv_native_comparison_20261121.json').write_text(json.dumps(comparisons,indent=2)+'\n',encoding='utf-8')
(ROOT/'results/reparo_bare_deny_candidates_20261121.json').write_text(json.dumps(candidates,indent=2)+'\n',encoding='utf-8')
(ROOT/'results/reparo_native_command_index_20261121.json').write_text(json.dumps(list(summaries.values()),indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
