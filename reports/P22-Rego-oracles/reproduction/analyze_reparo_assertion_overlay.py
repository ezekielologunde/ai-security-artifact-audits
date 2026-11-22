"""Check every generated assertion against the preceding per-request observations."""
from pathlib import Path
from collections import Counter, defaultdict
import gzip
import hashlib
import json

ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'work/reparo-assertion-overlay-v2'
counts = defaultdict(Counter)
outcomes = {}
records = []
for path in sorted((WORK / 'records').glob('*.json.gz')):
    row = json.loads(gzip.decompress(path.read_bytes()))
    tests = json.loads(row['stdout'])
    assert isinstance(tests, list) and not row.get('timeout')
    for test in tests:
        status = ('error' if test.get('error') else 'skip' if test.get('skip')
                  else 'fail' if test.get('fail') else 'pass')
        key = (row['kind'], row['identity'], test['name'])
        assert key not in outcomes
        outcomes[key] = status
        counts[row['kind']][status] += 1
    records.append(dict(kind=row['kind'], identity=row['identity'],
                        exit_code=row['exit_code'],
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
assert len(records) == 19
cases = json.loads((ROOT / 'results/reparo_typed_followup_cases_20261121.json').read_text())
comparisons = []
for case in cases:
    if not case['mutation_eligible']:
        continue
    statuses = {variant: outcomes[('overlay-' + variant, case['policy_id'],
                'test_typed_assertion_' + case['case_id'])]
                for variant in ('original', 'mutant')}
    a = case['original'].get('value', {})
    b = case['mutant'].get('value', {})
    strict = (a.get('allow') is False and a.get('deny') == []
              and b.get('allow') is True and b.get('deny') == [])
    baseline = a.get('allow') is True and a.get('deny') == []
    if strict:
        assert statuses == {'original': 'pass', 'mutant': 'fail'}
    if baseline:
        assert statuses['original'] == 'fail'
    comparisons.append(dict(case_id=case['case_id'], statuses=statuses,
                            strict_witness=strict, baseline_disagreement=baseline))
assert dict(counts['contract-controls']) == {'pass': 12}
assert dict(counts['overlay-original']) == {'pass': 68, 'fail': 12}
assert dict(counts['overlay-mutant']) == {'pass': 64, 'fail': 16}
assert len(comparisons) == 80
inventory = json.loads((ROOT / 'work/reparo-corpus-replay-v2/inventory.json').read_text())
source = ROOT / 'data/reparo-archive-20261121/selected/Final Policy with Test oracle/rego'
actual = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in source.rglob('*') if p.is_file()}
assert actual == inventory['source_hashes']
result = dict(date='2026-11-21', native_commands=19, case_count=80,
              counts={k: dict(v) for k, v in sorted(counts.items())},
              verified_comparisons=dict(
                  strict_witnesses_rejected=sum(c['strict_witness'] for c in comparisons),
                  baseline_contract_disagreements=sum(c['baseline_disagreement'] for c in comparisons)),
              all_acquired_source_hashes_unchanged=True, new_model_calls=0,
              contract='Explicit authored Boolean allow and set-valued deny with deny overrides; application contract not inferred.',
              interpretation='Conditional diagnostic evidence; no deployment efficacy, authenticated natural intent, population prevalence, or complete-suite semantic escape claim.',
              prior_control_fixture_failure_preserved='work/reparo-assertion-overlay-v1',
              records=records, cases=comparisons)
(ROOT / 'results/reparo_assertion_overlay_analysis_20261121.json').write_text(
    json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k not in ('records', 'cases')}, indent=2))
