from methods import *
from data import generate,population_curve
from study import metric,aggregate
import importlib.util,time
from b1_algorithm.process import api as API,_duration_fusion as DF

def load_module(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
    verify_freeze();spec=read(HERE/'protocol.json')['endtoend'];selection=read(HERE/'baseline_selection.json');engine=selection['estimator']
    save('endtoend/source_freeze.json',dict(created_utc=now(),before_physical_generation=True,files={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [HERE/'endtoend.py',HERE/'methods.py',HERE/'data.py',HERE/'freeze.json',HERE/'protocol.json']}))
    start=time.perf_counter();blocks=[];cases=[];ledger=[];s=np.arange(-900,2700,10.);e=s+10
    for k,scenario in enumerate(spec['mechanisms']):
        d=generate(spec['seed']+k,scenario,spec['users'],spec['events'],stage='endtoend');count=np.rint(np.asarray(d['raw_latent_fraction'])*180).astype(int);rng=np.random.default_rng(spec['seed']+k+500)
        for i,n in enumerate(count):
            task_id=f'e2e-{scenario}-{i:04d}';clean=np.zeros(len(s));begin=int(rng.integers(0,181-n)) if n else 0;inside=np.flatnonzero((s>=0)&(s<1800));clean[inside[begin:begin+n]]=1.5;post=s>=1800;clean[post]=-.4*(n/180)*np.exp(-(s[post]-1800)/180)
            power=3.-clean+rng.normal(0,.05,len(s));task=dict(task_id=task_id,user_id=str(d['users'][i]),meter_id=task_id,start_min=0.,end_min=30.,request_kw=1.5,notice_min=-15.,task_pre_treatment=True)
            cases.append(dict(task=task,starts_s=s,ends_s=e,power_kw=power,reference_kw=np.full(len(s),3.),sigma=.05));ledger.append(dict(task_id=task_id,mechanism=scenario,event_position=i,active_cells=int(n),true_cumulative_seconds=float(n*10),source='new_declared_physical_simulation_not_real_data'))
        d['outcome_seconds']=count*10.;d.pop('raw_latent_fraction');blocks.append(d);save('endtoend/'+scenario+'/clean_facts.json',d)
    save('endtoend/physical_inputs.json',cases);save('endtoend/evaluator.json',ledger)
    H=load_module(ROOT/'work/b1_cpop_fine_v3_20261031/common.py','e2e_frozen_native');H.HERE=HERE
    native_cases=[dict(case_id=j,starts=s/60,ends=e/60,y=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']),sigma=.05,train=np.ones(len(s),bool)) for j,c in enumerate(cases)]
    for j in range((len(cases)+23)//24):(HERE/'endtoend/native/cpop'/f'chunk{j:03d}').mkdir(parents=True,exist_ok=False)
    fits,meta=H.cp_batch(native_cases,'endtoend/native/cpop');save('endtoend/native_curves.json',fits);save('endtoend/native_receipt.json',meta)
    outputs=[];estimated={k:[] for k in spec['mechanisms']}
    for j,(c,l) in enumerate(zip(cases,ledger)):
        data=API.prepare(s/60,e/60,c['power_kw'],c['reference_kw'],c['task'],.05);DF.validate_domain(data);r=API.complete(data,{0:fits[j]},policy='effective_response_refined');assert r['status']=='ok',(c['task']['task_id'],r.get('reason'));value=r['duration_estimates']['cumulative_response_seconds'];assert 0<=value<=1800
        estimated[l['mechanism']].append(value);outputs.append(dict(task_id=c['task']['task_id'],process=r,true_cumulative_seconds=l['true_cumulative_seconds']))
        if (j+1)%80==0:print('Frozen first-block',j+1,'/',len(cases),flush=True)
    save('endtoend/first_block_outputs.json',outputs);entries=[]
    for data in blocks:
        scenario=data['mechanism'];truth=population_curve(scenario,rounded=True);save('endtoend/'+scenario+'/population_truth.json',dict(grid=GRID,mean_seconds=truth,criterion='expected_round_Beta_duration10s_using_survivalcdf21nodequadrature'))
        for mode in ['clean','extracted']:
            facts=dict(data,outcome_seconds=np.asarray(data['outcome_seconds']) if mode=='clean' else np.asarray(estimated[scenario]));save('endtoend/'+scenario+'/'+mode+'_inference_input.json',facts)
            result=dict(existing_DR=public_DR(facts,int(data['seed'])),continuous_DML=estimate(facts,'DML','single',int(data['seed'])))
            for key,kind in [('bounded_control','bounded'),('capacity_control','capacity'),('soft_two_part','hurdle')]:result[key]=estimate(facts,engine,kind,int(data['seed']))
            result['selected_base']=result[selection['selected']];mm={m:metric(r,truth,scenario) for m,r in result.items()};entry=dict(scenario=scenario,mode=mode,metrics=mm);entries.append(entry);save('endtoend/'+scenario+'/'+mode+'_results.json',dict(results=result,metrics=mm));print('Endtoend',scenario,mode,{m:round(r['penalized_rmse_seconds'],3) for m,r in mm.items()},flush=True)
    save('endtoend/summary.json',dict(entries=entries,clean=aggregate([r for r in entries if r['mode']=='clean']),extracted=aggregate([r for r in entries if r['mode']=='extracted']),physical_events=len(cases),users=spec['users']*len(spec['mechanisms']),paired_inputs_same_except_outcome=True,first_block_unchanged=True,elapsed_seconds=time.perf_counter()-start))
    print('Endtoend complete',len(cases),flush=True)
if __name__=='__main__':main()
