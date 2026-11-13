import argparse,json,sys
from pathlib import Path
import numpy as np,torch
from sklearn.metrics import roc_auc_score
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'ncm'))
from ncm import NCM,score,sequences,ewma
torch.set_num_threads(2)
parser=argparse.ArgumentParser();parser.add_argument('run_root',type=Path)
root=parser.parse_args().run_root
meta=json.loads((root/'reports/full_poison_metadata.json').read_text())
test=np.load(root/'data/cic2017/windows.npz')
keep=np.ones(len(test['X']),bool)
keep[meta['exclude_original_indices_from_evaluation']]=False
family=test['family_names'].tolist().index('Botnet')
results={}
def scores(m,z):
    seqs=sequences(z['day'],z['src'],z['t'])
    comp,_=score(m,z['X'].astype(np.float32),seqs)
    c=(comp-m.calib[:,0].numpy())/m.calib[:,1].numpy()
    return ewma(c[:,0]+c[:,1]+.5*(c[:,2]+c[:,3]),seqs)
for name,folder in [('clean','fresh'),('full_poison','full_poison')]:
    ck=torch.load(root/folder/'artifacts/ncm_gru64_s7.pt')
    m=NCM(h=ck['h'],arch=ck['arch']);m.load_state_dict(ck['state'],strict=False);m.eval()
    train=np.load(root/folder/'data/windows.npz')
    cal=(train['day']==0)&(train['t']>=ck['cut'])
    sc=scores(m,train)
    threshold=float(np.quantile(sc[cal],.99))
    sc_test=sc[:len(test['X'])]
    mask=keep & np.isin(test['day'],[3,4])
    pos=mask&(test['family']==family)
    benign=mask&(test['family']==0)
    binary=pos|benign
    results[name]={'threshold':threshold,'botnet_final_windows':int(pos.sum()),'botnet_detection':float((sc_test[pos]>threshold).mean()),'benign_window_false_alarm':float((sc_test[benign]>threshold).mean()),'botnet_auc':float(roc_auc_score(test['family'][binary]==family,sc_test[binary]))}
    print(name,results[name],flush=True)
results['scope']='Single seed and family; full backbone retrained; both use same held-out original rows with poison-source indices removed. Threshold uses complete calibration population including injected calibration rows.'
(root/'reports/full_poison_comparison.json').write_text(json.dumps(results,indent=2))
