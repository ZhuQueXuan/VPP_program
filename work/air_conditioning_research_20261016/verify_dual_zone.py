"""Independent pandas raw clock/windows, explicitSVD and scalar forecast metrics."""
from common import *
import math,numpy as np,pandas as pd,collections
from datetime import datetime
run=BASE/'runs/BL_DUAL_ZONE_01';vp=run/'verification.json';assert not vp.exists()
p=load(BASE/'dual_zone_protocol_v1.json');ad=BASE/'runs/PREP_DUAL_ZONE_01';stored={(r['file'],int(r['zone']),int(r['row'])):r for r in read(ad/'candidates.csv')}
data=[];flagschecked=0;fieldchecks=0
def check(a,b,key=''):
    global fieldchecks
    fieldchecks+=1
    if a is None:assert b in ('',None),(key,a,b)
    elif isinstance(a,bool):assert str(a)==str(b),(key,a,b)
    elif isinstance(a,(int,float)):assert math.isclose(a,float(b),rel_tol=2e-12,abs_tol=2e-9),(key,a,b)
    else:assert str(a)==str(b),(key,a,b)
for name,source in p['sources'].items():
    fp=ROOT/source['path'];assert sha(fp)==source['sha256'];d=pd.read_csv(fp);times=pd.to_datetime(d['Timestamp'],format='%Y-%m-%d %H:%M');n=len(d)
    assert n==288 and times.is_unique and bool((times.diff().iloc[1:]==pd.Timedelta(seconds=300)).all())
    day=int(name.split('Day')[1].split('(')[0]);split='training' if day<=4 else 'test'
    for zone in (1,2):
        tn=d[f"Room{zone}'s Indoor air temperature (°C)"]
        vectors={'T_prev_C':tn.shift(1),'T_now_C':tn,'Tout_C':d['Outdoor temperature (°C)'],'P_now_W':d[f"Room{zone}'s power consumption (W)"],'T_other_C':d[f"Room{3-zone}'s Indoor air temperature (°C)"],'target_T_C':tn.shift(-1)}
        finite=pd.DataFrame(vectors).apply(np.isfinite).all(axis=1)
        validtemp=pd.DataFrame({k:v.between(0,60) | v.isna() for k,v in vectors.items() if k!='P_now_W'}).all(axis=1)
        for i in range(n):
            row=stored[(name,zone,i+1)];missing=i in (0,n-1)
            expected={'missing_window':missing,'clock_invalid':False,'nonfinite':not bool(finite.iloc[i]),'temperature_QC':not bool(validtemp.iloc[i]),'admitted':not missing and bool(finite.iloc[i]) and bool(validtemp.iloc[i])}
            for k,v in expected.items():check(v,row[k],k);flagschecked+=1
            for k,v in vectors.items():check(float(v.iloc[i]) if pd.notna(v.iloc[i]) else None,row[k],k)
            check(times.iloc[i].isoformat(),row['timestamp']);check(split,row['split']);check(day,int(row['day']))
            check(times.iloc[i+1].isoformat() if i<n-1 else '',row['target_timestamp'])
            if expected['admitted']:data.append({'file':name,'zone':zone,'row':i+1,'day':day,'split':split,**{k:float(v.iloc[i]) for k,v in vectors.items()}})
assert len(stored)==4608 and len(data)==4576
cal=load(run/'calibration.json');params=cal['parameters']['rooms'];svdmax=0.;ranks={}
def features(r):return [1.,r['T_now_C']-r['T_prev_C'],r['Tout_C']-r['T_now_C'],r['P_now_W']/1000.,r['T_other_C']-r['T_now_C']]
coefs={}
for zone in (1,2):
    rows=[r for r in data if r['split']=='training' and r['zone']==zone];counts=collections.Counter(r['file'] for r in rows)
    x=np.array([features(r) for r in rows]);y=np.array([r['target_T_C']-r['T_now_C'] for r in rows]);w=np.sqrt(np.array([1/counts[r['file']] for r in rows]))
    u,s,vt=np.linalg.svd(x*w[:,None],full_matrices=False);keep=s>1e-12*s[0];beta=vt[keep].T@((u[:,keep].T@(y*w))/s[keep]);coefs[zone]=beta
    diff=float(max(abs(beta-np.array(params[str(zone)]['coefficients']))));svdmax=max(svdmax,diff);assert diff<2e-9
    ranks[str(zone)]=int(keep.sum());assert int(keep.sum())==cal['fits'][str(zone)]['rank']
    for k,lohi in params[str(zone)]['input_ranges'].items():check(min(r[k] for r in rows),lohi[0]);check(max(r[k] for r in rows),lohi[1])
pred={(r['file'],int(r['zone']),int(r['row'])):r for r in read(run/'predictions.csv')};test=[];predmax=0.
for r in data:
    if r['split']!='test':continue
    r=dict(r);r['B_P']=r['T_now_C'];r['B_TREND']=2*r['T_now_C']-r['T_prev_C'];r['M_HEAT5']=r['T_now_C']+math.fsum(float(c)*v for c,v in zip(coefs[r['zone']],features(r)))
    storedrow=pred[(r['file'],r['zone'],r['row'])]
    for k in ['B_P','B_TREND','M_HEAT5']:
        delta=abs(r[k]-float(storedrow[k]));predmax=max(predmax,delta);assert delta<2e-9
    ranges=params[str(r['zone'])]['input_ranges'];outside=any(not ranges[k][0]<=r[k]<=ranges[k][1] for k in ranges)
    check(outside,storedrow['outside_training_input_range']);r['outside']=outside;test.append(r)
assert len(test)==len(pred)==2288
metricchecks=0;metricmax=0.
def verify_group(rows,reference):
    global metricchecks,metricmax
    assert len(rows)==reference['rows']
    fresh={}
    for model in ['B_P','B_TREND','M_HEAT5']:
        e=[r[model]-r['target_T_C'] for r in rows];n=len(e)
        fresh[model]={'MAE_C':math.fsum(abs(v) for v in e)/n,'RMSE_C':math.sqrt(math.fsum(v*v for v in e)/n),'bias_C':math.fsum(e)/n,'max_abs_C':max(abs(v) for v in e)}
        for k,v in fresh[model].items():delta=abs(v-reference[model][k]);assert delta<2e-9;metricmax=max(metricmax,delta);metricchecks+=1
    improved=all(fresh['M_HEAT5'][k]<fresh[b][k] for b in ['B_P','B_TREND'] for k in ['MAE_C','RMSE_C'])
    assert improved==reference['improves_both_baselines'];return improved
m=load(run/'metrics.json');allpass=verify_group(test,m['groups']['all']);active=verify_group([r for r in test if r['P_now_W']>0],m['groups']['current_positive_P']);verify_group([r for r in test if r['P_now_W']==0],m['groups']['current_zero_P'])
roompass=[verify_group([r for r in test if r['zone']==g['zone']],g) for g in m['rooms']]
daypass=[verify_group([r for r in test if r['day']==g['day']],g) for g in m['days']]
for g in m['daily_rooms']:verify_group([r for r in test if r['day']==g['day'] and r['zone']==g['zone']],g)
success=allpass and active and all(roompass) and sum(daypass)>=2;summary=load(run/'summary.json');assert success==summary['predeclared_relative_success'];assert sum(r['outside'] for r in test)==summary['out_of_training_range_rows']
repeat=BASE/'runs/BL_DUAL_ZONE_02';receipt=load(run/'receipt.json');same={n:sha(repeat/n)==h for n,h in receipt['outputs'].items()};assert all(same.values())
result={'status':'passed','raw_rows':2304,'candidate_room_rows':4608,'admitted_room_rows':4576,'independent_flag_checks':flagschecked,'independent_field_checks':fieldchecks,'explicit_SVD_coefficient_max_difference':svdmax,'training_ranks':ranks,'all_test_predictions_checked':len(test),'prediction_max_difference_C':predmax,'metric_numeric_checks':metricchecks,'metric_max_difference_C':metricmax,'predeclared_relative_success':bool(success),'replay_equal':same,'source_clock_parser':'pandas vector/shift, versus stdlib source-order windows preparer','not_new_physical_experiment_or_independent_site':True,'verifier_sha256':sha(Path(__file__)),'protocol_sha256':sha(BASE/'dual_zone_protocol_v1.json')}
dump(vp,result);print(json.dumps(result,ensure_ascii=False,indent=2))
