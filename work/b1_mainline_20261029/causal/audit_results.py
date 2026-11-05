"""Read-only scientific re-calculation; writes a new audit receipt only."""
from pathlib import Path
import importlib,sys,json,hashlib
import numpy as np
import pandas as pd
from simulation import generate

ROOT=Path(__file__).parent


def main():
    protocol=json.loads((ROOT/'protocol.json').read_text())
    raw=pd.read_csv(ROOT/'results/replicate_metrics.csv')
    curves=pd.read_csv(ROOT/'results/curves.csv')
    summary=pd.read_csv(ROOT/'results/summary.csv')
    diagnostics=json.loads((ROOT/'results/diagnostics.json').read_text())
    assert len(raw)==400 and len(curves)==2800 and len(diagnostics)==100
    assert np.isfinite(curves['estimate']).all()
    maximum_truth=maximum_rmse=0.
    independent=[]
    for rep,seed in enumerate(protocol['main_seeds']):
        for scenario in protocol['scenarios']:
            truth=generate(seed,scenario,protocol['n_users'],protocol['events_per_user'])['truth_tau']
            frame=curves[(curves.rep==rep)&(curves.scenario==scenario)]
            diag=next(d for d in diagnostics if d['rep']==rep and d['scenario']==scenario)
            for method,group in frame.groupby('method'):
                group=group.sort_values('level')
                maximum_truth=max(maximum_truth,float(abs(group['truth'].to_numpy()-truth).max()))
                error=group['estimate'].to_numpy()-truth
                rmse=float(np.sqrt(sum(float(v)**2 for v in error[1:])/6))
                stored=raw[(raw.rep==rep)&(raw.scenario==scenario)&(raw.method==method)].iloc[0]
                maximum_rmse=max(maximum_rmse,abs(rmse-stored.curve_rmse))
                if scenario=='deterministic_no_overlap': assert not group.reportable.any()
                if method=='AIPW_shared' and diag['identified']:
                    joint=bool(np.all((truth>=group.lower.to_numpy())&(truth<=group.upper.to_numpy())))
                    assert joint==stored.joint_coverage
                independent.append(dict(rep=rep,scenario=scenario,method=method,curve_rmse=rmse))
    assert maximum_truth<1e-12 and maximum_rmse<1e-12
    independently=pd.DataFrame(independent).groupby(['scenario','method']).curve_rmse.mean()
    for row in summary.itertuples():
        assert abs(independently.loc[(row.scenario,row.method)]-row.mean_curve_rmse)<1e-12
    reference=np.load(ROOT/'results/external_prediction_reference.npz')
    d_idx=reference['d_idx']; y=reference['y'];mu=reference['mu'];pi=reference['pi']
    loop=np.array([[mu[i,j]+int(d_idx[i]==j)*(y[i]-mu[i,j])/max(pi[i,j],.01) for j in range(7)] for i in range(len(y))])
    np.testing.assert_allclose(loop,reference['scores'],atol=1e-12)
    ride_path=ROOT.parents[1]/'ride_b1_v02_reproduction_20261029/source/ride_b1'
    sys.path.insert(0,str(ride_path))
    original=importlib.import_module('ride.effects')
    from_ride=original.aipw_scores(y,d_idx,mu,pi,clip=.01)
    np.testing.assert_allclose(reference['scores'],from_ride,atol=1e-12)
    import sklearn,scipy
    receipt=dict(passed=True,replicate_rows=len(raw),curve_rows=len(curves),diagnostic_contexts=len(diagnostics),
                 independent_truth_max_error=maximum_truth,independent_rmse_max_error=maximum_rmse,
                 actual_RIDE_score_max_error=float(abs(from_ride-reference['scores']).max()),
                 deterministic_contexts_withheld=sum(d['scenario']=='deterministic_no_overlap' and not d['identified'] for d in diagnostics),
                 numpy=np.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__,
                 file_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'protocol.json',ROOT/'api.py',ROOT/'simulation.py',ROOT/'run.py',ROOT/'results/curves.csv',ROOT/'results/replicate_metrics.csv']})
    (ROOT/'results/audit_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
