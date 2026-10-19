"""Catalog-aware lexical comparison; semantic benchmark labels are not authorization."""
import collections,hashlib,json,math,re,time,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parent
STOP=set('the a an and or to for of in on with from using please my me is this that by as it be'.split())

def tokenize(text):
    text=re.sub(r'([a-z])([A-Z])',r'\1 \2',str(text))
    text=unicodedata.normalize('NFKC',text).casefold()
    return [w for w in re.findall(r'[^\W\d_]+',text) if w not in STOP]

def server_key(name):return ''.join(c for c in unicodedata.normalize('NFKC',name).casefold() if c.isalnum())

class Matcher:
    def __init__(self,variant):
        texts={}
        for path in sorted((ROOT/'data/benchmark/data/mcp_servers').glob('*/*.json')):
            source=path.parent.name;obj=json.loads(path.read_text(encoding='utf-8'))
            server=server_key(obj['name'])
            for tool in obj['tools']:
                key=(source,server,tool['name'])
                value=tool['name'] if variant=='names' else tool['name']+' '+str(tool.get('description') or '')
                if key in texts and texts[key]!=value:raise ValueError('Conflicting catalog definition: '+str(key))
                texts[key]=value
        self.catalog=texts;counts=collections.Counter()
        for value in texts.values():counts.update(set(tokenize(value)))
        self.idf={term:1+math.log((1+len(texts))/(1+freq)) for term,freq in counts.items()}
        self.vectors={key:self.vector(value) for key,value in texts.items()}

    def vector(self,text):
        counts=collections.Counter(tokenize(text))
        values={w:(1+math.log(tf))*self.idf[w] for w,tf in counts.items() if w in self.idf}
        norm=math.sqrt(sum(v*v for v in values.values()))
        return {w:v/norm for w,v in values.items()} if norm else {}

    def score(self,visible_input,source):
        # Accept only the declared input object. Groundtruth and match_tag never enter.
        if len(visible_input['tools'])!=len(visible_input['mcp_servers']):return None
        query=self.vector(visible_input['task']);scores=[]
        for name,server in zip(visible_input['tools'],visible_input['mcp_servers']):
            vector=self.vectors.get((source,server_key(server),name))
            if vector is None:return None
            scores.append(sum(v*vector.get(w,0) for w,v in query.items()))
        return min(scores) if scores else None

def metrics(rows,threshold=None,constant=None):
    tp=fp=fn=tn=unknown=0
    for row in rows:
        y=row['truth']
        if constant is None and row['score'] is None:unknown+=1;continue
        pred=constant if constant is not None else row['score']>=threshold
        if y and pred:tp+=1
        elif pred:fp+=1
        elif y:fn+=1
        else:tn+=1
    def divide(a,b):return a/b if b else None
    pos=divide(2*tp,2*tp+fp+fn) or 0;neg=divide(2*tn,2*tn+fp+fn) or 0
    return {'rows':len(rows),'assessed':tp+fp+fn+tn,'indeterminate':unknown,'coverage':(len(rows)-unknown)/len(rows),
        'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':divide(tp,tp+fp),'recall':divide(tp,tp+fn),
        'false_appropriate_rate':divide(fp,fp+tn),'macro_f1':(pos+neg)/2,'accuracy':divide(tp+tn,tp+fp+fn+tn)}

def main():
    out=ROOT/'results/lexical-v1';out.mkdir(parents=True,exist_ok=True)
    protocol=json.loads((ROOT/'PROTOCOL.json').read_text());expected=protocol['code_sha256']
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==expected,'Frozen code changed'
    summary={'protocol':protocol,'variants':{},'setting':'Catalog-aware IDF includes public test-server tool descriptions, never test tasks/labels; validation-only calibration.'}
    for variant in ['names','names_descriptions']:
        start=time.perf_counter();model=Matcher(variant);scored=[]
        for path in sorted((ROOT/'data/benchmark/data').glob('*/*/*.json')):
            if path.name not in {'test.json','validation.json'}:continue
            source=path.parent.name;split=path.stem;n=int(path.parent.parent.name[:2])
            for i,row in enumerate(json.loads(path.read_text(encoding='utf-8'))):
                assert row['match_tag'] in {'correct','wrong','null'}
                inp=row['input'];scored.append({'source':source,'split':split,'tools_per_task':n,'row':i,
                    'task_hash':hashlib.sha256(inp['task'].encode()).hexdigest(),
                    'truth':row['match_tag']=='correct','tag':row['match_tag'],'score':model.score(inp,source)})
        validation=[r for r in scored if r['source']=='ASTRA' and r['split']=='validation']
        candidates=[(metrics(validation,k/100)['macro_f1'],k/100) for k in range(101)]
        _,threshold=max(candidates) # Higher threshold wins exact ties: conservative fixed rule.
        test={}
        for source in ['ASTRA','TOUCAN']:
            for n in [1,2,3]:
                selected=[r for r in scored if r['source']==source and r['split']=='test' and r['tools_per_task']==n]
                test[source+'_'+str(n)]={'lexical':metrics(selected,threshold),'always_appropriate':metrics(selected,constant=True),
                    'always_inappropriate':metrics(selected,constant=False),'unique_task_hashes':len({r['task_hash'] for r in selected})}
        summary['variants'][variant]={'calibrated_threshold':threshold,'validation':metrics(validation,threshold),'test':test,
            'catalog_tool_definitions':len(model.catalog),'runtime_seconds_single_run':time.perf_counter()-start}
        with (out/(variant+'_predictions.jsonl')).open('w',encoding='utf-8') as f:
            for r in scored:f.write(json.dumps(r)+'\n')
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({v:{'threshold':r['calibrated_threshold'],'test_macro_f1':{k:round(x['lexical']['macro_f1'],3) for k,x in r['test'].items()},
        'indeterminate':{k:x['lexical']['indeterminate'] for k,x in r['test'].items()}} for v,r in summary['variants'].items()},indent=2))

if __name__=='__main__':main()
