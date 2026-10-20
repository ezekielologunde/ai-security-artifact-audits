"""Explicit complete-subset weighted rubric contract; a validation adapter, not a new method."""
def score_complete(judgments,rubric,invert=False):
    if not isinstance(judgments,list) or not isinstance(rubric,list):return {'status':'invalid','reason':'list_required','score':None}
    if not rubric:return {'status':'not_applicable','score':None}
    ids=[];weights={}
    for item in rubric:
        if not isinstance(item,dict):return {'status':'invalid','reason':'rubric_record','score':None}
        ident=item.get('id');points=item.get('points')
        if isinstance(ident,bool) or not isinstance(ident,(str,int)) or ident in weights:return {'status':'invalid','reason':'rubric_identity','score':None}
        if isinstance(points,bool) or not isinstance(points,int) or points not in [-5,-3,-2,-1,1,2,3,5]:return {'status':'invalid','reason':'rubric_weight','score':None}
        ids.append(ident);weights[ident]=points
    decisions={}
    for item in judgments:
        if not isinstance(item,dict):return {'status':'invalid','reason':'judgment_record','score':None}
        ident=item.get('id');decision=item.get('decision')
        if isinstance(ident,bool) or not isinstance(ident,(str,int)) or ident not in weights or ident in decisions:return {'status':'invalid','reason':'judgment_identity','score':None}
        if not isinstance(decision,str) or decision.lower() not in ['yes','no']:return {'status':'invalid','reason':'decision_token','score':None}
        decisions[ident]=decision.lower()=='yes'
    if set(decisions)!=set(weights):return {'status':'invalid','reason':'incomplete_coverage','score':None}
    numerator=sum(abs(weight) for ident,weight in weights.items() if decisions[ident]==(weight>0))
    denominator=sum(abs(weight) for weight in weights.values());value=numerator/denominator
    return {'status':'scored','score':1-value if invert else value,'numerator':numerator,'denominator':denominator,'criteria':len(ids)}
