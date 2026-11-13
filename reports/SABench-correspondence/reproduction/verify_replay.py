import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
for name in ['sabench_oracle_replay.json','sabench_normalization_comparison.json','sabench_cli_check.json']:
    assert json.loads((root/'results'/name).read_text())==json.loads((root/'reference'/name).read_text()),name
for name,sha in json.loads((root/'INPUT_SHA256.json').read_text()).items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha,name
print('Three full result receipts match; all packaged input hashes unchanged.')
