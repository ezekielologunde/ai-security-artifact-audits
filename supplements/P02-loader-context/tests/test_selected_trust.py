import pytest
from model_consistency.core import analyze


def snapshot(flag):
    return {'model_id':'org/target','revision':'a'*40,
            'readme':'No custom code is required for org/target.\n\n```python\n'
                     'AutoModel.from_pretrained("org/target", trust_remote_code=False)\n```\n\n'
                     'For another model:\n```python\n'
                     'AutoModel.from_pretrained("org/other", trust_remote_code=True)\n```',
            'config':{'model_type':'bert','auto_map':{'AutoModel':'modeling_optional.Model'}},
            'loading_path':{'auto_class':'AutoModel','trust_remote_code':flag},
            'artifacts':[{'path':'modeling_optional.py','format':'unknown'}]}


def test_selected_false_cannot_be_overridden_by_another_example():
    result=analyze(snapshot(False))['overlay']
    assert result['claim_assessments'][0]['consistency']=='unverifiable'
    evidence=result['claim_assessments'][0]['evidence'][0]
    assert evidence['documented_trust_remote_code'] is True
    assert evidence['selected_trust_remote_code'] is False
    assert result['loading_exposure']=='indeterminate'


def test_selected_true_with_matching_documented_example_retains_code_finding():
    case=snapshot(True)
    case['readme']='No custom code.\n```python\nAutoModel.from_pretrained("org/target", trust_remote_code=True)\n```'
    result=analyze(case)['overlay']
    assert result['claim_assessments'][0]['consistency']=='contradicted'
    assert result['loading_exposure']=='observed-loading-exposure'


def test_disabled_remote_code_does_not_hide_pickle_exposure():
    case=snapshot(False)
    case['artifacts'].append({'path':'weights.pkl','format':'pickle'})
    case['loading_path']['artifacts']=['weights.pkl']
    assert analyze(case)['overlay']['loading_exposure']=='observed-loading-exposure'


@pytest.mark.parametrize('flag',['false',0,None])
def test_non_boolean_selection_is_rejected(flag):
    with pytest.raises(ValueError,match='JSON boolean'):
        analyze(snapshot(flag))
