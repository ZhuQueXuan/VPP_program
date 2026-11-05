"""Independent estimated-GPS whole-user bootstrap audit on new audit inputs."""
from pathlib import Path
import json
import sys
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.research import fit_response_research
from b1_algorithm.effects.refit import refit_curve_uncertainty
from b1_algorithm.effects import continuous as CT

source=json.loads((HERE/'audit_integrated_model.json').read_text(encoding='utf-8'))['payload']
s=source['derivative_model'];p=json.loads(source['mean_model']['payload_json'])
assumptions=dict(p['declared_assumptions']);assumptions['randomized_assignment']=False
model=fit_response_research(s['X'],s['dose'],s['outcome'],s['users'],
    covariate_names=source['covariate_names'],task=p['task'],incentive_unit=p['incentive_unit'],
    dose_domain=p['dose_domain'],reference_dose=p['reference_dose'],assumptions=assumptions,
    config=s['configuration'],discover_structure=False)
grid=[.4,.73,1.17,1.65,2.]
seed=90335993
result=refit_curve_uncertainty(model,grid,draws=99,seed=seed,target_contrast=120.)
assert result['GPS_refitted_each_draw'] and result['outcome_nuisance_refitted_each_draw']
assert result['success_draws']+result['failed_draws']==99
assert len(result['draw_status'])==99
assert all(r.get('fold_integrity') for r in result['draw_status'] if r['status']=='ok')
if result['failed_draws']:assert result['status']=='incomplete' and not result.get('band_valid_for_use',False)
bp=json.loads(model['mean_model']['payload_json']);X=np.asarray(bp['X']);d=np.asarray(bp['dose']);y=np.asarray(model['derivative_model']['outcome']);u=np.asarray(bp['users'])
unique=np.unique(u);index=[np.flatnonzero(u==user) for user in unique]
rng=np.random.default_rng(seed);target=next(r['draw'] for r in result['draw_status'] if r['status']=='ok')
for _ in range(target+1):selected=rng.integers(0,len(unique),len(unique))
sample=np.concatenate([index[i] for i in selected])
cfg=dict(bp['configuration']);cfg['bandwidth']=bp['bandwidth'];cfg['return_audit']=True
independent=CT.fit_continuous_effects(X[sample],d[sample],y[sample],u[sample],
    dose_domain=bp['dose_domain'],grid=grid,reference_dose=bp['reference_dose'],
    incentive_unit=bp['incentive_unit'],task=bp['task'],continuous_assignment=True,
    assumptions=bp['declared_assumptions'],config=cfg)
curve=independent['causal_curve'] if independent['status']=='causal' else independent['standardized_association']
assert curve is not None,independent['reasons']
delta=float(np.max(abs(np.asarray(curve['contrasts'])-result['bootstrap_contrasts'][0])))
assert delta<1e-8,delta
errors=np.max(abs(np.asarray(result['bootstrap_contrasts'])-np.asarray(result['center_contrasts'])),axis=1)
radius=float(np.quantile(errors,.95))
assert abs(radius-result['absolute_supremum_radius'])<1e-10
result['independent_audit']=dict(first_successful_public_API_difference=delta,
    supremum_radius_independently_recomputed=radius,
    purpose='nuisance-refit arithmetic and cluster implementation; not empirical coverage proof')
with (HERE/'audit_refit_result.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(dict(status=result['status'],success=result['success_draws'],failed=result['failed_draws'],
    first_public_difference=delta,radius=radius,GPS_refitted=True),ensure_ascii=False))
