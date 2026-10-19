"""Preserve the failed pre-scoring freeze and record an input-enumeration repair."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
old=json.loads((ROOT/'PROTOCOL.json').read_text())
old_code=ROOT/'work/frozen/lexical_baseline_v1.py'
assert hashlib.sha256(old_code.read_bytes()).hexdigest()==old['code_sha256']
assert not list((ROOT/'results/lexical-v1').glob('*predictions*'))
record=dict(old,version='lexical-v2',code_sha256=hashlib.sha256((ROOT/'lexical_baseline.py').read_bytes()).hexdigest())
record['amendment']={'previous_version':'lexical-v1','previous_code_sha256':old['code_sha256'],
    'reason':'Initial run failed during catalog loading: a broad *.json glob included acquisition receipts, producing KeyError name before any validation/test scores were computed.',
    'change':'Enumerate only catalog payload paths declared by the frozen acquisition manifest. Feature definitions, calibration rule, outcomes and splits remain unchanged.',
    'test_outcomes_seen_before_amendment':False}
target=ROOT/'PROTOCOL_V2.json'
if target.exists():raise SystemExit('Version 2 already frozen; do not overwrite')
target.write_text(json.dumps(record,indent=2),encoding='utf-8')
(ROOT/'results/lexical-v1/FAILURE.json').write_text(json.dumps(record['amendment'],indent=2),encoding='utf-8')
print('Version 2 input-enumeration repair frozen before scoring')
