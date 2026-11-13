"""R6e runner: train a candidate (tf = Transformer backbone, gru_masked = GRU with the masked-history objective) and evaluate it with the scoreboard harness.
Usage: python r6e_run.py "[(cand, dataset, seed), ...]" TAG  -- results in DD/r6e/<cand>/<dataset>_s<seed>.json (scoreboard format), checkpoints beside them."""
import ast, os, shutil, subprocess, sys, time
DD = '/content/drive/MyDrive/cyberncm-data'; R = '/content/cyberncm'; JOBS = ast.literal_eval(sys.argv[1]); tag = sys.argv[2]
if not isinstance(JOBS,list) or any(not isinstance(job,(tuple,list)) or len(job)!=3 or job[0] not in ("tf","gru_masked") or job[1] not in ("cic2017","unsw","d2018","unraveled","cicapt") or type(job[2]) is not int or job[2] not in range(3) for job in JOBS):
    raise ValueError("Expected candidate/dataset/seed jobs from the declared protocol")
env = dict(os.environ, PYTHONPATH='/content/pinned', PYTHONWARNINGS='ignore', NCM_THREADS='4', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
def log(m):
    os.makedirs(f'{DD}/r6e', exist_ok=True)
    with open(f'{DD}/r6e/run.log', 'a') as f: f.write(time.strftime('%H:%M:%S ') + f'[{tag}] ' + m + '\n')
def run(cmd, cwd, what):
    t = time.time(); r = subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True)
    log(f'{what}: rc={r.returncode} {time.time()-t:.0f}s' + ('' if r.returncode == 0 else ' | ' + (r.stdout + r.stderr)[-500:].replace('\n', ' | '))); return r
for cand, ds, s in JOBS:
    out = f'{DD}/r6e/{cand}/{ds}_s{s}.json'; os.makedirs(f'{DD}/r6e/{cand}', exist_ok=True)
    if os.path.exists(out): continue
    Wd = f'/content/r6e/{cand}_{ds}/ncm'
    if not os.path.exists(Wd):
        os.makedirs(os.path.dirname(Wd), exist_ok=True); shutil.copytree(f'{R}/ncm', Wd, ignore=shutil.ignore_patterns('__pycache__', 'artifacts', 'data')); os.makedirs(f'{Wd}/artifacts', exist_ok=True); os.symlink(f'{DD}/{ds}', f'{Wd}/data')
        shutil.copy('/content/r6ecode/train_masked.py', f'{Wd}/train_masked.py')
    ck = f'{Wd}/artifacts/ncm_{"tf64" if cand == "tf" else "gru64m"}_s{s}.pt'
    if not os.path.exists(ck):
        r = run(f'python {"train.py tf 64" if cand == "tf" else "train_masked.py gru 64"} {s}', Wd, f'{cand} {ds} s{s} train')
        if r.returncode or not os.path.exists(ck): continue
        shutil.copy(ck, f'{DD}/r6e/{cand}/ckpt_{ds}_s{s}.pt')
    r = run(f'python scoreboard.py {ck} artifacts/sb_{cand}_s{s}.json --seed {s} --no-rf', Wd, f'{cand} {ds} s{s} eval')
    if r.returncode == 0: shutil.copy(f'{Wd}/artifacts/sb_{cand}_s{s}.json', out)
log('GROUP DONE')
