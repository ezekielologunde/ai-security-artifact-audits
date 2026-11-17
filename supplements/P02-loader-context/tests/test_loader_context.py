from model_consistency.core import analyze, extract_loader_context


def test_nearby_mentions_do_not_bind_distant_alternate_loader():
    text='Use MLX.\nNo custom code.\n'+'\n'*8+'Alternatively use Transformers.'
    result=analyze({'model_id':'a/b','revision':'fixed','readme':text})['overlay']
    assert result['claim_assessments'][0]['nearby_loader_context_lines']==[1]
    assert len(result['loader_context']['observations'])==2
    assert result['loader_context']['scope_binding']=='unverified'
    assert result['claim_assessments'][0]['consistency']=='unverifiable'


def test_fenced_and_quoted_mentions_preserve_provenance():
    text='~~~python\nimport transformers\n~~~\n> Requires recent llama.cpp.\nUse mlx_lm.'
    observations=extract_loader_context(text,'rev')['observations']
    assert [(x['source']['line'],x['in_fenced_code'],x['in_blockquote']) for x in observations]==[
        (2,True,False),(4,False,True),(5,False,False)]
    assert all(x['source']['revision']=='rev' for x in observations)
    assert observations[1]['qualification_candidate']


def test_mentions_do_not_resolve_qualification_versions():
    observations=extract_loader_context('Requires recent llama.cpp.\nTransformers >= 4.56.\nVersion unknown.','r')['observations']
    assert all(x['qualification_candidate'] for x in observations)
    assert observations[2]['loader_mentions']==[]


def test_no_loader_is_not_an_inferred_transformers_path():
    result=analyze({'model_id':'a/b','revision':'r','readme':'No custom code.','config':{'model_type':'qwen2'}})['overlay']
    assert result['loader_context']['observations']==[]
    assert result['claim_assessments'][0]['nearby_loader_context_lines']==[]
    assert result['claim_assessments'][0]['consistency']=='unverifiable'


def test_mismatched_fence_does_not_end_code_context():
    observations=extract_loader_context('````python\n```\nimport transformers\n````\nMLX','r')['observations']
    assert observations[0]['in_fenced_code']
    assert not observations[1]['in_fenced_code']
