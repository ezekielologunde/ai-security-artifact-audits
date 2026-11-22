"""Apply a prespecified native semantic check to every screened candidate."""
from collections import defaultdict
from pathlib import Path
import gzip
import hashlib
import json
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parent
WORK=ROOT/'work/reparo-typed-followup-v1'
WORK.mkdir(exist_ok=False)
INPUTS=WORK/'inputs';INPUTS.mkdir()
RECORDS=WORK/'records';RECORDS.mkdir()
SOURCE=ROOT/'data/reparo-archive-20261121/selected/Final Policy with Test oracle/rego'
candidate_path=ROOT/'results/reparo_bare_deny_candidates_20261121.json'
candidates=json.loads(candidate_path.read_text(encoding='utf-8'))
selected=[c for c in candidates if c['eligible_for_semantic_followup']]
assert len(selected)==148
unique={json.dumps([c['suite'],c['test_name'],c['literal_input']],sort_keys=True):c for c in selected}
assert len(unique)==83
cases=[];tasks=[];policies={};groups={};suite_map={}
def record_path(kind,identity):
    name=hashlib.sha256((kind+'\0'+identity).encode()).hexdigest()+'.json.gz'
    return ROOT/'work/reparo-corpus-replay-v2/records'/name
pattern=re.compile(rb'(?m)^([ \t]*default[ \t]+allow[ \t]*(?::=|=)[ \t]*)false([ \t]*(?:#[^\r\n]*)?\r?$)')
for policy_id in sorted({c['policy_id'] for c in selected}):
    ast=json.loads(gzip.decompress(record_path('parse-policy',policy_id).read_bytes()))['parsed']
    defaults=[r for r in ast.get('rules',[]) if r.get('default') and r.get('head',{}).get('name')=='allow' and r['head'].get('value')=={'type':'boolean','value':False}]
    original=(SOURCE/policy_id/'final_policy.rego').read_bytes()
    matches=list(pattern.finditer(original))
    directory=hashlib.sha256(policy_id.encode()).hexdigest()[:20]
    p=INPUTS/directory;p.mkdir()
    (p/'original.rego').write_bytes(original)
    eligible=len(defaults)==1 and len(matches)==1
    info=dict(policy_id=policy_id,directory=directory,eligible=eligible,ast_defaults=len(defaults),source_declarations=len(matches),original_sha256=hashlib.sha256(original).hexdigest())
    if eligible:
        mutant=pattern.sub(lambda m:m.group(1)+b'true'+m.group(2),original)
        assert mutant!=original
        (p/'mutant.rego').write_bytes(mutant)
        info['mutant_sha256']=hashlib.sha256(mutant).hexdigest()
        tasks.append(dict(kind='check-mutant',identity=policy_id,args=['check','/inputs/'+directory+'/mutant.rego']))
    policies[policy_id]=info
for number,(serialized,candidate) in enumerate(sorted(unique.items())):
    cid=hashlib.sha256(serialized.encode()).hexdigest()[:20]
    info=policies[candidate['policy_id']]
    case=dict(case_id=cid,suite=candidate['suite'],policy_id=candidate['policy_id'],test_name=candidate['test_name'],request=candidate['literal_input'],mutation_eligible=info['eligible'])
    cases.append(case)
    if not info['eligible']:continue
    directory=info['directory']
    input_file=directory+'/'+cid+'.json'
    (INPUTS/input_file).write_text(json.dumps(candidate['literal_input']),encoding='utf-8')
    package='.'.join(candidate['policy_package'])
    query='{"allow":'+package+'.allow,"deny":'+package+'.deny}'
    for variant in ('original','mutant'):
        tasks.append(dict(kind='decision-'+variant,identity=cid,args=['eval','--format','json','--data','/inputs/'+directory+'/'+variant+'.rego','--input','/inputs/'+input_file,'--stdin'],stdin=query))
    suite=candidate['suite']
    if suite not in suite_map:
        test_name='tests-'+hashlib.sha256(suite.encode()).hexdigest()[:12]+'.rego'
        oracle=suite.rsplit('/',1)[1]
        (INPUTS/directory/test_name).write_bytes((SOURCE/candidate['policy_id']/('final_rendered_tests_'+oracle+'.rego')).read_bytes())
        suite_map[suite]=dict(directory=directory,test_file=test_name)
        tasks.append(dict(kind='mutant-suite',identity=suite,args=['test','--format','json','--verbose','--timeout','10s','/inputs/'+directory+'/mutant.rego','/inputs/'+directory+'/'+test_name]))
    group_id=hashlib.sha256((suite+'\0'+candidate['test_name']).encode()).hexdigest()[:20]
    case['group_id']=group_id
    if group_id not in groups:
        groups[group_id]=dict(suite=suite,test_name=candidate['test_name'])
        for variant in ('original','mutant'):
            tasks.append(dict(kind='named-'+variant,identity=group_id,args=['test','--format','json','--verbose','--timeout','10s','--run',re.escape(candidate['test_name']),'/inputs/'+directory+'/'+variant+'.rego','/inputs/'+directory+'/'+suite_map[suite]['test_file']]))
manifest=dict(date='2026-11-21',candidate_sha256=hashlib.sha256(candidate_path.read_bytes()).hexdigest(),policies=policies,cases=cases,groups=groups,suites=suite_map,tasks=tasks)
(WORK/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
(WORK/'tasks.json').write_text(json.dumps(tasks),encoding='utf-8')
print(json.dumps({'cases':len(cases),'mutation_eligible_cases':sum(c['mutation_eligible'] for c in cases),'policy_variants':len(policies),'groups':len(groups),'commands':len(tasks)}),flush=True)
def wslpath(path):return '/mnt/'+path.drive[0].lower()+'/'+path.as_posix().split(':/',1)[1]
# The shared replay driver preserves native arguments and private namespace boundaries.
command=['wsl.exe','-d','Ubuntu','--','python3',wslpath(ROOT/'replay_reparo_corpus.py'),'--linux-root',wslpath(ROOT),'reparo-typed-followup-v1']
with (WORK/'driver-stderr.txt').open('w',encoding='utf-8') as error_file:
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=error_file,text=True,encoding='utf-8',bufsize=1)
    count=0
    for line in process.stdout:
        row=json.loads(line)
        if row.get('progress'):print(json.dumps(row),flush=True);continue
        name=hashlib.sha256((row['kind']+'\0'+row['identity']).encode()).hexdigest()+'.json.gz'
        (RECORDS/name).write_bytes(gzip.compress(json.dumps(row).encode(),compresslevel=6,mtime=0))
        count+=1
    assert process.wait()==0,(WORK/'driver-stderr.txt').read_text()
assert count==len(tasks)
print(json.dumps({'completed':count,'cases':len(cases),'manifest':'work/reparo-typed-followup-v1/manifest.json'}),flush=True)
