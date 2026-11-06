#!/usr/bin/env python3
"""Explicit, task-scoped bridge to the trusted toolkit. No daemon or app execution."""
import argparse,hashlib,json,os,pathlib,re,subprocess,sys,time,uuid

def hash_file(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(pathlib.Path(path).read_text())
def atomic(path,value):
 path=pathlib.Path(path);temporary=path.with_name('.'+uuid.uuid4().hex)
 temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.chmod(0o600);temporary.replace(path)
def git(repo,*args):
 env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
 env.update(GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_SYSTEM=os.devnull,GIT_CONFIG_NOSYSTEM='1',GIT_OPTIONAL_LOCKS='0',GIT_TERMINAL_PROMPT='0')
 return subprocess.run(['git','-c','core.fsmonitor=false','-c','core.quotePath=false','-C',str(repo),*args],env=env,stdin=subprocess.DEVNULL,capture_output=True,check=True,timeout=60).stdout

def binding(state):
 state=pathlib.Path(state).resolve();bound=load(state/'binding.json')
 if hash_file(__file__)!=bound['adapter_sha256']:raise ValueError('on-demand adapter changed after preparation')
 toolkit=pathlib.Path(bound['toolkit_root'])
 for relative,expected in bound['trusted_toolkit_files'].items():
  if hash_file(toolkit/relative)!=expected:raise ValueError('trusted toolkit implementation changed')
 for name,expected in bound['prepared_files'].items():
  if hash_file(state/name)!=expected:raise ValueError('accepted configuration changed')
 return state,bound

def prepare(args):
 project=pathlib.Path(args.project_root).resolve(strict=True);toolkit=pathlib.Path(args.toolkit_root).resolve(strict=True)
 state=pathlib.Path(args.state_dir).absolute();profile=load(args.profile);consent=load(args.consent_file)['public_source_export']
 if profile['task_ref']!=args.task_ref or not args.authorize_task:raise ValueError('explicit matching task authorization required')
 name=profile['project']
 if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',name) or not re.fullmatch(r'[0-9a-f]{40}',args.source_sha):raise ValueError('invalid project/SHA')
 if consent['sources'].get(name)!=args.source_sha or consent['model']!=args.model:raise ValueError('consent does not bind this project/SHA/model')
 if not consent['provider'].startswith('Claude/Anthropic'):raise ValueError('unsupported provider consent')
 for line in git(project,'worktree','list','--porcelain').decode().splitlines():
  if line.startswith('worktree ') and state.resolve().is_relative_to(pathlib.Path(line[9:]).resolve()):raise ValueError('state must be outside all source checkouts')
 if state.exists():raise ValueError('state directory already exists; resume instead of overwriting')
 for relative,expected in profile['trusted_toolkit_files'].items():
  path=pathlib.Path(relative)
  if path.is_absolute() or '..' in path.parts or hash_file(toolkit/path)!=expected:raise ValueError('trusted toolkit hash/path mismatch')
 version=subprocess.run(['claude','--version'],capture_output=True,check=True,timeout=15).stdout.decode().strip()
 if version!=profile['validated_cli_version']:raise ValueError('Claude version requires permission revalidation')
 state.mkdir(mode=0o700,parents=True)
 git(state,'clone','--shared','--no-checkout',str(project),str(state/'repo'))
 git(state/'repo','checkout','-B','a2-on-demand',args.source_sha)
 if git(state/'repo','status','--porcelain=v1','--untracked-files=all').strip():raise ValueError('snapshot clone is not clean')
 atomic(state/'profile.json',profile)
 atomic(state/'authorization.json',{'provider':consent['provider'],'project':name,'model':args.model,'source_sha':args.source_sha,'task_ref':args.task_ref,'source_consent_sha256':hash_file(args.consent_file)})
 (state/'policy.txt').write_text(profile['policy']+'\n');nodes=[]
 for recipe in profile['nodes']:
  node=recipe['id']
  if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',node):raise ValueError('invalid node')
  for relative in recipe['paths']:
   path=pathlib.Path(relative)
   if path.is_absolute() or '..' in path.parts:raise ValueError('invalid source path')
   metadata=git(project,'ls-tree',args.source_sha,'--',relative).decode()
   if not metadata.startswith(('100644 blob ','100755 blob ')):raise ValueError('required path is not committed regular source')
  (state/(node+'.brief.txt')).write_text(recipe['brief']+'\n')
  common=[sys.executable,str(pathlib.Path(__file__).resolve())]
  nodes.append({'id':node,'authorized':True,'role':'reviewer','review_sha':args.source_sha,'argv':common+['worker','--state-dir',str(state),'--node',node],'cwd':'.','scope':['.'],'depends_on':recipe['depends_on'],'acceptance':[common+['verify','--state-dir',str(state),'--node',node]],'timeout_seconds':recipe['timeout_seconds']+40,'max_attempts':1,'blocked_exit_codes':[2,78]})
 plan={'schema_version':1,'id':'a2-'+name.lower()+'-'+uuid.uuid4().hex[:12],'integration_branch':'a2-on-demand','capacity':2,'nodes':nodes}
 atomic(state/'plan.json',plan)
 prepared={p.name:hash_file(p) for p in state.iterdir() if p.is_file()}
 bound={'project':name,'source_sha':args.source_sha,'model':args.model,'task_ref':args.task_ref,'toolkit_root':str(toolkit),'trusted_toolkit_files':profile['trusted_toolkit_files'],'adapter_sha256':hash_file(__file__),'prepared_files':prepared,'notification_mode':'explicit delegated subscriber; no push into arbitrary chat','native_task_id':None}
 atomic(state/'binding.json',bound)
 subprocess.run([sys.executable,str(toolkit/'templates/agent-runtime.py'),'validate',str(state/'plan.json'),'--repo',str(state/'repo')],check=True,timeout=20)
 print(json.dumps({'prepared':True,'state_dir':str(state),'source_sha':args.source_sha,'model_calls_started':0,'plan_sha256':hash_file(state/'plan.json')}))

def runtime(args):
 state,bound=binding(args.state_dir)
 command=[sys.executable,str(pathlib.Path(bound['toolkit_root'])/'templates/agent-runtime.py'),args.command,str(state/'plan.json'),'--repo',str(state/'repo')]
 if args.command in ['events','watch','ack','status']:command+=['--consumer',args.consumer]
 if args.command=='watch':command+=['--poll-seconds',str(args.poll_seconds),'--shortest-worker-seconds',str(args.shortest_worker_seconds),'--max-wait',str(args.max_wait)]
 if args.command=='ack':command+=['--through',str(args.through)]
 return subprocess.call(command)

def worker(args):
 state,bound=binding(args.state_dir);recipe=next(x for x in load(state/'profile.json')['nodes'] if x['id']==args.node)
 run=os.environ.get('TOOLKIT_RUN_ID');sha=os.environ.get('TOOLKIT_REVIEW_SHA')
 if not re.fullmatch('[0-9a-f]{32}',run or '') or os.environ.get('TOOLKIT_NODE_ID')!=args.node or sha!=bound['source_sha']:raise ValueError('runtime attempt/SHA binding missing')
 authorization=load(state/'authorization.json')
 if authorization['source_sha']!=sha or authorization['model']!=bound['model']:raise ValueError('prepared source consent mismatch')
 attempt=state/'attempts'/args.node/run;attempt.mkdir(parents=True,mode=0o700)
 handle={'runtime_run_id':run,'node_id':args.node,'reviewed_sha':sha,'handle_kind':'claude_cli_session','provider_session_id':None,'native_task_id':None,'provider_terminal_result_observed':False,'observer_poll_seconds':0.2,'started_at':time.time(),'model':bound['model']}
 atomic(attempt/'session-handle.json',handle)
 command=[sys.executable,str(pathlib.Path(bound['toolkit_root'])/'templates/agent-runtime/readonly-review.py'),'--repo',str(state/'repo'),'--policy',str(state/'policy.txt'),'--brief',str(state/(args.node+'.brief.txt')),'--expected-sha',sha,'--model',bound['model'],'--output',str(attempt/'review.json'),'--timeout',str(recipe['timeout_seconds']),'--budget-usd',str(recipe['budget_usd']),'--effort',recipe['effort']]
 for relative in recipe['paths']:command+=['--path',relative]
 with (attempt/'adapter.stdout').open('xb') as out,(attempt/'adapter.stderr').open('xb') as err:
  child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=out,stderr=err)
  offset=0;buffer=b'';observed=0;error=None
  try:
   while True:
    candidates=list(attempt.glob('readonly-review-*/events.jsonl'));chunk=b''
    if len(candidates)>1:raise ValueError('ambiguous native trace')
    if candidates:
     trace=candidates[0]
     if trace.is_symlink() or not trace.is_file():raise ValueError('unsafe native trace')
     with trace.open('rb') as stream:stream.seek(offset);chunk=stream.read(1048576);offset+=len(chunk)
     observed+=len(chunk)
     if observed>33554432:raise ValueError('native trace byte bound')
     buffer+=chunk
     while b'\n' in buffer:
      line,buffer=buffer.split(b'\n',1)
      if not line.strip():continue
      event=json.loads(line)
      if event.get('type')=='system' and event.get('subtype')=='init':
       session=event.get('session_id')
       if event.get('model')!=bound['model'] or set(event.get('tools',[]))!={'Read','Glob','Grep'} or not isinstance(session,str):raise ValueError('unverified native init')
       uuid.UUID(session)
       if handle['provider_session_id'] not in [None,session]:raise ValueError('session changed')
       handle.update(provider_session_id=session,native_init_observed_at=time.time(),actual_tools=event['tools']);atomic(attempt/'session-handle.json',handle)
      if event.get('type')=='result':
       if event.get('session_id')!=handle['provider_session_id']:raise ValueError('terminal session mismatch')
       handle.update(provider_terminal_result_observed=True,native_terminal_observed_at=time.time(),native_result_subtype=event.get('subtype'));atomic(attempt/'session-handle.json',handle)
    if child.poll() is not None and not chunk:break
    time.sleep(.2)
  except Exception as exc:
   error=type(exc).__name__+': '+str(exc);child.terminate()
   try:child.wait(timeout=5)
   except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
 handle.update(finished_at=time.time(),adapter_exit_code=child.returncode,observer_error=error);atomic(attempt/'session-handle.json',handle)
 return 2 if error or not handle['provider_session_id'] or not handle['provider_terminal_result_observed'] else child.returncode

def verify(args):
 state,bound=binding(args.state_dir);run=os.environ.get('TOOLKIT_RUN_ID');sha=os.environ.get('TOOLKIT_REVIEW_SHA')
 if not re.fullmatch('[0-9a-f]{32}',run or '') or sha!=bound['source_sha']:raise ValueError('invalid runtime acceptance binding')
 attempt=state/'attempts'/args.node/run;review=load(attempt/'review.json');handle=load(attempt/'session-handle.json')
 if review['verdict']!='PASS' or review['reviewed_sha']!=sha or handle['runtime_run_id']!=run or handle['node_id']!=args.node or handle['reviewed_sha']!=sha:raise ValueError('review acceptance mismatch')
 if not handle['provider_session_id'] or handle['native_task_id'] is not None or not handle['provider_terminal_result_observed'] or handle['observer_error'] or handle['adapter_exit_code']!=0:raise ValueError('native result not accepted')
 if set(handle['actual_tools'])!={'Read','Glob','Grep'} or review['model']!=bound['model'] or not review['process']['cleanup_complete'] or review['process']['exit_code']!=0:raise ValueError('permissions/model/process acceptance failed')
 print(json.dumps({'accepted':True,'runtime_run_id':run,'reviewed_sha':sha,'handle_kind':'claude_cli_session','provider_session_id':handle['provider_session_id'],'native_task_id':None}))
 return 0

def main():
 parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
 p=sub.add_parser('prepare')
 for option in ['project-root','toolkit-root','state-dir','profile','source-sha','model','consent-file','task-ref']:p.add_argument('--'+option,required=True)
 p.add_argument('--authorize-task',action='store_true')
 for name in ['run','resume','events','watch','ack','status','worker','verify']:
  p=sub.add_parser(name);p.add_argument('--state-dir',required=True)
  if name in ['events','watch','ack','status']:p.add_argument('--consumer',default='main')
  if name=='watch':
   p.add_argument('--poll-seconds',type=float,required=True);p.add_argument('--shortest-worker-seconds',type=float,required=True);p.add_argument('--max-wait',type=float,required=True)
  if name=='ack':p.add_argument('--through',type=int,required=True)
  if name in ['worker','verify']:p.add_argument('--node',required=True)
 args=parser.parse_args()
 try:
  if args.command=='prepare':prepare(args);return 0
  if args.command=='worker':return worker(args)
  if args.command=='verify':return verify(args)
  return runtime(args)
 except (OSError,ValueError,KeyError,StopIteration,subprocess.SubprocessError) as error:
  print(json.dumps({'status':'BLOCKED','reason':type(error).__name__+': '+str(error)}));return 2
if __name__=='__main__':sys.exit(main())
