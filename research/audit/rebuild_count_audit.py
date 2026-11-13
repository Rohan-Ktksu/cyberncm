"""Rebuild daily CIC windows in an isolated work folder, preserving canonical data.
Usage: python rebuild_count_audit.py PREP_PY DATA_ROOT WORK_DIR OUTPUT_DIR
PREP_PY may be an explicitly extracted historical revision; its SHA is recorded.
"""
from pathlib import Path
import argparse,gc,hashlib,importlib.util,json,os
import numpy as np,pandas as pd
parser=argparse.ArgumentParser(description=__doc__)
for name in ('prep_py','data_root','work_dir','output_dir'): parser.add_argument(name,type=Path)
args=parser.parse_args()
prep_path=args.prep_py.resolve();base=args.data_root.resolve()
work=args.work_dir.resolve();out=args.output_dir.resolve()
work.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
(work/'data').mkdir(exist_ok=True)
for day in ['monday','tuesday','wednesday','thursday','friday']:
 p=work/'data'/f'{day}.csv'
 if not p.exists(): p.symlink_to(base/'cic2017-raw'/f'{day}.csv')
p=work/'data'/'orig'
if not p.exists(): p.symlink_to(base/'cic2017-orig',target_is_directory=True)
os.chdir(work)
spec=importlib.util.spec_from_file_location('audit_prep',prep_path)
prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)
canonical=np.load(base/'cic2017'/'windows.npz')
rows=[]
for di,day in enumerate(prep.DAYS):
 print('START',day,flush=True)
 df=pd.read_csv(work/'data'/f'{day}.csv',usecols=list(prep.COLS)).rename(columns=prep.COLS)
 nraw=len(df);df,rate=prep.recover_time(df,day)
 df['family']=df['label'].str.replace(' - Attempted','',regex=False)
 X,src,t,fam=prep.windows(df)
 old=set(zip(canonical['src'][canonical['day']==di].tolist(),canonical['t'][canonical['day']==di].tolist()))
 new=set(zip(src.tolist(),t.tolist()))
 row=dict(day=day,raw_flows=nraw,kept_flows=len(df),rebuilt_windows=len(X),canonical_windows=len(old),canonical_only_keys=len(old-new),rebuilt_only_keys=len(new-old),exact_hour_match_fraction=float(rate))
 rows.append(row);print(json.dumps(row),flush=True)
 np.savez_compressed(out/f'count_audit_{day}.npz',X=X,src=src,t=t,family=fam.astype(str))
 (out/'count_audit.json').write_text(json.dumps(dict(pandas=pd.__version__,numpy=np.__version__,prep_sha256=hashlib.sha256(prep_path.read_bytes()).hexdigest(),rows=rows,scope='Diagnostic rebuild; historical environment and source must be compared explicitly'),indent=2))
 del df,X,src,t,fam;gc.collect()
print('AUDIT_FINISHED',sum(r['rebuilt_windows'] for r in rows),flush=True)
