"""Freeze method/code before the first public-test scoring run."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
target=ROOT/'PROTOCOL.json'
if target.exists():raise SystemExit('Protocol already frozen; preserve it and version amendments separately.')
code=ROOT/'lexical_baseline.py'
record={'version':'lexical-v1','frozen_local_date':'2026-10-18','external_preregistration':False,
    'dataset_revision':'ee05b9b6e6c1c91688db45b187da68f6b2ecb8e7','code_sha256':hashlib.sha256(code.read_bytes()).hexdigest(),
    'pre_scoring_exposure':'Schemas, class balances and first-record examples inspected; no lexical test predictions inspected before this freeze.',
    'hypotheses':'Description-inclusive lexical scoring improves macro-F1 versus names/constant controls on held-out ASTRA; ASTRA calibration may transfer poorly to TOUCAN.',
    'features':'Visible input.task and zipped input.tools/input.mcp_servers; public catalog tool names/descriptions only. Groundtruth and match_tag used solely for evaluation.',
    'representations':'TF-IDF: NFKC/camel-case tokenization, fixed generic stopwords, 1+log(TF), smoothed IDF, L2 normalization; request score is minimum requested-tool cosine.',
    'calibration':'Choose a separate threshold per representation on all ASTRA validation complexities; grid 0..1 step .01; maximize macro-F1 with higher threshold winning ties. Apply unchanged to all ASTRA and TOUCAN tests.',
    'unknown_policy':'Missing catalog mappings yield indeterminate; report coverage and covered confusion counts. Do not silently count unknown as correct.',
    'interpretation':'Per-example semantic-match labels do not establish organizational authorization, actual tokens, least privilege, attacker reachability, or superiority over authors neural models.',
    'statistics':'Descriptive per-source/per-complexity counts; repeated same-task variants are not independent samples; no significance or population estimates.',
    'data_manifest_sha256':hashlib.sha256((ROOT/'data/benchmark_manifest.json').read_bytes()).hexdigest()}
target.write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps(record,indent=2))
