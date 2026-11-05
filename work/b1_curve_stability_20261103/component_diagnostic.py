"""Post-confirmation mathematical ceiling, never an estimator or tuning rule."""
from pathlib import Path
import json,numpy as np
from prepare import save
HERE=Path(__file__).resolve().parent
s=json.loads((HERE/'confirmation/summary.json').read_text(encoding='utf-8'))
out=[]
for r in s['rows']:
    folder=HERE/'confirmation'/f"{r['seed']}-{r['mechanism']}"
    truth=json.loads((folder/'truth.json').read_text(encoding='utf-8'))
    a=np.asarray(r['policies']['retained_S']['contrast']);b=np.asarray(r['policies']['strong_LL2']['contrast'])
    target=np.asarray(truth['contrasts']);delta=a-b
    alpha=float(np.clip(delta@(target-b)/(delta@delta),0,1)) if delta@delta>0 else 1.
    error=float(np.sqrt(np.mean((alpha*a+(1-alpha)*b-target)**2)))
    out.append(dict(seed=r['seed'],mechanism=r['mechanism'],truth_only_best_alpha=alpha,
        truth_only_lower_bound_rmse=error,retained_rmse=r['policies']['retained_S']['curve_rmse_seconds'],
        actual_nested_alpha=r['raw_alpha_spline']))
summary={}
for kind in dict.fromkeys(r['mechanism'] for r in out):
    rr=[r for r in out if r['mechanism']==kind]
    summary[kind]=dict(cohorts=len(rr),mathematical_bound_at_retained=sum(r['truth_only_best_alpha']==1 for r in rr),
        mean_bound_rmse=float(np.mean([r['truth_only_lower_bound_rmse'] for r in rr])),
        mean_retained_rmse=float(np.mean([r['retained_rmse'] for r in rr])))
save(HERE/'component_ceiling_diagnostic.json',dict(
    scope='post-confirmation explanatory lower bound for the fixed two-curve family; uses truth and is impossible as a real estimator',
    used_to_change_parameters_or_select_method=False,formal_scores_replaced=False,per_mechanism=summary,rows=out))
print(json.dumps(summary))
