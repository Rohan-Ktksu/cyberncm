"""Diagnose one stored FP32 outlier without re-exporting or changing model/data."""
import argparse,sys,json,hashlib,platform
from pathlib import Path
import numpy as np,torch,onnxruntime as ort
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'ncm'))
from ncm import sequences,nearest
from export import load,Step
p=argparse.ArgumentParser();p.add_argument('windows');p.add_argument('checkpoint');p.add_argument('onnx');p.add_argument('output');p.add_argument('--row',type=int,default=57227);a=p.parse_args()
torch.set_num_threads(2)
z=np.load(a.windows);X=z['X'].astype(np.float32);seqs=sequences(z['day'],z['src'],z['t']);idx=next(q for q in seqs if a.row in q);position=int(np.flatnonzero(idx==a.row)[0]);x=X[idx];m,_=load(a.checkpoint)
opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1;sess=ort.InferenceSession(a.onnx,opts,providers=['CPUExecutionProvider'])
with torch.no_grad():
 c,s=m(torch.from_numpy(x)[None]);ref=m.surprise(c)[0].numpy();norm=m.normalize(torch.from_numpy(x));tokens=nearest(norm,m.codebook)[1].numpy()
 h=np.zeros((m.layers,1,m.h),np.float32);hp=torch.zeros(m.layers,1,m.h);step=Step(m).eval();got=[];stream_tokens=[];step_scores=[];step_tokens=[];h_errors=[]
 for row in x:
  out=sess.run(None,{'x':row[None],'h':h});h=out[4];got.append(float(out[0][0]));stream_tokens.append(int(out[2][0]));pt=step(torch.from_numpy(row[None]),hp);hp=pt[4];step_scores.append(float(pt[0][0]));step_tokens.append(int(pt[2][0]));h_errors.append(float(np.abs(h-hp.numpy()).max()))
 i=position;v=norm[i];book=m.codebook
 direct=((v.double()[None]-book.double())**2).sum(-1);ordered=torch.argsort(direct)[:5]
 expanded=(v*v).sum()-2*v@book.T+(book*book).sum(-1)
 single_token=int(nearest(v[None],book)[1][0]);native_prev=torch.zeros_like(s[0,i]) if i==0 else s[0,i-1]
 ks={str(int(k)):float(-torch.log_softmax(m.tok(native_prev),-1)[int(k)]) for k in set([int(tokens[i]),stream_tokens[i],single_token,int(ordered[0])])}
 result={'scope':'One known outlier sequence only; not a full parity rerun or model fix.','environment':{'python':platform.python_version(),'torch':torch.__version__,'numpy':np.__version__,'ort':ort.__version__},'sha256':{name:hashlib.sha256(Path(getattr(a,name)).read_bytes()).hexdigest() for name in ['windows','checkpoint','onnx']},'row':a.row,'sequence_windows':len(idx),'sequence_position':i,'reference_score':float(ref[i]),'onnx_score':got[i],'pytorch_step_score':step_scores[i],'token':{'pytorch_sequence':int(tokens[i]),'onnx_step':stream_tokens[i],'pytorch_single':single_token,'pytorch_step':step_tokens[i],'float64_direct':int(ordered[0])},'nearest_float64_squared_distances':[{'token':int(k),'distance':float(direct[k]),'single_expanded_float32':float(expanded[k])} for k in ordered],'token_negative_log_probability_native_previous_state':ks,'k_calibration_std':float(m.calib[3,1]),'onnx_vs_pytorch_step_hidden_max_at_row':h_errors[i],'sequence_max_raw_difference':float(np.max(np.abs(np.asarray(got)-ref))),'sequence_token_disagreements':int((np.asarray(stream_tokens)!=tokens).sum())}
ks=result['token_negative_log_probability_native_previous_state'];pred=.5*(ks[str(result['token']['onnx_step'])]-ks[str(result['token']['pytorch_sequence'])])/result['k_calibration_std']
result.update(token_term_predicted_score_change=pred,observed_score_change=result['onnx_score']-result['reference_score'],score_change_residual=result['onnx_score']-result['reference_score']-pred)
Path(a.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
