"""Regression: reporting must include computed multi-day budgets and unknown dataset names."""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path
class BudgetReportTest(unittest.TestCase):
 def test_multiday_budget_in_report(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);rd=p/'runs';sd=p/'score';rd.mkdir();sd.mkdir()
   report={'dev':{'family_mean_auc':.9},'final':{'family_mean_auc':.89,'false_per_host_day_at_80pct_5min':1.}}
   names=['L1 threshold only']+[f'{level} @ {budget}' for level in ['L2 + target normalisation','L3 + target vocabularies and calibration'] for budget in ['10 min','1440 min','4320 min','full']]
   (rd/'cic2017_to_unraveled_s0.json').write_text(json.dumps({'models':{n:report for n in names}}))
   (sd/'unraveled_s0.json').write_text(json.dumps({'models':{'v0 NCM, smoothed':report}}))
   script=Path(__file__).resolve().parents[1]/'R11/code/r11_decide.py'
   r=subprocess.run([sys.executable,str(script),str(rd),str(sd),str(p/'out.md')],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr)
   output=(p/'out.md').read_text()
   self.assertIn('1440 min',output);self.assertIn('4320 min',output)
   self.assertNotIn('mean over 5 seeds',output)
if __name__=='__main__':unittest.main()
