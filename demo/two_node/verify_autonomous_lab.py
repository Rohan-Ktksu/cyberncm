"""Verify opt-in lab automation with actual detector processes and real loopback probes."""
import json,os,socket,subprocess,sys,tempfile,time
from pathlib import Path
from bootstrap import ensure_setup
from node_b import http_probe
from protocol import sha256_file
from verify_live_two_process import req_json,wait_http
import config
HERE=Path(__file__).resolve().parent

def free_port():
 with socket.socket() as s:
  s.bind(('127.0.0.1',0));return s.getsockname()[1]

def main():
 files=[config.CHECKPOINT,config.CHECKPOINT.with_suffix('.onnx'),config.WINDOWS]
 before={str(p):sha256_file(p) for p in files};results=[]
 (HERE/'runtime').mkdir(exist_ok=True)
 for mode in ('expiry','kill-switch'):
  with tempfile.TemporaryDirectory(dir=HERE/'runtime',prefix='autonomous-check-',ignore_cleanup_errors=True) as td:
   root=Path(td);ensure_setup(runtime_dir=root)
   b,a,lab=free_port(),free_port(),free_port()
   env=dict(os.environ,CYBERNCM_DEMO_RUNTIME=str(root),CYBERNCM_NODE_B_PORT=str(b),CYBERNCM_NODE_A_PORT=str(a),CYBERNCM_LAB_PORT=str(lab),CYBERNCM_AUTONOMOUS_LAB='1')
   processes=[];logs=[]
   try:
    log=(root/'b.log').open('w');logs.append(log)
    processes.append(subprocess.Popen([sys.executable,str(HERE/'node_b.py')],cwd=HERE,env=env,stdout=log,stderr=subprocess.STDOUT))
    base=f'http://127.0.0.1:{b}'
    assert wait_http(base+'/health') and processes[0].poll() is None
    assert http_probe(config.LAB_CLIENT,port=lab)['ok']
    log=(root/'a.log').open('w');logs.append(log)
    processes.append(subprocess.Popen([sys.executable,str(HERE/'node_a.py'),'--speed','1000','--autostart'],cwd=HERE,env=env,stdout=log,stderr=subprocess.STDOUT))
    deadline=time.monotonic()+30
    state={}
    while time.monotonic()<deadline:
     _,state=req_json(base+'/api/state')
     if state['node_b']['active_blocks']:break
     time.sleep(.1)
    block=state['node_b']['active_blocks'][0]
    assert block['approval_mode']=='autonomous-lab' and block['ttl']<=10
    assert not http_probe(config.LAB_CLIENT,port=lab)['ok']
    assert http_probe(config.CONTROL_CLIENT,port=lab)['ok']
    if mode=='kill-switch':
     assert req_json(base+'/api/autonomy/disable','POST',{})[0]==403
     assert req_json(base+'/api/autonomy/disable','POST',{},headers={config.OPERATOR_HEADER:'1'})[0]==200
    else:
     deadline=time.monotonic()+12
     while time.monotonic()<deadline:
      _,state=req_json(base+'/api/state')
      if not state['node_b']['active_blocks']:break
      time.sleep(.2)
    assert http_probe(config.LAB_CLIENT,port=lab)['ok']
    time.sleep(1)
    _,state=req_json(base+'/api/state')
    assert not state['node_b']['active_blocks']
    assert len([e for e in state['node_b']['enforcer_events'] if e['type']=='block_applied'])==1
    if mode=='kill-switch':assert not state['node_b']['autonomous_lab']
    results.append(dict(scenario=mode,real_detector=True,block_without_approval=True,ttl=block['ttl'],lab_failed=True,control_succeeded=True,recovered=True,no_automatic_reblock=True))
   finally:
    for p in processes:
     if p.poll() is None:p.terminate()
    for p in processes:
     try:p.wait(timeout=5)
     except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
    for f in logs:f.close()
 after={str(p):sha256_file(p) for p in files};assert before==after
 result=dict(scenarios=results,files_unchanged=True,sha256=before,scope='Opt-in loopback lab gate only; recorded FP32 detector. No independent sensing, kernel firewall, or G1 approval.')
 (HERE/'runtime/autonomous_verification.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
