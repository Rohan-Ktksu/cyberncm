"""Run all Friday file orders using the specified preprocessing revision.
Usage: python friday_order_audit.py PREP_PY DATA_ROOT OUTPUT_JSON
Requires data/raw links prepared by rebuild_count_audit.py; run from that work folder.
"""
from pathlib import Path
import argparse,gc,glob,importlib.util,itertools,json
import numpy as np,pandas as pd
parser=argparse.ArgumentParser(description=__doc__)
for name in ('prep_py','data_root','output_json'): parser.add_argument(name,type=Path)
args=parser.parse_args()
spec=importlib.util.spec_from_file_location('audit_prep',args.prep_py.resolve())
prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)
work=Path.cwd();canonical=np.load(args.data_root/'cic2017'/'windows.npz')
raw=pd.read_csv(work/'data'/'friday.csv',usecols=list(prep.COLS)).rename(columns=prep.COLS)
original_glob=glob.glob
paths=original_glob('data/orig/Friday-*.parquet')
permutations=[]
for order in itertools.permutations(paths):
 prep.glob.glob=lambda pattern,order=order:list(order)
 recovered,rate=prep.recover_time(raw.copy(),'friday')
 keys=set(zip(recovered['src'].tolist(),np.floor(recovered['t'].to_numpy()/5)*5))
 old=set(zip(canonical['src'][canonical['day']==4].tolist(),canonical['t'][canonical['day']==4].tolist()))
 row=dict(order=[Path(p).name for p in order],friday_windows=len(keys),total_windows=int((canonical['day']!=4).sum())+len(keys),canonical_only_keys=len(old-keys),rebuilt_only_keys=len(keys-old))
 permutations.append(row);print(json.dumps(row),flush=True)
 del recovered;gc.collect()
prep.glob.glob=original_glob
args.output_json.write_text(json.dumps(permutations,indent=2))
print('ORDER_AUDIT_FINISHED')
