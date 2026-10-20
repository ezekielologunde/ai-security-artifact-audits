import copy,json
from pathlib import Path
from model_consistency.core import analyze, bind_report, extract_claims

ROOT=Path(__file__).resolve().parents[1]

def test_upstream_is_preserved_without_mutation():
    cases=json.loads((ROOT/'experiment/controlled_cases.json').read_text())
    case=next(x for x in cases if x['scanner_report'])
    snapshot=copy.deepcopy(case['snapshot']);report=copy.deepcopy(case['scanner_report'])
    result=analyze(snapshot,report)
    assert result['upstream_report']==report
    assert snapshot==case['snapshot'] and report==case['scanner_report']
    result['upstream_report']['target']['revision']='changed'
    assert report==case['scanner_report']

def test_local_dependency_is_unverifiable():
    snapshot={'model_id':'o/m','revision':'1','readme':'Adapter requires base model org/Base.',
              'adapter_config':{'base_model_name_or_path':'./checkpoint'},'artifacts':[]}
    assessment=analyze(snapshot)['overlay']['claim_assessments'][0]
    assert assessment['consistency']=='unverifiable'

def test_identity_rejects_stale_hash_and_revision():
    snapshot={'model_id':'o/m','revision':'1','artifacts':[{'path':'weights.pkl','sha256':'abc'}]}
    report={'target':{'model_id':'o/m','revision':'1'},'artifact_sha256':{'weights.pkl':'abc'}}
    assert bind_report(snapshot,report)=='matched'
    report['target']['revision']='0';assert bind_report(snapshot,report)=='mismatched-target-or-revision'
    report['target']['revision']='1';report['artifact_sha256']['weights.pkl']='wrong'
    assert bind_report(snapshot,report)=='mismatched-artifact-hash'
    del report['artifact_sha256'];assert bind_report(snapshot,report)=='unknown-artifact-identity'

def test_scope_keeps_unused_pickle_out_of_loading_path():
    snapshot={'model_id':'o/m','revision':'1','readme':'The selected loading path is pickle-free.',
              'config':{'model_type':'bert'},'loading_path':{'auto_class':'AutoModel','artifacts':['weights.safetensors']},
              'artifacts':[{'path':'legacy.pkl','format':'pickle'},{'path':'weights.safetensors','format':'safetensors'}]}
    result=analyze(snapshot)['overlay']
    assert result['claim_assessments'][0]['consistency']=='consistent-with-observed-evidence'
    assert result['loading_exposure']=='no-exposure-observed-within-inspected-scope'

def test_quotes_code_and_availability_are_not_exclusivity():
    assert extract_claims('Safetensors available.\n> Only Safetensors.\n```\nOnly Safetensors.\n```\nNot only Safetensors.')==[]

def test_ancestry_is_not_adapter_dependency():
    snapshot={'model_id':'o/m','revision':'1','readme':'Fine-tuned from org/A.',
              'card_data':{'base_model':'org/A'},'adapter_config':{'base_model_name_or_path':'org/B'}}
    result=analyze(snapshot)['overlay']
    assert result['claim_assessments']==[]
    assert result['provenance_comparison']['candidate_disagreement']
    assert result['provenance_comparison']['consistency']=='unverifiable'

def test_unhashed_format_evidence_is_rejected():
    snapshot={'model_id':'o/m','revision':'1','artifacts':[{'path':'a','sha256':'abc'},{'path':'b','sha256':'xyz'}]}
    report={'target':{'model_id':'o/m','revision':'1'},'artifact_sha256':{'a':'abc'},'verified_formats':{'b':'pickle'}}
    assert bind_report(snapshot,report)=='unbound-format-evidence'
