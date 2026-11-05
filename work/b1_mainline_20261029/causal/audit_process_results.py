"""Independent serialized-output arithmetic audit; never changes process files."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd

ROOT=Path(__file__).parent
P=ROOT.parent/'process/main'


def main():
    metrics=pd.read_csv(P/'all_metrics.csv')
    curves=np.load(P/'all_curves.npz')
    events=json.loads((P/'events.json').read_text())
    native=pd.read_csv(P/'cpop_segments.csv')
    summary=pd.read_csv(P/'summary.csv')
    pairs=pd.read_csv(P/'paired.csv')
    assert len(events)==960 and len(metrics)==5760
    rmse_diff=eta_diff=projection_diff=0.
    for event in events:
        i=event['event_id'];delta=event['delta_min']
        starts=np.arange(-15,45-1e-8,delta);ends=starts+delta
        request=(starts>=-1e-9)&(starts<30-1e-9)
        truth,y=curves[f'{i}_truth'],curves[f'{i}_y']
        frame=metrics[metrics.event_id==i]
        assert len(frame)==6
        eta=sum(float(v)*delta for v in y[request])/(1.5*30)
        for row in frame.itertuples():
            pred=curves[f'{i}_{row.method}']
            rmse=np.sqrt(sum((float(a)-float(b))**2 for a,b in zip(pred[request],truth[request]))/request.sum())
            rmse_diff=max(rmse_diff,abs(rmse-row.request_rmse))
            eta_diff=max(eta_diff,abs(eta-row.eta_raw))
        seg=native[native.event_id==i]
        # Independent antiderivative evaluation, including declared edge extension.
        projected=[]
        for a,b in zip(starts,ends):
            integral=0.;covered=0.
            for k,row in enumerate(seg.itertuples()):
                left=min(row.x0,starts[0]) if k==0 else row.x0
                right=max(row.x1,ends[-1]) if k==len(seg)-1 else row.x1
                lo,hi=max(a,left),min(b,right)
                if hi>lo:
                    integral+=row.gradient/2*(hi*hi-lo*lo)+row.intercept*(hi-lo)
                    covered+=hi-lo
            assert abs(covered-(b-a))<1e-7
            projected.append(integral/(b-a))
        projection_diff=max(projection_diff,float(abs(np.array(projected)-curves[f'{i}_CPOP_original_R']).max()))
    assert rmse_diff<1e-12 and eta_diff<1e-12 and projection_diff<1e-10
    for row in summary.itertuples():
        frame=metrics[(metrics.method==row.method)&np.isclose(metrics.delta_min,row.delta_min)]
        assert len(frame)==row.n==320
        assert abs(frame.request_rmse.mean()-row.request_rmse)<1e-12
        assert abs(frame.eta_abs_error_pp.mean()-row.eta_mae_pp)<1e-12
        for key in ['onset_s','target_s','recovery_s']:
            assert int(frame[key+'_joint_valid'].sum())==getattr(row,key+'_n_joint_valid')
            assert int(frame[key+'_false_positive'].sum())==getattr(row,key+'_false_positive')
            assert int(frame[key+'_miss'].sum())==getattr(row,key+'_miss')
    for row in pairs.itertuples():
        frame=metrics[np.isclose(metrics.delta_min,row.delta_min)]
        table=frame.pivot(index=['rep','mechanism','sigma_kw'],columns='method',values='request_rmse')
        diffs=(table.Grid_average-table[row.comparator]).groupby(level='rep').mean()
        assert len(diffs)==20
        assert abs(diffs.mean()-row.mean_difference)<1e-12
        assert int((diffs<0).sum())==row.wins_blocks
    receipt=dict(passed=True,metric_rows=len(metrics),observation_variants=len(events),independent_seed_blocks=20,
                 summary_rows=len(summary),paired_rows=len(pairs),maximum_request_rmse_recalculation_error=rmse_diff,
                 maximum_raw_eta_recalculation_error=eta_diff,maximum_CPOP_projection_antiderivative_error=projection_diff,
                 feature_denominators_counts_rechecked=True,
                 input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [P/'all_metrics.csv',P/'cpop_segments.csv',P/'summary.csv',P/'paired.csv']})
    (ROOT/'process_independent_audit.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__': main()
