import ast,hashlib,itertools,json,argparse
from pathlib import Path

def build_case(number,style,flag,distractor,layout,mapping):
    case_id=f'B{number:03d}'
    model_id='binding-fixture/'+case_id
    prefix=['import transformers'] if style=='qualified-class' else ['from transformers import AutoModel']
    if style=='assigned-variable':prefix.append('repo = '+repr(model_id))
    target='repo' if style=='assigned-variable' else repr(model_id)
    cls='transformers.AutoModel' if style=='qualified-class' else 'AutoModel'
    if layout=='one-line':
        call=[f'model = {cls}.from_pretrained({target}, trust_remote_code={flag})']
    else:
        call=[f'model = {cls}.from_pretrained(',f'    {target},',f'    trust_remote_code={flag},',')']
    code='\n'.join(prefix+call)
    ast.parse(code)  # syntax validation only
    lines=['# '+case_id,'','No custom code is required.','','```python',*prefix,*call,'```']
    selected_line=6+len(prefix)
    if distractor=='other-model':
        other='AutoModel.from_pretrained("binding-fixture/other", trust_remote_code=True)'
        ast.parse(other)
        lines+=['','Another model example:','```python',other,'```']
    elif distractor=='comment':
        lines+=['','<!-- Historical example text: trust_remote_code=True -->']
    readme='\n'.join(lines)+'\n'
    assert lines[selected_line-1].startswith('model = ')
    config={'model_type':'bert'}
    if mapping:config['auto_map']={'AutoModel':'modeling_custom.Model'}
    snapshot={'model_id':model_id,'revision':hashlib.sha1(readme.encode()).hexdigest(),
              'readme':readme,'config':config,
              'loading_path':{'auto_class':'AutoModel','readme_call_line':selected_line},
              'artifacts':[{'path':'modeling_custom.py','format':'unknown'}]}
    return {'case_id':case_id,'factors':{'style':style,'remote_code':flag,'distractor':distractor,
                                       'layout':layout,'mapping':mapping},
            'reference':{'selected_target':model_id,'selected_class':'AutoModel',
                         'selected_remote_code':flag,'mapping_present':mapping,
                         'enabled_declared_custom_route':flag and mapping,
                         'scope':'Authored documentation/configuration route; no runtime truth'},
            'selected_python_example':code,'snapshot':snapshot}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    if args.output.exists():raise SystemExit('Refusing overwrite')
    factors=itertools.product(['direct-literal','assigned-variable','qualified-class'],[False,True],['none','other-model','comment'],['one-line','multi-line'],[False,True])
    cases=[build_case(i,*v) for i,v in enumerate(factors,1)]
    args.output.write_text(json.dumps(cases,indent=2)+'\n',encoding='utf-8')
    print(len(cases),'authored cases generated')
