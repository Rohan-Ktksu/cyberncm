"""Optional exact-array cache for rule-independent R12b site scores."""
import hashlib,json,os
from pathlib import Path
import numpy as np

def site_scores(directory,key,compute):
    if directory is None:
        values=compute();validate(*values);return (*values,False)
    root=Path(directory);root.mkdir(parents=True,exist_ok=True)
    encoded=json.dumps(key,sort_keys=True,separators=(',',':'))
    path=root/(hashlib.sha256(encoded.encode()).hexdigest()+'.npz')
    if path.exists():
        with np.load(path,allow_pickle=False) as z:
            if z['key'].item()!=encoded:raise ValueError('Score cache key mismatch')
            values=(z['scores'],z['calibration'],int(z['nfit']))
        validate(*values);return (*values,True)
    values=compute();validate(*values)
    tmp=path.with_suffix(f'.{os.getpid()}.tmp')
    with tmp.open('wb') as f:np.savez_compressed(f,key=np.array(encoded),scores=values[0],calibration=values[1],nfit=values[2])
    os.replace(tmp,path);return (*values,False)

def validate(scores,calibration,nfit):
    if scores.ndim!=1 or calibration.ndim!=1 or not len(scores) or not 0<len(calibration)<=len(scores) or not 0<nfit<=len(scores) or not np.isfinite(scores).all() or not np.isfinite(calibration).all():
        raise ValueError('Invalid site scores or calibration; no result/cache may be used')
