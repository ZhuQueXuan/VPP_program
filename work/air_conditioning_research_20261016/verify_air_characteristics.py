"""Independent pandas/NumPy counts, quantiles, every pair and every plotted value."""
from common import *
import pandas as pd,numpy as np,math,collections
run=BASE/'runs/CHAR_AIR_01';out=run/'verification.json';assert not out.exists()
s=load(run/'characteristics.json');p=load(BASE/'air_characteristic_protocol_v1.json');numeric=0;maxdiff=0.
def equal(a,b):
    global numeric,maxdiff
    if isinstance(a,dict):
        for k,v in a.items():equal(v,b[k])
    elif isinstance(a,(int,float)) and not isinstance(a,bool):
        numeric+=1;maxdiff=max(maxdiff,abs(float(a)-float(b)));assert math.isclose(float(a),float(b),rel_tol=2e-12,abs_tol=2e-10),(a,b)
    else:assert a==b,(a,b)
frames={name:pd.read_csv(ROOT/src['path']) for name,src in p['sources'].items()}
for g in s['room_day_summaries']:
    d=frames[g['file']];room=g['room'];t=d[f"Room{room}'s Indoor air temperature (°C)"].to_numpy();power=d[f"Room{room}'s power consumption (W)"].to_numpy();dt=np.diff(t)
    equal({'labels':len(t),'adjacent_pairs':len(dt),'temperature_C':{'min':float(t.min()),'max':float(t.max()),'mean':float(t.mean())},'reported_power_W':{'min':float(power.min()),'max':float(power.max()),'mean':float(power.mean())},'positive_power_labels':int((power>0).sum()),'zero_power_labels':int((power==0).sum()),'temperature_increments':{'warming':int((dt>0).sum()),'cooling':int((dt<0).sum()),'unchanged':int((dt==0).sum()),'min_C_per_min':float(dt.min()/5),'max_C_per_min':float(dt.max()/5),'signed_quantiles_C_per_min':{str(q):float(np.quantile(dt,q,method='linear')/5) for q in [.05,.5,.95]},'absolute_quantiles_C_per_min':{str(q):float(np.quantile(abs(dt),q,method='linear')/5) for q in [.05,.5,.95]}}},g)
    a=power[:-1]>0;b=power[1:]>0
    pattern={'zero->zero':int((~a&~b).sum()),'zero->positive':int((~a&b).sum()),'positive->zero':int((a&~b).sum()),'positive->positive':int((a&b).sum())};equal(pattern,g['reported_power_pair_patterns'])
pairs=read(run/'adjacent_pairs.csv');assert len(pairs)==4592
keys=set()
for row in pairs:
    key=(row['file'],int(row['room']),int(row['start_row']));assert key not in keys;keys.add(key)
    d=frames[key[0]];i=key[2]-1;room=key[1];temp=f"Room{room}'s Indoor air temperature (°C)";power=f"Room{room}'s power consumption (W)"
    equal(float(d[temp].iloc[i+1]-d[temp].iloc[i]),float(row['temperature_increment_C']))
    assert int(row['end_row'])==i+2
    assert pd.Timestamp(d['Timestamp'].iloc[i]).isoformat()==row['start_timestamp'];assert pd.Timestamp(d['Timestamp'].iloc[i+1]).isoformat()==row['end_timestamp']
    expected=('positive' if d[power].iloc[i]>0 else 'zero')+'->'+('positive' if d[power].iloc[i+1]>0 else 'zero');assert row['reported_power_pattern']==expected
pred=read(BASE/'runs/BL_DUAL_ZONE_01/predictions.csv');plook={(r['file'],int(r['zone']),r['target_timestamp']):float(r['M_HEAT5']) for r in pred}
plot=BASE/'runs/AIR_CURVES_01';pv=read(plot/'plotted_values.csv');assert len(pv)==2304
plotkeys=set();forecastcount=0
for r in pv:
    k=(r['file'],int(r['room']),r['source_timestamp']);assert k not in plotkeys;plotkeys.add(k);d=frames[k[0]];i=int(pd.Timestamp(k[2]).hour*12+pd.Timestamp(k[2]).minute//5)
    assert pd.Timestamp(d['Timestamp'].iloc[i]).isoformat()==k[2]
    equal(float(d[f"Room{k[1]}'s Indoor air temperature (°C)"].iloc[i]),float(r['measured_T_C']));equal(float(d[f"Room{k[1]}'s power consumption (W)"].iloc[i]),float(r['reported_P_W']))
    if k in plook:equal(plook[k],float(r['forecast_at_this_target_time_C']));forecastcount+=1
    else:assert r['forecast_at_this_target_time_C']==''
assert forecastcount==2288 and len(plotkeys)==2304
repeat=BASE/'runs/CHAR_AIR_02';rec=load(run/'receipt.json');same={n:sha(repeat/n)==h for n,h in rec['outputs'].items()};assert all(same.values())
plotrec=load(plot/'receipt.json');assert all(sha(plot/n)==h for n,h in plotrec['outputs'].items())
equal(sum(g['labels'] for g in s['room_day_summaries']),s['total_room_labels']);equal(sum(g['adjacent_pairs'] for g in s['room_day_summaries']),s['total_adjacent_room_pairs'])
result={'status':'passed','room_day_summaries_checked':16,'all_adjacent_pairs_checked':4592,'all_plotted_source_room_labels_checked':2304,'all_forecasts_target_time_checked':forecastcount,'numeric_checks':numeric,'max_numeric_difference':maxdiff,'characteristic_two_artifacts_replay_equal':same,'visual_review':'PNG manually inspected by assistant:8panels, readable source/target-time labels, no overlapping legends or clipped curves; power proxy caveat/source attribution visible. SVGsamefigure exported, not separately browser-rendered.','not_control_or_independent_forecast_evidence':True,'verifier_sha256':sha(Path(__file__)),'protocol_sha256':sha(BASE/'air_characteristic_protocol_v1.json')}
dump(out,result);print(json.dumps(result,ensure_ascii=False,indent=2))
