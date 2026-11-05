"""Provisional raw-only review, all48 selected windows; no model-derived labels."""
from common import *
import collections
assert not (HERE/'real_test/predictions.json').exists()
samples=read(HERE/'real_test/samples.json')
# Onset and recovery endpoints were reviewed against original rows before
# original/adapted fits. Uncertain attribution remains unknown, never negative.
positive={
205:([-4,0],None,'right_censored_by_window','Clear drop at0 then sustained lower state.'),
207:([-3,0],[7,11],'observed_recovery','11s short limit excursion; both current and power return at11.'),
217:([0,4],[59,63],'observed_recovery','At0 still within preceding fluctuation; clear increase by4 and return63.'),
218:([-4,0],None,'right_censored_by_window','Large persistent drop; no observed return in window.'),
219:([-4,0],None,'interrupted_by_new_limit','Initial small drop followed by additional lower limits, no return.'),
221:([-11,0],None,'interrupted_by_new_limit','Clear rise from previously observed7.5A; no return to that low state.'),
223:([-5,0],[27,31],'observed_recovery','Small short rise from30.2A; first low state again at31.'),
225:([-4,0],[63,67],'observed_recovery','Rise from single native preceding low observation; return67. Provisional sparse prior state.'),
228:([0,3],None,'interrupted_by_new_limit','Small rise by3 after prior decline; subsequent large opposite change19 prevents unique first-response recovery.'),
229:([-4,0],None,'interrupted_by_new_limit','Clear drop then further lower levels; no return.'),
230:([-4,0],[13,16],'observed_recovery','Current limit returns13; measured current/power first return16.'),
231:([-2,0],[0,4],'observed_recovery','One observed short low point at0, actual return4. Retained as visible short change.'),
232:([-4,0],None,'right_censored_by_window','Multi-point rise begins0 and ramps to plateau; no return.'),
235:([-3,0],[21,24],'observed_recovery','Slow return from large transient;21 still below prior current range,24 first matches8.8A/1.854kW. Later stop unrelated, not fault-labeled.')}
unknown={220:'Only .1A shift near recording resolution with drifting power; anchor following not resolved.',237:'Previous lower limit only3s; its delayed dip occurs at selected upward edge. Prior low state not established, no unique new-response boundary.',241:'Large oscillations already before edge and continue after; isolated anchor response not resolved.'}
window_changes={205,207,209,216,217,218,219,220,221,223,225,228,229,230,231,232,235,237,238,239,241,242,244,246}
notes={201:'Limit remains far above current; small fluctuations, no resolved following change.',206:'Nonbinding limits above28A current; earlier power dip precedes edge.',208:'Nonbinding limit; later power drift while current stays near28A.',209:'No following change at anchor; later isolated current/power dip retained as separate observation, no fault truth.',213:'Small pre-anchor power dip without matching current change; no following anchor response.',238:'Quiet125A pilot with about62A/current and23kW; hardware/channel definition uncertain, retained without ordinary single-AC truth.',239:'No following change at0; later charging stop about37s.',240:'Pilot0 while positive current and power; channel-definition flag, no anchor task.',242:'Pilot0; later large measured dip under constant reported pilot, not labeled a response or fault.',244:'No current shift following edge; later power drift.',245:'Reported limits exceed current; later power dip not a resolved following response.',246:'Pilot0; later current/power excursion retained as background observation.'}
annotations=[];inputs=[]
def bracket(s,values):
    if values is None:return None
    ix=[s['relative_seconds'].index(float(v)) for v in values];assert ix[1]==ix[0]+1
    return dict(relative_seconds=[float(v) for v in values],raw_row_indices=[s['raw_row_indices'][i] for i in ix],endpoint_current_a=[s['current_a'][i] for i in ix],endpoint_power_kw=[s['power_kw'][i] for i in ix])
for s in samples:
    case=s['case'];on=end=None;status='not_applicable';truth=None
    if case in positive:on,end,status,note=positive[case];anchor='observed_change';truth=1
    elif case in unknown:anchor='unknown';note=unknown[case];status='unresolved'
    elif s['stratum']=='quiet_limit':anchor='not_applicable';note=notes.get(case,'No reported-limit edge; quiet observation context only.')
    else:anchor='no_clear_following_change';truth=0;note=notes.get(case,'No resolved current-and-power following change; limit is nonbinding and small fluctuations retained.')
    whole='observed_change' if case in window_changes else 'no_resolved_change';ob=bracket(s,on);eb=bracket(s,end)
    ann=dict(**{k:s[k] for k in ['case','event_id','source_path','local','source_sha256','split','user_group','station_group','anchor_timestamp','raw_row_index','stratum']},window_observation_label=whole,anchor_following_label=anchor,onset_bracket=ob,recovery_completion_bracket=eb,end_status=status,notes=note,gold_physical_truth=False,independent_review_status='pending',review_source='single_assistant_raw_review_before_model_outputs',effective_duration_seconds=None,causal_success=None,fault_label=None)
    annotations.append(ann)
    target=dict(window_visible_change=int(whole=='observed_change'),window_label_status=whole,anchor_visible_following=truth,anchor_label_status=anchor,onset_bracket_seconds=None if ob is None else ob['relative_seconds'],recovery_completion_bracket_seconds=None if eb is None else eb['relative_seconds'],recovery_status=status,effective_duration_seconds=None,fault_label=None,causal_response_success=None)
    inputs.append(dict(event_id=s['event_id'],split='test',model_input={k:s[k] for k in ['relative_seconds','current_a','pilot_a','power_kw']},provisional_targets=target,label_source=ann['review_source'],independent_review_status='pending',physical_gold=False))
save('real_test/annotations.json',annotations);save('real_test/inputs.json',inputs);save('real_test/review_receipt.json',dict(created_utc=now(),raw_pages_viewed=12,all_selected_windows_reviewed=len(samples),label_counts=dict(collections.Counter(a['anchor_following_label'] for a in annotations)),recovery_references=len([a for a in annotations if a['recovery_completion_bracket'] is not None]),no_model_output_reviewed_before_labels=True,not_independent_human_gold=True))
paths=[HERE/'annotate_test.py']+[HERE/'real_test'/n for n in ['annotations.json','inputs.json','review_receipt.json','samples.json','selection.json']]
save('real_test/label_freeze.json',dict(created_utc=now(),before_real_model_outputs=True,files={str(p.relative_to(HERE/'real_test')) if p.parent==HERE/'real_test' else '../annotate_test.py':sha(p) for p in paths}))
print(json.dumps(dict(counts=dict(collections.Counter(a['anchor_following_label'] for a in annotations)),recovery_references=sum(a['recovery_completion_bracket'] is not None for a in annotations))),flush=True)
