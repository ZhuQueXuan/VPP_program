"""Evaluation only: independently derive signed true cumulative energy from declared actions."""
from pathlib import Path
import json,hashlib,csv
import numpy as np
from scipy.stats import binomtest
BASE=Path(__file__).resolve().parent
P=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))

def main():
    receipt=json.loads((BASE/'run_receipt.json').read_text())
    assert hashlib.sha256((BASE/'intervals.npz').read_bytes()).hexdigest()==receipt['intervals_sha256']
    intervals=np.load(BASE/'intervals.npz')
    times=intervals['post_times_s']
    truths=[]
    for name,d in P['mechanisms'].items():
        # Debt at release .5 kWh, repaid linearly over 720 s, including negative credit.
        if name=='no_action':truths.append(np.zeros(len(times)))
        else:truths.append(.5-(.5-d)*np.minimum((times-1800)/720,1))
    truth=np.array(truths)
    np.savez_compressed(BASE/'evaluator_truth.npz',debt_path=truth,endpoint=truth[:,-1])
    rows=[];states=[]
    for s,model in enumerate(P['observation_models']):
        for m,name in enumerate(P['mechanisms']):
            est=intervals['debt_path'][s,m];width=intervals['path_width'][s]
            end=intervals['endpoint_debt'][s,m];lo=intervals['endpoint_lower'][s,m];hi=intervals['endpoint_upper'][s,m]
            true=truth[m,-1]
            covers=(lo<=true+1e-14)&(hi>=true-1e-14)
            pathcovers=np.all((est-width<=truth[m]+1e-14)&(est+width>=truth[m]-1e-14),axis=-1)
            ci=binomtest(int(covers.sum()),len(covers)).proportion_ci(.95,method='exact')
            rows.append(dict(model=model,mechanism=name,n=len(end),true_debt_kwh=true,
                endpoint_coverage=float(covers.mean()),coverage_mc_low=ci.low,coverage_mc_high=ci.high,
                simultaneous_path_coverage=float(pathcovers.mean()),
                endpoint_bias=float(np.mean(end-true)),endpoint_rmse=float(np.sqrt(np.mean((end-true)**2))),
                endpoint_width=float(intervals['endpoint_width'][s]),
                naive_endpoint_sign_unpaid_rate=float(np.mean(end>0))))
            for e in P['margins_kwh']:
                within=hi<=e;above=lo>e;unresolved=~(within|above)
                incorrect=(within&(true>e+1e-12))|(above&(true<=e+1e-12))
                states.append(dict(model=model,mechanism=name,margin_kwh=e,
                    within_margin=float(within.mean()),above_margin=float(above.mean()),
                    unresolved=float(unresolved.mean()),incorrect_decisive=float(incorrect.mean())))
    with (BASE/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with (BASE/'decisions.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(states[0]));w.writeheader();w.writerows(states)
    out=dict(metrics=rows,decisions=states,limitations='known declared Gaussian difference covariance/bias only; epsilon numerical sensitivity not business service guarantee')
    (BASE/'evaluation.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    for r in rows:
        if r['mechanism']=='restored':print(json.dumps(r))

if __name__=='__main__':main()
