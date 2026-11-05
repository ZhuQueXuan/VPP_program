"""Read-only evaluator audit of default template constraint violations."""
from pathlib import Path
import json
import numpy as np
HERE=Path(__file__).resolve().parent;STUDY=HERE.parents[1]/'b1_ev_mainline_20261030'
def main():
    target=HERE/'truth_constraint_counts.json'
    if target.exists():raise RuntimeError('receipt already exists')
    rows=[]
    for scenario in ('positive','zero'):
        n=responded=exceed=idle=multiple_runs=0;shapes={}
        for seed in range(5312100,5312108):
            values=json.loads((STUDY/f'evaluator/{seed}_{scenario}_truth.json').read_text(encoding='utf-8'))
            for row in values:
                n+=1;s=np.array(row['relative_starts_min']);r=np.array(row['true_reduction_kw']);q=row['q_kw'];W=row['W_min']
                req=(s>=0)&(s<W);post=s>=W
                yes=r[req]>=.1*q;active=bool(yes.any());responded+=int(active)
                if active:shapes[row['latent']['shape']]=shapes.get(row['latent']['shape'],0)+1
                exceed+=int(np.any(r[post]<-q-1e-12))
                positive=np.flatnonzero(r[req]>1e-12)
                idle+=int(bool(len(positive)) and positive[-1] < int(W)-1)
                transitions=int(np.sum(yes & np.r_[True,~yes[:-1]]))
                multiple_runs+=int(transitions>=2)
        rows.append(dict(scenario=scenario,events=n,true_response=responded,
            post_interval_rebound_exceeds_default_q=exceed,
            full_minute_terminal_idle_before_rebound=idle,
            two_or_more_task_threshold_runs=multiple_runs,shape_among_responders=shapes))
    result=dict(evaluator_only=True,model_fits=0,production_modified=False,counts=rows,
        limits='Terminal idle count only detects >=1 complete minute; multiple-run count uses declared0.1q interval threshold. These reveal scenario support and are not fitted-error attributions.')
    with target.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
