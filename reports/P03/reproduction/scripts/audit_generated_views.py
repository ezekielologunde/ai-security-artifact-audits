"""Measure view leakage and repeatability; no fitted detector or population claims."""
import ast, collections, hashlib, json, logging, sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]

def metrics(truth,pred):
    tp=int((truth & pred).sum());fp=int((~truth & pred).sum())
    fn=int((truth & ~pred).sum());tn=int((~truth & ~pred).sum())
    return {'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,'accuracy':(tp+tn)/len(truth)}

def fingerprint(df):
    # Hash a multiset of canonical row values, retaining duplicates and ignoring row order.
    cols=sorted(df.columns)
    hashes=sorted(hashlib.sha256(json.dumps(list(row),default=str,separators=(',',':')).encode()).digest() for row in df[cols].itertuples(index=False,name=None))
    return hashlib.sha256(b''.join(hashes)).hexdigest()

def main():
    records=[];frames=[]
    source=ROOT/'data/sources/Deepa-15__shadowai-enterprise-dataset/files/generators/violation_generator.py'
    parsed=ast.parse(source.read_text(encoding='utf-8'))
    function=next(n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name=='verify_detector_view')
    namespace={'logger':logging.getLogger('component-audit')}
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),namespace)
    for number in [1,2]:
        folder=ROOT/'work'/f'generator-run-{number}'/'outputs'
        if not (folder/'detector_view.csv').exists():continue
        detector=pd.read_csv(folder/'detector_view.csv')
        truth=pd.read_csv(folder/'ground_truth.csv',usecols=['session_id','is_violation'])
        joined=detector.merge(truth,on='session_id',validate='one_to_one')
        assert len(joined)==len(detector)==len(truth)
        y=joined['is_violation'].astype(bool)
        shortcut=joined['session_type'].eq('shadow_ai_violation')
        always_negative=pd.Series(False,index=joined.index)
        # AI-use evidence is not a policy authorization label.
        ai_domain=joined['destination_domain'].isin(['chat.openai.com','claude.ai','gemini.google.com','copilot.microsoft.com','www.perplexity.ai'])
        validator=namespace['verify_detector_view'](detector)
        record={'run':number,'rows':len(joined),'positive_labels':int(y.sum()),'prevalence':float(y.mean()),
            'detector_columns':detector.columns.tolist(),'session_type_counts':detector['session_type'].value_counts().to_dict(),
            'direct_alias_shortcut':metrics(y,shortcut),'always_negative':metrics(y,always_negative),
            'original_validator_accepts_detector_view':bool(validator),
            'network_nonidentifier_multiset_sha256':fingerprint(detector.drop(columns=['session_id'])),
            'labeled_nonidentifier_multiset_sha256':fingerprint(joined.drop(columns=['session_id']))}
        if ai_domain is not None:record['ai_domain_as_violation_baseline']=metrics(y,ai_domain)
        records.append(record);frames.append(detector)
    if len(records)!=2:raise ValueError('Both full generator runs are required')
    output={'protocol':'source-audit-v1; exploratory mechanism confirmation, not held-out validation',
        'source_revision':'b1d2966939edde18edc08a08f52145fc1378d567','runs':records,
        'raw_detector_files_identical':hashlib.sha256((ROOT/'work/generator-run-1/outputs/detector_view.csv').read_bytes()).hexdigest()==hashlib.sha256((ROOT/'work/generator-run-2/outputs/detector_view.csv').read_bytes()).hexdigest(),
        'network_rows_identical_ignoring_session_ids_and_order':records[0]['network_nonidentifier_multiset_sha256']==records[1]['network_nonidentifier_multiset_sha256'],
        'labeled_rows_identical_ignoring_session_ids_and_order':records[0]['labeled_nonidentifier_multiset_sha256']==records[1]['labeled_nonidentifier_multiset_sha256'],
        'interpretation':'Perfect direct-alias prediction is an invalid detection result; class labels leak through session_type. Generated sessions are synthetic. No author-published model result was evaluated.'}
    (ROOT/'results/view_audit.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    removed={'session_type','session_id'}
    schema={'method':'Remove the confirmed label alias and identifier; no assertion of exhaustive leakage removal',
        'excluded':sorted(removed),'remaining_columns':[c for c in frames[0].columns if c not in removed]}
    (ROOT/'results/restricted_feature_schema.json').write_text(json.dumps(schema,indent=2),encoding='utf-8')
    print(json.dumps(output,indent=2))

if __name__=='__main__':main()
