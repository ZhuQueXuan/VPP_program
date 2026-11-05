from common import *
from model import current_baseline
P=ROOT/'work/b1_effective_gate_20261102';checks=0
for stage in ['main_test','weak_test']:
    cases=read(P/stage/'facts.json');curves={r['task_id']:r['results'] for r in read(P/stage/'curves.json')};b,m,X=current_baseline(cases,curves)
    old={r['task_id']:r for r in read(P/stage/'metrics.json') if r['method']=='candidate'};oldX=np.load(P/stage/'effective_X.npy')
    assert np.array_equal(X[:,:426],oldX)
    for i,c in enumerate(cases):
        r=old[c['task_id']];assert np.allclose(b[i],[r['predicted_cumulative_seconds'],r['predicted_longest_seconds']],rtol=0,atol=1e-8)
        if r['rejected']:assert not m[i].any()
        checks+=1
write('baseline_replay.json',dict(old_tasks_exact=checks,old426_descriptors_exact=True,previous_qualification_preserved=True))
print('Previous adopted baseline replay exact',checks,flush=True)
