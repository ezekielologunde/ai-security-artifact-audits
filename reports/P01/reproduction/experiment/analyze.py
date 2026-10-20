import csv,json,statistics,hashlib
from collections import Counter
from pathlib import Path
P=Path(__file__).resolve().parent.parent
R=P/'experiment/results/measured-v2'
rows=json.loads((R/'runs.json').read_text(encoding='utf-8'))
receipts=json.loads((R/'verifier_receipts.json').read_text(encoding='utf-8'))
lookup={(r['run_id'],r['feed']):r['evaluation']['verdict'] for r in receipts}
assert len(rows)==720 and len(receipts)==1440
assert len({r['run_id'] for r in rows})==720
summary=[]
for arm in dict.fromkeys(r['arm'] for r in rows):
 subset=[r for r in rows if r['arm']==arm]
 result={'arm':arm,'runs':len(subset),'unique_scenarios':len({r['scenario_id'] for r in subset}),
  'old_root_effects':sum(r['truth']['old_root_effects'] for r in subset),
  'independent_effects':sum(r['truth']['independent_effects'] for r in subset),
  'ground_truth_blockers':sum(r['truth']['closure_blocker'] for r in subset)}
 for feed in ['administrative','snapshot','probe']:
  verdicts=[r['administrative_verdict'] if feed=='administrative' else lookup[r['run_id'],feed] for r in subset]
  for v in ['CLOSED','INCOMPLETE','UNKNOWN']:result[feed+'_'+v.lower()]=verdicts.count(v)
  result[feed+'_false_closed']=sum(v=='CLOSED' and r['truth']['closure_blocker'] for v,r in zip(verdicts,subset))
 samples=sorted(ms for r in subset for ms in r['truth']['admission_ms'])
 result['decision_median_ms']=statistics.median(samples)
 result['decision_p95_ms']=samples[int(.95*(len(samples)-1))]
 result['worker_median_ms']=statistics.median(r['worker_ms'] for r in subset)
 summary.append(result)
 # Repeat counts must not disguise distinct scenario-level evidence.
 for scenario in {r['scenario_id'] for r in subset}:
  repeats=[r for r in subset if r['scenario_id']==scenario]
  assert len({(r['truth']['old_root_effects'],r['truth']['independent_effects'],r['truth']['closure_blocker'],lookup[r['run_id'],'snapshot'],lookup[r['run_id'],'probe']) for r in repeats})==1
out=P/'outputs'
(out/'experiment_results.json').write_text(json.dumps({'runs':720,'unique_scenarios':24,'source_cases':12,'repeats':5,'arm_summary':summary,'schema_evaluations':1440,'schema_errors':0,'interpretation':'Descriptive finite-corpus evidence only; repeat runs are not independent attack samples.'},indent=2),encoding='utf-8')
with (out/'experiment_results.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
print(json.dumps(summary,indent=2))
