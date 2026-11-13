"""PR34 report completeness regression tests; no training or cloud dependencies."""
from pathlib import Path
import json,subprocess,sys,tempfile,unittest
SCRIPT=Path(__file__).with_name('r6e_decide.py')
DATASETS=('cic2017','unsw','d2018','unraveled','cicapt')
class DecisionTests(unittest.TestCase):
 def run_case(self,mode):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);rd=root/'runs';sd=root/'score';rd.mkdir();sd.mkdir();out=root/'report.md';out.write_text('OLD VERDICT')
   if mode!='empty':
    def value(seed):return {'seed':seed,'models':{'v0 NCM, smoothed':{sp:{'family_mean_auc':.8} for sp in ('dev','final')}}}
    for ds in DATASETS:
     for seed in range(5):(sd/f'{ds}_s{seed}.json').write_text(json.dumps(value(seed)))
     for candidate in ('tf','gru_masked'):
      (rd/candidate).mkdir(exist_ok=True)
      for seed in range(3):(rd/candidate/f'{ds}_s{seed}.json').write_text(json.dumps(value(seed)))
     (rd/f'ensemble_{ds}.json').write_text(json.dumps({'dataset':ds,'leave_one_out':{sp:[.8]*5 for sp in ('dev','final')}}))
    if mode=='missing':(rd/'tf/cicapt_s2.json').unlink()
    if mode=='metadata':(rd/'tf/cicapt_s2.json').write_text(json.dumps(value(9)))
   r=subprocess.run([sys.executable,str(SCRIPT),str(rd),str(sd),str(out)],capture_output=True,text=True)
   return r.returncode,out.read_text()
 def test_complete(self):
  code,text=self.run_case('complete');self.assertEqual(code,0);self.assertIn('Candidates that pass: none',text)
 def test_incomplete_no_conclusion(self):
  for mode in ('empty','missing','metadata'):
   with self.subTest(mode=mode):
    code,text=self.run_case(mode);self.assertNotEqual(code,0);self.assertIn('INCOMPLETE',text);self.assertNotIn('Candidates that pass',text)
if __name__=='__main__':unittest.main()
