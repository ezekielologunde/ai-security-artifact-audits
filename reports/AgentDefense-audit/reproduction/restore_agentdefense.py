"""Restore hash-pinned upstream inputs as inert Git blobs; never check out code."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent

def main():
    spec = json.loads((ROOT / 'agentdefense_inputs.json').read_text(encoding='utf-8'))
    dest = ROOT / 'data/agentdefense-review/source'
    for row in spec['files']:
        p = dest / row['path']
        assert p.resolve().is_relative_to(dest.resolve())
        if p.exists():
            assert hashlib.sha256(p.read_bytes()).hexdigest() == row['sha256'], 'Refusing changed input: ' + row['path']
    work = ROOT / 'work'
    work.mkdir(exist_ok=True)
    results = ROOT / 'results'
    results.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='restore-git-', dir=work) as temporary:
        repo = Path(temporary)
        subprocess.run(['git', 'init', '--quiet', str(repo)], check=True, timeout=20)
        with (results / 'restore-git.stdout').open('wb') as stdout, (results / 'restore-git.stderr').open('wb') as stderr:
            process = subprocess.Popen(['git', '-c', 'http.lowSpeedLimit=100', '-c', 'http.lowSpeedTime=20',
                'fetch', '--quiet', '--depth=1', 'https://github.com/' + spec['repository'] + '.git', spec['revision']],
                cwd=repo, stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            try:
                code = process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                else:
                    process.kill()
                process.wait(timeout=20)
                raise
            assert code == 0, 'Fetch failed; see retained restore-git.stderr'
        for row in spec['files']:
            data = subprocess.check_output(['git', 'show', spec['revision'] + ':' + row['path']], cwd=repo, timeout=30)
            assert len(data) == row['bytes']
            assert hashlib.sha256(data).hexdigest() == row['sha256']
            assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == row['git_blob_sha1']
            p = dest / row['path']
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.exists():
                assert p.read_bytes() == data
            else:
                p.write_bytes(data)
    receipt = dict(repository=spec['repository'], revision=spec['revision'], files_verified=len(spec['files']),
                   bytes=sum(r['bytes'] for r in spec['files']), payload_or_source_execution=False)
    (results / 'restoration_receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt))

if __name__ == '__main__':
    main()
