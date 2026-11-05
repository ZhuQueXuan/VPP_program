from setup_study import *

def main():
    if (HERE/'checks.json').exists():raise RuntimeError('check receipt exists; preserve it')
    a,b,bhat,z,yhat,users,records=panel(4432100,'rct_positive',600)
    checks=[]
    def checked(name,condition):
        assert condition,name
        checks.append(name)
    y,groups,pre=metered._metered_outcomes(records)
    checked('independent raw integral',np.max(np.abs(y-z))<1e-12 and groups==users and pre)
    potential_z=a['potential']-b[:,None]
    checked('relative target equals net delivery under common reference',np.max(np.abs((potential_z-potential_z[:,[0]])-(a['potential']-a['potential'][:,[0]])))<1e-12)
    cfg=EffectConfig(seed=4432100,n_boot=199,return_audit=True)
    kwargs=dict(levels=LEVELS,assumptions=assumptions('rct_positive'),known_pi=a['assignment_pi'],effect_config=cfg)
    result=metered.estimate_metered_effects(records,a['X'],a['d'],**kwargs)
    checked('meter-only causal entry available without any reference',result['status']=='causal' and result['metered_pipeline']['reference_required'] is False)
    direct=fit_effects(a['X'],a['d'],z,users,levels=LEVELS,task=task_context('negative_normalized_actual_energy'),
        assumptions=kwargs['assumptions'],known_pi=kwargs['known_pi'],config=cfg)
    checked('same standard AIPW baseline numerical agreement',np.max(np.abs(np.asarray(result['causal_curve']['contrasts'])-direct['causal_curve']['contrasts']))<1e-12)
    original=fit_effects(a['X'],a['d'],yhat,users,levels=LEVELS,task=task_context(),assumptions=kwargs['assumptions'],known_pi=kwargs['known_pi'],config=cfg)
    audit=original['audit'];mu=np.asarray(audit['auxiliary_result_predictions']);pi=np.asarray(audit['propensity_predictions']);idx=np.asarray(audit['dose_index'])
    shifted_scores=aipw_scores(yhat-bhat,idx,mu-bhat[:,None],pi)
    before=np.asarray(audit['aipw_scores']).mean(0);after=shifted_scores.mean(0)
    checked('synchronously shifted auxiliary score contrasts are invariant',np.max(np.abs((before-before[0])-(after-after[0])))<1e-12)
    base=records[0]
    invalid={
      'missing meter value':lambda r:r.update(power_kw=[None]+list(r['power_kw'][1:])),
      'boolean meter value':lambda r:r.update(power_kw=[True]+list(r['power_kw'][1:])),
      'numeric string':lambda r:r.update(power_kw=['1']+list(r['power_kw'][1:])),
      'nonfinite meter':lambda r:r.update(power_kw=[np.inf]+list(r['power_kw'][1:])),
      'missing task interval':lambda r:r.update(starts_min=r['starts_min'][1:],ends_min=r['ends_min'][1:],power_kw=r['power_kw'][1:]),
      'partial meter boundary':lambda r:r.update(starts_min=r['starts_min']+.1,ends_min=r['ends_min']+.1),
      'unsupported request':lambda r:r['task'].update(request_kw=3.),
      'zero request':lambda r:r['task'].update(request_kw=0.),
      'nonpredeclared request type':lambda r:r['task'].update(task_pre_treatment='true'),
      'invalid identity':lambda r:r['task'].update(user_id=1),
      'out of order':lambda r:r.update(starts_min=r['starts_min'][::-1],ends_min=r['ends_min'][::-1]),
    }
    for label,change in invalid.items():
        rec=copy.deepcopy(base);change(rec)
        bad=metered.estimate_metered_effects([rec],[[0.]], [0.])
        checked(label,bad['status']=='invalid_input' and bad['causal_curve'] is None)
    for rename in ('task','user'):
        rec=copy.deepcopy(base);rec['task']['task_id']='renamed'
        if rename=='user':rec['task']['user_id']='another-user'
        bad=metered.estimate_metered_effects([base,rec],[[0.],[0.]],[0.,1.])
        checked('duplicate physical window despite renamed '+rename,bad['status']=='invalid_input')
    bad_records=copy.deepcopy(records);bad_records[3]['power_kw'][2]=np.nan
    checked('no implicit removal of failed event',metered.estimate_metered_effects(bad_records,a['X'],a['d'],**kwargs)['status']=='invalid_input')
    unknown=copy.deepcopy(records)
    for rec in unknown:rec['task']['task_pre_treatment']=None
    checked('unknown task predeclaration cannot give causal conclusion',metered.estimate_metered_effects(unknown,a['X'],a['d'],**kwargs)['status']=='association')
    checked('unconfirmed causal assumptions give association',metered.estimate_metered_effects(records,a['X'],a['d'],levels=LEVELS,effect_config=cfg)['status']=='association')
    checked('sparse support withheld',metered.estimate_metered_effects(records,a['X'],np.zeros(len(z)),**kwargs)['status']=='unsupported')
    checked('absolute outcome not labelled delivery',result['task']['outcome_name']=='negative_normalized_actual_energy' and not result['metered_pipeline']['absolute_levels_are_net_delivery'])
    receipt=dict(passed=True,n_checks=len(checks),checks=checks,baseline_max_difference=float(np.max(np.abs(np.asarray(result['causal_curve']['contrasts'])-direct['causal_curve']['contrasts']))),
        candidate_sha256=sha(HERE/'prototype.py'),scope='input functionality and target identity, not new estimator performance')
    (HERE/'checks.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
