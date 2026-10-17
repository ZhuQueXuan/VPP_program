"""Independent stdlib raw CSV/datetime and nearest-event bisect verification."""
from common import *
import math,bisect,datetime,collections
run=BASE/'runs/HIL_DIAGNOSTIC_01';vp=run/'verification.json';assert not vp.exists()
summary=load(run/'summary.json');protocol=load(BASE/'hil_diagnostic_protocol_v1.json');cal=load(BASE/'runs/BL_HIL_POWER_01/calibration.json')['parameters']
flags=collections.defaultdict(list)
for r in read(run/'row_flags.csv'):flags[r['file']].append((int(r['row']),r['near_jump']=='True'))
jumpoutput=load(run/'jumps.json');count=0;numeric=0;maxdiff={};testdata=[];eventcount=0
def compare(a,b,key=''):
    global numeric
    if isinstance(a,dict):
        for k in a:compare(a[k],b[k],k)
    elif isinstance(a,(int,float)) and not isinstance(a,bool):
        numeric+=1;assert math.isclose(a,b,rel_tol=2e-12,abs_tol=2e-8),(key,a,b)
        maxdiff[key]=max(maxdiff.get(key,0.),abs(a-b))
    else:assert a==b,(key,a,b)
def statistics(data):
    obj={}
    groups={'all':lambda r:True,'within_60s_of_observed_jump':lambda r:r[3],'other_rows':lambda r:not r[3],'Q_le0_and_Ptotal_ge1000W':lambda r:r[4]<=0 and r[0]>=1000}
    for g,selector in groups.items():
        chosen=[r for r in data if selector(r)];obj[g]={}
        for model,idx in [('B_COP',1),('M_TEMP',2)]:
            error=[r[idx]-r[0] for r in chosen];allerror=[r[idx]-r[0] for r in data]
            sae=math.fsum(abs(x) for x in error);sse=math.fsum(x*x for x in error)
            obj[g][model]={'rows':len(error),'MAE_W':sae/len(error) if error else None,'RMSE_W':math.sqrt(sse/len(error)) if error else None,'SAE_W':sae,'SSE_W2':sse,'row_share':len(error)/len(data),'SAE_share':sae/math.fsum(abs(x) for x in allerror),'SSE_share':sse/math.fsum(x*x for x in allerror)}
    return obj
oldpred={(r['file'],int(r['row'])):r for r in read(BASE/'runs/BL_HIL_POWER_01/predictions.csv')};predmax=0.;context_expected=[]
for table in summary['files']:
    name=table['file'];raw=read(ROOT/protocol['sources'][name]['path']);n=len(raw)
    times=[datetime.datetime.fromisoformat(r['TimeStamp']) for r in raw];assert all((b-a).total_seconds()==1 for a,b in zip(times,times[1:]))
    outer=[float(r['Outdoor Unit Power (W)']) for r in raw]
    events=[i for i in range(1,n) if abs(outer[i]-outer[i-1])>=500]
    eventcount+=len(events);assert len(events)==table['observed_jumps']
    actual=[r for r in jumpoutput if r['file']==name]
    for i,r in zip(events,actual):compare({'row':i+1,'timestamp':raw[i]['TimeStamp'],'delta_outer_W':outer[i]-outer[i-1],'window_clipped':i<60 or i+60>=n},{k:r[k] for k in ('row','timestamp','delta_outer_W','window_clipped')})
    assert len(actual)==len(events)
    assert table['upward']==sum(outer[i]-outer[i-1]>=500 for i in events)
    assert table['downward']==sum(outer[i]-outer[i-1]<=-500 for i in events)
    assert table['clipped_jump_windows']==sum(i<60 or i+60>=n for i in events)
    data=[]
    for i,r in enumerate(raw):
        k=bisect.bisect_left(events,i)
        near=any(abs(i-events[j])<=60 for j in (k-1,k) if 0<=j<len(events))
        assert flags[name][i]==(i+1,near);count+=1
        q=float(r['Cooling Capacity (kW)']);t=float(r['T_Outdoor (C)']);y=outer[i]+float(r['Indoor Unit Power (W)'])
        bc=cal['B_COP'][0]+cal['B_COP'][1]*q;mt=cal['M_TEMP'][0]+q*(cal['M_TEMP'][1]+cal['M_TEMP'][2]*(t-35))
        data.append((y,bc,mt,near,q))
        if table['split']=='test':
            old=oldpred[(name,i+1)];predmax=max(predmax,abs(bc-float(old['B_COP'])),abs(mt-float(old['M_TEMP'])));assert predmax<2e-8
        if 'OAT85F_' in name and 492<=i<853:context_expected.append((i+1,r,y,bc,mt))
    compare(statistics(data),table['groups'])
    if table['split']=='test':testdata.extend(data)
assert len(testdata)==len(oldpred)==130256;assert count==341639
compare(statistics(testdata),summary['pooled_old_test'])
context=read(run/'worst_context.csv');assert len(context)==len(context_expected)==361
for got,(i,r,y,bc,mt) in zip(context,context_expected):
    assert int(got['data_row'])==i
    for k,v in r.items():
        if k=='TimeStamp':assert got[k]==v
        else:compare(float(v),float(got[k]),'context_source_numeric')
    for k,v in [('total_electric_W',y),('fixed_B_COP_W',bc),('fixed_M_TEMP_W',mt)]:compare(v,float(got[k]),k)
# The one complete SplitSmart CSV gets a second, pandas-based parser/clock check.
import pandas as pd,numpy as np
sp=BASE/'downloads/SPLITSMART_PREVIEW_01/dataC108AC01.csv';df=pd.read_csv(sp);audit=load(BASE/'runs/SPLITSMART_QA_02/summary.json');assert len(df)==audit['rows']==1092
tt=pd.to_datetime(df['Time_Stamp'],format='ISO8601',utc=True);dt=tt.diff().dt.total_seconds().iloc[1:]
assert int((dt<0).sum())==audit['backward']==88 and int((dt==0).sum())==audit['adjacent_duplicate']==0
compare(float(dt.median()),audit['interval_median_s'],'interval_median_s');compare(float(dt.min()),audit['interval_min_s'],'interval_min_s');compare(float(dt.max()),audit['interval_max_s'],'interval_max_s')
for field,expected in audit['numeric_fields'].items():
    v=pd.to_numeric(df[field],errors='coerce');finite=v[np.isfinite(v)]
    assert len(finite)==expected['finite_numeric'] and int(finite.nunique())==expected['distinct_finite']
    if len(finite):compare(float(finite.min()),expected['min'],field+'_min');compare(float(finite.max()),expected['max'],field+'_max')
assert df['Real_Power'].isna().all();assert int(df['room_temp'].nunique())==3
replay=BASE/'runs/HIL_DIAGNOSTIC_02';r=load(run/'receipt.json');same={n:sha(replay/n)==h for n,h in r['outputs'].items()};assert all(same.values())
result={'status':'passed','raw_HIL_rows_and_flags_checked':count,'observed_jump_rows_checked':eventcount,'old_test_predictions_unchanged_checked':len(oldpred),'max_prediction_difference_W':predmax,'numeric_checks':numeric,'max_numeric_differences_by_field':maxdiff,'worst_context_original_rows_checked':361,'SplitSmart_independent_full_file_rows':len(df),'SplitSmart_real_power_all_missing_verified':True,'SplitSmart_room_temperature_3_distinct_verified':True,'replay_equal':same,'scope':'Independent CSV/clock/window aggregation and algebra verification, not new physical observations or blind validation.','verifier_sha256':sha(Path(__file__)),'protocol_sha256':sha(BASE/'hil_diagnostic_protocol_v1.json')}
dump(vp,result);print(json.dumps(result,ensure_ascii=False,indent=2))
