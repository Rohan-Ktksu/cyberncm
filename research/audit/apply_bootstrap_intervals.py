"""Patch only corrected seed-zero AUC intervals; preserve every point/range and FA interval.
Usage: python apply_bootstrap_intervals.py RESULTS CSV_IN MD_IN OUTPUT_DIR
"""
import csv,hashlib,io,json,re,sys
from pathlib import Path
results,csv_in,md_in,out=map(Path,sys.argv[1:5]);out.mkdir(parents=True,exist_ok=True)
DATASETS={'cic2017':'CIC-IDS2017','unsw':'UNSW-NB15','d2018':'CSE-CIC-IDS2018','unraveled':'Unraveled','cicapt':'CICAPT-IIoT'}
MODELS=('v0 NCM, smoothed','token distance, smoothed','isolation forest, smoothed');updates={};sources={}
for ds in DATASETS:
 p=results/f'{ds}_s0.json';d=json.loads(p.read_text(encoding='utf-8'))
 assert d['status']=='COMPLETE' and d['seed']==0 and d['inputs_unchanged']
 assert len(d['point_checks'])==6 and all(x['matches_3_decimals'] for x in d['point_checks'])
 assert set(d['models'])==set(MODELS)
 for model in MODELS:
  assert set(d['models'][model])=={'dev','final'}
  for split in ('dev','final'):
   b=d['models'][model][split]['bootstrap'];lo,hi=b['family_mean_auc_ci95'];assert b['B']==200 and 0<=lo<=hi<=1
   updates[(ds,model,split)]=(lo,hi)
 sources[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
with csv_in.open(newline='',encoding='utf-8') as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
original=[dict(r) for r in rows];changed=[]
for row in rows:
 key=(row['dataset'],row['model'],row['split'])
 if row['metric']=='family_mean_auc' and key in updates:
  lo,hi=updates[key];changed.append(dict(dataset=key[0],model=key[1],split=key[2],old=[row['boot95_lo_seed0'],row['boot95_hi_seed0']],new=[lo,hi]));row['boot95_lo_seed0']=repr(lo);row['boot95_hi_seed0']=repr(hi)
assert len(changed)==30 and len({(r['dataset'],r['model'],r['split']) for r in changed})==30
for before,after in zip(original,rows):assert {k:v for k,v in before.items() if k not in ('boot95_lo_seed0','boot95_hi_seed0')}=={k:v for k,v in after.items() if k not in ('boot95_lo_seed0','boot95_hi_seed0')}
text=md_in.read_text(encoding='utf-8');lines=text.splitlines(keepends=True);ds=None;md_keys=set()
for i,line in enumerate(lines):
 for key,name in DATASETS.items():
  if line.startswith('### '+name+' ('):ds=key
 if ds is None or not line.startswith('| '):continue
 cells=line.split('|')
 if len(cells)<7:continue
 key=(ds,cells[1].strip(),cells[2].strip())
 if key not in updates:continue
 lo,hi=updates[key];assert len(re.findall(r'\[[^\]]*\]',cells[3]))==1
 cells[3]=re.sub(r'\[[^\]]*\]',f'[{lo:.3f} to {hi:.3f}]',cells[3]);lines[i]='|'.join(cells);assert key not in md_keys;md_keys.add(key)
assert md_keys==set(updates)
with (out/'scoreboard.csv').open('w',newline='',encoding='utf-8') as f:writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
(out/'SCOREBOARD.md').write_text(''.join(lines),encoding='utf-8')
receipt={'scope':'Only 30 seed-zero family-mean AUC interval pairs updated. All historical point estimates, ranges, seed counts, FA intervals and family tables preserved.','source_sha256':sources,'input_csv_sha256':hashlib.sha256(csv_in.read_bytes()).hexdigest(),'input_md_sha256':hashlib.sha256(md_in.read_bytes()).hexdigest(),'changes':changed}
(out/'bootstrap_interval_changes.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('Validated 30 interval updates; historical point/range columns unchanged.')
