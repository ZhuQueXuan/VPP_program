"""Select an EV reference using completed non-event history only.

The current task response is never a selection label. This opt-in selector
does not change predict_reference defaults or correct the selected curve by
the failed pre-notice offset method.
"""
from dataclasses import replace
from collections.abc import Mapping
import numpy as np
from .core import ReferenceWindow,predict_reference
from ..contracts import number,identifier,array


def select_ev_reference(model,window,histories,*,validation_events=3):
    """Return {reference: ReferencePrediction, selection: diagnostics}.

    Histories must cover the query-relative prefix and prediction grid. At
    least two strictly earlier non-event curves supply each pseudo-event's
    prior. Validation users remain the query user and are never re-trained.
    """
    if not isinstance(window,ReferenceWindow) or window.resource_type!='EV':raise ValueError('EV ReferenceWindow required')
    if type(validation_events) is not int or not 1<=validation_events<=5:raise ValueError('1..5 fixed historical validation events required')
    if not isinstance(histories,(list,tuple)) or len(histories)<validation_events+2:raise ValueError('completed history for validation and at least two priors required')
    query_start=number(window.task_start_min,'task start');notice=number(window.notice_min,'notice')
    lead=query_start-notice;W=number(window.task_end_min,'task end')-query_start
    rel_s=np.asarray(window.starts_min,float)-query_start;rel_e=np.asarray(window.ends_min,float)-query_start
    pre_s=np.asarray(window.pre_starts_min,float)-query_start;pre_e=np.asarray(window.pre_ends_min,float)-query_start
    records=[];ids=set()
    for h in histories:
        if not isinstance(h,Mapping) or h.get('non_event') is not True:raise ValueError('declared non-event historical record required')
        source=identifier(h.get('source_id'),'historical source ID')
        if source in ids or source==window.task_id:raise ValueError('historical sources must be unique and exclude current task')
        ids.add(source)
        if h.get('user_id')!=window.user_id or h.get('meter_id')!=window.meter_id:raise ValueError('historical user/meter must match query')
        s=array(h.get('starts_min'),'historical starts');e=array(h.get('ends_min'),'historical ends');p=array(h.get('power_kw'),'historical power')
        if s.shape!=e.shape or p.shape!=s.shape or not np.allclose(e-s,1.,atol=1e-9,rtol=0) or not np.allclose(s[1:],e[:-1],atol=1e-9,rtol=0):raise ValueError('complete one-minute historical meter grid required')
        available=number(h.get('available_at_min'),'history availability')
        if available<float(e[-1])-1e-9 or available>notice+1e-9:raise ValueError('all selection labels must be completed and available before query notice')
        # The historical grid uses the same relative endpoints as prefix plus
        # prediction. Its event start is determined by that declared lattice.
        start=float(s[0]-pre_s[0])
        if records and any(abs(start-r['start'])<=1e-9 for r in records):raise ValueError('duplicate historical time window')
        context=h.get('reference_context')
        if not isinstance(context,Mapping):raise ValueError('explicit historical calendar/temperature context and availability required')
        hour=number(context.get('clock_hour'),'historical clock hour');weekday=number(context.get('weekday'),'historical weekday')
        if not 0<=hour<24 or weekday!=int(weekday) or not 0<=weekday<=6:raise ValueError('valid explicit historical calendar required')
        cal_at=number(context.get('calendar_available_min'),'historical calendar availability')
        temp_at=number(context.get('temperature_available_min'),'historical temperature availability')
        if cal_at>start-lead+1e-9 or temp_at>start-lead+1e-9:raise ValueError('historical context must have been available at its pseudo-notice')
        records.append(dict(source=source,start=start,s=s,e=e,p=p,available=available,hour=hour,weekday=int(weekday),
            cal_at=cal_at,temp_at=temp_at,temperature=number(h.get('temperature_c'),'historical temperature')))
    records.sort(key=lambda r:r['start'])
    if set(window.prior_source_ids)!=ids:raise ValueError('query prior source ledger must match supplied historical sources')
    def read(record,relative_s,relative_e):
        wanted=record['start']+relative_s
        indices=np.searchsorted(record['s'],wanted)
        if np.any(indices>=len(record['s'])) or not np.allclose(record['s'][indices],wanted,atol=1e-8,rtol=0) or not np.allclose(record['e'][indices],record['start']+relative_e,atol=1e-8,rtol=0):raise ValueError('history lacks aligned prefix or prediction window')
        return record['p'][indices]
    actual_prior=np.mean([read(h,rel_s,rel_e) for h in records],axis=0)
    if not np.allclose(actual_prior,np.asarray(window.prior_mean_kw,float),atol=1e-8,rtol=0):raise ValueError('query prior must equal its supplied observed historical average')
    ledger=[];errors={name:[] for name in ('gbdt','prev10')}
    for index in range(len(records)-validation_events,len(records)):
        h=records[index];pseudo_notice=h['start']-lead
        earlier=[r for r in records[:index] if r['available']<=pseudo_notice+1e-9 and r['e'][-1]<=pseudo_notice+1e-9]
        if len(earlier)<2:raise ValueError('pseudo-event prior needs at least two completed strictly earlier histories')
        pseudo=replace(window,task_id=h['source'],task_start_min=h['start'],task_end_min=h['start']+W,notice_min=pseudo_notice,
            starts_min=h['start']+rel_s,ends_min=h['start']+rel_e,pre_starts_min=h['start']+pre_s,pre_ends_min=h['start']+pre_e,
            pre_power_kw=read(h,pre_s,pre_e),pre_available_min=pseudo_notice,
            prior_mean_kw=np.mean([read(r,rel_s,rel_e) for r in earlier],axis=0),prior_available_min=max(r['available'] for r in earlier),
            prior_source_count=len(earlier),prior_source_ids=tuple(r['source'] for r in earlier),
            clock_hour=h['hour'],weekday=h['weekday'],calendar_available_min=h['cal_at'],
            temperature_c=h['temperature'],temperature_available_min=h['temp_at'])
        target=read(h,rel_s,rel_e);use=(rel_s>=-1e-9)&(rel_e<=W+1e-9)
        per={}
        for method in errors:
            pred=predict_reference(model,pseudo,method=method)
            if pred.reference_status!='available':raise ValueError('historical validation prediction unavailable: '+str(pred.reasons))
            score=float(np.mean(abs(pred.reference_kw[use]-target[use])));errors[method].append(score);per[method]=score
        ledger.append(dict(task_id=h['source'],label_available_min=h['available'],pseudo_notice_min=pseudo_notice,
            prior_sources=[r['source'] for r in earlier],mae_kw=per))
    means={k:float(np.mean(v)) for k,v in errors.items()}
    chosen=min(means,key=lambda m:(means[m],m!='gbdt'))
    prediction=predict_reference(model,window,method=chosen)
    return dict(reference=prediction,selection=dict(method=chosen,mean_history_task_mae_kw=means,
        validation_events=validation_events,ledger=ledger,query_notice_min=notice,current_response_used=False,
        model_retrained=False,reference_offset_correction_used=False,uncertainty_calibration_recomputed=False,
        interpretation='past-user validation only; no guarantee of current counterfactual accuracy'))
