"""Read-only integrity checks for the committed measured artifact."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 results=ROOT/'experiment/results/measured-v2'
 design_path=results/'frozen_design.json'
 design=json.loads(design_path.read_text(encoding='utf-8'))
 assert hashlib.sha256(design_path.read_bytes()).hexdigest()==(results/'frozen_design.sha256').read_text().strip()
 for name,expected in design['code_sha256'].items():
  assert hashlib.sha256((ROOT/'experiment'/name).read_bytes()).hexdigest()==expected,name
 rows=json.loads((results/'runs.json').read_text(encoding='utf-8'))
 receipts=json.loads((results/'verifier_receipts.json').read_text(encoding='utf-8'))
 assert len(rows)==720 and len({r['run_id'] for r in rows})==720
 assert len(receipts)==1440 and all('verdict' in r['evaluation'] for r in receipts)
 assert len({r['scenario_id'] for r in rows})==24
 assert all(len([r for r in rows if r['arm']==arm])==120 for arm in design['arms'])
 print('Verified frozen code/design hashes, 720 runs, 24 scenarios and 1,440 valid receipts.')
if __name__=='__main__':main()
