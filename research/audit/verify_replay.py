import json,hashlib,ipaddress
import numpy as np
from pathlib import Path
import stream
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
models=[Path('artifacts/ncm_gru64_s0.pt'),Path('artifacts/ncm_gru64_s0.onnx')]
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in models}
keys=[]
Original=stream.Emitter
class VerifiedEmitter(Original):
 def __init__(self,path):
  super().__init__(path);keys.append(self.key.public_key())
stream.Emitter=VerifiedEmitter
metrics = stream.main(str(models[0]),4)
rows=[json.loads(x) for x in Path('artifacts/directives_fri.jsonl').read_text().splitlines()]
for row in rows:
 stream.SCHEMA.validate(row)
 unsigned=dict(row);signature=bytes.fromhex(unsigned.pop('ed25519_signature'))
 keys[0].verify(signature,json.dumps(unsigned,sort_keys=True,separators=(',',':')).encode())
events=json.loads(Path('artifacts/demo_events_fri.json').read_text())
assert len(events)==len(rows)
assert [r['monotonic_seq'] for r in rows]==list(range(1,len(rows)+1))
after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in models}
assert before==after
# Independently reconstruct active quarantine coverage before each window's action.
z=np.load('data/windows.npz');mask=z['day']==4
src,t,fam=(z[k][mask] for k in ('src','t','family'))
covered=np.zeros(len(t),bool)
for subject in np.unique(src):
 starts=np.array(sorted(t.min()+event['t_ms']/1000 for row,event in zip(rows,events)
     if row['enforcement_action']['directive_type']=='OPTIMISTIC_QUARANTINE_DROP'
     and int(ipaddress.ip_address(row['enforcement_action']['src_cidr'].split('/')[0]))==int(subject)))
 if not len(starts):continue
 idx=np.flatnonzero(src==subject);previous=np.searchsorted(starts,t[idx],side='left')-1
 valid=previous>=0
 # Current replay emits a fixed TTL for every quarantine directive.
 assert all(row['enforcement_action']['ttl_seconds']==stream.TTL for row in rows)
 covered[idx[valid]]=t[idx[valid]] < starts[previous[valid]]+stream.TTL
assert int(covered[fam>0].sum())==metrics['attack_windows_covered']
assert int(covered[fam==0].sum())==metrics['benign_windows_covered']
result=dict(dataset='CIC-IDS2017 canonical Friday',seed=0,windows=len(t),coverage=metrics,coverage_reconstructed_from_events=True,directives=len(rows),events=len(events),all_schema_valid=True,all_signatures_verified=True,sequence_numbers_contiguous=True,model_files_unchanged=True,sha256=before,format='FP32',mode='offline replay; no network enforcement',limitations='Historical prototype checkpoint, not scoreboard seed-2. Full replay success does not establish deployment safety. Negative first-quarantine times are pre-attack alerts, not evidence of prediction.')
Path('verification.json').write_text(json.dumps(result,indent=2))
print('VERIFICATION',json.dumps(result))
