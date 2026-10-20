"""Verify process/recovery records against fresh raw SQLite reads."""
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
        parser.error('directory name required')
    root = Path(__file__).resolve().parent
    folder = root/'results'/args.name
    protocol = json.loads((folder/'protocol.json').read_text())
    source_file = protocol.get('source_file', 'process_recovery.py')
    assert source_file in ('process_recovery.py', 'process_recovery_v2.py')
    assert hashlib.sha256((root/source_file).read_bytes()).hexdigest() == protocol['source_sha256']
    records = json.loads((folder/'records.json').read_text())
    assert len(records) == protocol['repeats'] * 16
    assert len({r['run_id'] for r in records}) == len(records)
    combinations = {(r['control'], r['restore'], r['interleaving']) for r in records}
    assert len(combinations) == 16
    for row in records:
        case = folder/row['run_id']
        for filename, expected in row['sha256'].items():
            assert hashlib.sha256((case/filename).read_bytes()).hexdigest() == expected, (row['run_id'], filename, 'hash mismatch')
        for filename, column in [('checkpoints.sqlite', 'final'), ('backup.sqlite', 'backup')]:
            with sqlite3.connect(f'file:{(case/filename).as_posix()}?mode=ro', uri=True) as db:
                values = {r: db.execute('SELECT COUNT(*) FROM checkpoints WHERE thread_id=?', (r,)).fetchone()[0] for r in ('A', 'B')}
                assert values == row[column]
        with sqlite3.connect(f'file:{(case/"authority.sqlite").as_posix()}?mode=ro', uri=True) as db:
            assert db.execute("SELECT active,epoch FROM roots WHERE root='A'").fetchone() == (0, 1)
            assert db.execute("SELECT active,epoch FROM roots WHERE root='B'").fetchone() == ((0, 1) if row['control'] == 'blanket' else (1, 0))
            audit = [list(r) for r in db.execute('SELECT seq,root,operation,allowed FROM audit ORDER BY seq')]
            assert audit == row['audit']
            cut = next(r[0] for r in audit if r[2] == 'retire')
            assert not any(r[0] > cut and r[1] == 'A' and r[3] for r in audit)
        guarded = row['control'] in ('durable', 'blanket')
        assert row['worker']['status'] == ('denied' if guarded else 'completed')
        assert row['access_probe']['status'] == ('denied' if guarded else 'readable')
        assert row['independent']['status'] == ('denied' if row['control'] == 'blanket' else 'completed')
        if row['control'] == 'blanket':
            assert row['final']['B'] == row['after_late']['B']
        else:
            assert row['final']['B'] > row['after_late']['B']
        assert row['after_delete']['A'] == 0
        assert row['backup']['A'] > 0
        if guarded:
            assert row['final']['A'] == row['after_restore']['A']
        else:
            assert row['final']['A'] > row['after_restore']['A']
    result = {'runs': len(records), 'source_hash_verified': True, 'three_database_hashes_per_run_verified': True, 'raw_checkpoint_and_authority_state_verified': True, 'independent_external_review': False}
    (folder/'verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))

if __name__ == '__main__':
    main()
