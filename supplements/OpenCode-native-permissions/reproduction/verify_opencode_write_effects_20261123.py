"""MIT. Check recorded native tool outcomes and final physical fixture readback."""
from pathlib import Path
import hashlib,json,psutil
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/opencode-write-effects-20261123-r2'
result=json.loads((OUT/'RESULTS.json').read_text())
protocol=json.loads((ROOT/'OPENCODE_WRITE_EFFECT_PROTOCOL_20261123.json').read_text())
acq=json.loads((ROOT/'results/opencode_binary_acquisition_20261123.json').read_text())
assert result['error'] is None and [c['id'] for c in result['conditions']]==[c['id'] for c in protocol['conditions']]
assert all(c['match'] and c['write_advertised'] for c in result['conditions'])
assert hashlib.sha256(Path(acq['binary_path']).read_bytes()).hexdigest()==acq['binary_sha256']
assert not [pid for pid in result['owned_shutdown_pids'] if psutil.pid_exists(pid)]
for condition in result['conditions']:
    assert condition['after']==condition['expected_after']
    if condition['reply']!='none':assert condition['pre_reply_file_unchanged'] and condition['pending_request']
    tools=[c for m in condition['native_messages']['data'] if m['type']=='assistant' for c in m.get('content',[]) if c.get('type')=='tool']
    assert len(tools)==1 and tools[0]['name']=='write'
    assert tools[0]['state']['input']=={'path':condition['resource'],'content':'NATIVE_WRITE_'+condition['id']}
    if condition['configured_effect']=='deny':
        assert tools[0]['state']['error']['type']=='permission.rejected'
    if condition['reply']=='reject':
        assert tools[0]['state']['error']['type']=='aborted' and 'declined' in tools[0]['state']['error']['message']
BASE=ROOT/'work/opencode-write-effects-20261123-r2'
final={rel:(BASE/rel).read_text() for rel in ['project-A/protected.txt','project-A/utility.txt','project-B/protected.txt']}
assert final=={'project-A/protected.txt':'NATIVE_WRITE_successor_saved_allow','project-A/utility.txt':'NATIVE_WRITE_utility_allow','project-B/protected.txt':'BASELINE_B'}
record={'date':'2026-11-23','confirmation_conditions':7,'all_match':True,'native_write_tool_records_verified':7,'physical_final_readback':final,'binary_unchanged':True,'owned_process_tree_confirmed_absent':result['owned_shutdown_pids'],'native_idle_observations':sum(c['native_terminal']['type']=='idle' for c in result['conditions']),'completed_tool_errors_without_idle':sum(c['native_terminal']['type']=='completed_tool_error' for c in result['conditions']),'real_inference_models':0,'calibration_run_counted_in_confirmation':False,'scope':'Controlled built-in file effects and permission handling only; not restart durability, in-flight revocation or deployment efficacy.'}
(OUT/'VERIFICATION.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
