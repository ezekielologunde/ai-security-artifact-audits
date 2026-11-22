"""Execute a declared-contract assertion comparison on all selected cases."""
from pathlib import Path
from collections import defaultdict
import gzip
import hashlib
import json
import shutil
import subprocess
from rego_assertion_overlay import generate,HELPERS

ROOT=Path(__file__).resolve().parent
WORK=ROOT/'work/reparo-assertion-overlay-v2'
WORK.mkdir(exist_ok=False)
INPUTS=WORK/'inputs';INPUTS.mkdir()
RECORDS=WORK/'records';RECORDS.mkdir()
previous=ROOT/'work/reparo-typed-followup-v1'
manifest=json.loads((previous/'manifest.json').read_text(encoding='utf-8'))
candidate_rows=json.loads((ROOT/'results/reparo_bare_deny_candidates_20261121.json').read_text(encoding='utf-8'))
packages={r['policy_id']:r['policy_package'] for r in candidate_rows if r['eligible_for_semantic_followup']}
by_policy=defaultdict(list)
for c in manifest['cases']:
    if c['mutation_eligible']:by_policy[c['policy_id']].append(dict(case_id=c['case_id'],expected='deny',input=c['request']))
assert sum(map(len,by_policy.values()))==80 and len(by_policy)==9
tasks=[];case_index=[]
for policy_id,cases in sorted(by_policy.items()):
    info=manifest['policies'][policy_id]
    directory=info['directory']
    dst=INPUTS/directory;dst.mkdir()
    for variant in ('original','mutant'):shutil.copyfile(previous/'inputs'/directory/(variant+'.rego'),dst/(variant+'.rego'))
    package='.'.join(packages[policy_id][1:])
    module=generate(package,cases,'bool-allow-deny-overrides')
    (dst/'typed_assertions.rego').write_text(module,encoding='utf-8')
    for variant in ('original','mutant'):
        tasks.append(dict(kind='overlay-'+variant,identity=policy_id,args=['test','--format','json','--verbose','--timeout','10s','/inputs/'+directory+'/'+variant+'.rego','/inputs/'+directory+'/typed_assertions.rego']))
    case_index.extend(dict(case_id=c['case_id'],policy_id=policy_id) for c in cases)
control='package typed_controls\nimport rego.v1\n'+HELPERS+'''
test_allow_true_empty if { _typed_contract_permitted(true, set()) }
test_no_deny_true_empty if { not _typed_contract_denied(true, set()) }
test_deny_false_empty if { _typed_contract_denied(false, set()) }
test_no_allow_false_empty if { not _typed_contract_permitted(false, set()) }
test_deny_true_nonempty if { _typed_contract_denied(true, {"reason"}) }
test_no_allow_true_nonempty if { not _typed_contract_permitted(true, {"reason"}) }
test_deny_false_nonempty if { _typed_contract_denied(false, {"reason"}) }
test_no_allow_false_nonempty if { not _typed_contract_permitted(false, {"reason"}) }
test_null_allow_unresolved if { not _typed_contract_denied(null, set()); not _typed_contract_permitted(null, set()) }
test_array_deny_unresolved if { not _typed_contract_denied(false, []); not _typed_contract_permitted(false, []) }
test_string_allow_unresolved if { not _typed_contract_denied("false", set()); not _typed_contract_permitted("false", set()) }
_missing_denied if { _typed_contract_denied(data.missing_value, set()) }
_missing_permitted if { _typed_contract_permitted(data.missing_value, set()) }
test_missing_allow_unresolved if { not _missing_denied; not _missing_permitted }
'''
(INPUTS/'controls.rego').write_text(control,encoding='utf-8')
tasks.append(dict(kind='contract-controls',identity='truth-table',args=['test','--format','json','--verbose','--timeout','10s','/inputs/controls.rego']))
(WORK/'tasks.json').write_text(json.dumps(tasks),encoding='utf-8')
(WORK/'case-index.json').write_text(json.dumps(case_index,indent=2)+'\n',encoding='utf-8')
def wslpath(path):return '/mnt/'+path.drive[0].lower()+'/'+path.as_posix().split(':/',1)[1]
command=['wsl.exe','-d','Ubuntu','--','python3',wslpath(ROOT/'replay_reparo_corpus.py'),'--linux-root',wslpath(ROOT),'reparo-assertion-overlay-v2']
with (WORK/'driver-stderr.txt').open('w',encoding='utf-8') as error_file:
    p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=error_file,text=True,encoding='utf-8',bufsize=1)
    count=0
    for line in p.stdout:
        row=json.loads(line)
        if row.get('progress'):print(json.dumps(row),flush=True);continue
        name=hashlib.sha256((row['kind']+'\0'+row['identity']).encode()).hexdigest()+'.json.gz'
        (RECORDS/name).write_bytes(gzip.compress(json.dumps(row).encode(),compresslevel=6,mtime=0));count+=1
    assert p.wait()==0,(WORK/'driver-stderr.txt').read_text()
assert count==19
print(json.dumps({'commands':19,'source_cases':80,'authored_contract_controls':12,'contract':'bool-allow-deny-overrides'}),flush=True)
