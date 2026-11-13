"""Audit stored ONNX exports against their matching PyTorch checkpoint; no re-export."""
import argparse,hashlib,json,platform
from pathlib import Path
import numpy as np,torch,onnxruntime as ort
from sklearn.metrics import roc_auc_score
from export import load,stream
from ncm import score,sequences,ewma
p=argparse.ArgumentParser()
for name in ('windows','checkpoint','fp32','int8','output'):p.add_argument(name,type=Path)
a=p.parse_args();torch.set_num_threads(2)
m,ck=load(str(a.checkpoint))
z=np.load(a.windows);X=z['X'].astype(np.float32);day,src,t,fam=(z[k] for k in ('day','src','t','family'))
seqs=sequences(day,src,t)
with torch.no_grad():ref=m.surprise(torch.from_numpy(score(m,X,seqs)[0])).numpy()
smref=ewma(ref,seqs);te=day>0;cal=(day==0)&(t>=np.quantile(t[day==0],.8))
threshold=float(np.quantile(smref[cal],.99))
result=dict(environment=dict(python=platform.python_version(),numpy=np.__version__,torch=torch.__version__,ort=ort.__version__),sha256={k:hashlib.sha256(getattr(a,k).read_bytes()).hexdigest() for k in ('windows','checkpoint','fp32','int8')},reference_auc=float(roc_auc_score(fam[te]>0,smref[te])),reference_threshold=threshold,models={})
raw={}
opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
for name,path in [('FP32',a.fp32),('INT8',a.int8)]:
 sess=ort.InferenceSession(str(path),opts,providers=['CPUExecutionProvider'])
 got=stream(sess,m,X,seqs);raw[name]=got;sm=ewma(got,seqs)
 diff=np.abs(got-ref);rel=diff/np.maximum(np.abs(ref),1)
 worst=int(np.argmax(diff))
 result['models'][name]=dict(finite=bool(np.isfinite(got).all()),max_abs_difference=float(diff.max()),abs_difference_quantiles=np.quantile(diff,[.5,.95,.99,.999]).tolist(),max_relative_difference_scale_floor_1=float(rel.max()),worst_row=worst,reference_at_worst=float(ref[worst]),onnx_at_worst=float(got[worst]),correlation=float(np.corrcoef(ref,got)[0,1]),auc=float(roc_auc_score(fam[te]>0,sm[te])),threshold_alarm_disagreements_test=int(((sm[te]>threshold)!=(smref[te]>threshold)).sum()),test_windows=int(te.sum()))
 print(name,json.dumps(result['models'][name]),flush=True)
result['int8_vs_fp32_correlation']=float(np.corrcoef(raw['FP32'],raw['INT8'])[0,1])
result['int8_minus_fp32_auc']=result['models']['INT8']['auc']-result['models']['FP32']['auc']
a.output.write_text(json.dumps(result,indent=2))
print('PARITY_AUDIT_FINISHED',flush=True)

