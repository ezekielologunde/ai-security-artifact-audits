"""Compare the complete replay JSON with the retained experiment result."""
import json
from pathlib import Path
root = Path(__file__).resolve().parent
expected = json.loads((root / 'expected/agentdefense_entrypoint_audit.json').read_text(encoding='utf-8'))
actual = json.loads((root / 'results/agentdefense_entrypoint_audit.json').read_text(encoding='utf-8'))
assert actual == expected, 'Replay differs from retained result; inspect both JSON files'
print('Exact replay match: all seven frames, paired counts, decision equality, selectors and input hashes.')
