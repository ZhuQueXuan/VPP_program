"""Numerical migration and public-route checks; no new performance experiment."""
from pathlib import Path
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import ast,copy,hashlib,json,sys,time
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import analyze_event,analyze_events,provided_reference,estimate_event_effects,estimate_metered_effects
from b1_algorithm import api as pipeline
from b1_algorithm.process import api as process
from b1_algorithm.process import batch
from b1_algorithm.effects import EffectConfig

def main():
    assert not (HERE/'verification.json').exists()
    checks=[];maximum=0.;started=time.perf_counter()
    def check(name,value):
        assert value,name
        checks.append(name)
    original=ROOT/'work/ride_b1_v02_reproduction_20261029/source/ride_b1/ride/identify.py'
    new=ROOT/'B1算法/b1_algorithm/process/_ride_identify.py'
    old_nodes={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(original.read_text(encoding='utf-8')).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    new_nodes={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(new.read_text(encoding='utf-8')).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    check('all vendored solver functions and classes are AST-identical to teacher original',all(old_nodes[name]==node for name,node in new_nodes.items()))
    check('original interval template byte identity',(ROOT/'B1算法/b1_algorithm/process/_ride_template.py').read_bytes()==(original.parent/'template.py').read_bytes())
    task=dict(task_id='verify',user_id='u',meter_id='m',start_min=0.,end_min=30.,notice_min=-15.,request_kw=1.5)
    folder=ROOT/'work/b1_unknown_reference_20261030/test'
    metrics=pd.read_csv(folder/'metrics.csv');observations=np.load(folder/'inputs_and_truth.npz');curves=np.load(folder/'method_curves.npz')
    rows=metrics[(metrics.method=='original_RIDE_template_3starts')&(metrics.seed<=4431203)&(metrics.context==0)&metrics.reference.isin(['fixed_gbdt','oracle_diagnostic'])]
    for row in rows.itertuples(index=False):
        blob=np.load(ROOT/f'data/B1_unknown_reference_v1_20261030/test/contexts_{row.seed}.npz')
        s=blob['starts'];e=blob['ends'];b=blob[f'0_ref_{row.reference}'];p=observations[row.identity+'_power']
        value=process.identify_process(s,e,p,b,task,.15,config=dict(rscript_path='absent_R_for_python_template.exe'))
        check('one-minute default original RIDE route '+str(row.index),value['status']=='ok' and value['method']=='RIDE_template_average')
        difference=float(np.max(np.abs(np.asarray(value['reduction_interval_kw'])-curves[f'{row.index}_original_RIDE_template_3starts'])))
        maximum=max(maximum,difference);assert difference<1e-12
        assert abs(value['eta_raw']-float(np.mean((b-p)[15:45])/1.5))<1e-12
    check('32 frozen one-minute curves and raw integrals match original RIDE',len(rows)==32 and maximum<1e-12)
    old=ROOT/'work/b1_formal_v1_20261029/process/test'
    old_meta=json.loads((old/'events.json').read_text());old_obs=np.load(old/'observations.npz');old_curves=np.load(old/'curves.npz')
    coarse=[m for m in old_meta if m['rep']==0 and m['delta_min']==15.]
    for m in coarse:
        i=m['event_id'];s=np.arange(-15.,45.,15.);b=np.full(4,3.);p=b-old_obs[f'{i}_raw']
        value=process.identify_process(s,s+15.,p,b,task,m['sigma_kw'])
        difference=float(np.max(np.abs(np.asarray(value['reduction_interval_kw'])-old_curves[f'{i}_RIDE_original'])))
        maximum=max(maximum,difference);assert difference<1e-12
        assert value['selection_evidence']['coarse_assumption_sensitive'] and value['physical_timing'] is None
        assert value['uncertainty_status']=='process_confidence_interval_not_validated'
        assert abs(value['eta_raw']-float(np.mean((b-p)[1:3])/1.5))<1e-12
    check('16 frozen coarse RIDE curves match with raw accounting and unidentified timing',len(coarse)==16)
    def record(delta,eta=.3,index=0):
        start=1000.+index*120.;s=start+np.arange(-15.,45.,delta);e=s+delta;b=np.full(len(s),3.)
        power=b-np.where((s>=start)&(e<=start+30.),1.5*eta,0.)
        t=dict(task_id=f'public-{index}',user_id=f'u-{index//2}',meter_id=f'm-{index//2}',
            start_min=start,end_min=start+30.,notice_min=start-15.,request_kw=1.5,task_pre_treatment=True)
        return dict(task=t,starts_min=s,ends_min=e,power_kw=power,
            reference=provided_reference(t,s,e,b,available_at_min=start-15.),noise_sigma_kw=.05)
    original_runtime=pipeline._default_runtime_config
    def unavailable():raise ValueError('controlled missing R identity fixture')
    pipeline._default_runtime_config=unavailable
    try:
        pure=analyze_events([record(1.,index=0),record(15.,index=1)])
        check('public one-minute and coarse templates work with no R',all(v['status']=='ok' and v['process']['method']=='RIDE_template_average' for v in pure))
        mixed=analyze_events([record(1.,index=0),record(1/6,index=1),record(15.,index=2)])
        check('missing R affects native route only; mixed order preserved',[v['status'] for v in mixed]==['ok','degraded','ok'] and mixed[1]['process']['method']=='raw_F0')
    finally:pipeline._default_runtime_config=original_runtime
    old_fit=process.fit_original_ride
    try:
        process.fit_original_ride=lambda data:dict(status='unavailable',reason='controlled optimizer failure')
        bad=analyze_event(**record(1.))
        check('template failure explicitly degrades raw F0',bad['status']=='degraded' and bad['process']['method']=='raw_F0' and abs(bad['outcome']['value']-.3)<1e-12)
    finally:process.fit_original_ride=old_fit
    none=analyze_event(**record(1.,eta=0.))
    check('genuine M0 distinct from failure',none['status']=='ok' and none['process']['selection_evidence']['structure']==0)
    fine=[m for m in old_meta if m['rep']==0 and abs(m['delta_min']-1/6)<1e-8 and m['mechanism'] in ('none','slow','multiplateau')]
    requests=[]
    for m in fine:
        i=m['event_id'];s=np.arange(-15.,45.,1/6);b=np.full(len(s),3.)
        requests.append(dict(starts_min=s,ends_min=s+1/6,power_kw=b-old_obs[f'{i}_raw'],reference_kw=b,task=task,noise_sigma_kw=m['sigma_kw']))
    config=original_runtime();config.update(artifact_dir=str(HERE/'native_regression'),timeout_seconds=180)
    values=batch.identify_process_batch(requests,config=config)
    for m,value in zip(fine,values):
        check('10-second original guarded route '+str(m['event_id']),value['status']=='ok' and value['selection_evidence']['policy']=='guarded')
        diff=float(np.max(np.abs(np.asarray(value['reduction_interval_kw'])-old_curves[f'{m["event_id"]}_unified_default'])))
        maximum=max(maximum,diff);assert diff<1e-9,diff
    check('actual native10second results preserve frozen curves',len(values)==6)
    explicit=analyze_event(**record(1.),process_method='cpop',process_config=config)
    check('CPOP remains available as explicit public baseline',explicit['status']=='ok' and explicit['process']['method']=='CPOP')
    check('explicit legacy coarse route remains available',analyze_event(**record(15.),process_method='conservative')['process']['method']=='raw_coarse')
    check('unknown process method withheld',analyze_event(**record(1.),process_method='unknown')['status']=='unavailable')
    cohort=[];x=[];d=[]
    for user in range(30):
        for arm in (0.,1.):
            cohort.append(record(15.,eta=.1+.2*arm+.01*np.sin(user),index=2*user+int(arm)))
            x.append([np.sin(user)]);d.append(arm)
    events=analyze_events(cohort)
    a=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,same_outcome_definition=True,randomized_assignment=True,conditional_exchangeability=None)
    effects=estimate_event_effects(events,x,d,levels=[0.,1.],known_pi=np.full((60,2),.5),assumptions=a,effect_config=EffectConfig(seed=902,n_boot=199))
    check('new default original-RIDE events feed existing effects',effects['status']=='causal' and abs(effects['causal_curve']['contrasts'][1]-.2)<1e-12)
    meter_records=[{k:v for k,v in rec.items() if k in ('task','starts_min','ends_min','power_kw')} for rec in [record(1.,index=i) for i in range(2)]]
    check('optional metered interface remains available',estimate_metered_effects(meter_records,[[0.],[0.]],[0.,1.],levels=[0.,1.])['status']=='unsupported')
    receipt=dict(passed=True,n_checks=len(checks),checks=checks,numerical_migration_cases=32+16+6,
        maximum_curve_difference=maximum,vendored_identical_definitions=len(new_nodes),
        elapsed_seconds=time.perf_counter()-started,scope='source parity and routing regression, not independent post-selection performance evidence')
    (HERE/'verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
