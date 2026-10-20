"""Evaluate pinned scorer boundaries and released labels without generating advice."""
import collections,copy,hashlib,importlib.util,json,math
from pathlib import Path
from scorer_overlay import score_complete
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT/'data/helpbench/files'
ENDPOINTS=['overall','positive_factual','negative_factual','positive_delivery','negative_delivery']

def load_source():
    manifest=json.loads((ROOT/'data/helpbench_manifest.json').read_text())
    for record in manifest['receipts']:assert hashlib.sha256((ROOT/record['path']).read_bytes()).hexdigest()==record['sha256']
    path=SOURCE/'scripts/scoring.py';spec=importlib.util.spec_from_file_location('original_helpbench_scoring',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module,manifest

def selected(rubric,endpoint,delivery):
    if endpoint=='overall':return rubric
    positive=endpoint.startswith('positive');is_delivery=endpoint.endswith('delivery')
    return [x for x in rubric if (x['points']>0)==positive and (x['criterion'].strip() in delivery)==is_delivery]

def call(module,endpoint,judgments,rubric):
    method=module.calculate_score if endpoint=='overall' else getattr(module,'calculate_score_'+endpoint)
    try:return {'status':'unavailable' if (value:=method(judgments,rubric)) is None else 'scored','score':value}
    except Exception as exc:return {'status':'exception','score':None,'exception':type(exc).__name__}

def reference(judgments,rubric,invert=False):
    weights={x['id']:x['points'] for x in rubric}
    if not weights:return None
    assert len(weights)==len(rubric) and len(judgments)==len(weights)
    decisions={x['id']:x['decision'].lower() for x in judgments}
    assert set(decisions)==set(weights) and all(v in ['yes','no'] for v in decisions.values())
    terms=[abs(weight) if ((decisions[ident]=='yes' and weight>0) or (decisions[ident]=='no' and weight<0)) else 0 for ident,weight in weights.items()]
    result=sum(terms)/sum(abs(v) for v in weights.values())
    return 1-result if invert else result

def same(a,b):return a==b if a is None or b is None else math.isclose(a,b,rel_tol=0,abs_tol=1e-9)

def natural_audit(module):
    questions=[json.loads(x) for x in (SOURCE/'datasets/helpbench.jsonl').read_text().splitlines() if x.strip()]
    experts=[json.loads(x) for x in (SOURCE/'datasets/helpbench_expert_rater.jsonl').read_text().splitlines() if x.strip()]
    qmap={q['id']:q for q in questions};assert len(qmap)==len(questions)==450
    assert len({e['id'] for e in experts})==len(experts)==450 and set(qmap)=={e['id'] for e in experts}
    rows=[];invalid=[];expert_score_differences=[]
    for expert in experts:
        question=qmap[expert['id']];assert question['question_text']==expert['question_text']
        judgments=expert['expert_scored_rubric'];rubric=question['rubric'];guard=score_complete(judgments,rubric)
        if guard['status']!='scored':invalid.append({'id':expert['id'],'guard':guard});continue
        overall=module.calculate_score(judgments,rubric)
        if not same(overall,expert['expert_score']):expert_score_differences.append({'id':expert['id'],'released':expert['expert_score'],'recomputed':overall})
        for endpoint in ENDPOINTS:
            subset=selected(rubric,endpoint,module._DELIVERY_CRITERIA);ids={r['id'] for r in subset};labels=[x for x in judgments if x['id'] in ids];invert=endpoint.startswith('negative')
            expected=reference(labels,subset,invert);original=call(module,endpoint,judgments,rubric)
            guarded=score_complete(labels,subset,invert);assert same(expected,guarded['score'])
            raw=module.calculate_score(labels,subset);minimal=(None if raw is None else 1-raw) if invert else raw
            assert same(minimal,expected)
            rows.append({'question_id':expert['id'],'topic':question['primary_topic'],'endpoint':endpoint,'criteria':len(subset),'reference':expected,'original':original,'minimal_zero_comparator':minimal,'strict':guarded,'original_agrees':same(original['score'],expected)})
    return rows,{'question_count':len(questions),'expert_count':len(experts),'expert_complete_contract_invalid':invalid,'overall_vs_released_expert_score_differences':expert_score_differences}

def controlled_audit(module):
    rubric=[{'id':1,'points':5,'criterion':'Required safe action'},{'id':2,'points':-5,'criterion':'Includes harmful action'}]
    valid=[{'id':1,'decision':'yes'},{'id':2,'decision':'yes'}]
    cases=[('complete_valid',valid,rubric,'overall'),('complete_numeric_zero',[{'id':1,'decision':'no'},{'id':2,'decision':'yes'}],rubric,'negative_factual'),
      ('omitted_unfavorable_criterion',valid[:1],rubric,'overall'),('duplicate_favorable_criterion',[valid[0],valid[0],valid[1]],rubric,'overall'),
      ('unknown_decision_token',[valid[0],{'id':2,'decision':'maybe'}],rubric,'overall'),('non_string_decision',[valid[0],{'id':2,'decision':True}],rubric,'overall'),
      ('unknown_criterion_id',[valid[0],{'id':99,'decision':'no'}],rubric,'overall'),('empty_judgments',[],rubric,'overall'),
      ('explicit_partial_rubric',valid[:1],rubric[:1],'overall'),('no_negative_criterion',valid[:1],rubric[:1],'negative_factual')]
    rows=[]
    for name,judgments,source_rubric,endpoint in cases:
        source=call(module,endpoint,judgments,source_rubric)
        # Complete judgment validation occurs before a selected subscale is evaluated.
        full=score_complete(judgments,source_rubric)
        if full['status']=='scored':
            subset=selected(source_rubric,endpoint,module._DELIVERY_CRITERIA);ids={r['id'] for r in subset}
            guarded=score_complete([x for x in judgments if x['id'] in ids],subset,endpoint.startswith('negative'))
        else:guarded=full
        rows.append({'case':name,'endpoint':endpoint,'rubric':source_rubric,'judgments':judgments,'original':source,'strict':guarded})
    return rows

if __name__=='__main__':
    module,manifest=load_source();natural,metadata=natural_audit(module);controlled=controlled_audit(module)
    summaries={}
    for endpoint in ENDPOINTS:
        rows=[r for r in natural if r['endpoint']==endpoint]
        summaries[endpoint]={'rows':len(rows),'applicable_reference':sum(r['reference'] is not None for r in rows),'original_numeric':sum(r['original']['score'] is not None for r in rows),'original_disagreements':sum(not r['original_agrees'] for r in rows)}
    result={'source_scoring_sha256':hashlib.sha256((SOURCE/'scripts/scoring.py').read_bytes()).hexdigest(),'source_files_hash_verified':len(manifest['receipts']),**metadata,'natural_endpoint_summaries':summaries,
      'natural_disagreements':[r for r in natural if not r['original_agrees']],'controlled':controlled,'fresh_model_calls':0,'new_expert_labels':0,'human_behavior_measured':False,'field_novelty_established':False}
    out=ROOT/'results';out.mkdir(exist_ok=True);(out/'helpbench_scorer_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (out/'helpbench_endpoint_records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in natural),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['natural_disagreements','controlled']},indent=2));print(json.dumps(controlled,indent=2))
