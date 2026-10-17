"""Predefine observed step-response features before calculating crossings/errors."""
from mapping_common import *
import datetime
out=BASE/'kit_step_protocol_v1.json';assert not out.exists()
source=BASE/'downloads/KIT_LF_SOURCE_01';qa=BASE/'runs/KIT_SOURCE_QA_01'
p={'id':'KIT_RECORDED_PHASE_STEP_V1','decision':'D058','date':'2026-10-16','frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'question':'Characterise recorded phase-current changes following published current-limit changes in new KIT LF traces; no new predictive model, fitting or control-capacity claim.',
 'object':'All18 original LF recording sets/16 brand-model combinations,12 brands in Zenodo17866847v1.0.0; do not merge with Dortmund/EPFL devices or inherit their parameters.',
 'sources':{n:{'path':f.relative_to(ROOT).as_posix(),'sha256':sha(f)} for n,f in {
    'LF':source/'ev-charging_lf.parquet','index':source/'charging.csv','metadata':BASE/'downloads/EV_NEXT_SOURCE_01/kit_zenodo_record.json',
    'catalog':BASE/'downloads/EV_NEXT_SOURCE_01/kit_dataset_page.html','QA':qa/'summary.json','trace_quality':qa/'trace_quality.json'}.items()},
 'evidence':'Dataset officialCC-BY4.0 metadata and full-file MD5 checked. Author preprint abstract describes50Hz phase measurements and current-limit changes; full SSRN PDF403 not bypassed. Not exact full-paper reproduction or standards compliance.',
 'time':'timestamp_ns physical/logical TIMESTAMP_MICROS(isAdjustedToUTC=false). Decode integer microseconds and use within-trace relative differences; retain original Parquet row order, never sort/interpolate. No physical microsecond precision or timezone/network timestamp claim.',
 'candidate':'Every adjacent change in the raw setpoint_a becomes an event; first row is not a change. Report every candidate and all3 phases, not just successful responses.',
 'admission':{'command':'Both previous and new commands>=6A and absolute change>=2A. These are prespecified study operating filters, not claims of current IEC compliance.',
    'pre':'Complete[-5s,0) window with constant previous command, first/last observations within50ms of its edges.',
    'post':'Complete[0,15s) window with constant new command, first/last observations within50ms of edges; this is retrospective complete-held-command conditioning, not an availability prediction.',
    'continuity':'Strictly increasing finite timestamps, all adjacent gaps within entire[-5,15) window<=50ms; otherwise exclude window, keep status. All finite phase current and command, no target/error clipping.',
    'phase':'For each L1/L2/L3 independently require PRE-window observed median>=1A. Label preceding measured-load condition, not a confirmed connection/charging state. Report excluded inactive/start/stop cases separately; do not infer phase activity from future maximum.',
    'intent':'No output/response-residual based deletion; slow, limited, overshooting or unreached eligible responses remain.'},
 'features':{'baseline':'PRE observed phase-current median I0, input change du=u_new-u_old. Normalised progress=sign(du)*(I(t)-I0)/abs(du), not normalised by future observed final response.',
    'crossings':'First original sample with progress>=0.1 or>=0.9 and all subsequent original samples remaining above that threshold for at least100000us; search crossing starts in[0,10s], confirmation can extend to10.1s. Return original sample interval bounds, no interpolated crossing or asserted sub-sample precision.',
    'censoring':'No qualifying crossing means not observed within10s at requested command-step magnitude; return null/censored, never0 or artificial10s delay. It may reflect limited draw, timing, physical dynamics or other unknowns; not proof of a particular fault or infinite latency.',
    'transition_duration':'t90_sample-t10_sample only when both observed; not a count of90percent accurate predictions.',
    'steady':'Observed current median in[10,15s) minus NEW command, unitsA; report signed/absolute errors without using it to select phases/events.',
    'ideal_comparison':'Instantaneous exact tracking is an interpretive ideal only. No fit/no claimed error reduction versus earlier baselines; no90percent model-accuracy conversion.'},
 'aggregation':['all candidates/phase admissions and exclusion flags','up/down separately','each recording and brand/model/date','L1/L2/L3 separately','observed10/90 crossings and censored counts','median/p95/max conditional crossing times','steady error/bias and worst event retained','event counts distinct from recording sets, vehicles and correlated phase observations'],
 'reproducibility':'Before features bind all candidate windows and statuses with hashes; one calculation plus deterministic replay; independently reconstruct counts/window semantics and scalar threshold/statistics; preserve source order/limits.',
 'not_verified':['hardware/network dispatch-to-response delay','physical sensor clock/accuracy calibration','all startups/stops/inactive phases','cause of limited response','available maximum/firm capacity','user demand/departure/authorization','full IEC compliance','independent site/vehicle generalisation','103 formal90percent']}
dump(out,p);dump(BASE/'kit_step_freeze_v1.json',{'date':'2026-10-16','before_step_features':True,'protocol_sha256':sha(out)})
print(sha(out))
