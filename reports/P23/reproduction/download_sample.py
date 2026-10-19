"""Acquire the author's shipped inert sample for offline conformance tests."""
import json
from pathlib import Path
import source_io as io
ROOT=Path(__file__).resolve().parent;io.ROOT=ROOT
if __name__=='__main__':
    row=json.loads((ROOT/'data/source_manifest.json').read_text())[0]
    name='data/beir_nq_sample.parquet'
    receipt=io.fetch(f'https://raw.githubusercontent.com/{row["repository"]}/{row["revision"]}/{name}',ROOT/'data/source-code'/name,1_000_000)
    (ROOT/'data/sample_manifest.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(receipt['bytes'],receipt['sha256'])
