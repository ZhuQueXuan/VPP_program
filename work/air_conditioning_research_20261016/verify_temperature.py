"""Independent original CSV sample/time join and SVD fit/metrics checks."""
from common import *
import sys,math
from datetime import datetime
from collections import defaultdict,Counter
sys.path.insert(0,str(ROOT/'work/python_packages/pv_metadata_20261015'))
import duckdb,numpy as np
prep=BASE/'runs/PREP_TEMPERATURE_01';run=BASE/'runs/BL_TEMPERATURE_02';repeat=BASE/'runs/BL_TEMPERATURE_03'
dest=run/'verification.json';assert not dest.exists()
rooms=load(prep/'room_coverage.json');assert len(rooms)==36 and all(r['admitted_room'] for r in rooms)
raw=BASE/'downloads/PLEIA_RAW_01/selected_raw';sids={r['sensor_id'] for r in rooms};hids={r['hvac_id'] for r in rooms}
sdata=defaultdict(list);hdata=defaultdict(list)
for name,selected,target in [('data-sensor.csv',sids,sdata),('data-hvac.csv',hids,hdata)]:
    with (raw/name).open(encoding='utf-8-sig',newline='') as f:
        for n,r in enumerate(csv.DictReader(f,delimiter=';'),start=1):
            uid=int(r['IDdevice'])
            if uid not in selected:continue
            t=int(round(datetime.fromisoformat(r['Date']).timestamp()*1000))
            values=(n,t,float(r['V2'])) if name=='data-sensor.csv' else (n,t,float(r['V4']),float(r['V5']),float(r['V12']))
            target[uid].append(values)
    print('independent parsed',name,sum(map(len,target.values())),flush=True)
con=duckdb.connect();con.execute("SET memory_limit='768MB'");con.execute('SET threads=2')
parameters={(r['block'],r['room']):r for r in load(run/'calibration.json')['rooms']}
candidate_checks=0;prediction_checks=0;numeric_checks=0;maxcoef=0.;maxpred=0.;frames=[]
flags=['window_missing','sensor_time_ambiguous','cadence_invalid','temperature_invalid','control_unavailable_or_stale','control_time_ambiguous','control_fields_outside_study']
for room in rooms:
    key=(room['block'],room['room']);ss=sdata[room['sensor_id']][::-1];hh=hdata[room['hvac_id']][::-1]
    sr=np.array([r[0] for r in ss]);ts=np.array([r[1] for r in ss],dtype=np.int64);T=np.array([r[2] for r in ss]);N=len(T)
    assert np.all(np.diff(ts)>=0)
    _,inverse,cnt=np.unique(ts,return_inverse=True,return_counts=True);nt=cnt[inverse]
    prev=np.r_[np.nan,T[:-1]];target=np.r_[T[1:],np.nan]
    pt=np.r_[0,ts[:-1]];tt=np.r_[ts[1:],0];pnt=np.r_[0,nt[:-1]];tnt=np.r_[nt[1:],0]
    htime=np.array([r[1] for r in hh],dtype=np.int64);assert np.all(np.diff(htime)>=0)
    _,hi,hc=np.unique(htime,return_inverse=True,return_counts=True);hcount=hc[hi]
    indices=np.searchsorted(htime,ts,side='right')-1;valid=indices>=0;ix=np.maximum(indices,0)
    hs=np.array([r[2] for r in hh])[ix];hm=np.array([r[3] for r in hh])[ix];sp=np.array([r[4] for r in hh])[ix]
    age=ts-htime[ix]
    missing=np.zeros(N,dtype=bool);missing[[0,-1]]=True
    ff={'window_missing':missing,'sensor_time_ambiguous':(nt!=1)|(pnt!=1)|(tnt!=1),
      'cadence_invalid':(ts-pt<540000)|(ts-pt>660000)|(tt-ts<540000)|(tt-ts>660000),
      'temperature_invalid':~(np.isfinite(T)&np.isfinite(prev)&np.isfinite(target)&(T>=0)&(T<=60)&(prev>=0)&(prev<=60)&(target>=0)&(target<=60)),
      'control_unavailable_or_stale':~valid|(age<0)|(age>600000),
      'control_time_ambiguous':~valid|(hcount[ix]!=1),
      'control_fields_outside_study':~(valid&np.isin(hs,[0,1])&np.isin(hm,[0,1,2])&((hs==0)|np.isin(hm,[1,2]))&np.isfinite(sp)&(sp>=5)&(sp<=40))}
    split=np.full(N,'outside_split',dtype=object)
    split[(ts>=1609459200000)&(tt<1630454400000)&~missing]='training'
    split[(ts>=1630454400000)&(tt<1640995200000)&~missing]='test'
    # SQL CASE classifies boundary-missing rows with NULL targets as outside; origin/target comparisons elsewhere unchanged.
    q=(split!='outside_split')
    for f in flags:q=q&~ff[f]
    original=con.execute('SELECT * FROM read_parquet(?) WHERE block=? AND room=? ORDER BY srcrow DESC',[str(prep/'all_candidates.parquet'),*key]).fetchnumpy()
    assert np.array_equal(original['srcrow'],sr)
    for f in flags:
        assert np.array_equal(original[f],ff[f]),(key,f,np.flatnonzero(original[f]!=ff[f])[:5])
        candidate_checks+=N
    # Only quality admission is meaningful for edge rows with missing previous/target observations.
    assert np.array_equal(original['quality_admitted'],q),key
    assert np.array_equal(original['split'][~missing],split[~missing]),key
    X=np.column_stack([np.ones(N),T-prev,((hs==1)&(hm==1))*(sp-T),((hs==1)&(hm==2))*(sp-T),((hs==1)&(hm==1)).astype(float),((hs==1)&(hm==2)).astype(float)])
    train=q&(split=='training');test=q&(split=='test')
    assert int(train.sum())==room['train_rows'] and int(test.sum())==room['test_rows']
    U,S,Vh=np.linalg.svd(X[train],full_matrices=False)
    reciprocal=np.zeros_like(S);good=S>1e-12*S[0];reciprocal[good]=1/S[good]
    beta=Vh.T@(reciprocal*(U.T@(target[train]-T[train])))
    c=np.array(parameters[key]['beta']);maxcoef=max(maxcoef,float(np.max(abs(beta-c))));assert np.allclose(beta,c,rtol=1e-9,atol=1e-9),key
    prediction=np.column_stack([T[test],2*T[test]-prev[test],T[test]+X[test]@beta])
    published=con.execute('SELECT * FROM read_parquet(?) WHERE block=? AND room=? ORDER BY origin_ms',[str(run/'predictions.parquet'),*key]).fetchnumpy()
    assert np.array_equal(published['origin_ms'],ts[test]);assert np.array_equal(published['target_ms'],tt[test])
    assert np.array_equal(published['target_temp'],target[test])
    for j,m in enumerate(('B_P','B_TREND','M_ARX')):
        diff=float(np.max(abs(prediction[:,j]-published[m])));maxpred=max(maxpred,diff);assert diff<1e-8,(key,m,diff)
    prediction_checks+=int(test.sum())
    frames.append({'block':key[0],'room':key[1],'target':target[test],'prediction':prediction,'state':hs[test],'mode':hm[test],
       'month':published['month']})
    print('verified room',key,int(test.sum()),flush=True)

stored=load(run/'metrics.json');maxmetric=0.
def metric_check(records,mask_builder,expected):
    global numeric_checks,maxmetric
    y=np.concatenate([r['target'][mask_builder(r)] for r in records]);pred=np.concatenate([r['prediction'][mask_builder(r)] for r in records])
    assert len(y)==expected['rows']
    computed={}
    for j,m in enumerate(('B_P','B_TREND','M_ARX')):
        errors=(pred[:,j]-y).tolist();n=len(errors)
        vals={'MAE_C':math.fsum(abs(v) for v in errors)/n,'RMSE_C':math.sqrt(math.fsum(v*v for v in errors)/n),
          'bias_C':math.fsum(errors)/n,'max_abs_error_C':max(map(abs,errors))}
        computed[m]=vals
        for k,v in vals.items():
            numeric_checks+=1;diff=abs(v-expected[m][k]);maxmetric=max(maxmetric,diff);assert diff<1e-8,(m,k,diff)
    return computed
room_computed=[]
for r in frames:
    expected=next(x for x in stored['rooms'] if (x['block'],x['room'])==(r['block'],r['room']))
    room_computed.append(metric_check([r],lambda d:np.ones(len(d['target']),dtype=bool),expected))
for group,expected in stored['groups'].items():
    def mask(d):
        if group=='all':return np.ones(len(d['target']),dtype=bool)
        if group=='on':return d['state']==1
        if group=='off' or group=='state:off':return d['state']==0
        if group=='state:on_heating':return (d['state']==1)&(d['mode']==1)
        if group=='state:on_cooling':return (d['state']==1)&(d['mode']==2)
        if group.startswith('month:'):return d['month']==group.split(':')[1]
        raise AssertionError(group)
    metric_check(frames,mask,expected)
for m in ('B_P','B_TREND','M_ARX'):
    for k in ('MAE_C','RMSE_C'):
        value=math.fsum(r[m][k] for r in room_computed)/len(room_computed)
        diff=abs(value-stored['room_equal_mean_metrics'][m][k]);assert diff<1e-8;numeric_checks+=1;maxmetric=max(maxmetric,diff)
replay={n:sha(run/n)==sha(repeat/n) for n in load(run/'receipt.json')['outputs']};assert all(replay.values())
result={'date':'2026-10-16','status':'passed','protocol_sha256':sha(BASE/'temperature_protocol_v1.json'),
 'candidate_sensor_rows':sum(len(v) for v in sdata.values()),'candidate_flag_membership_checks':candidate_checks,
 'test_rows':prediction_checks,'independent_parser':'stdlib original CSV/time vs DuckDB original CSV/time; derived Parquet decoding shared',
 'independent_fit':'explicit thin-SVD reconstruction vs np.linalg.lstsq','maximum_coefficient_difference':maxcoef,
 'maximum_prediction_difference_C':maxpred,'metric_checks':numeric_checks,'maximum_metric_difference_C':maxmetric,
 'replay_artifacts_equal':replay,'verifier_sha256':sha(Path(__file__)),
 'scientific_result':'ARX failed prespecified relative gain; preserve persistence reference and all errors, no refit/tuning on observed held-out data.',
 'limits':'Observed-temperature forecast only, not causal thermal parameters or controllable electrical capacity.'}
dump(dest,result);print(json.dumps(result,ensure_ascii=False,indent=2))
