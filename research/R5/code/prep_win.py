"""Run prep.py (CIC-IDS2017) with a different window length. Usage, from a folder `ncm/` that holds prep.py and the raw inputs: python prep_win.py SECONDS
Writes data/windows.npz as prep.py does; the `t` array is the window start in seconds."""
import sys
import prep
prep.W = float(sys.argv[1]); print("window length", prep.W, flush=True)
prep.main()
