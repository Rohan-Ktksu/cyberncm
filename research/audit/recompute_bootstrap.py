"""Recompute seed-zero scoreboard source-bootstrap intervals; preserve historical files.
Usage: python recompute_bootstrap.py WINDOWS CHECKPOINT ORIGINAL_RESULT OUTPUT
"""
import argparse,hashlib,json,os,platform,time
from pathlib import Path
import numpy as np,torch
from sklearn.ensemble import IsolationForest
import scoreboard as SB
from ncm import NCM,score,sequences,ewma

def main():
 p=argparse.ArgumentParser();p.add_argument('windows',type=Path);p.add_argument('checkpoint',type=Path);p.add_argument('original',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 torch.set_num_threads(int(os.environ.get('NCM_THREADS','1')))
 inputs={k:hashlib.sha256(getattr(a,k).read_bytes()).hexdigest() for k in ['windows','checkpoint','original']}
 old=json.loads(a.original.read_text());assert old['seed']==0
 d=SB.load(a.windows);d['fam']=d['family'];X=d['X'];ck=torch.load(a.checkpoint);m=NCM(h=ck['h'],arch=ck['arch']);m.load_state_dict(ck['state'],strict=True)
 seqs=sequences(d['day'],d['src'],d['t']);comp,_=score(m,X,seqs);cal=(d['day']==0)&(d['t']>=ck['cut']);train=(d['day']==0)&(d['t']<ck['cut']);c=(comp-comp[cal].mean(0))/comp[cal].std(0)
 zn=m.normalize(torch.from_numpy(X)).numpy();iso=-IsolationForest(n_estimators=200,random_state=0).fit(zn[train]).score_samples(zn)
 models={'v0 NCM, smoothed':ewma(c[:,0]+c[:,1]+.5*(c[:,2]+c[:,3]),seqs),'token distance, smoothed':ewma(c[:,0],seqs),'isolation forest, smoothed':ewma(iso,seqs)}
 sps={k:SB.Split(d,v) for k,v in d['splits'].items()};rng=np.random.default_rng(0)
 out={'status':'RUNNING','seed':0,'input_sha256':inputs,'environment':{'python':platform.python_version(),'torch':torch.__version__,'numpy':np.__version__},'models':{},'point_checks':[],'note':'Author rerun. Same 200 source resamples and RNG order as scoreboard; weighted AUC credits ties. Historical point estimates remain unchanged.'}
 def save():
  tmp=a.output.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2)+'\n');os.replace(tmp,a.output)
 for name,sc in models.items():
  assert np.isfinite(sc).all(),name
  out['models'][name]={};thr=float(np.quantile(sc[cal],.99))
  for split,sp in sps.items():
   original=old['models'][name][split];B=original['bootstrap']['B'];assert B==200
   point=SB.report(sp,sc,d['names'],thr);expected=original['family_mean_auc'];got=point['family_mean_auc'];matches=round(got,3)==round(expected,3)
   out['point_checks'].append({'model':name,'split':split,'original_family_mean_auc':expected,'recomputed_family_mean_auc':got,'matches_3_decimals':matches})
   if not matches:out['status']='POINT_MISMATCH';save();raise ValueError('Point estimate mismatch: '+name+'/'+split)
   print('BOOTSTRAP_START',name,split,B,flush=True);point['bootstrap']=SB.bootstrap(sp,sc,B,rng);out['models'][name][split]=point;save();print('BOOTSTRAP_DONE',name,split,point['bootstrap'],flush=True)
 assert inputs=={k:hashlib.sha256(getattr(a,k).read_bytes()).hexdigest() for k in inputs}
 out['status']='COMPLETE';out['inputs_unchanged']=True;save();print('COMPLETE',a.output,flush=True)
if __name__=='__main__':main()
