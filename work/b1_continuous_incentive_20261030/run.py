"""Frozen new simulation comparison and direct API examples, not a report."""
from pathlib import Path
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,time
import numpy as np
import pandas as pd
from scipy.special import expit
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import fit_continuous_effects,export_incentive_curve

ASSUMPTIONS=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,same_outcome_definition=True,conditional_exchangeability=True,randomized_assignment=False)
TASK=dict(task_id='common-37min',outcome_name='eta_raw',outcome_unit='ratio',target_population='synthetic_EV_population',
          window_minutes=[0.,37.],q_kw=1.5,task_pre_treatment=True,reference_status='provided',reference_uncertainty='not_propagated')

def generate(seed,scenario,users=600,events=4):
    rng=np.random.default_rng(seed);groups=np.repeat(np.arange(users),events);n=len(groups)
    x=rng.uniform(-1,1,(n,1));common=rng.normal(0,.04,users)[groups];e=rng.normal(0,.04,n)
    if scenario=='observational_saturating':d=2.4*expit(.8*x[:,0]+1.5*rng.normal(size=n));density=None
    elif scenario=='deterministic_no_support':d=2.4*expit(3*x[:,0]);density=None
    else:d=rng.uniform(0,2.4,n);density=np.full(n,1/2.4)
    def shape(a):
        if scenario=='randomized_zero':return np.zeros_like(a)
        if scenario=='randomized_nonmonotone':return .4*np.sin(np.pi*a/2.4)
        return .5*(1-np.exp(-1.3*a))
    y=.2+.16*x[:,0]+.08*x[:,0]**2+common+shape(d)+e
    assumptions=ASSUMPTIONS.copy()
    if density is not None:assumptions.update(randomized_assignment=True,conditional_exchangeability=None)
    return x,d,y,groups,density,assumptions,shape


def main():
    if (HERE/'study_receipt.json').exists():raise RuntimeError('completed study must not be overwritten')
    start=time.perf_counter();rows=[];seeds=range(30103010,30103022)
    scenarios=['randomized_saturating','observational_saturating','randomized_zero','randomized_nonmonotone','deterministic_no_support']
    out=HERE/'results';out.mkdir(exist_ok=True);raw=ROOT/'data/B1_continuous_incentive_v1_20261030';raw.mkdir(exist_ok=True)
    for seed in seeds:
        for scenario in scenarios:
            x,d,y,users,pdf,assumptions,truth=generate(seed,scenario)
            result=fit_continuous_effects(x,d,y,users,dose_domain=[0,2.4],grid=np.linspace(0,2.4,81),reference_dose=0,
                incentive_unit='元/千瓦时（模拟）',continuous_assignment=True,task=TASK,assumptions=assumptions,
                known_density=pdf,config=dict(seed=seed,n_boot=199))
            row=dict(seed=seed,scenario=scenario,status=result['status'],events=len(y),users=600)
            if result['status']=='causal':
                grid=np.asarray(result['causal_curve']['incentive_values']);target=truth(grid)-truth(np.array([0.]))[0]
                for key,curve in [('continuous_DR',result['causal_curve']),*result['comparators'].items()]:
                    row[key+'_rmse']=float(np.sqrt(np.mean((np.asarray(curve['contrasts'])-target)**2)))
                if seed==30103010:
                    result['simulation_only']=True
                    (out/(scenario+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                    pd.DataFrame(dict(user=users,X=x[:,0],offered_incentive=d,eta_observed=y)).to_csv(raw/(scenario+'.csv'),index=False)
                    pd.DataFrame(dict(incentive=grid,true_effect=target,estimated_effect=result['causal_curve']['contrasts'])).to_csv(out/(scenario+'_curve.csv'),index=False)
                    export_incentive_curve(result,out/(scenario+'.png'),title={'randomized_saturating':'连续激励：增长后趋缓（模拟验证）',
                        'observational_saturating':'非随机激励分配（模拟验证）','randomized_zero':'零作用场景（模拟验证）',
                        'randomized_nonmonotone':'非单调形态压力测试（模拟）'}[scenario])
            else:row['reason']=str(result['reasons'])
            rows.append(row);print(seed,scenario,result['status'],flush=True)
    frame=pd.DataFrame(rows);frame.to_csv(HERE/'comparison.csv',index=False)
    summary=[]
    for scenario,part in frame.groupby('scenario',sort=False):
        values={name:float(part[name].mean()) for name in frame.columns if name.endswith('_rmse') and part[name].notna().any()}
        summary.append(dict(scenario=scenario,successful_curves=int((part.status=='causal').sum()),attempts=len(part),**values))
    receipt=dict(completed=True,repetitions=12,events_per_case=2400,case_variants=60,summary=summary,
        frozen_protocol='protocol.json',fit_on_continuous_incentives=True,discretization_used=False,
        selected_method_after_test=False,smoothing_band_is_complete_causal_CI=False,real_device_validation=False,
        main_process_baseline_unchanged='CPOP',continuous_effect_method='established Kennedy DR, not a new estimator',
        elapsed_seconds=time.perf_counter()-start)
    (HERE/'study_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
