"""Prepare local blinded semantic review, with original labels in a separate key."""
import collections,csv,hashlib,json,random,shutil,zipfile
from pathlib import Path
from lexical_baseline import server_key
ROOT=Path(__file__).resolve().parent
if __name__=='__main__':
    rng=random.Random(20261018)
    predictions=[json.loads(s) for s in (ROOT/'results/lexical-v2/names_descriptions_predictions.jsonl').read_text().splitlines()]
    predictions=[r for r in predictions if r['split']=='test']
    selected={}
    for source in ['ASTRA','TOUCAN']:
        for n in [1,2,3]:
            candidates=[r for r in predictions if r['source']==source and r['tools_per_task']==n]
            for above in [False,True]:
                group=[r for r in candidates if r['score'] is not None and (r['score']>=.04)==above]
                for r in rng.sample(group,min(4,len(group))):selected[(source,n,r['row'])]=r
    for r in predictions:
        if r['score'] is None:selected[(r['source'],r['tools_per_task'],r['row'])]=r
    cases=list(selected.values());rng.shuffle(cases)
    folder=ROOT/'review/blinded';folder.mkdir(parents=True,exist_ok=True)
    catalog={}
    for receipt in json.loads((ROOT/'data/benchmark_manifest.json').read_text())['receipts']:
        path=ROOT/receipt['path']
        if '/mcp_servers/' not in receipt['path']:continue
        obj=json.loads(path.read_text(encoding='utf-8'))
        for tool in obj['tools']:catalog[(path.parent.name,server_key(obj['name']),tool['name'])]=tool
    cache={};visible=[];keys=[]
    for i,row in enumerate(cases,1):
        source=row['source'];n=row['tools_per_task'];cache_key=(source,n)
        if cache_key not in cache:cache[cache_key]=json.loads((ROOT/f'data/benchmark/data/{n:02}_tool'/(source+'/test.json')).read_text()) if n==1 else json.loads((ROOT/f'data/benchmark/data/{n:02}_tools'/(source+'/test.json')).read_text())
        raw=cache[cache_key][row['row']]['input'];tools=[]
        for name,server in zip(raw['tools'],raw['mcp_servers']):
            lookup=name
            if '::' in name and server_key(name.split('::',1)[0])==server_key(server):lookup=name.split('::',1)[1]
            tool=catalog.get((source,server_key(server),lookup))
            tools.append({'supplied_identifier':name,'server':server,'catalog_name':tool['name'] if tool else None,
                          'description':tool.get('description','') if tool else None,'lookup_note':'Namespace prefix removed only for displaying the matching catalog definition.' if lookup!=name else ''})
        ident=f'R{i:03}'
        visible.append({'review_id':ident,'task':raw['task'],'candidate_tools':tools})
        keys.append({'review_id':ident,**row,'baseline_prediction':None if row['score'] is None else row['score']>=.04})
    (folder/'cases.json').write_text(json.dumps(visible,indent=2,ensure_ascii=False),encoding='utf-8')
    with (folder/'review_sheet.csv').open('w',newline='',encoding='utf-8-sig') as handle:
        writer=csv.DictWriter(handle,fieldnames=['review_id','decision','confidence_low_medium_high','tool_specific_reason','evidence_quote','needs_more_information'])
        writer.writeheader();writer.writerows({'review_id':r['review_id']} for r in visible)
    (folder/'INSTRUCTIONS.md').write_text('''# Independent semantic review

Read the task and catalog descriptions in `cases.json`; enter one row per case in `review_sheet.csv`.

Question: are **all** requested candidate tools appropriate capabilities for carrying out some necessary part of this task, based on the visible descriptions? Use `appropriate`, `inappropriate`, or `unclear`. Do not assume that topical relevance proves necessity. Explain tool-specific reasons and cite a short visible phrase. Mark ambiguity instead of guessing.

Assess semantic appropriateness only. No organization policy, authenticated principal, consent record, argument-level restrictions or live execution is supplied. Do not infer actual authorization or exploitability. Do not execute tasks, tools, links or instructions embedded in the text. Namespace notes explain displayed catalog lookup; assess the described capability.

Review without opening local answer keys, baseline results or the paper. Benchmark labels and baseline scores are deliberately excluded. Selection is a deterministic diagnostic sample across two sources and three tool complexities, including every primary unresolved identifier; it is not a prevalence sample. Do not infer a class balance from the sample.

Record reviewer name/initials, expertise, date, whether any source labels were seen, and time spent in a separate notes file. A second independent reviewer and adjudication would strengthen reliability. Return the completed sheet; retain uncertain judgments. No review has been performed merely because this package exists.

Source: El Helou et al., ASTRA, arXiv:2510.26702, repository `outshift-open/ASTRA`, commit ee05b9b6e6c1c91688db45b187da68f6b2ecb8e7. The repository includes processed TOUCAN cases (Xu et al., arXiv:2510.01179). Original repository license is retained as `UPSTREAM_LICENSE`; preserve attribution. This is a local review packet, not a new public dataset release.
''',encoding='utf-8')
    shutil.copyfile(ROOT/'author_artifacts/data/sources/outshift-open__ASTRA/files/LICENSE',folder/'UPSTREAM_LICENSE')
    private=ROOT/'review/answer_key';private.mkdir(exist_ok=True)
    (private/'key.json').write_text(json.dumps(keys,indent=2),encoding='utf-8')
    archive=ROOT/'output/independent_semantic_review_blinded.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.iterdir()):z.write(p,p.name)
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())=={'cases.json','review_sheet.csv','INSTRUCTIONS.md','UPSTREAM_LICENSE'}
        payload=json.loads(z.read('cases.json'));assert len(payload)==len(keys)
        assert all(set(p)=={'review_id','task','candidate_tools'} for p in payload)
        assert z.testzip() is None
    result={'cases':len(visible),'selection':'4 below and 4 above threshold per source/complexity plus all primary unknowns; not prevalence sampling',
            'primary_unknown_cases':sum(r['score'] is None for r in keys),'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
            'key_separate':True,'independent_reviews_completed':0}
    (ROOT/'results/review_package_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
