"""Execute only the original developer-authored controlled experiment."""
import importlib.util, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
work = ROOT/'work/controlled-run'
assert not work.exists(), 'Preserve an existing execution; use a fresh copied package'
spec = importlib.util.spec_from_file_location('original_provenance_runner',ROOT/'scripts/run_experiment.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
module.ROOT = work; module.OUT = work/'results'; module.OUT.mkdir(parents=True)
artifacts = module.fixtures()
module.controlled(module.make_cases(artifacts, []))
def normalized(value):
    if isinstance(value,dict): return {k:normalized(v) for k,v in value.items() if k!='runtime_seconds'}
    if isinstance(value,list): return [normalized(v) for v in value]
    return value
checks = {}
for name in ['controlled_summary.json','controlled_predictions.json','error_analysis.json']:
    ref=json.loads((ROOT/'reference-results'/name).read_text()); fresh=json.loads((module.OUT/name).read_text())
    checks[name] = normalized(ref)==normalized(fresh) if name=='controlled_summary.json' else ref==fresh
result={'controlled_cases':36,'reference_comparisons':checks,'natural_repositories_replayed':0,'independent_labels':False,'excluded_comparison_field':'controlled_summary.systems.*.runtime_seconds'}
(work/'reproduction.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
assert all(checks.values()), checks
print(json.dumps(result,indent=2))
