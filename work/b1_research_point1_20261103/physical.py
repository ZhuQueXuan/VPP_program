from study import *


def main():
    spec=PROTOCOL['physical'];seed=spec['seed'];kind=spec['mechanism'];folder=HERE/'physical'
    source=[Path(__file__),HERE/'data.py',HERE/'protocol.json']
    save(folder/'generator_freeze.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source})
    d=generate(seed,kind,spec['users'],spec['events']);rng=np.random.default_rng(seed+333)
    records=[];factors=[];ledger=[];s=np.arange(-900.,2700.,10.);e=s+10
    for i,(value,user,x,amount) in enumerate(zip(d['outcome'],d['users'],d['X'],d['treatment'])):
        count=int(np.rint(value/10));clean=np.zeros(len(s));inside=np.flatnonzero((s>=0)&(s<1800))
        first=int(rng.integers(0,181-count)) if count else 0
        clean[inside[first:first+count]]=1.5
        post=s>=1800;clean[post]=-.35*(count/180)*np.exp(-(s[post]-1800)/180)
        actual=3.-clean+rng.normal(0,.05,len(s));start=float(i*90)
        task=dict(task_id=f'rp1-physical-{i:04d}',user_id=user,meter_id=user+'-meter',
            start_min=start,end_min=start+30,request_kw=1.5,notice_min=start-15,task_pre_treatment=True)
        starts=(start+s/60).tolist();ends=(start+e/60).tolist()
        reference=provided_reference(task,starts,ends,np.full(len(s),3.),available_at_min=start-16)
        records.append(dict(task=task,starts_min=starts,ends_min=ends,power_kw=actual.tolist(),
                            reference=reference,noise_sigma_kw=.05))
        record=dict(task_id=task['task_id'],user_id=user,meter_id=task['meter_id'],
            offered_incentive=amount,treatment_set_min=start-20,
            available_at_min=dict(offered_incentive=start-20,**{name:start-30 for name in NAMES}),
            state_as_of_min={name:start-30 for name in NAMES},**dict(zip(NAMES,x)))
        factors.append(record);ledger.append(dict(task_id=task['task_id'],true_seconds=count*10))
    save(folder/'raw_records.json',records);save(folder/'factor_records.json',factors);save(folder/'truth_ledger.json',ledger)
    print('Raw native chain starting',len(records),flush=True)
    process_config=dict(rscript_path=str(ROOT/'work/b1_mainline_20261029/runtime/R-4.6.1/app/bin/Rscript.exe'),
        r_library=str(ROOT/'work/b1_mainline_20261029/runtime/r_library'),artifact_dir=str(folder/'native'),timeout_seconds=180)
    events=analyze_events(records,process_method='effective_response_refined',process_config=process_config)
    save(folder/'events.json',events)
    assert all(row['status']=='ok' for row in events),[(i,r['status'],r['reasons']) for i,r in enumerate(events) if r['status']!='ok'][:5]
    study=EVFactorStudy('research-point-one-physical','元/千瓦时',covariates=tuple(NAMES),outcome_source='duration_estimates')
    model=fit_research_point_one(events,factors,study,dose_domain=DOMAIN,reference_dose=.4,
        assumptions=assumptions(kind),config=cfg(seed),groups=GROUPS)
    save_research_point_one(model,folder/'model.json');query=query_research_point_one(model,GRID)
    t=truth(GRID,kind,rounded=True);save(folder/'truth_curve.json',t);save(folder/'query.json',query)
    extracted=np.array([r['process']['duration_estimates']['cumulative_response_seconds'] for r in events])
    score=metric(query,t);score.update(events=len(events),users=spec['users'],source='new physical simulation not real',
        first_block_duration_mae=float(np.mean(abs(extracted-np.array([r['true_seconds'] for r in ledger])))),
        raw_public_API_used=True,high_level_factor_contract_used=True,no_events_filtered=True,
        feature_rows=len(model['process_feature_table']))
    save(folder/'score.json',score)
    print('Raw native chain complete',json.dumps(score),flush=True)


if __name__=='__main__':main()
