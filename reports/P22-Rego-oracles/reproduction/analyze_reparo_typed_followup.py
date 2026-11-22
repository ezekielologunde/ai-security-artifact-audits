"""Distinguish static candidates, per-request witnesses and complete-suite outcomes."""
from collections import Counter
from pathlib import Path
import gzip
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parent
WORK=ROOT/'work/reparo-typed-followup-v1'
manifest=json.loads((WORK/'manifest.json').read_text(encoding='utf-8'))
records={}
for p in (WORK/'records').glob('*.json.gz'):
    r=json.loads(gzip.decompress(p.read_bytes()))
    key=(r['kind'],r['identity']);assert key not in records
    records[key]=r
assert len(records)==335
def parsed(r):
    if 'parsed' in r:return r['parsed']
    try:return json.loads(r['stdout'])
    except (ValueError,TypeError):return None
def decision(r):
    p=parsed(r)
    if r['exit_code']!=0:return dict(status='command-error',exit_code=r['exit_code'])
    try:value=p['result'][0]['expressions'][0]['value']
    except (KeyError,IndexError,TypeError):return dict(status='undefined-or-unrepresented')
    return dict(status='defined',value=value)
def group(r,name):
    p=parsed(r)
    if not isinstance(p,list):return dict(status='not-executed',exit_code=r['exit_code'],matching_tests=0)
    selected=[t for t in p if re.sub(r'#\d+$','',t['name'])==name]
    outcomes=Counter('error' if t.get('error') else 'skip' if t.get('skip') else 'fail' if t.get('fail') else 'pass' for t in selected)
    return dict(status='executed',exit_code=r['exit_code'],matching_tests=len(selected),outcomes=dict(outcomes),all_pass=bool(selected) and outcomes['pass']==len(selected))
cases=[]
for c in manifest['cases']:
    row=dict(c)
    if not c['mutation_eligible']:
        row['classification']='mutation-ineligible';cases.append(row);continue
    policy=manifest['policies'][c['policy_id']]
    check=records[('check-mutant',c['policy_id'])]
    row['mutant_check_exit_code']=check['exit_code']
    original=decision(records[('decision-original',c['case_id'])])
    mutant=decision(records[('decision-mutant',c['case_id'])])
    og=group(records[('named-original',c['group_id'])],c['test_name'])
    mg=group(records[('named-mutant',c['group_id'])],c['test_name'])
    row.update(original=original,mutant=mutant,original_named_group=og,mutant_named_group=mg)
    ov=original.get('value',{});mv=mutant.get('value',{})
    pass_both=og.get('all_pass',False) and mg.get('all_pass',False)
    witness=check['exit_code']==0 and ov.get('allow') is False and ov.get('deny')==[] and mv.get('allow') is True and mv.get('deny')==[] and pass_both
    baseline_counterexample=ov.get('allow') is True and ov.get('deny')==[] and og.get('all_pass',False)
    row['primary_mechanistic_witness']=witness
    row['baseline_allow_true_empty_deny_while_negative_group_passes']=baseline_counterexample
    row['named_group_passes_original_and_mutant']=pass_both
    row['classification']='strict-mechanistic-witness' if witness else 'baseline-permissive-signals-with-passing-negative-assertion' if baseline_counterexample else 'other-recorded-outcome'
    cases.append(row)
baseline_index=json.loads((ROOT/'results/reparo_native_command_index_20261121.json').read_text(encoding='utf-8'))
baseline={(r['kind'],r['identity']):r for r in baseline_index}
suites=[]
for suite in manifest['suites']:
    original=baseline[('test',suite)]
    mutant=records[('mutant-suite',suite)]
    p=parsed(mutant)
    suites.append(dict(suite=suite,original_exit_code=original['exit_code'],original_tests=original['tests'],original_outcomes=original['outcomes'],mutant_exit_code=mutant['exit_code'],mutant_tests=len(p) if isinstance(p,list) else None,mutant_outcomes=dict(Counter('error' if t.get('error') else 'skip' if t.get('skip') else 'fail' if t.get('fail') else 'pass' for t in p)) if isinstance(p,list) else None,original_full_suite_passed=original['exit_code']==0 and original['tests']>0,mutant_full_suite_passed=mutant['exit_code']==0 and isinstance(p,list) and len(p)>0))
primary=[c for c in cases if c.get('primary_mechanistic_witness')]
baseline_counter=[c for c in cases if c.get('baseline_allow_true_empty_deny_while_negative_group_passes')]
source=ROOT/'data/reparo-archive-20261121/selected/Final Policy with Test oracle/rego'
inventory=json.loads((ROOT/'work/reparo-corpus-replay-v2/inventory.json').read_text(encoding='utf-8'))
actual={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
assert actual==inventory['source_hashes']
checks={identity:r['exit_code'] for (kind,identity),r in records.items() if kind=='check-mutant'}
denominator=sum(s['original_full_suite_passed'] for s in suites)
escapes=sum(s['original_full_suite_passed'] and s['mutant_full_suite_passed'] for s in suites)
strict_suites={c['suite'] for c in primary}
confirmed_escapes=sum(s['original_full_suite_passed'] and s['mutant_full_suite_passed'] and s['suite'] in strict_suites for s in suites)
summary=dict(date='2026-11-21',source_informed_static_candidates=83,mutation_eligible_cases=sum(c['mutation_eligible'] for c in cases),mutation_ineligible_cases=sum(not c['mutation_eligible'] for c in cases),mutant_policies=len(checks),mutant_checks=dict(Counter(str(c) for c in checks.values())),native_commands=335,strict_mechanistic_witness_cases=len(primary),strict_witness_suites=len({c['suite'] for c in primary}),strict_witness_policy_variants=len({c['policy_id'] for c in primary}),strict_witness_repositories=len({c['policy_id'].split('/')[0] for c in primary}),baseline_allow_true_empty_deny_with_passing_negative_cases=len(baseline_counter),baseline_counterexample_suites=len({c['suite'] for c in baseline_counter}),named_groups_pass_both_cases=sum(c.get('named_group_passes_original_and_mutant',False) for c in cases),full_suites_evaluated=len(suites),originally_passing_candidate_suites=denominator,passing_suites_unrejecting_default_change=escapes,passing_suites_with_strict_source_request_semantic_witness=confirmed_escapes,full_suite_interpretation='A default change remaining un-rejected is not a confirmed semantic mutant escape without a distinguishing request in the stated domain. No such strict source-request witness is established for the originally passing suites here.',all_acquired_source_hashes_unchanged=True,new_model_calls=0,interpretation='Conditional native test-semantics observations. No authentication of application intent, paper aggregate score correction, deployment exploit, population prevalence or new mutation-testing algorithm claimed. Native duplicate test instances are grouped; unique cases retain distinct literal inputs.',runtime='Official OPA v1.22.4 qualification runtime; paper runtime identity not established')
(ROOT/'results/reparo_typed_followup_summary_20261121.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
(ROOT/'results/reparo_typed_followup_cases_20261121.json').write_text(json.dumps(cases,indent=2)+'\n',encoding='utf-8')
(ROOT/'results/reparo_typed_followup_suites_20261121.json').write_text(json.dumps(suites,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,indent=2))
