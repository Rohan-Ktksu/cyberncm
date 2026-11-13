"""Stream one day of CSECICIDS2018_improved.zip (authors' corrected flows) into flows/<name>.parquet, keeping only the
columns prep needs. Usage: python fetch_day.py <member.csv> <outname> [--until-attack] [--zip PATH]
--until-attack: stop at the first chunk that contains an attack label (benign-only training span).
--zip PATH: read a local copy of the zip instead of streaming it over HTTP."""
import io, sys, time, urllib.request, zipfile
import pandas as pd, pyarrow as pa, pyarrow.parquet as pq

U = "https://intrusion-detection.distrinet-research.be/CNS2022/Datasets/CSECICIDS2018_improved.zip"
member, out = sys.argv[1], sys.argv[2]
until = "--until-attack" in sys.argv
local = sys.argv[sys.argv.index("--zip") + 1] if "--zip" in sys.argv else None
KEEP = ["Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol", "Timestamp", "Flow Duration", "Total Fwd Packet",
        "Total Bwd packets", "Total Length of Fwd Packet", "Total Length of Bwd Packet", "Fwd Packet Length Max",
        "Flow IAT Mean", "Packet Length Mean", "FIN Flag Count", "SYN Flag Count", "RST Flag Count", "PSH Flag Count",
        "ACK Flag Count", "FWD Init Win Bytes", "Label"]


class Remote(io.RawIOBase):
    """Seekable file over HTTP range requests, with retries."""
    def __init__(s):
        s.pos, s.n = 0, int(urllib.request.urlopen(urllib.request.Request(U, method="HEAD")).headers["Content-Length"])
    def seekable(s): return True
    def readable(s): return True
    def tell(s): return s.pos
    def seek(s, o, w=0):
        s.pos = {0: o, 1: s.pos + o, 2: s.n + o}[w]
        return s.pos
    def readinto(s, b):
        k = min(len(b), s.n - s.pos)
        if k <= 0: return 0
        for attempt in range(8):
            try:
                r = urllib.request.Request(U, headers={"Range": f"bytes={s.pos}-{s.pos + k - 1}"})
                d = urllib.request.urlopen(r, timeout=60).read()
                break
            except Exception:
                time.sleep(2 * (attempt + 1))
        else:
            raise IOError("download failed")
        b[:len(d)] = d
        s.pos += len(d)
        return len(d)


z = zipfile.ZipFile(local or io.BufferedReader(Remote(), 8 << 20))
writer, rows = None, 0
with z.open(member) as f:
    for ch in pd.read_csv(f, usecols=KEEP, chunksize=500_000):
        if until and (ch["Label"] != "BENIGN").any():
            break
        # seconds since epoch, independent of the datetime unit (pandas 3 parses to microseconds, not nanoseconds)
        ch["t"] = (pd.to_datetime(ch["Timestamp"]) - pd.Timestamp("1970-01-01")) / pd.Timedelta(seconds=1)
        ch = ch.drop(columns="Timestamp")
        ch["Label"] = ch["Label"].astype(str)
        tb = pa.Table.from_pandas(ch, preserve_index=False)
        writer = writer or pq.ParquetWriter(f"flows/{out}.parquet", tb.schema)
        writer.write_table(tb)
        rows += len(ch)
        print(out, rows, flush=True)
writer.close()
print(out, "done", rows)
