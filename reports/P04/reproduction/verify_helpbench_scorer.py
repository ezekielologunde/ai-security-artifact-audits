"""Independent arithmetic and behavioral controls, with source bytes preserved."""
import collections,hashlib,json,math,xml.etree.ElementTree as ET
from pathlib import Path
from audit_helpbench_scorer import ROOT,SOURCE,load_source,canonical_question_id
from scorer_overlay import score_complete

def run():
    source,manifest=load_source();checks=[]
    questions=[json.loads(line) for line in (SOURCE/'datasets/helpbench.jsonl').read_text().splitlines() if line.strip()]
    experts=[json.loads(line) for line in (SOURCE/'datasets/helpbench_expert_rater.jsonl').read_text().splitlines() if line.strip()]
    qmap={q['id']:q for q in questions};assert len(qmap)==450
    assert all(qmap[canonical_question_id(e['id'])]['question_text']==e['question_text'] for e in experts)
    checks.append('independent_ID_and_text_join')
    worst=collections.Counter();all_counts=collections.Counter();score_agree=0
    for expert in experts:
        rubric=qmap[canonical_question_id(expert['id'])]['rubric'];labels={x['id']:x['decision'] for x in expert['expert_scored_rubric']}
        assert len(labels)==len(rubric) and set(labels)=={x['id'] for x in rubric}
        earned=sum(abs(r['points']) for r in rubric if (r['points']>0 and labels[r['id']]=='yes') or (r['points']<0 and labels[r['id']]=='no'))
        assert math.isclose(earned/sum(abs(r['points']) for r in rubric),expert['expert_score'],rel_tol=0,abs_tol=1e-9);score_agree+=1
        for name,is_delivery in [('negative_factual',False),('negative_delivery',True)]:
            negative=[r for r in rubric if r['points']<0 and ((r['criterion'].strip() in source._DELIVERY_CRITERIA)==is_delivery)]
            if negative:
                all_counts[name]+=1
                if all(labels[r['id']]=='yes' for r in negative):worst[name]+=1
    assert score_agree==450 and dict(worst)=={'negative_delivery':39,'negative_factual':19} and dict(all_counts)=={'negative_delivery':450,'negative_factual':439}
    checks.append('independent_full_weighted_score_and_zero_endpoint_recount')
    primary=json.loads((ROOT/'results/helpbench_scorer_audit.json').read_text());assert primary['expert_complete_contract_invalid']==[] and primary['overall_vs_released_expert_score_differences']==[]
    assert len(primary['natural_disagreements'])==58 and all(r['reference']==1 and r['original']['score'] is None for r in primary['natural_disagreements'])
    checks.append('all_observed_disagreements_are_defined_maximum_inverted_endpoints')
    rubric=[{'id':1,'points':5},{'id':2,'points':-5}];labels=[{'id':1,'decision':'yes'},{'id':2,'decision':'yes'}]
    assert score_complete(labels,rubric)['score']==.5
    for bad in [labels[:1],labels+[labels[0]],[labels[0],{'id':2,'decision':'maybe'}],[labels[0],{'id':2,'decision':True}],[labels[0],{'id':True,'decision':'yes'}],[labels[0],{'id':99,'decision':'no'}],[]]:
        assert score_complete(bad,rubric)['status']=='invalid'
    checks.append('missing_duplicate_unknown_and_nonstring_judgments_rejected')
    assert score_complete(labels[:1],rubric[:1])['score']==1 and score_complete([],[])['status']=='not_applicable'
    for bad_id in ['01',True,'1.0','x']:
        try:canonical_question_id(bad_id)
        except ValueError:pass
        else:raise AssertionError('Noncanonical join ID accepted')
    checks.append('legitimate_selected_subset_and_unavailable_controls')
    sub=[{'id':2,'points':-5}];assert score_complete([labels[1]],sub,invert=True)['score']==1
    assert score_complete([{'id':2,'decision':'no'}],sub,invert=True)['score']==0
    checks.append('both_numeric_inversion_endpoints_preserved')
    tree=ET.parse(ROOT/'results/helpbench_upstream_junit.xml');suites=tree.getroot();assert sum(int(s.get('tests',0)) for s in suites.iter('testsuite'))==9
    assert all(int(s.get('failures',0))==int(s.get('errors',0))==0 for s in suites.iter('testsuite'))
    checks.append('nine_original_tests_pass_without_source_changes')
    aggregate=json.loads((ROOT/'results/helpbench_conditional_aggregate.json').read_text())
    for name,stats in aggregate['endpoints'].items():
        assert stats['all_applicable_reference_denominator']-stats['source_numeric_denominator']==worst[name]
        recovered=(stats['source_skip_None_mean']*stats['source_numeric_denominator']+worst[name])/stats['all_applicable_reference_denominator']
        assert math.isclose(recovered,stats['reference_all_applicable_mean'],rel_tol=0,abs_tol=1e-12)
    checks.append('conditional_consumer_denominator_identity')
    for record in manifest['receipts']:assert hashlib.sha256((ROOT/record['path']).read_bytes()).hexdigest()==record['sha256']
    checks.append('all_ten_original_source_and_data_hashes_unchanged')
    return {'checks_passed':len(checks),'checks':checks,'overall_scores_independently_reproduced':score_agree,'zero_endpoint_counts':dict(worst),'new_model_calls':0,'independent_external_review':False}
if __name__=='__main__':
    result=run();(ROOT/'results/helpbench_scorer_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
