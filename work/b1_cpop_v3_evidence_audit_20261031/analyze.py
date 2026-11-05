"""Read saved v3 evidence only. No estimator, simulation or tuning is run."""
import hashlib,json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
V3=ROOT/'work/b1_cpop_fine_v3_20261031'
OLD=ROOT/'work/b1_command_feature_selection_20261031'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

freeze=read(V3/'validation_freeze.json');method=freeze['method']
facts=read(V3/'facts/test.json');truth={r['task_id']:r for r in read(V3/'evaluator/test.json')}
curves={r['task_id']:r for r in read(V3/'outputs/test_curves.json')}
cases=[]
for c in facts:
    if c['kind']!='one_finebin_response':continue
    clean=np.asarray(truth[c['task_id']]['true_reduction_kw']);ix=np.flatnonzero(clean>=.15)
    assert len(ix)==1
    i=int(ix[0]);r=curves[c['task_id']]['results'];info=r[method]['fine_evidence']
    raw=np.asarray(c['reference_kw'])-np.asarray(c['power_kw'])
    left,right=raw[i-2:i],raw[i+1:i+3];center=float((np.median(left)+np.median(right))/2)
    cases.append(dict(task_id=c['task_id'],base_task_id=c['base_task_id'],condition=c['condition'],
        time_seconds=c['starts_s'][i],index=i,true_kw=float(clean[i]),raw_kw=float(raw[i]),
        cpop_kw=r['cpop']['prediction'][i],v3_kw=r[method]['prediction'][i],replacement_kw=center,
        explicitly_replaced=i in info['flagged_indices'],command_protected=i in info['protected_indices']))
assert len(cases)==36 and all(c['explicitly_replaced'] and not c['command_protected'] for c in cases)
real=read(OLD/'real_cases.json')
windows=sorted(set((min(c['starts_s']),max(c['ends_s'])) for c in real))
manifest=read(V3/'completion_receipt.json')['file_sha256']
changed=[p for p,h in manifest.items() if not (V3/p).is_file() or sha(V3/p)!=h]
assert not changed
paths=[V3/p for p in ['candidate.py','run_real.py','simulation.py','controls.py','controls_receipt.json','fine_data_audit.json']]
result=dict(scope='Analysis only; no new fits, observations or parameter selection',
    cause='Pre-CPOP replacement of isolated samples; duration rule is downstream, not cause of the new10s pulse erasure.',
    affected_paired_inputs=len(cases),affected_base_tasks=len({c['base_task_id'] for c in cases}),
    all36_true_pulses_explicitly_replaced=True,all36_outside_command_guard=True,
    simulated_grid_seconds=10.,real_grid_seconds=.1,
    real_100ms_used_to_decide_simulated10s_pulses=False,
    original_21ms_used_in_candidate_decisions=False,
    command_usage='Only changes guard +/-1 observed sample; no response-delay, tracking, reversal or action-consistency inference.',
    real_window_seconds=windows,real_events=len(real),real_fault_labels=False,real_clean_truth=False,
    original_v3_manifest_files_unchanged=len(manifest),source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in paths},
    true_short_cases=cases)
with (HERE/'evidence.json').open('x',encoding='utf-8') as h:json.dump(result,h,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in result.items() if k not in ['true_short_cases','source_sha256']}))
print(json.dumps(cases[:1]))
