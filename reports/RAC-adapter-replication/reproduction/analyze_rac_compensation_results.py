"""Derive compensation-result findings directly from native receipts and enum values."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent
original=ROOT/'results/rac_compensation_results_initial_enum_summary_20261121.json'
d=json.loads(original.read_text())
assert hashlib.sha256((ROOT/'run_rac_compensation_results_initial.py').read_bytes()).hexdigest()==d['harness_sha256']
cases=[]
for c in d['cases']:
    mismatch=c['explicit_error_returned'] and c['rollback'].get('success') is True and c['final_record_status']=='COMPENSATED'
    cases.append(dict(condition=c['condition'],explicit_error_bookkeeping_mismatch=mismatch,
        rollback_success=c['rollback'].get('success'),rollback_exception=c['rollback'].get('exception'),
        active_sessions_after=c['after']['active_sessions'],artifact_rows_after=c['after']['artifact_rows'],
        final_record_status=c['final_record_status']))
result=dict(date='2026-11-21',original_receipt_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
    original_case_count=len(cases),explicit_error_bookkeeping_mismatches=sum(c['explicit_error_bookkeeping_mismatch'] for c in cases),
    native_adapter_mismatches=sum(c['explicit_error_bookkeeping_mismatch'] and c['condition'].startswith('native-') for c in cases),
    original_observations_reexecuted_for_correction=False,acquired_source_unchanged=d['summary']['acquired_sources_unchanged'],
    counter_correction='Initial summary compared actual enum string COMPENSATED with lowercase compensated; raw measurements preserved.',cases=cases)
guard_path=ROOT/'results/rac_compensation_status_guard_20261121.json'
if guard_path.exists():
    guard=json.loads(guard_path.read_text());by_name={c['condition']:c for c in guard['cases']}
    assert set(by_name)=={c['condition'] for c in cases}
    for c in cases:
        g=by_name[c['condition']]
        assert (g['after']['active_sessions'],g['after']['artifact_rows'])==(c['active_sessions_after'],c['artifact_rows_after'])
        c['guard_rollback_success']=g['rollback'].get('success')
        c['guard_rollback_exception']=g['rollback'].get('exception')
        c['guard_final_record_status']=g['final_record_status']
    result['status_guard']=dict(cases=len(by_name),explicit_errors_reported_as_failure=sum(c['explicit_error_bookkeeping_mismatch'] and c['guard_rollback_success'] is not True and c['guard_rollback_exception'] is not None for c in cases),
        fixture_states_unchanged=True,success_controls_preserved=all(by_name[n]['rollback'].get('success') is True for n in ('core-success','native-success')),
        success_returning_noop_still_reported_success=by_name['native-success-returning-noop']['rollback'].get('success') is True,
        interpretation='Status interpretation only; the wrapper neither completes failed compensations nor detects a falsely successful no-op from external state.')
(ROOT/'results/rac_compensation_analysis_20261121.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
