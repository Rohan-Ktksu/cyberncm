"""Reproduce the report from committed point estimates; optionally verify original Drive files."""
from pathlib import Path
import argparse,json,hashlib,tempfile,subprocess,sys
parser=argparse.ArgumentParser();parser.add_argument('--original-data',type=Path)
args=parser.parse_args();here=Path(__file__).resolve().parents[1]
bundle=json.loads((here/'results/report_inputs.json').read_text())
if args.original_data:
 for name,want in bundle['sha256'].items():
  assert hashlib.sha256((args.original_data/name).read_bytes()).hexdigest()==want,name
with tempfile.TemporaryDirectory(dir=here,prefix='report-check-') as td:
 root=Path(td).resolve();assert root.is_relative_to(here.resolve())
 for name,data in bundle['files'].items():
  target=(root/name).resolve();assert target.is_relative_to(root)
  target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(data))
 report=root/'out.md'
 subprocess.run([sys.executable,str(here/'code/r6e_decide.py'),str(root/'r6e'),str(root/'scoreboard'),str(report)],check=True,stdout=subprocess.DEVNULL)
 assert report.read_text()==(here/'results/report_verified.md').read_text()
print('PASS: all stored report inputs reproduce the committed decision table. Training not rerun.')
