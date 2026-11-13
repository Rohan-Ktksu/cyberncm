import argparse,json
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser(description="Prepare the fixed seed-7 Botnet full-backbone sensitivity run")
parser.add_argument('source',type=Path)
parser.add_argument('run_root',type=Path)
args=parser.parse_args();source=args.source;root=args.run_root
(root/'full_poison/data').mkdir(parents=True,exist_ok=True)
(root/'reports').mkdir(parents=True,exist_ok=True)
with np.load(source) as z:
    data={k:z[k] for k in z.files}
mon=data['day']==0
family=data['family_names'].tolist().index('Botnet')
pool=np.flatnonzero((data['day']>0)&(data['family']==family))
rng=np.random.default_rng(7)
n=min(int(np.ceil(.005*mon.sum())),len(pool)//2)
pick=rng.choice(pool,n,replace=False)
times=rng.uniform(data['t'][mon].min(),data['t'][mon].max(),n)
for key in ('X','day','src','t','family'):
    extra=np.zeros(n,data[key].dtype) if key=='day' else times if key=='t' else data[key][pick]
    data[key]=np.concatenate([data[key],extra])
np.savez_compressed(root/'full_poison/data/windows.npz',**data)
cut=np.quantile(data['t'][data['day']==0],.8)
fit=(data['day']==0)&(data['t']<cut)
meta={'seed':7,'family':'Botnet','requested_poison_relative_to_original_day0':.005,'injected':n,'injected_fit':int(fit[-n:].sum()),'injected_calibration':int(n-fit[-n:].sum()),'exclude_original_indices_from_evaluation':pick.tolist(),'purpose':'one-family full-backbone poisoning sensitivity; not independent confirmation or original R7c reproduction'}
(root/'reports/full_poison_metadata.json').write_text(json.dumps(meta,indent=2))
print({k:v for k,v in meta.items() if not isinstance(v,list)})
