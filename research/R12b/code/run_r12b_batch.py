"""Rebuild six R12 site inputs, reproduce all 18 rule-zero controls, then finish 72 runs.
Usage: python run_r12b_batch.py DATA_ROOT OUTPUT_ROOT SOURCE_DIR
Run after other heavy jobs finish. Sources include historical prep scripts.
"""
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
import numpy as np
from r12_reference import check_rule_zero
base,root,sources=map(Path,sys.argv[1:4]);root.mkdir(parents=True,exist_ok=True)
results=root/'results';results.mkdir(exist_ok=True);cache=root/'score_cache';cache.mkdir(exist_ok=True)
env=dict(os.environ,NCM_THREADS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONUNBUFFERED='1',NCM_SCORE_CACHE_DIR=str(cache),PYTHONPATH=str(sources))
DS=('cic2017','d2018','unraveled');RULES=((2,3,.995),(5,6,.999),(12,12,.999),(12,12,.9999))

def state(phase,**extra):
 (root/'status.json').write_text(json.dumps(dict(phase=phase,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**extra),indent=2))

def run(command,log):
 (root/(log+'.command.json')).write_text(json.dumps(command,indent=2))
 with (root/(log+'.log')).open('w') as f:p=subprocess.run(command,env=env,stdout=f,stderr=subprocess.STDOUT)
 if p.returncode:raise RuntimeError(f'{log} exited {p.returncode}')

def link(source,target):
 if target.exists() or target.is_symlink():
  if target.resolve()!=source.resolve():raise ValueError(f'Conflicting input link: {target}')
 else:target.symlink_to(source,target_is_directory=source.is_dir())

def check_population(work,ds,k):
 with np.load(work/'data/windows.npz') as z,np.load(work/'data/pair_map.npz') as pm:
  day,ids,t=z['day'],z['src'],z['t'];sites=pm['site'][ids];src=pm['source'][ids]
  if set(np.unique(sites))!=set(range(k)):raise ValueError('Site population incomplete')
  if ds=='d2018':
   with np.load(base/ds/'windows.npz') as original:keep=np.isin(src,np.unique(original['src']))
   day,sites,t=day[keep],sites[keep],t[keep]
  got={}
  for j in range(k):
   mask=sites==j;mon=mask&(day==0);cut=np.quantile(t[mon],.8)
   got[str(j)]={'windows':int(mask.sum()),'day0_fit_windows':int((mon&(t<cut)).sum())}
 reference=json.loads((base/'r12'/f'{ds}_k{k}_s0.json').read_text())
 expected={j:{field:values[field] for field in ('windows','day0_fit_windows')} for j,values in reference['sites'].items()}
 (root/f'{ds}_k{k}_population.json').write_text(json.dumps({'observed':got,'historical':expected,'matches':got==expected},indent=2))
 if got!=expected:raise ValueError(f'{ds}/K={k}: reconstructed site populations differ from R12; no sweep verdict')

try:
 state('PREPARING')
 backup=Path('/content/drive/MyDrive/cyberncm/R2')
 # Historical Unraveled prep expects this absolute input path.
 unraveled=Path('/content/data/unraveled');unraveled.mkdir(parents=True,exist_ok=True)
 link(backup/'data/unraveled/flows',unraveled/'flows')
 site_dirs={};raw_files=[]
 raw_files+=list((base/'cic2017-raw').glob('*.csv'))+list((base/'cic2017-orig').glob('*.parquet'))
 raw_files+=list((backup/'datasets_backup/cse_cic_ids2018/flows_extracted').glob('d?.parquet'))
 raw_files+=list((backup/'data/unraveled/flows').rglob('*.csv'))
 if len(list((backup/'data/unraveled/flows').rglob('*.csv')))!=173:raise ValueError('Expected 173 Unraveled raw flow files')
 manifest={str(p):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(raw_files)}
 (root/'raw_input_manifest.json').write_text(json.dumps(manifest,indent=2))
 for ds in DS:
  for k in (2,4):
   state('PREPARING',dataset=ds,K=k)
   work=Path('/content/cyberncm-r12b-prep')/root.parent.name/root.name/f'{ds}_k{k}'/'ncm';work.mkdir(parents=True,exist_ok=True);(work/'data').mkdir(exist_ok=True)
   for name in ['prep.py','prep_site.py','prep_2018.py','prep_unraveled.py']:shutil.copy2(sources/name,work/name)
   if ds=='cic2017':
    for day in ['monday','tuesday','wednesday','thursday','friday']:link(base/'cic2017-raw'/(day+'.csv'),work/'data'/(day+'.csv'))
    link(base/'cic2017-orig',work/'data/orig')
   if ds=='d2018':link(backup/'datasets_backup/cse_cic_ids2018/flows_extracted',work.parent/'flows')
   script={'cic2017':'prep.py','d2018':'prep_2018.py','unraveled':'prep_unraveled.py'}[ds]
   cmd=[sys.executable,str(sources/'run_site_prep.py'),str(k),script]
   (root/f'prep_{ds}_k{k}.command.json').write_text(json.dumps(cmd,indent=2))
   with (root/f'prep_{ds}_k{k}.log').open('w') as f:p=subprocess.run(cmd,cwd=work,env=env,stdout=f,stderr=subprocess.STDOUT)
   if p.returncode:raise RuntimeError(f'Prep {ds}/K={k} exited {p.returncode}')
   saved=root/'prepared_sites'/f'{ds}_k{k}';saved.mkdir(parents=True,exist_ok=True)
   for name in ['windows.npz','pair_map.npz']:shutil.copy2(work/'data'/name,saved/name)
   check_population(work,ds,k);site_dirs[(ds,k)]=saved
 for rule in range(4):
  for ds in DS:
   for k in (2,4):
    for seed in range(3):
     name=f'{ds}_k{k}_r{rule}_s{seed}';state('RULE_ZERO_CONTROLS' if rule==0 else 'SWEEP',run=name)
     command=[sys.executable,str(sources/'r12b_sim.py'),str(site_dirs[(ds,k)]),str(base/'scoreboard/ckpt'/f'{ds}_s{seed}.pt'),str(results/(name+'.json')),str(seed),str(base/ds/'windows.npz') if ds=='d2018' else '-',*[str(x) for x in RULES[rule]]]
     run(command,name)
     if rule==0:check_rule_zero(json.loads((results/(name+'.json')).read_text()),json.loads((base/'r12'/f'{ds}_k{k}_s{seed}.json').read_text()))
 run([sys.executable,str(sources/'r12b_decide.py'),str(results),str(root/'report.md'),str(base/'r12')],'decision')
 state('COMPLETE',runs=72)
except Exception as exc:
 state('FAILED',error=str(exc));(root/'report.md').write_text('INCOMPLETE: '+str(exc)+'\nNo R12b verdict.\n');raise
