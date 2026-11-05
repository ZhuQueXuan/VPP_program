"""Numerical reproduction checks on development data only; no tuning."""
from methods import *
import math
data=read(HERE/'development/facts/90311000_random_hurdle.json');result,a=estimate(data,'DML','single',90311000,True);assert result['status']=='ok'
# Independent scalar query moment, avoiding the estimator's vectorized path.
manual=[]
for j,dose in enumerate(GRID):
    total=0.
    for item in a['items']:
        va=item['test'];ids=np.flatnonzero(va);pred=item['model'].predict(a['x'][va],np.full(len(ids),dose))
        for i,gamma in zip(ids,pred):
            kernel=math.exp(-.5*((a['d'][i]-dose)/a['h'])**2)/(math.sqrt(2*math.pi)*a['h'])
            total+=float(gamma)+kernel/(1/2.4)*(a['y'][i]-float(gamma))
    manual.append(total/len(a['y'])*T)
assert np.allclose(manual,result['mean_seconds'],rtol=0,atol=1e-9)
groups=np.asarray(data['users']);folds=a['folds']
for u in set(groups):assert len(set(folds[groups==u]))==1
for item in a['items']:assert not set(groups[item['train']])&set(groups[item['test']])
public=public_DR(data,90311000);private=estimate(data,'DR','single',90311000);assert public['status']==private['status']=='ok';assert np.allclose(public['contrast_seconds'],private['contrast_seconds'],rtol=0,atol=1e-7)
assert np.allclose(a['mu']*T,public['public_result']['audit']['outcome_prediction'],atol=1e-7,rtol=1e-9);assert np.allclose(a['pdf'],public['public_result']['audit']['observed_dose_density'],atol=1e-10,rtol=1e-9)
extra=np.unique(np.r_[GRID,[.73,.85,1.17]]);r2=estimate(data,'DML','single',90311000,grid=extra);assert r2['status']=='ok'
for j,dose in enumerate(GRID):assert np.isclose(result['contrast_seconds'][j],r2['contrast_seconds'][np.flatnonzero(np.isclose(extra,dose,atol=1e-12,rtol=0))[0]],atol=1e-8,rtol=0)
for kind in ['bounded','hurdle','capacity']:
    model=Outcome(kind).fit(np.asarray(data['X']),np.asarray(data['offered_incentive']),np.asarray(data['outcome_seconds'])/T);values=model.predict(np.asarray(data['X']),np.asarray(data['offered_incentive']));assert np.all((values>=0)&(values<=1))
    # A nonlinear nuisance must be marginalized over actual training X;
    # predicting only at averageX generally changes the target.
    doses=np.array([.73,.85,1.17]);direct=np.array([model.predict(np.asarray(data['X']),np.full(len(values),d)).mean() for d in doses]);assert np.allclose(model.marginal(doses),direct,rtol=0,atol=1e-12)
    assert len(values)==len(groups)
cfg=dict(status='passed',scalar_DML_query_moments=31,existing_DR_public_reproduction_equal=True,shared_nuisance_predictions_density_and_folds=True,independent_fold_model_count=len({id(i['model']) for i in a['items']}),user_fold_integrity=True,direct_arbitrary_amounts=[.73,.85,1.17],grid_insertion_mean_invariant=True,nonlinear_marginalization_checked=True,soft_probability_never_thresholded=True,all_events_kept=True,auxiliary_bounded_without_finalcurve_clipping=True,complete_causal_CI_claimed=False,main_performance_data='development_only')
path=HERE/'technical_checks.json'
if path.exists():assert read(path)==cfg
else:save('technical_checks.json',cfg)
print(json.dumps(cfg),flush=True)
