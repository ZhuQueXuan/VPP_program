import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import sys,json,hashlib,csv,time
from pathlib import Path
import numpy as np
from scipy.special import expit
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.effects.continuous import fit_continuous_effects,ContinuousEffectConfig
from b1_algorithm.effects.frozen import fit_continuous_model,query_continuous_model,save_continuous_model,find_incentive_threshold
OUT=Path(__file__).parent;DATA=ROOT/'data/B1_finish_queries_v1_20261030'
DATA.mkdir(exist_ok=False);(OUT/'models').mkdir(exist_ok=False)
protocol=json.loads((OUT/'protocol.json').read_text())
freeze={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/'run.py',OUT/'protocol.json',ROOT/'B1算法/b1_algorithm/effects/frozen.py',ROOT/'B1算法/b1_algorithm/effects/continuous.py']}
(OUT/'source_freeze.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
grid=np.array(protocol['grid']);ref=.8;rows=[]
assumptions={v:True for v in ('pre_treatment_X','consistent_treatment','no_interference','same_outcome_definition','conditional_exchangeability')}
task=dict(task_id='step4-EV30',outcome_name='duration',outcome_unit='seconds',target_population='synthetic-cohort',window_minutes=[0,30],q_kw=1.5,task_pre_treatment=True,reference_status='not_applicable',reference_uncertainty='not_applicable')
def shape(name,a):
    if name in ('saturating','deterministic_assignment'):return 420*(1-np.exp(-1.2*a))
    if name=='nonmonotonic':return 350*np.sin(3.4*a)
    return np.zeros_like(a,dtype=float)
def derivative(name,a):
    if name in ('saturating','deterministic_assignment'):return 504*np.exp(-1.2*a)
    if name=='nonmonotonic':return 1190*np.cos(3.4*a)
    return np.zeros_like(a,dtype=float)
for seed in protocol['seeds']:
    rng=np.random.default_rng(seed);x=np.repeat(rng.normal(size=(600,2)),2,axis=0)
    noise=rng.normal(size=1200);z=.55*x[:,0]+.4*x[:,1]+1.2*noise
    users=[f'u{i//2}' for i in range(1200)]; eps=rng.normal(0,35,1200)
    for name in protocol['shapes']:
        started=time.perf_counter();d=2.4*expit(.55*x[:,0]+.4*x[:,1] if name=='deterministic_assignment' else z)
        y=500+shape(name,d)+55*x[:,0]+40*x[:,1]+eps
        path=DATA/f'{seed}_{name}.csv'
        with path.open('x',newline='',encoding='utf-8') as f:
            writer=csv.writer(f);writer.writerow(['user','X0','X1','incentive','observed_seconds']);writer.writerows(zip(users,x[:,0],x[:,1],d,y))
        options=dict(dose_domain=[0,2.4],reference_dose=ref,incentive_unit='CNY',task=task,continuous_assignment=True,assumptions=assumptions,config=ContinuousEffectConfig(seed=seed,n_boot=199))
        row=dict(seed=seed,shape=name,events=1200,users=600)
        direct=fit_continuous_effects(x,d,y,users,grid=grid,**options)
        try:
            model=fit_continuous_model(x,d,y,users,**options);save_continuous_model(model,OUT/'models'/f'{seed}_{name}.json')
            query=query_continuous_model(model,grid)
            row.update(status=query['status'],direct_status=direct['status'],model_id=model.sha256)
            if query['curve'] is not None:
                curve=direct.get('causal_curve') or direct.get('standardized_association')
                row['direct_max_abs_difference']=max(float(np.max(abs(np.array(query['curve'][k])-curve[k]))) for k in ('mean_outcomes','contrasts'))
                row['contrast_RMSE_seconds']=float(np.sqrt(np.mean((np.array(query['curve']['contrasts'])-(shape(name,grid)-shape(name,ref)))**2)))
                row['smoothed_derivative_vs_truth_RMSE']=float(np.sqrt(np.mean((np.array(query['sensitivity']['values'])-derivative(name,grid))**2)))
            threshold=find_incentive_threshold(model,target_contrast=120,search_domain=[.4,2],mesh_step=.04)
            row.update(threshold_status=threshold['status'],point_crossing=threshold['first_point_crossing'],candidate_cells=len(threshold['candidate_cells']),not_reached_possible=threshold['not_reached_possible'])
            (OUT/f'{seed}_{name}_query.json').write_text(json.dumps(dict(query=query,threshold=threshold),allow_nan=False),encoding='utf-8')
        except ValueError as exc:
            row.update(status='unsupported_fit',reason=str(exc),direct_status=direct['status'])
        row['seconds']=time.perf_counter()-started;rows.append(row)
        (OUT/f'{seed}_{name}_receipt.json').write_text(json.dumps(row,indent=2),encoding='utf-8')
        print(json.dumps(row),flush=True)
(OUT/'results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print('DONE',len(rows),flush=True)
