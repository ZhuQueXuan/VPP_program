"""Preregister restricted common-command mapping BEFORE fitting or errors."""
from mapping_common import *
import datetime
qa=BASE/'runs/EV_SOURCE_QA_02';protocol=BASE/'common_command_mapping_protocol_v1.json';assert not protocol.exists()
p={'id':'EV_COMMON_COMMAND_MAPPING_V1','decision':'D057','date':'2026-10-16','frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'purpose':'First bounded EV component: static published-record input/output mapping without unverified state/connector enums; NOT dynamic control, charging-state or available-capacity certification.',
 'scope_change':'Official parameters/API attempts04 and native verified-TLS attempt05 failed. Do not guess STATE=4 or connector IDs. Continue a smaller research question whose inputs have source unit evidence.',
 'object':'48 precisely indexed EVTEC dynamic V1G trials across8 vehicle models,25AC/23DC; no Wirelane/unmapped/V2G or other data joined.',
 'sources':{'archive':{'path':load(qa/'summary.json')['archive_path'],'sha256':load(qa/'summary.json')['archive_sha256']},
    **{n:{'path':(qa/n).relative_to(ROOT).as_posix(),'sha256':sha(qa/n)} for n in ('archive_inventory.csv','dynamic_v1g_quality.json','verification.json')},
    'metadata':{'path':'work/ev_charging_research_20261016/downloads/EV_SOURCE_03/measurements.csv','sha256':sha(BASE/'downloads/EV_SOURCE_03/measurements.csv')},
    'paper':{'path':'work/ev_charging_research_20261016/downloads/EV_SOURCE_02/esser_2025_paper.pdf','sha256':sha(BASE/'downloads/EV_SOURCE_02/esser_2025_paper.pdf')}},
 'sample_rule':{'order':'Original row order. Never sort/reassign timestamps, interpolate, resample, round commands, or fill values.',
    'clock':'epoch magnitude interpreted as ms for within-file elapsed-time guard only. Row must be later than all preceding finite raw epochs; adjacent raw step must be strictly positive and<=2000ms. Any violated/invalid clock restarts a coherent block; require>=5000ms coherent block history before use. First row starts block but warmup excludes it.',
    'guard_reason':'Paper G/C polling0.5-1s;2s is prespecified diagnostic continuity allowance used in prior QA, not an estimated device delay.5s warmup is conservative study exclusion, not business rule.',
    'inputs':'All AC_Power_set_ID2,ID3,ID4 finite, exactly equal and nonnegative in the SAME current published record. This common command avoids selecting an interface by future delivered power. Units kW.',
    'target':'P_kocos_200 finite in the SAME published G/C row, kW grid-side; no DC output target mixed. Negative measured values retained. No state, SOC or output-based quality filter.',
    'interpretation':'Current complete published row assumed available. Identical commands do not prove interface connected/charging; all such states remain in cohort. Static reconstruction, no genuine future forecasting or response latency.'},
 'split':{'group':'Exact vehicle+AC/DC+plug_type from indexed metadata, not all source devices pooled as one resource.',
    'rule':'Within each group order whole trials by first/min raw epoch, tie by member. Earliest floor(n/2) train, all remaining test; all15 groups retained. Require disjoint chronological trial ranges train max<test min before errors; fail explicitly if not. No row random split.',
    'provenance':'Entire source archive has historical use and QA values seen; this is new frozen model comparison on existing observations, not blind or independent new-data confirmation.'},
 'models':{'B_SET':'Prediction=u (directly equating common setpoint with grid draw),0 fit.',
    'M_CAP':'Prediction=min(u,c_g),one c>=0 per vehicle/mode/plug group, c<=maximum training command. c is a training-fitted mapping breakpoint, NOT physical maximum or guaranteed acceptance.',
    'fit':'Minimise squared kW error in training, weighting each experiment equally (each row weight1/n_valid_trial). Enumerate command breakpoints and interval weighted target means clipped within interval; choose minimum objective, tie largest c. No offset/gain/SOC/state/online refit or tuning.',
    'paper_relation':'Motivated by charging acceptance/limits and Esser reported setpoint-vs-output nonlinearity. This one-breakpoint study baseline is our simplification, not precise reproduction of the paper SOC regressions.'},
 'evaluation':{'primary':['test pooled MAE_kW','test pooled RMSE_kW'],'positive':'Both lower than B_SET overall AND within each of AC and DC, with nonempty test in both; this is relative evidence only.',
    'mandatory':['all15 groups','every test trial','experiment equal means','coverage/all exclusion causes','negative actual and prediction counts','bias/p95/worst/source context','command0 and command>0 groups','out-of-training-command-range counts'],
    'no_absolute_claim':'No absolute task tolerance established; no conversion to90percent success or dispatch reliability. Rows are correlated points, not independent instruction events.',
    'on_failure':'Retain failure and original criteria, do not change warmup/gap/common-command cohort/model/fitting after errors.'},
 'reproducibility':'Before fit create immutable sample/coverage/admission hashes; deterministic replay, independent raw pandas and separate clock/model-fit/metrics calculations; only publish final kernel if supported with limitations.',
 'unverified':['official STATE/ConnectorType enum mapping','dataset license separate from article','actual network arrival/physical clock/dynamic delays','charging state or reason for limited draw','SOC accuracy/efficiency','departure/demand/authorization','available maximum/shiftable energy/firm capacity','station shared network constraints','V2G capability or willingness','independent site/vehicle validation','103 official90percent']}
dump(protocol,p);dump(BASE/'common_command_mapping_freeze_v1.json',{'protocol_sha256':sha(protocol),'date':'2026-10-16','before_mapping_fit_and_errors':True})
print(sha(protocol))
