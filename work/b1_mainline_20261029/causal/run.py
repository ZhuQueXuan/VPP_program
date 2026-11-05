"""Frozen main comparison. Run verify.py first; never uses truth for fitting."""
import os
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[name]='1'
from pathlib import Path
import json,hashlib,time,platform
import numpy as np
import pandas as pd
from api import LEVELS,fit_discrete,cluster_inference
from simulation import generate

ROOT=Path(__file__).parent


def main():
    started=time.time()
    protocol_bytes=(ROOT/'protocol.json').read_bytes()
    protocol=json.loads(protocol_bytes)
    verification=json.loads((ROOT/'verification.json').read_text())
    assert verification['passed']
    out=ROOT/'results'
    out.mkdir(exist_ok=False)
    rows,curves,diagnostics=[],[],[]
    for rep,seed in enumerate(protocol['main_seeds']):
        for scenario in protocol['scenarios']:
            data=generate(seed,scenario,protocol['n_users'],protocol['events_per_user'])
            known=data['assignment_pi'] if scenario=='rct_positive' else None
            result=fit_discrete(data['X'],data['d'],data['y'],data['groups'],known_pi=known,seed=seed)
            diag=result['diagnostics']
            diagnostics.append(dict(rep=rep,seed=seed,scenario=scenario,identified=result['identified'],**diag))
            audit=result['audit']
            if audit is None: continue
            idx,mu,pi=audit['d_idx'],audit['mu'],audit['pi']
            n=len(idx)
            means=np.array([data['y'][idx==j].mean() for j in range(7)])
            plugin=mu.mean(0)
            ipw=(np.eye(7)[idx]*data['y'][:,None]/np.maximum(pi,.01)).mean(0)
            aipw=audit['scores'].mean(0)
            methods={'Unadjusted_arm_mean':means,'Plugin_shared':plugin,'IPW_shared':ipw,'AIPW_shared':aipw}
            # Unadjusted arm mean only has a causal interpretation in the RCT.
            for method,apo in methods.items():
                tau=apo-apo[0]
                err=tau-data['truth_tau']
                infer=None
                if method=='AIPW_shared': infer=audit['raw_band']
                row=dict(rep=rep,seed=seed,scenario=scenario,method=method,n_events=n,n_users=protocol['n_users'],
                         diagnostic_pass=result['identified'],causally_valid_comparator=bool(method!='Unadjusted_arm_mean' or scenario=='rct_positive'),
                         curve_rmse=float(np.sqrt(np.mean(err[1:]**2))),absolute_max_error=float(np.max(abs(err[1:]))),
                         joint_coverage=None,threshold_contains_truth=None,threshold_candidates_count=None,
                         threshold_includes_not_reached=None)
                if infer is not None and result['identified']:
                    row['joint_coverage']=bool(np.all((data['truth_tau']>=infer['lower'])&(data['truth_tau']<=infer['upper'])))
                    th=result['threshold']
                    row['threshold_contains_truth']=bool(data['true_first'] in th['indices'] if data['true_first']>=0 else th['not_reached'])
                    row['threshold_candidates_count']=len(th['indices'])+int(th['not_reached'])
                    row['threshold_includes_not_reached']=th['not_reached']
                rows.append(row)
                for j in range(7):
                    curves.append(dict(rep=rep,seed=seed,scenario=scenario,method=method,level=float(LEVELS[j]),
                                       truth=float(data['truth_tau'][j]),estimate=float(tau[j]),
                                       reportable=bool(result['identified'] and (method!='Unadjusted_arm_mean' or scenario=='rct_positive')),
                                       lower=float(infer['lower'][j]) if infer is not None else None,
                                       upper=float(infer['upper'][j]) if infer is not None else None))
            if rep==0 and scenario=='observational_positive':
                np.savez_compressed(out/'external_prediction_reference.npz',X=data['X'],d=data['d'],y=data['y'],groups=data['groups'],
                                    d_idx=idx,mu=mu,pi=pi,folds=audit['folds'],scores=audit['scores'],truth_tau=data['truth_tau'])
        print(f'finished rep {rep+1}/{len(protocol["main_seeds"])}',flush=True)
    raw=pd.DataFrame(rows); raw.to_csv(out/'replicate_metrics.csv',index=False)
    pd.DataFrame(curves).to_csv(out/'curves.csv',index=False)
    # Lists retained without lossy conversion in JSON.
    (out/'diagnostics.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),encoding='utf-8')
    summary=raw.groupby(['scenario','method']).agg(repetitions=('rep','size'),mean_curve_rmse=('curve_rmse','mean'),
          median_curve_rmse=('curve_rmse','median'),diagnostic_passes=('diagnostic_pass','sum'),
          joint_coverage=('joint_coverage','mean'),coverage_denominator=('joint_coverage','count'),
          threshold_containment=('threshold_contains_truth','mean'),mean_threshold_candidates=('threshold_candidates_count','mean')).reset_index()
    summary.to_csv(out/'summary.csv',index=False)
    receipt=dict(protocol_sha256=hashlib.sha256(protocol_bytes).hexdigest(),elapsed_seconds=time.time()-started,
                 python=platform.python_version(),n_rows=len(raw),n_curve_rows=len(curves),all_estimates_finite=bool(np.isfinite(pd.DataFrame(curves)['estimate']).all()),
                 n_independent_seed_blocks=len(protocol['main_seeds']),n_paired_scenarios=len(protocol['scenarios']),
                 total_event_variants=len(protocol['main_seeds'])*len(protocol['scenarios'])*protocol['n_users']*protocol['events_per_user'],
                 original_source_mutations=False,standard_estimator_adaptation_not_novel_causal_estimator=True)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(summary.to_string(index=False));print(json.dumps(receipt,indent=2))


if __name__=='__main__': main()
