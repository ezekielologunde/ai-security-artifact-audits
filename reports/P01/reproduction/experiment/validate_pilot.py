import json,subprocess
from pathlib import Path
from adapter import bundle
from run_experiment import ROOT,NODE
p=ROOT/'experiment/results/pilot-v1'
rows=json.loads((p/'runs.json').read_text(encoding='utf-8'))
objects=[{'run_id':r['run_id'],'feed':f,'bundle':bundle(p/'runs'/r['run_id'],r['case'],f)} for r in rows for f in ['snapshot','probe']]
(p/'repaired_pilot_bundles.json').write_text(json.dumps(objects),encoding='utf-8')
subprocess.run([str(NODE),str(Path(__file__).parent/'verify_batch.mjs'),str(p/'repaired_pilot_bundles.json'),str(p/'repaired_pilot_receipts.json')],check=True)
receipts=json.loads((p/'repaired_pilot_receipts.json').read_text())
assert not any(x['evaluation'].get('runner_state')=='VALIDATION_ERROR' for x in receipts)
print('pilot schema conformance passed; pilot excluded from measured results')
