"""Cross-process checkpoint retirement and checkpoint-only restore conformance."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

os.environ['LANGSMITH_TRACING'] = 'false'
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

class State(TypedDict):
    canary: str

class Retired(Exception):
    pass

def authority(path, root):
    with sqlite3.connect(path) as db:
        return db.execute('SELECT active,epoch FROM roots WHERE root=?', (root,)).fetchone()

class GuardedSaver(SqliteSaver):
    """Bound trusted root/epoch; serialize each mediated operation with retirement."""
    def __init__(self, conn, auth, root):
        super().__init__(conn)
        self.auth, self.root = auth, root

    def guarded(self, operation, config, *args, **kwargs):
        if config['configurable']['thread_id'] != self.root:
            raise ValueError('root attribution mismatch')
        with sqlite3.connect(self.auth, timeout=15) as db:
            db.execute('BEGIN IMMEDIATE')
            allowed = db.execute('SELECT active,epoch FROM roots WHERE root=?', (self.root,)).fetchone() == (1, 0)
            if allowed:
                result = getattr(super(), operation)(config, *args, **kwargs)
            db.execute('INSERT INTO audit(root,operation,allowed) VALUES(?,?,?)', (self.root, operation, int(allowed)))
            db.commit()
        if not allowed:
            raise Retired(self.root)
        return result

    def get_tuple(self, config):
        return self.guarded('get_tuple', config)

    def put(self, config, checkpoint, metadata, new_versions):
        return self.guarded('put', config, checkpoint, metadata, new_versions)

    def put_writes(self, config, writes, task_id, task_path=''):
        return self.guarded('put_writes', config, writes, task_id, task_path)

def wait_file(path, process=None):
    limit = time.monotonic() + 25
    while not path.exists():
        if process is not None and process.poll() is not None:
            raise RuntimeError('worker ended before barrier')
        if time.monotonic() > limit:
            raise TimeoutError(str(path))
        time.sleep(.01)

def worker(folder, control, root, interleaving, action):
    config = {'configurable': {'thread_id': root}}
    conn = sqlite3.connect(folder/'checkpoints.sqlite', check_same_thread=False, timeout=15)
    saver = GuardedSaver(conn, folder/'authority.sqlite', root) if control in ('durable', 'blanket') else SqliteSaver(conn)
    try:
        if action == 'read':
            result = {'status': 'readable' if saver.get_tuple(config) is not None else 'absent'}
        else:
            if control == 'cached' and authority(folder/'authority.sqlite', root) != (1, 0):
                raise Retired(root)
            def echo(state):
                if action == 'late' and interleaving == 'mid_graph':
                    (folder/'ready').write_text('ready')
                    wait_file(folder/'release')
                return state
            builder = StateGraph(State)
            builder.add_node('echo', echo)
            builder.add_edge(START, 'echo'); builder.add_edge('echo', END)
            graph = builder.compile(checkpointer=saver)
            if action == 'late' and interleaving == 'late_start':
                (folder/'ready').write_text('ready')
                wait_file(folder/'release')
            graph.invoke({'canary': f'{action}-{root}'}, config)
            result = {'status': 'completed'}
    except Retired:
        result = {'status': 'denied'}
    finally:
        conn.close()
    print(json.dumps(result))

def counts(path):
    with sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True) as db:
        return {r: db.execute('SELECT COUNT(*) FROM checkpoints WHERE thread_id=?', (r,)).fetchone()[0] for r in ('A', 'B')}

def launch(folder, control, root, interleaving, action):
    return subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker', str(folder), control, root, interleaving, action], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def finish(process):
    try:
        out, err = process.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill(); process.communicate(); raise
    if process.returncode:
        raise RuntimeError(err)
    return json.loads(out)

def case(folder, control, restore, interleaving):
    folder.mkdir()
    with sqlite3.connect(folder/'authority.sqlite') as db:
        db.executescript('CREATE TABLE roots(root TEXT PRIMARY KEY,active INTEGER,epoch INTEGER);CREATE TABLE audit(seq INTEGER PRIMARY KEY,root TEXT,operation TEXT,allowed INTEGER);')
        db.executemany('INSERT INTO roots VALUES(?,1,0)', [('A',), ('B',)])
    for root in ('A', 'B'):
        assert finish(launch(folder, 'unmediated', root, interleaving, 'calibration'))['status'] == 'completed'
    checkpoint = folder/'checkpoints.sqlite'; backup = folder/'backup.sqlite'
    before = counts(checkpoint)
    with sqlite3.connect(checkpoint) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    proc = launch(folder, control, 'A', interleaving, 'late')
    try:
        wait_file(folder/'ready', proc)
        with sqlite3.connect(folder/'authority.sqlite', timeout=15) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('UPDATE roots SET active=0,epoch=epoch+1 WHERE root=?', ('A',))
            if control == 'blanket':
                db.execute('UPDATE roots SET active=0,epoch=epoch+1 WHERE root=?', ('B',))
            db.execute("INSERT INTO audit(root,operation,allowed) VALUES('A','retire',0)")
            db.commit()
        with SqliteSaver.from_conn_string(str(checkpoint)) as saver:
            saver.delete_thread('A')
        deleted = counts(checkpoint)
        assert deleted['A'] == 0
        if restore:
            with sqlite3.connect(backup) as source, sqlite3.connect(checkpoint) as target:
                source.backup(target)
        restored = counts(checkpoint)
    finally:
        (folder/'release').write_text('release')
    outcome = finish(proc)
    after = counts(checkpoint)
    independent = finish(launch(folder, control, 'B', interleaving, 'postcut'))
    read = finish(launch(folder, control, 'A', interleaving, 'read'))
    expected = 'denied' if control in ('durable', 'blanket') else 'completed'
    assert outcome['status'] == expected, (control, restore, interleaving, outcome)
    assert independent['status'] == ('denied' if control == 'blanket' else 'completed')
    assert read['status'] == ('denied' if control in ('durable', 'blanket') else 'readable')
    if control in ('durable', 'blanket'):
        assert after['A'] == restored['A']
    else:
        assert after['A'] > restored['A']
    with sqlite3.connect(folder/'authority.sqlite') as db:
        audit = list(db.execute('SELECT seq,root,operation,allowed FROM audit ORDER BY seq'))
    cut = next(r[0] for r in audit if r[2] == 'retire')
    assert not any(r[0] > cut and r[1] == 'A' and r[3] for r in audit)
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (checkpoint, backup, folder/'authority.sqlite')}
    return {'control': control, 'restore': restore, 'interleaving': interleaving, 'before': before, 'after_delete': deleted, 'after_restore': restored, 'after_late': after, 'final': counts(checkpoint), 'backup': counts(backup), 'worker': outcome, 'independent': independent, 'access_probe': read, 'audit': audit, 'sha256': files}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', nargs=5)
    parser.add_argument('--name'); parser.add_argument('--repeats', type=int, default=5)
    args = parser.parse_args()
    if args.worker:
        worker(Path(args.worker[0]), *args.worker[1:]); return
    if not args.name or Path(args.name).name != args.name or args.name in ('.', '..') or args.repeats < 1:
        parser.error('new directory name and positive repeats required')
    out = Path(__file__).resolve().parent/'results'/args.name
    out.mkdir(parents=True, exist_ok=False)
    protocol = {'frozen_utc': datetime.now(timezone.utc).isoformat(), 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'repeats': args.repeats, 'controls': ['unmediated', 'cached', 'durable', 'blanket'], 'restores': [False, True], 'interleavings': ['late_start', 'mid_graph'], 'packages': {p: importlib.metadata.version(p) for p in ('langgraph', 'langgraph-checkpoint-sqlite')}, 'limits': ['Trusted root and initial epoch; synchronous APIs only', 'All mediated operations serialize through external authority SQLite', 'Checkpoint-only restoration; authority is not restored', 'No physical erasure, model, effect sink, distributed guarantee or crash atomicity']}
    (out/'protocol.json').write_text(json.dumps(protocol, indent=2))
    rows = []
    for repeat in range(args.repeats):
        for control in protocol['controls']:
            for restore in protocol['restores']:
                for interleaving in protocol['interleavings']:
                    ident = f'r{repeat}-{control}-restore{int(restore)}-{interleaving}'
                    rows.append({'run_id': ident, **case(out/ident, control, restore, interleaving)})
                    (out/'records.json').write_text(json.dumps(rows, indent=2))
    summary = {'runs': len(rows), 'assertions_passed': True, 'by_control': {c: {'runs': sum(r['control'] == c for r in rows), 'late_completed': sum(r['control'] == c and r['worker']['status'] == 'completed' for r in rows), 'A_readable': sum(r['control'] == c and r['access_probe']['status'] == 'readable' for r in rows), 'B_completed': sum(r['control'] == c and r['independent']['status'] == 'completed' for r in rows), 'restored_A_rows_retained': sum(r['control'] == c and r['restore'] and r['final']['A'] > 0 for r in rows)} for c in protocol['controls']}}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)); print(json.dumps(summary))

if __name__ == '__main__':
    main()
