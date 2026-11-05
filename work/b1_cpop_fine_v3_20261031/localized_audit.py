"""Post-comparison diagnostic: any-task positivity is not short-event recall.

This adds no selection or adoption decision. In contaminated tasks a different
spike can mask the removal of the true pulse in the whole-task miss count.
"""
from common import *

def main():
    cases=read('facts/test.json');truth={r['task_id']:r for r in read('evaluator/test.json')};curves=read('outputs/test_curves.json')
    rows=[];flags=[];method=read('validation_freeze.json')['method']
    for c,r in zip(cases,curves):
        s=np.array(c['starts_s']);use=(s>=0)&(s<1800);clean=np.array(truth[c['task_id']]['true_reduction_kw'])
        fit=r['results'][method];ix=set(fit['fine_evidence']['flagged_indices']);inj=set(truth[c['task_id']]['injected_indices'])
        flags.append(dict(condition=c['condition'],flagged_injected=len(ix&inj),flagged_noninjected=len(ix-inj),injected=len(inj)))
        if c['kind'] not in ['one_minute_response','one_finebin_response','one_minute_gap','one_finebin_gap']:continue
        for m,fit in r['results'].items():
            pred=np.array(fit['prediction']);d={k:c[k] for k in ['task_id','base_task_id','kind','condition']};d['method']=m
            if c['kind'].endswith('response'):
                actual=use&(clean>=.15);d['localized_miss']=not bool(np.any(pred[actual]>=.15));d['actual_samples']=int(actual.sum());d['retained_actual_samples']=int(np.sum(pred[actual]>=.15))
            else:
                gap=use&(clean<.15);d['entire_true_gap_filled']=bool(np.all(pred[gap]>=.15));d['actual_samples']=int(gap.sum());d['retained_gap_samples']=int(np.sum(pred[gap]<.15))
            rows.append(d)
    summary=[]
    for m in ['cpop',method,'labs']:
      for kind in ['one_minute_response','one_finebin_response','one_minute_gap','one_finebin_gap']:
       for condition in ['all','gaussian','single_sample_spikes','persistent_bursts']:
        rr=[r for r in rows if r['method']==m and r['kind']==kind and (condition=='all' or r['condition']==condition)]
        key='localized_miss' if kind.endswith('response') else 'entire_true_gap_filled'
        summary.append(dict(method=m,kind=kind,condition=condition,n=len(rr),**{key:sum(r[key] for r in rr)}))
    ff=[]
    for condition in ['gaussian','single_sample_spikes','persistent_bursts']:
        rr=[r for r in flags if r['condition']==condition];ff.append(dict(condition=condition,**{k:sum(r[k] for r in rr) for k in ['flagged_injected','flagged_noninjected','injected']}))
    write('localized_rows.json',rows);write('localized_diagnosis.json',dict(scope='Post-comparison descriptive audit only; frozen outcome/adoption records unchanged',summary=summary,flags=ff))
    print(json.dumps([r for r in summary if r['condition']=='all']));print(json.dumps(ff))
if __name__=='__main__':main()
