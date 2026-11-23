"""MIT. Scripted provider requests, unchanged native tool pipeline, physical readback."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import base64,hashlib,json,os,re,secrets,socket,subprocess,threading,time,urllib.request,urllib.error
import psutil
ROOT=Path(__file__).resolve().parent
ACQ=json.loads((ROOT/'results/opencode_binary_acquisition_20261123.json').read_text())
BINARY=Path(ACQ['binary_path'])
assert hashlib.sha256(BINARY.read_bytes()).hexdigest()==ACQ['binary_sha256']
PROTOCOL=json.loads((ROOT/'OPENCODE_WRITE_EFFECT_PROTOCOL_20261123.json').read_text())
assert (ROOT/'OPENCODE_WRITE_EFFECT_AMENDMENT_20261123.json').exists()
BASE=ROOT/'work/opencode-write-effects-20261123-r2';BASE.mkdir(exist_ok=False)
OUT=ROOT/'results/opencode-write-effects-20261123-r2';OUT.mkdir(exist_ok=False)
env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','PATH','PROCESSOR_ARCHITECTURE','OS','NUMBER_OF_PROCESSORS'}}
for key,folder in {'XDG_DATA_HOME':'data','XDG_CACHE_HOME':'cache','XDG_CONFIG_HOME':'config','XDG_STATE_HOME':'state','TMP':'tmp','TEMP':'tmp','APPDATA':'appdata','LOCALAPPDATA':'localappdata','OPENCODE_TEST_HOME':'home'}.items():
    path=BASE/folder;path.mkdir(exist_ok=True);env[key]=str(path)
env.update(DO_NOT_TRACK='1',OPENCODE_DISABLE_AUTOUPDATE='1')
projects=[]
for name in ['A','B']:
    project=BASE/f'project-{name}';project.mkdir()
    (project/'protected.txt').write_text('BASELINE_'+name)
    for args in [['init','-q'],['add','protected.txt'],['-c','user.name=Permission Research Fixture','-c','user.email=fixture@example.invalid','-c','core.hooksPath=','commit','-qm','Synthetic fixture '+name]]:
        subprocess.run(['git',*args],cwd=project,env=env,capture_output=True,check=True)
    projects.append(project)
provider_calls=[];cases={}
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        identifiers=re.findall(r'FIXTURE_CASE=([a-z_]+)',json.dumps(body.get('messages',[])))
        assert identifiers and len(set(identifiers))==1,identifiers
        active=cases[identifiers[0]]
        first=not active['emitted'];active['emitted']=True
        call={'id':'call_'+active['id'],'type':'function','function':{'name':'write','arguments':json.dumps({'path':active['path'],'content':active['marker']})}}
        message={'role':'assistant','content':None,'tool_calls':[call]} if first else {'role':'assistant','content':'FIXTURE_DONE_'+active['id']}
        finish='tool_calls' if first else 'stop'
        provider_calls.append({'condition':active['id'],'path':self.path,'request':body,'scripted_message':message})
        usage={'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}
        if body.get('stream'):
            delta={'role':'assistant','tool_calls':[{'index':0,**call}]} if first else message
            chunks=[{'id':'chatcmpl-fixture','object':'chat.completion.chunk','created':1,'model':'fixture','choices':[{'index':0,'delta':delta,'finish_reason':None}]},{'id':'chatcmpl-fixture','object':'chat.completion.chunk','created':1,'model':'fixture','choices':[{'index':0,'delta':{},'finish_reason':finish}],'usage':usage}]
            data=(''.join('data: '+json.dumps(c)+'\n\n' for c in chunks)+'data: [DONE]\n\n').encode();content='text/event-stream'
        else:
            data=json.dumps({'id':'chatcmpl-fixture','object':'chat.completion','created':1,'model':'fixture','choices':[{'index':0,'message':message,'finish_reason':finish}],'usage':usage}).encode();content='application/json'
        self.send_response(200);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
provider=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=threading.Thread(target=provider.serve_forever,daemon=True);thread.start()
config={'model':'lab/fixture','providers':{'lab':{'package':'@ai-sdk/openai-compatible','settings':{'baseURL':f'http://127.0.0.1:{provider.server_port}/v1','apiKey':'local-fixture-only'},'models':{'fixture':{'type':'chat','name':'Scripted write fixture','capabilities':{'tools':True,'input':['text'],'output':['text']},'limit':{'context':16384,'output':1024}}}}}}
for project in projects:(project/'opencode.json').write_text(json.dumps(config,indent=2)+'\n')
password=secrets.token_urlsafe(24);env['OPENCODE_SERVER_PASSWORD']=password
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
headers={'Authorization':'Basic '+base64.b64encode(('opencode:'+password).encode()).decode(),'Content-Type':'application/json'}
api_calls=[]
def api(method,path,body=None,timeout=12,record=True):
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=None if body is None else json.dumps(body).encode(),headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:status=response.status;raw=response.read(6_000_001)
    except urllib.error.HTTPError as error:status=error.code;raw=error.read(100000)
    assert len(raw)<=6_000_000
    data=json.loads(raw) if raw else None
    if record:api_calls.append({'method':method,'path':path,'payload':body,'status':status,'response':data})
    assert 200<=status<300,(status,data)
    return data
def read(path):return path.read_text() if path.exists() else None
def condition(ident,project,resource,effect,reply,expected):
    marker='NATIVE_WRITE_'+ident
    target=project/resource;before=read(target)
    cases[ident]={'id':ident,'path':resource,'marker':marker,'emitted':False}
    session=api('POST','/api/session',{'title':'Synthetic write '+ident,'location':{'directory':str(project)},'model':{'providerID':'lab','id':'fixture'},'permissions':[{'action':'edit','resource':resource,'effect':effect}]})['data']
    api('POST',f"/api/session/{session['id']}/prompt",{'text':'FIXTURE_CASE='+ident+' Run the controlled fixture once, then finish.'})
    pending=None;pre_reply_unchanged=None;terminal=None;messages=None
    for _ in range(160):
        requests=api('GET',f"/api/session/{session['id']}/permission",record=False)['data']
        if requests:
            assert len(requests)==1 and pending is None
            pending=requests[0]
            assert reply in ['always','reject'],('Unexpected prompt',ident,pending)
            assert pending['action']=='edit' and pending['resources']==[resource]
            pre_reply_unchanged=read(target)==before
            assert pre_reply_unchanged
            api('POST',f"/api/session/{session['id']}/permission/{pending['id']}/reply",{'decision':reply})
        messages=api('GET',f"/api/session/{session['id']}/message",record=False)
        idle=[m for m in messages['data'] if m['type']=='idle']
        if idle:terminal=idle[0];break
        completed=[m for m in messages['data'] if m['type']=='assistant' and m.get('finish')=='error' and m.get('time',{}).get('completed') and any(c.get('type')=='tool' and c.get('state',{}).get('status')=='error' and c.get('time',{}).get('completed') for c in m.get('content',[]))]
        if completed:
            terminal={'type':'completed_tool_error','message_id':completed[0]['id'],'session_idle_not_established':True}
            break
        time.sleep(.1)
    (OUT/f'{ident}_observation.json').write_text(json.dumps({'messages':messages,'pending':pending,'completion':terminal,'before':before,'after':read(target)},indent=2)+'\n')
    assert terminal is not None,('No native completion observation',ident)
    after=read(target)
    wanted=marker if expected=='write' else before
    observed_calls=[x for x in provider_calls if x['condition']==ident]
    assert observed_calls and observed_calls[0]['scripted_message'].get('tool_calls'),('No scripted write request',ident)
    result={'id':ident,'session_id':session['id'],'project_id':session['projectID'],'resource':resource,'configured_effect':effect,'reply':reply,'pending_request':pending,'pre_reply_file_unchanged':pre_reply_unchanged,'before':before,'after':after,'expected_after':wanted,'match':after==wanted,'native_terminal':terminal,'native_messages':messages,'provider_requests':len(observed_calls),'write_advertised':any(x.get('function',{}).get('name')=='write' for x in observed_calls[0]['request'].get('tools',[]))}
    conditions.append(result)
    print(json.dumps({k:v for k,v in result.items() if k in ['id','match','write_advertised','pre_reply_file_unchanged','provider_requests']}),flush=True)
    assert result['match'],('Physical effect mismatch',ident)
    if reply!='none':assert pending is not None
    if effect=='deny':assert 'permission' in json.dumps(messages).lower() or 'denied' in json.dumps(messages).lower()
    return session
stdout=(OUT/'stdout.txt').open('wb');stderr=(OUT/'stderr.txt').open('wb')
process=subprocess.Popen([str(BINARY),'serve','--hostname','127.0.0.1','--port',str(port)],cwd=projects[0],env=env,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
conditions=[];error=None;saved=None;owned=[]
try:
    ready=False
    for _ in range(50):
        if process.poll() is not None:raise RuntimeError('Owned server exited')
        try:api('GET','/openapi.json',timeout=1,record=False);ready=True;break
        except (OSError,AssertionError,ValueError):time.sleep(.5)
    assert ready
    condition('initial_reject',projects[0],'protected.txt','ask','reject','unchanged')
    condition('utility_allow',projects[0],'utility.txt','allow','none','write')
    a=condition('approve_always',projects[0],'protected.txt','ask','always','write')
    saved=api('GET','/api/permission/saved')['data']
    matching=[x for x in saved if x['action']=='edit' and x['resource']=='*' and x['projectID']==a['projectID']]
    assert len(matching)==1
    condition('successor_saved_allow',projects[0],'protected.txt','ask','none','write')
    condition('explicit_deny',projects[0],'protected.txt','deny','none','unchanged')
    call_id=matching[0]['id'];api('DELETE',f'/api/permission/saved/{call_id}')
    condition('removed_saved_approval',projects[0],'protected.txt','ask','reject','unchanged')
    b=condition('independent_project',projects[1],'protected.txt','ask','reject','unchanged')
    assert a['projectID']!=b['projectID']
except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)}
finally:
    if process.poll() is None:
        children=psutil.Process(process.pid).children(recursive=True);owned=[x.pid for x in children]+[process.pid]
        for child in children:
            try:child.terminate()
            except psutil.NoSuchProcess:pass
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
        _,alive=psutil.wait_procs(children,timeout=3)
        for child in alive:
            try:child.kill()
            except psutil.NoSuchProcess:pass
    provider.shutdown();provider.server_close();thread.join(timeout=3);stdout.close();stderr.close()
    result={'date':'2026-11-23','binary_sha256':ACQ['binary_sha256'],'error':error,'conditions':conditions,'saved_approvals':saved,'provider_calls':provider_calls,'api_calls':api_calls,'owned_shutdown_pids':owned,'server_terminal_exit':process.poll(),'real_model_inference':False,'scope':'Native built-in file-write effects from scripted local tool requests; not model efficacy or general task utility.'}
    (OUT/'RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'conditions':len(conditions),'matching':sum(x['match'] for x in conditions),'error':error,'owned_shutdown_pids':owned},indent=2))
if error:raise SystemExit(1)
