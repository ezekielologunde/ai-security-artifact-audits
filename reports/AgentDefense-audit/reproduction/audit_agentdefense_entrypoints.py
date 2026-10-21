"""Run inspected standard-library definitions only; payloads remain inert strings."""
import ast
import collections
import hashlib
import json
import sys
import tempfile
import time
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'data/agentdefense-review/source'
FRAME_NAMES = [
    'attacks/combined_attacks.json', 'attacks/novel_2024_2025.json',
    'benign_baseline/benign_baseline.json', 'consolidated/tier1_critical_tests.json',
    'consolidated/tier2_high_tests.json', 'consolidated/tier3_medium_tests.json',
    'consolidated/benign_tests.json',
]

def main():
    manifest = json.loads((ROOT / 'agentdefense_inputs.json').read_text(encoding='utf-8'))
    for row in manifest['files']:
        data = (SOURCE / row['path']).read_bytes()
        assert len(data) == row['bytes']
        assert hashlib.sha256(data).hexdigest() == row['sha256'], row['path']
    paths = [SOURCE / p for p in FRAME_NAMES + ['scripts/defense_adapters.py', 'scripts/evaluate.py']]
    paths += [ROOT / 'AGENTDEFENSE_ENTRYPOINT_PROTOCOL.md']
    before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    env = dict(json=json, time=time, sys=sys, Path=Path, dataclass=dataclass,
               ABC=ABC, abstractmethod=abstractmethod,
               **{name: getattr(typing, name) for name in ['Dict', 'Any', 'Optional', 'List']})
    selected = {
        'scripts/defense_adapters.py': {'DefenseResult', 'DefenseAdapter', 'MockDefense'},
        'scripts/evaluate.py': {'EvaluationResult', 'load_dataset', 'run_evaluation'},
    }
    for name, wanted in selected.items():
        tree = ast.parse((SOURCE / name).read_text(encoding='utf-8'))
        nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in wanted]
        assert {n.name for n in nodes} == wanted
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE / name), 'exec'), env)

    class RecordingMock(env['MockDefense']):
        def __init__(self):
            super().__init__()
            self.outcomes = []
            self.empty = 0

        def evaluate(self, request):
            self.empty += request == {}
            result = super().evaluate(request)
            self.outcomes.append(result)
            return result

    frames = {}
    with tempfile.TemporaryDirectory(prefix='agentdefense-label-audit-') as work:
        for index, name in enumerate(FRAME_NAMES):
            original = json.loads((SOURCE / name).read_text(encoding='utf-8'))
            rows = original if isinstance(original, list) else original['tests']
            normalized = [dict(row, expected_block=not row['is_benign']) if type(row.get('is_benign')) is bool else row for row in rows]
            # JSON's ASCII serialization changes neither parsed strings nor request values.
            # It avoids a Windows default-encoding dependency in upstream load_dataset.
            results = []
            adapters = []
            for label, data in [('published', rows), ('normalized', normalized)]:
                path = Path(work) / f'{index}-{label}.json'
                path.write_text(json.dumps(data, ensure_ascii=True), encoding='ascii')
                adapter = RecordingMock()
                result = env['run_evaluation'](path, adapter)
                results.append(asdict(result))
                adapters.append(adapter)
                assert len(adapter.outcomes) == len(rows)
            assert adapters[0].outcomes == adapters[1].outcomes
            frames[name] = dict(records=len(rows), published=results[0], normalized=results[1],
                                empty_requests=adapters[0].empty, unchanged_adapter_decisions=True)
    tier = json.loads((SOURCE / 'consolidated/tier1_critical_tests.json').read_text(encoding='utf-8'))
    after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert before == after
    result = dict(revision='b5dfdf3c6cf33fb3c0b39865384b9ca833aa4183',
                  frames=frames, README_programmatic_selected_attacks_rows=len(tier.get('attacks', [])),
                  actual_tier1_tests_rows=len(tier['tests']), source_SHA256=before,
                  source_bytes_unchanged=True, adapter='upstream MockDefense, AST-selected unchanged definitions',
                  network_or_model_or_attack_execution=False,
                  scope='Documented tier1 entry point primary; remaining frames secondary. Label-schema normalization only; natural labels not independently validated.')
    out = ROOT / 'results/agentdefense_entrypoint_audit.json'
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'source_SHA256'}, indent=2))

if __name__ == '__main__':
    main()
