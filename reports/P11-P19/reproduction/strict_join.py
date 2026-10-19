"""Explicit identity-preserving outcome join; missing outcomes remain unknown."""
KEY=('model','task_id','perturbation_type')
def identity(row):
    if any(k not in row or row[k] is None or row[k]=='' for k in KEY):raise ValueError('Complete model/task/perturbation identity required')
    return tuple(row[k] for k in KEY)
def join_outcomes(tokens,outcomes):
    indexed={}
    for row in outcomes:
        key=identity(row)
        if key in indexed:raise ValueError('Duplicate correctness identity')
        if not isinstance(row.get('is_correct'),bool):raise ValueError('Correctness must be an explicit boolean')
        indexed[key]=row
    result=[];seen=set()
    for row in tokens:
        key=identity(row)
        if key in seen:raise ValueError('Duplicate token identity')
        seen.add(key)
        result.append({**row,'is_correct':indexed.get(key,{}).get('is_correct')})
    return result
def cost_outcomes(rows):
    high=[r for r in rows if r['token_multiplier']>2 and r['is_correct'] is not None]
    low=[r for r in rows if r['token_multiplier']<1.2 and r['is_correct'] is not None]
    return {'high_cost_correct_pct':100*sum(r['is_correct'] for r in high)/len(high) if high else None,
            'low_cost_incorrect_pct':100*sum(not r['is_correct'] for r in low)/len(low) if low else None,
            'high_cost_labeled_rows':len(high),'low_cost_labeled_rows':len(low),
            'unknown_correctness_rows':sum(r['is_correct'] is None for r in rows)}
