"""Two-worker CPU batch for the five declared seed-zero bootstrap reruns."""
import concurrent.futures,json,os,subprocess,sys,time
from pathlib import Path
base,root=map(Path,sys.argv[1:3]);sources=Path(__file__).resolve().parent

def run(ds):
 command=[sys.executable,str(sources/'recompute_bootstrap.py'),str(base/ds/'windows.npz'),str(base/'scoreboard/ckpt'/f'{ds}_s0.pt'),str(base/'scoreboard'/f'{ds}_s0.json'),str(root/f'{ds}_s0.json')]
 (root/f'{ds}_command.json').write_text(json.dumps(command,indent=2))
 env=dict(os.environ,NCM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONUNBUFFERED='1')
 started=time.time()
 with (root/f'{ds}.log').open('w') as log:code=subprocess.call(command,cwd=sources,env=env,stdout=log,stderr=subprocess.STDOUT)
 result={'dataset':ds,'exit_code':code,'elapsed_seconds':time.time()-started};(root/f'{ds}_status.json').write_text(json.dumps(result,indent=2));return result
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 results=list(pool.map(run,['cic2017','unsw','d2018','unraveled','cicapt']))
(root/'batch_status.json').write_text(json.dumps(results,indent=2));sys.exit(int(any(r['exit_code']!=0 for r in results)))
