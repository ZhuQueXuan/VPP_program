from candidate import *
def with_span(stats,rows,pred):
    out=dict(stats)
    for name in stats:
        span=[];short=[]
        for r,p in zip(rows,pred):
            t=r['provisional_targets'];on=t['onset_bracket_seconds'];end=t['recovery_completion_bracket_seconds'];e=p['methods'][name]
            if on is not None and end is not None:
                value=None if e['onset_seconds'] is None or e['recovery_seconds'] is None else e['recovery_seconds']-e['onset_seconds'];lo=max(0.,end[0]-on[1]);hi=max(0.,end[1]-on[0]);err=180. if value is None else min(180.,max(lo-value,value-hi,0.));ep=180. if value is None else min(180.,abs(value-(end[1]-on[1])));span.append((err,ep))
                if hi<=60:short.append(not e['detected'])
        out[name]=dict(out[name],observed_span=dict(n=len(span),interval_mae_seconds=float(np.mean([v[0] for v in span])) if span else None,endpoint_mae_seconds=float(np.mean([v[1] for v in span])) if span else None),short_observed_changes=len(short),short_observed_misses=sum(short))
    return out
def main():
    for p,h in read(HERE/'model_freeze.json')['files'].items():assert sha(ROOT/p)==h,p
    for n,h in read(HERE/'real_test/label_freeze.json')['files'].items():assert sha(HERE/'real_test'/n)==h,n
    rows=read(HERE/'real_test/inputs.json');h=load(ROOT/'work/b1_cpop_fine_v3_20261031/common.py','closing_native');h.HERE=HERE
    directory='real_test/native_attempt02'
    (HERE/directory/'labs').mkdir(parents=True,exist_ok=False)
    ids=[];cases=[];vectors=[]
    for row in rows:
        a=B.arrays(row)
        if a is None:continue
        j=len(ids);ids.append(row['event_id']);n=len(a['p']);x=np.arange(1,n+1,dtype=float);cases.append(dict(case_id=j,starts=x-.5,ends=x+.5,y=a['p'],sigma=B.context(a)['sigma_p'],train=np.ones(n,bool)));vectors.append(a['p'])
    for j in range((len(cases)+23)//24):(HERE/directory/'cpop'/f'chunk{j:03d}').mkdir(parents=True,exist_ok=False)
    cp,cm=h.cp_batch(cases,directory+'/cpop');lb,lm=h.labs_batch(vectors,directory+'/labs');curves={key:dict(cpop=cp[j],labs=lb[j]) for j,key in enumerate(ids)};save('real_test/native_curves.json',curves);save('real_test/native_receipt.json',dict(cpop=cm,labs=lm))
    parent,oldmodel=parent_models();newmodel=read(HERE/'candidate_model.json');eligible=read(HERE/'training_decision.json')['candidate_eligible'];oldpred=[];newpred=[]
    for row in rows:
        cp=curves.get(row['event_id'],{}).get('cpop',{}).get('prediction',[]);base=B.predictions([row],curves,3)[0];old=dict(base,methods=dict(base['methods'],candidate=A.infer(row,cp,parent,oldmodel)));new=dict(base,methods=dict(base['methods'],candidate=infer(row,cp,parent,newmodel) if eligible else old['methods']['candidate']));oldpred.append(old);newpred.append(new)
    oldstats=with_span(B.score(rows,oldpred),rows,oldpred);newstats=with_span(B.score(rows,newpred),rows,newpred);old=oldstats['candidate'];new=newstats['candidate'];checks=dict(training_eligible=eligible,has_recovery_reference=new['recovery']['n']>0,recovery_gain5=new['recovery']['capped_interval_mae_seconds'] is not None and old['recovery']['capped_interval_mae_seconds']>0 and new['recovery']['capped_interval_mae_seconds']<old['recovery']['capped_interval_mae_seconds'] and new['recovery']['capped_interval_mae_seconds']<=.95*old['recovery']['capped_interval_mae_seconds'])
    for key in ['false_positive','false_negative','spurious_recovery','short_observed_misses']:checks[key+'_nonincrease']=new[key]<=old[key]
    checks['missing_return_nonincrease']=new['recovery']['missing']<=old['recovery']['missing']
    checks['endpoint_nonincrease']=new['recovery']['capped_first_observed_mae_seconds']<=old['recovery']['capped_first_observed_mae_seconds']
    checks['span_nonincrease']=new['observed_span']['interval_mae_seconds']<=old['observed_span']['interval_mae_seconds'] and new['observed_span']['endpoint_mae_seconds']<=old['observed_span']['endpoint_mae_seconds']
    save('real_test/predictions.json',dict(retained=oldpred,candidate=newpred));save('real_test/scores.json',dict(retained=oldstats,candidate=newstats));save('real_test/decision.json',dict(checks=checks,adopt_closing_candidate=all(checks.values()),selected_real_branch='closing_candidate' if all(checks.values()) else 'retained_state_v2',no_more_tuning=True,labels_provisional=True,external_test_still_closed=True))
    print(json.dumps(native(dict(checks=checks,old=old,new=new))),flush=True)
if __name__=='__main__':main()
