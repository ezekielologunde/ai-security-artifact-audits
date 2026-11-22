"""Acquire or accept pinned local inputs; do not execute downloaded source code."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import shutil
import stat
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
ARCHIVE_SHA = '8cd430b36a64a130be89be64b9eb4aac97759035f55172b829a1a7e63100714c'
OPA_SHA = '35e3b352e715e80624ead6c89930d8585f6f7d94cdc409eb2a9fe36620dcccba'
ARCHIVE_URL = 'https://anonymous.4open.science/api/repo/Reparo-8333/zip'
OPA_URL = 'https://github.com/open-policy-agent/opa/releases/download/v1.22.4/opa_linux_amd64_static'

def acquire(destination, local, url, expected, maximum):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    if local:
        assert hashlib.sha256(local.read_bytes()).hexdigest() == expected
        try:
            os.link(local, destination)
        except OSError:
            shutil.copyfile(local, destination)
    else:
        request = urllib.request.Request(url, headers={'User-Agent': 'reproducible-policy-audit/1.0'})
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read(maximum + 1)
        if len(body) > maximum or hashlib.sha256(body).hexdigest() != expected:
            raise ValueError('Input identity changed or download invalid; refusing a different snapshot: ' + url)
        destination.write_bytes(body)
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == expected

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--opa', type=Path)
    args = parser.parse_args()
    (ROOT / 'results').mkdir(exist_ok=True)
    (ROOT / 'work').mkdir(exist_ok=True)
    out = ROOT / 'data/reparo-archive-20261121'
    out.mkdir(parents=True, exist_ok=False)
    archive = out / 'reparo-public-snapshot.zip'
    acquire(archive, args.archive, ARCHIVE_URL, ARCHIVE_SHA, 100_000_000)
    files = []
    with zipfile.ZipFile(archive) as z:
        assert len(z.infolist()) < 20000
        assert sum(m.file_size for m in z.infolist()) < 500_000_000
        assert z.testzip() is None
        for item in z.infolist():
            if item.is_dir():
                continue
            name = PurePosixPath(item.filename)
            assert not name.is_absolute() and '..' not in name.parts and '\\' not in item.filename
            assert not stat.S_ISLNK(item.external_attr >> 16)
            body = z.read(item)
            files.append(dict(path=item.filename, bytes=len(body), sha256=hashlib.sha256(body).hexdigest()))
            prefix = 'Final Policy with Test oracle/rego/'
            if prefix in item.filename:
                relative = item.filename.split(prefix, 1)[1]
                target = out / 'selected/Final Policy with Test oracle/rego' / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
    assert len(files) == 3621
    receipt = dict(archive_sha256=ARCHIVE_SHA, source=ARCHIVE_URL, files=files,
                   identity='Mutable service snapshot identified by local byte hash; original author commit unresolved.',
                   rights='Local acquisition; no redistribution grant asserted.')
    (ROOT / 'results/reparo_archive_acquisition_20261121.json').write_text(json.dumps(receipt, indent=2) + '\n')
    opa = ROOT / 'tools/opa-v1.22.4/opa_linux_amd64_static'
    acquire(opa, args.opa, OPA_URL, OPA_SHA, 100_000_000)
    print(json.dumps(dict(archive_sha256=ARCHIVE_SHA, opa_sha256=OPA_SHA, original_paper_runtime_established=False)))

if __name__ == '__main__':
    main()
