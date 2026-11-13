"""R9: cost of v0 on a single pinned CPU core (a labelled SUBSTITUTE for an edge board).
Usage (from a folder where `ncm.py` and `export.py` import, i.e. a copy of ncm/): taskset -c 0 python r9_bench.py CKPT WINDOWS_NPZ OUT.json
Exports the streaming step to ONNX (FP32), quantizes to INT8 (as export.py), then measures on one thread:
size, latency per batch (1, 8, 64, 512 sources; median, p95, p99 over 2000 runs after 200 warm-up runs), peak resident memory,
and parity: ONNX FP32 against PyTorch, INT8 against FP32 (surprise correlation and difference in smoothed AUC, attack vs benign on the test days)."""
import json, os, resource, sys, time
import numpy as np, onnxruntime as ort, torch
from sklearn.metrics import roc_auc_score
from export import Step, load, stream
from ncm import ewma, score, sequences
from onnxruntime.quantization import QuantType, quantize_dynamic

CK, WIN, OUT = sys.argv[1:4]; torch.set_num_threads(1)
m, ck = load(CK); fp32, int8 = OUT.replace(".json", ".fp32.onnx"), OUT.replace(".json", ".int8.onnx")
torch.onnx.export(Step(m), (torch.zeros(2, m.d), torch.zeros(m.layers, 2, m.h)), fp32, input_names=["x", "h"], dynamo=False, opset_version=17,
                  output_names=["surprise", "stage_probs", "token", "next_token", "h_out"], dynamic_axes={"x": {0: "B"}, "h": {1: "B"}})
quantize_dynamic(fp32, int8, weight_type=QuantType.QInt8)
z = np.load(WIN, allow_pickle=True); X, day, src, t, fam = z["X"].astype(np.float32), z["day"], z["src"], z["t"], z["family"]; seqs = sequences(day, src, t); te = day > 0
opts = ort.SessionOptions(); opts.intra_op_num_threads = 1; opts.inter_op_num_threads = 1
res = {"cpu": [l.split(":")[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")][0], "affinity": sorted(os.sched_getaffinity(0)), "parameters": int(sum(p.numel() for p in m.parameters())),
       "hidden_state_bytes_per_source": int(m.layers * m.h * 4), "models": {}}
raw = {}
for name, path in (("FP32", fp32), ("INT8", int8)):
    sess = ort.InferenceSession(path, opts); r = {"size_kb": os.path.getsize(path) / 1024, "latency_ms": {}}
    for B in (1, 8, 64, 512):
        xb, hb = X[:B], np.zeros((m.layers, B, m.h), np.float32)
        for _ in range(200): sess.run(None, {"x": xb, "h": hb})
        ts = []
        for _ in range(2000):
            t0 = time.perf_counter(); sess.run(None, {"x": xb, "h": hb}); ts.append((time.perf_counter() - t0) * 1e3)
        r["latency_ms"][str(B)] = {"median": float(np.median(ts)), "p95": float(np.percentile(ts, 95)), "p99": float(np.percentile(ts, 99))}
    raw[name] = stream(sess, m, X, seqs); sm = ewma(raw[name], seqs); r["auc_attack_vs_benign_test_days"] = float(roc_auc_score(fam[te] > 0, sm[te]))
    res["models"][name] = r
with torch.no_grad(): ref = m.surprise(torch.from_numpy(score(m, X, seqs)[0])).numpy()
res["onnx_fp32_vs_pytorch_max_abs_diff"] = float(np.abs(ref - raw["FP32"]).max())
res["int8_vs_fp32_surprise_corr"] = float(np.corrcoef(raw["FP32"], raw["INT8"])[0, 1])
res["int8_minus_fp32_auc"] = res["models"]["INT8"]["auc_attack_vs_benign_test_days"] - res["models"]["FP32"]["auc_attack_vs_benign_test_days"]
res["peak_rss_mb_whole_process_including_dataset"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
json.dump(res, open(OUT, "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "models"}, indent=1)); print({n: {"kb": round(v["size_kb"]), "ms64": v["latency_ms"]["64"], "auc": round(v["auc_attack_vs_benign_test_days"], 4)} for n, v in res["models"].items()})
