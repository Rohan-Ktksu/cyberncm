"""Run historical site preprocessing with the measured canonical Friday file order.
This is a reconstruction candidate, accepted only after historical R12 checks.
"""
import glob,runpy,sys
from pathlib import Path
original=glob.glob
FRIDAY=['Friday-WorkingHours-Morning.pcap_ISCX.csv.parquet','Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv.parquet','Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv.parquet']
def ordered(pattern,*args,**kwargs):
 files=original(pattern,*args,**kwargs)
 if str(pattern).endswith('Friday-*.parquet'):
  if {Path(p).name for p in files}!=set(FRIDAY):raise ValueError('Unexpected Friday original input set')
  files=sorted(files,key=lambda p:FRIDAY.index(Path(p).name))
  print('Explicit Friday input order:',files,flush=True)
 return files
glob.glob=ordered
# sys.argv: wrapper K prep.py|prep_2018.py|prep_unraveled.py
sys.argv[0]='prep_site.py'
runpy.run_path(str(Path.cwd()/'prep_site.py'),run_name='__main__')
