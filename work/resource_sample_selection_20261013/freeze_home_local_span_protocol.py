"""Freeze one four-event, retrospective, gap-safe candidate before computing new integrals."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'home_capacity_local_span_protocol_v1.json'
LOCAL=ROOT/'downloads/rwth_home_local_span_20261014'
if OUT.exists(): raise FileExistsError(OUT)
LOCAL.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((ROOT/'home_capacity_sample_protocol_v1.json').read_text('utf-8'))
specs=[('home_capacity_sample_protocol_v1.json','BL_HOME_CAP_20261014_01'),
       ('home_capacity_crossperiod_protocol_v2.json','BL_HOME_CROSS_20261014_01'),
       ('home_capacity_crossperiod_protocol_v3.json','BL_HOME_THIRD_20261014_01'),
       ('home_capacity_crossperiod_protocol_v4.json','BL_HOME_FOURTH_20261014_01')]
events=[]
for name,old_run in specs:
    path=ROOT/name; p=json.loads(path.read_text('utf-8'))
    assert p['rest_proxy']==base['rest_proxy'] and p['pairing']==base['pairing']
    if 'relative_path' in p['source']:
        sources=[{'path':p['source']['relative_path'],'sha256':p['source']['sha256']}]
    else:
        admission=ROOT/p['source']['relative_directory']/p['source']['admission_receipt']
        sources=json.loads(admission.read_text('utf-8'))['source_members']
    for s in sources:
        if sha(ROOT/s['path'])!=s['sha256']: raise ValueError('source changed')
    if sha(ROOT/p['reference']['relative_path'])!=p['reference']['sha256']: raise ValueError('reference changed')
    old=ROOT/'home_capacity_baseline_runs'/old_run
    events.append({'sample_id':p['sample']['sample_id'],'prior_protocol_file':name,'prior_protocol_sha256':sha(path),
        'information':p['information'],'source_members':sources,'reference':p['reference'],
        'old_baseline_run':old_run,'old_prediction_sha256':sha(old/'predictions.csv'),'old_metric_sha256':sha(old/'metrics.csv')})
p={'protocol_id':'RWTH-HOME-ID01-LOCAL-SPAN-v1','data_card_version':'DC-20261014-12','date':'2026-10-14',
   'frozen_at_utc':datetime.now(timezone.utc).isoformat(),
   'purpose':'four already-seen controlled tests, retrospective comparison of same-block complete historical proxy with original full-window proxy and metadata baselines',
   'design_usage':'all reference values and old scores seen; 2019 gap structure and one unintegrated endpoint pair seen; NOT independent or blind confirmation',
   'source_metadata':{k:base['source'][k] for k in ('system_id','series_cells','nominal_capacity_ah','nominal_energy_kwh','datasheet_usable_energy_kwh')},
   'rest_proxy':base['rest_proxy'],'inherited_pairing':base['pairing'],'events':events,
   'changed_rules':{
       'history_gate':'allow incomplete fixed history; partition by native time difference!=1 second; do not resample or extend any original history window',
       'gap_reset':'clear rest tail and pending high at every time gap; no pair crosses a gap',
       'left_censoring':'first rest run of an observed block beginning at its first row has unknown physical onset; record but exclude its anchor from pairing, including at window start; keep all excluded records',
       'pair_quality':'both eligible anchors in same block; all rows high through low inclusive finite and Interpolated=0, consecutive native seconds; net I and UI both strictly positive',
       'pair_selection':'latest eligible low then high by native time, across all observed blocks; no reference value or prediction error used; no preferred event or block',
       'integral':'same left rectangle [high,low), -sum(I)/3600 Ah and -sum(I*U)/3600000 kWh; charging retained; no unseen drain/OCV/efficiency correction',
       'age':'report low-to-history-cutoff and low-to-test age seconds/days; no fitted or invented freshness cutoff; old spans remain historical proxies, not current capability',
       'unavailable':'retain event/model/output and explicit reason, no nominal fallback or dropping failed cases'},
   'comparison':{'models':['B_NOM','B_DS','B_HIST_SPAN','B_LOCAL_SPAN'],
       'old_models':'copy only exact frozen previous predictions after new features exist; recompute their metrics against matching original published XLSX labels; preserve original missing status',
       'new_model':'B_LOCAL_SPAN uses newly frozen latest eligible same-block span; fit none',
       'outputs':['capacity_Ah','energy_kWh'],
       'metrics':['signed_error','absolute_error','absolute_error_percent_of_reference'],
       'reporting':'per event and output, all 32 rows incl unavailable; number of events with predictions separately, no posthoc averaged score or accuracy claim'},
   'verification':{'repeat_artifact_hash_equal':True,'raw_independent_rebuild_all_blocks_rests_anchors_pairs_selection':True,'original_XLSX_labels_and_all_32_predictions_metrics':True,'integral_prediction_metric_absolute_tolerance':1e-9,'voltage_absolute_tolerance':1e-12},
   'no_search':'no threshold, age cutoff, history extension, exclusion or parameter search after new score; changes need new protocol',
   'scope':'one system, shared measurement chain, voltage proxy not true full SOC or VPP maximum; no proof of stable superiority or 90% goal'}
OUT.open('x',encoding='utf-8',newline='\n').write(json.dumps(p,ensure_ascii=False,indent=2))
preserved={str((ROOT/'home_capacity_baseline_runs'/e['old_baseline_run']/n).relative_to(ROOT)):sha(ROOT/'home_capacity_baseline_runs'/e['old_baseline_run']/n) for e in events for n in ('predictions.csv','metrics.csv')}
for name,_ in specs: preserved[name]=sha(ROOT/name)
for n in ('work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md','outputs/课题一_锂离子储能单体特性研究样板_v1_20261014.md'):
    preserved[str((ROOT.parent.parent/n).resolve())]=sha(ROOT.parent.parent/n)
(LOCAL/'freeze_receipt_01.json').open('x',encoding='utf-8').write(json.dumps({'protocol_sha256':sha(OUT),'event_count':4,'status':'frozen_before_new_local_integrals_or_scores','preserved_files':preserved},ensure_ascii=False,indent=2))
print(json.dumps({'protocol_sha256':sha(OUT),'events':4,'new_integrals_or_scores_computed':False},ensure_ascii=False))
