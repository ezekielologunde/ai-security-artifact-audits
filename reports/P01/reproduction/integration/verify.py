"""Read raw committed effects without using the HTTP service's scorer."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    if Path(args.name).name != args.name or args.name in ('.', '..'):
        parser.error('Use a result directory name')
    root = Path(__file__).resolve().parent
    folder = root / 'results' / args.name
    protocol = json.loads((folder / 'protocol.json').read_text())
    assert hashlib.sha256((root / 'run.py').read_bytes()).hexdigest() == protocol['source_sha256']
    records = json.loads((folder / 'records.json').read_text())
    assert len(records) == protocol['repeats'] * 16
    assert len({r['run_id'] for r in records}) == len(records)
    for row in records:
        case = folder / row['run_id']
        path = case / ('effects.sqlite' if row['backend'] == 'sqlite' else 'effects.jsonl')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['effects_sha256']
        if row['backend'] == 'sqlite':
            with sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True) as db:
                effects = list(db.execute('SELECT root,phase FROM effects'))
        else:
            effects = [(e['root'], e['phase']) for e in map(json.loads, path.read_text().splitlines())]
        assert sorted(e for e in effects if e[1] == 'calibration') == [('A', 'calibration'), ('B', 'calibration')]
        expected = {('B', 'graph-after-cut')}
        if not row['fenced']:
            expected.add(('A', 'in-flight-after-cut'))
            if not row['cleanup']:
                expected.add(('A', 'pending-after-cut'))
            if not row['graph_gate']:
                expected.add(('A', 'graph-after-cut'))
        assert sorted(e for e in effects if e[1] != 'calibration') == sorted(expected), row['run_id']
        assert sum(e[0] == 'A' for e in expected) == row['retired_effects']
        assert row['independent_effects'] == 1
        assert next(r['status'] for r in row['receipts'] if r['phase'] == 'forged') == 403
    print(json.dumps({'verified_runs': len(records), 'raw_effects_match': True,
                      'source_hash_matches': True, 'checkpoint_state_independently_verified': False}))


if __name__ == '__main__':
    main()
