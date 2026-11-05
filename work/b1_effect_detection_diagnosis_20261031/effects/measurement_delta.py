"""Describe revised-vs-CPOP measurement changes without causal attribution."""
from pathlib import Path
import json
import pandas as pd
import numpy as np
P=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
ev=pd.read_csv(P/'event_measurement.csv');event_rows=[];curve_rows=[]
for scenario in ('positive','zero'):
 g=ev[(ev.scenario==scenario)&ev.label.isin(['ride_revised_duration','cpop_duration'])]
 wide=g.pivot(index=['seed','task_id'],columns='label',values=['measured','error','dose'])
 delta=wide['measured'].ride_revised_duration-wide['measured'].cpop_duration
 event_rows.append(dict(scenario=scenario,events=len(delta),mean_delta=float(delta.mean()),
    rms_delta=float(np.sqrt(np.mean(delta**2))),centered_rms_delta=float(delta.std(ddof=0)),
    correlation_delta_dose=float(np.corrcoef(delta,wide['dose'].cpop_duration)[0,1]),
    mean_event_absolute_error_improvement=float((abs(wide['error'].ride_revised_duration)-abs(wide['error'].cpop_duration)).mean())))
 for seed in range(7240200,7240208):
  a=read(P/f'fits/{seed}_{scenario}_ride_revised_duration.json')['causal_curve']
  b=read(P/f'fits/{seed}_{scenario}_cpop_duration.json')['causal_curve']
  m=np.array(a['mean_outcomes'])-b['mean_outcomes'];c=np.array(a['contrasts'])-b['contrasts']
  assert np.max(abs(c-(m-m[2])))<1e-10
  curve_rows.append(dict(seed=seed,scenario=scenario,mean_curve_delta_rms=float(np.sqrt(np.mean(m*m))),
    mean_curve_delta_average=float(m.mean()),reference_delta=float(m[2]),
    contrast_curve_delta_rms=float(np.sqrt(np.mean(c*c))),centered_mean_curve_delta_rms=float(m.std())))
result=dict(schema='b1.measurement-delta-diagnosis.v1',event_deltas=event_rows,curve_deltas=curve_rows,
    interpretation='A constant mean shift cancels exactly in contrasts, but observed revised-vs-CPOP changes are heterogeneous; low dose correlation does not prove most improvement is a constant or a causal mechanism.')
(P/'measurement_delta.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
pd.DataFrame(curve_rows).to_csv(P/'measurement_delta.csv',index=False,encoding='utf-8-sig')
print(json.dumps(event_rows,ensure_ascii=False))
