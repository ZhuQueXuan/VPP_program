"""Freeze one simple temperature prediction test before fit/error calculations."""
from common import *
from datetime import datetime,timezone
dest=BASE/'temperature_protocol_v1.json';assert not dest.exists()
qa=BASE/'runs/PLEIA_SOURCE_QA_01'
sources={p.name:{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in (BASE/'downloads/PLEIA_METADATA_01/pleia_record.json',qa/'summary.json',qa/'relations_quality.json',BASE/'runs/PLEIA_SOURCE_VERIFY_01/verification.json')}
for p in sorted((BASE/'downloads/PLEIA_RAW_01/selected_raw').iterdir()):
    if p.name!='MU62_dm.txt':sources[p.name]={'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)}
protocol={'date':'2026-10-16','decision':'D059','frozen_utc':datetime.now(timezone.utc).isoformat(),
 'question':'One-step next approximately10minute recorded room temperature, using current/prior room observations and last historical HVAC record. Not physical response to an imposed control change.',
 'sources':sources,'object':'All rooms with exactly one unique mapped sensor and one uniquely room-assigned terminal, with actual records.36schema candidates. No outcome-based room choice.',
 'clock':'Building explicit offsets decoded to UTC. Raw per-device order is descending; reverse it using descending original source row, never repair inversions. Require original three adjacent sensor records strictly chronological, unique per id/time. No averaging/dedup/fill/interpolation.',
 'sample':'Previous/current/next original sensor observations with both adjacent spacings540000..660000ms inclusive. All3temperatures finite0..60C (broad quality screen, not comfort). Target is next observed temperature at its published timestamp, not exact fixed10minute physical forecast. Do not use future spacing/clock/control as predictor.',
 'HVAC':'Latest timestamp not later than current sensor time, age0..600000ms inclusive. Count all raw duplicates; if latest key has>1row, reject without falling back. State0or1, mode0/1/2, on-state only mode1or2; setpoint finite5..40C. Filters prespecified quality/study restrictions, not universal comfort/IEC definitions. Current last state assumed available at source timestamp, not verified real online availability.',
 'split':{'training':'origin>=2021-01-01T00:00:00UTC and target<2021-09-01T00:00:00UTC',
          'test':'origin>=2021-09-01T00:00:00UTC and target<2022-01-01T00:00:00UTC',
          'minimum_per_room':{'training':1000,'test':1000},'reason':'Fixed chronological full seasonal blocks; no random adjacent-point split. Same rooms/site, not independent-site validation. Training and test target intervals disjoint; preceding historical observations may be available across cut.'},
 'models':{'B_P':'T_current','B_TREND':'T_current+(T_current-T_previous), no future interval feature',
  'M_ARX':'T_current + beta dot [1, T_current-T_previous, heating_on*(setpoint-T_current), cooling_on*(setpoint-T_current), heating_on, cooling_on]',
  'fit':'6coefficients per room, np.linalg.lstsq training only, rcond1e-12. No standardisation, regularisation, clipping, routing, tuning or outcome-based predictor/room selection. Coefficients statistical, not physical heat capacity/COP.'},
 'success':'Primary M_ARX versus B_P pooled and room-equal mean MAE/RMSE all strictly lower, and on-state pooled MAE/RMSE strictly lower; >=half eligible rooms both improve. Secondary B_TREND fully reported, not switched after scores. Failure retained, not tuning on same held-out labels.',
 'reports':['all rows and overlapping exclusion flags','all eligible/excluded rooms','pooled, room-equal and every room','on/off and heating/cooling/off groups','calendar month','MAE/RMSE/bias/max','worst errors and unavailable outputs'],
 'not_verified':['single-unit electrical power or capacity','causal control response/end-to-end latency','user comfort bounds/authorization/occupancy','weather synchronization','independent site/entity generalization','long recursive forecasts','P1/103formal90percent'],
 'no_advanced_branch':True}
dump(dest,protocol);dump(BASE/'temperature_freeze_v1.json',{'protocol_sha256':sha(dest),'before_sample_fit_or_errors':True,'script_sha256':sha(Path(__file__))})
print('protocol',sha(dest))
