"""Supplementary frozen-curve checks and original manifest verification."""
import hashlib
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'b1_cpop_jump_v2_20261031'
def read(name):return json.loads((SOURCE/name).read_text(encoding='utf-8'))

manifest=read('artifact_manifest.json')
bad=[]
for name,expected in manifest.items():
    p=SOURCE/name
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:bad.append(name)
assert not bad
truth={r['task_id']:r for r in read('evaluator/test.json')}
curves=read('outputs/test_curves.json')
d=dict(n=len(curves),v2_selected_jumps=0,both_predictions_within_05kw=0,
       truth_within_05kw=0,flipped_bins=0,better_task_curve=0,worse_task_curve=0,
       lower_penalized_objective=0)
for r in curves:
    a=np.array(r['results']['cpop']['prediction'])[15:45]
    b=np.array(r['results']['jump_1p0']['prediction'])[15:45]
    t=np.array(truth[r['task_id']]['true_reduction_kw'])[15:45]
    flipped=(a>=.15)!=(b>=.15)
    d['flipped_bins']+=int(flipped.sum())
    d['both_predictions_within_05kw']+=int(np.sum(flipped&(abs(a-.15)<=.05)&(abs(b-.15)<=.05)))
    d['truth_within_05kw']+=int(np.sum(flipped&(abs(t-.15)<=.05)))
    j=r['results']['jump_1p0']
    d['v2_selected_jumps']+=int(bool(j['jump_boundaries']))
    d['lower_penalized_objective']+=int(j['objective']<j['original_family_cost']-1e-7)
    da=np.mean((a-t)**2);db=np.mean((b-t)**2)
    d['better_task_curve']+=int(db<da-1e-12)
    d['worse_task_curve']+=int(db>da+1e-12)
d.update(original_manifest_files_checked=len(manifest),original_manifest_changed=bad,
    scope='Descriptive existing-test checks; objective values are model-dependent, not duration accuracy or significance.')
with (HERE/'supplement.json').open('x',encoding='utf-8') as h:json.dump(d,h,indent=2)
print(json.dumps(d))
