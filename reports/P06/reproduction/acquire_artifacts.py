"""Reuse the program's bounded source inventory helper for author artifacts."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
helper=ROOT/'source_io.py'
spec=importlib.util.spec_from_file_location('program_acquisition',helper)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.ROOT=ROOT/'author_artifacts';module.REPOS=['outshift-open/ASTRA','agntcy/identity-service']
module.main()
records=json.loads((module.ROOT/'data/source_manifest.json').read_text())
for row in records:
    print(row['repository'],'DATA CANDIDATES',[(x['path'],x.get('size')) for x in row['files'] if x['path'].endswith(('.json','.jsonl','.csv','.parquet','.zip'))][:45])
