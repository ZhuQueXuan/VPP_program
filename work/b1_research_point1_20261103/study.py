import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
from pathlib import Path
import sys,json,time,hashlib
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'));sys.path.insert(0,str(HERE/'runtime/site-packages'))
from b1_api import *
from b1_algorithm.effects.continuous import ContinuousEffectConfig,local_linear_weights
from b1_algorithm.effects.frozen import _payload
from data import generate,truth,NAMES

PROTOCOL=json.loads((HERE/'protocol.json').read_text(encoding='utf-8'))
GRID=np.array(PROTOCOL['query_grid']);DOMAIN=PROTOCOL['domain']
TASK=dict(task_id='rp1-common30min',outcome_name='cumulative_response_seconds',outcome_unit='seconds',
    target_population='new declared simulation population including nonresponders',window_minutes=[0.,30.],
    q_kw=1.5,task_pre_treatment=True,reference_status='provided',reference_uncertainty='not_propagated')
GROUPS=dict(slack_below=dict(covariate='deadline_slack',threshold=0,side='below'),
    slack_above=dict(covariate='deadline_slack',threshold=0,side='above'))


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)


def assumptions(kind):
    return dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,same_outcome_definition=True,
        conditional_exchangeability=kind!='hidden_confounding',randomized_assignment=kind=='randomized')


def cfg(seed):return ContinuousEffectConfig(seed=int(seed),n_boot=99)


def metric(query,t):
    c=query['mean_curve']['curve'];direct=query['direct_marginal_effect'];smooth=query['retained_smoothed_derivative']
    result=dict(mean_status=query['mean_curve']['status'],direct_status=direct['status'])
    if c is not None:
        result['curve_rmse_seconds']=float(np.sqrt(np.mean((np.asarray(c['contrasts'])-t['contrasts'])**2)))
        result['smoothed_derivative_rmse']=float(np.sqrt(np.mean((np.asarray(smooth['values'])-t['derivative'])**2)))
    if direct['status']=='ok':result['direct_derivative_rmse']=float(np.sqrt(np.mean((np.asarray(direct['estimates'])-t['derivative'])**2)))
    result['target_first_crossing']=query['target_threshold'].get('first_point_crossing')
    result['zero_effect_band_excludes_zero']=bool(query['mean_curve'].get('inference') is not None and
        np.any((np.asarray(query['mean_curve']['inference']['lower'])>0)|(np.asarray(query['mean_curve']['inference']['upper'])<0)))
    return result


def cohort(stage,seed,kind,spec):
    start=time.perf_counter();folder=HERE/stage/f'{seed}-{kind}'
    d=generate(seed,kind,spec['users'],spec['events']);save(folder/'facts.json',d)
    m=fit_response_research(d['X'],d['treatment'],d['outcome'],d['users'],covariate_names=NAMES,
        task=TASK,incentive_unit='元/千瓦时',dose_domain=DOMAIN,reference_dose=PROTOCOL['reference'],
        assumptions=assumptions(kind),known_density=d['known_density'],config=cfg(seed),groups=GROUPS)
    save_research_point_one(m,folder/'model.json');q=query_research_point_one(m,GRID,target_contrast=120.)
    t=truth(GRID,kind);save(folder/'query.json',q);save(folder/'truth.json',t)
    score=metric(q,t);score.update(seed=seed,mechanism=kind,events=len(d['users']),users=spec['users'],elapsed_seconds=time.perf_counter()-start)
    group_truth={}
    for name,side in [('slack_below','below'),('slack_above','above')]:
        group_truth[name]=truth(GRID,kind,side)
    save(folder/'group_truth.json',group_truth)
    groups=q['group_effects']
    if all(groups[n].get('mean_curve',{}).get('curve') is not None for n in GROUPS):
        predicted=np.array(groups['slack_above']['mean_curve']['curve']['contrasts'])-np.array(groups['slack_below']['mean_curve']['curve']['contrasts'])
        actual=np.array(group_truth['slack_above']['contrasts'])-np.array(group_truth['slack_below']['contrasts'])
        score['group_effect_difference_rmse_seconds']=float(np.sqrt(np.mean((predicted-actual)**2)))
    score['structure_edges']={k:len(v.get('edges') or []) for k,v in m['structure'].items()}
    # Shared compact-kernel local quadratic derivative on the same DR pseudo-outcome.
    p,x,amount,xi,stabilized,res,users,config=_payload(FrozenContinuousModel(**m['mean_model']))
    local=[]
    for a in GRID:
        z=(amount-a)/p['bandwidth'];w=.75*(1-z*z)*(abs(z)<=1)
        Z=np.column_stack([np.ones(len(z)),z,z*z]);coef=np.linalg.lstsq(Z*np.sqrt(w[:,None]),xi*np.sqrt(w),rcond=None)[0]
        local.append(float(coef[1]/p['bandwidth']))
    score['shared_epanechnikov_quadratic_derivative_rmse']=float(np.sqrt(np.mean((np.array(local)-t['derivative'])**2)))
    save(folder/'score.json',score);print(stage,seed,kind,json.dumps(score),flush=True);return score


def aggregate(rows):
    keys=['curve_rmse_seconds','smoothed_derivative_rmse','direct_derivative_rmse',
          'shared_epanechnikov_quadratic_derivative_rmse','group_effect_difference_rmse_seconds']
    return dict(cohorts=len(rows),**{k:dict(mean=float(np.mean([r[k] for r in rows if k in r])),outputs=sum(k in r for r in rows)) for k in keys})


def main(stage):
    if stage=='development':spec=PROTOCOL['development']
    elif stage=='final':
        spec=PROTOCOL['final'];freeze=json.loads((HERE/'source_freeze.json').read_text(encoding='utf-8'))
        for p,h in freeze['files'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    else:raise ValueError(stage)
    rows=[]
    for seed in spec['seeds']:
        for kind in spec['mechanisms']:rows.append(cohort(stage,seed,kind,spec))
    save(HERE/stage/'summary.json',dict(rows=rows,aggregate=aggregate(rows),independent_seed_blocks=len(spec['seeds'])))


if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'development')
