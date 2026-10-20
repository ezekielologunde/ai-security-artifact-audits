"""Download only the pinned task ledger required for safe synthetic adaptation."""
import hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REV='ab13f59d3f1236e7e65224d4fd6cc00dcdaaf68b'
URL=f'https://huggingface.co/datasets/zhmzm/AgentTrap/resolve/{REV}/data/tasks.jsonl'
def main():
 design=json.loads((ROOT/'experiment/results/measured-v2/frozen_design.json').read_text(encoding='utf-8'))
 path=ROOT/'datasets/upstream/agenttrap/hf_dataset/data/tasks.jsonl'
 expected=design['source_sha256']
 if path.exists():
  data=path.read_bytes()
  if hashlib.sha256(data).hexdigest()!=expected:raise SystemExit('Existing task ledger differs from the measured source. It was not overwritten.')
  print('Pinned task ledger already present and hash verified.');return
 req=urllib.request.Request(URL,headers={'User-Agent':'agent-offboarding-research/1.0'})
 with urllib.request.urlopen(req,timeout=60) as response:data=response.read(5_000_001)
 if len(data)>5_000_000:raise SystemExit('Unexpectedly large task ledger')
 if hashlib.sha256(data).hexdigest()!=expected:raise SystemExit('Downloaded source hash mismatch; no data saved')
 rows=[json.loads(line) for line in data.decode('utf-8').splitlines()]
 if len(rows)!=141:raise SystemExit('Unexpected task count')
 path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
 print('Downloaded and hash-verified 141 task records. No skill code was downloaded or executed.')
if __name__=='__main__':main()
