"""Independent original ZIP/pandas reconstruction and centred-moment algebra.

Does not import prepare/run/kernel functions. This verifies computation and
reproducibility of this one dataset, not independent physical measurement.
"""
from common import *
import argparse,zipfile,math,collections,platform
import numpy as np
import pandas as pd
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args()
assert Path(a.run_id).name==a.run_id
out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
run=BASE/'runs/BL_CURVE_01';repeat=BASE/'runs/BL_CURVE_02';pp=BASE/'curve_protocol_v1.json';p=load(pp)
assert sha(pp)==load(BASE/'curve_freeze_v1.json')['protocol_sha256']
for name,h in load(run/'receipt.json')['artifacts'].items():
    assert sha(run/name)==h==sha(repeat/name)
archive=ROOT/p['archive']['path'];assert sha(archive)==p['archive']['sha256']
prepared=pd.read_csv(BASE/'runs/PREP_CURVE_01/candidates.csv')
stored=pd.read_csv(run/'predictions.csv');param=load(run/'parameters.json')
metrics=load(run/'metrics.json');diag=load(run/'diagnostics.json')
assert param['protocol_sha256']==sha(pp) and param['bin_width_mps']==0.5
checks=collections.Counter();maxdiff=collections.defaultdict(float);rebuilt=[];trains={}
def close(x,y,tol,kind):
    aa=np.asarray(x,dtype=float);bb=np.asarray(y,dtype=float)
    assert aa.shape==bb.shape
    assert np.array_equal(np.isnan(aa),np.isnan(bb))
    finite=np.isfinite(aa)&np.isfinite(bb)
    delta=float(np.max(np.abs(aa[finite]-bb[finite]))) if np.any(finite) else 0.
    assert delta<=tol,(kind,delta,tol)
    maxdiff[kind]=max(maxdiff[kind],delta);checks[kind]+=aa.size
with zipfile.ZipFile(archive) as z:
    for member,info in sorted(p['members'].items()):
        unit=info['unit']
        with z.open(member) as f:
            raw=pd.read_csv(f,skiprows=9,usecols=['# Date and time','Wind speed (m/s)','Power (kW)'])
        assert len(raw)==52560
        tt=pd.to_datetime(raw['# Date and time'],format='%Y-%m-%d %H:%M:%S',utc=True)
        vv=raw['Wind speed (m/s)'].to_numpy();yy=raw['Power (kW)'].to_numpy()
        clock=tt.diff().dt.total_seconds().ne(600).to_numpy(copy=True);clock[0]=False
        flags={'wind_invalid':~np.isfinite(vv)|(vv<0),'power_invalid':~np.isfinite(yy),
          'clock_invalid':clock,'time_duplicate':tt.duplicated().to_numpy(),
          'time_outside':((tt<pd.Timestamp('2018-01-01',tz='UTC'))|(tt>=pd.Timestamp('2019-01-01',tz='UTC'))).to_numpy()}
        ok=~np.logical_or.reduce(list(flags.values()))
        split=np.where(tt<pd.Timestamp('2018-10-01',tz='UTC'),'training','test')
        q=prepared[prepared.unit==unit]
        assert np.array_equal(q['row'],np.arange(1,52561))
        assert np.array_equal(pd.to_datetime(q.timestamp,utc=True).to_numpy(),tt.to_numpy())
        assert np.array_equal(q.split,split) and np.array_equal(q.admitted,ok)
        for key,v in flags.items():assert np.array_equal(q[key],v);checks['source_flags']+=len(v)
        close(q.wind_mps,vv,1e-10,'source_wind_mps');close(q.power_kW,yy,1e-9,'source_power_kW')
        train=ok&(split=='training');test=ok&(split=='test');x=vv[train];y=yy[train]
        pu=param['units'][str(unit)];assert pu['training_rows']==len(x)
        trains[unit]=(x.min(),x.max())
        close([pu['training_wind_min_mps'],pu['training_wind_max_mps']],[x.min(),x.max()],1e-10,'range_mps')
        for key,feature in [('B_LINEAR',x),('B_CUBIC',x*x*x)]:
            fx=feature.mean();fy=y.mean();slope=np.sum((feature-fx)*(y-fy))/np.sum((feature-fx)**2)
            close(pu[key],[fy-slope*fx,slope],1e-8,'coefficient')
        bins=pd.DataFrame({'id':np.floor(x/0.5).astype(int),'wind':x,'power':y}).groupby('id').agg(n=('wind','size'),v=('wind','mean'),p=('power','mean'))
        assert list(bins.index)==pu['bin_ids'] and bins.n.tolist()==pu['bin_counts']
        close(pu['knot_wind_mps'],bins.v,1e-10,'knot_mps');close(pu['knot_power_kW'],bins.p,1e-8,'knot_kW')
        assert np.all(np.diff(bins.v)>0)
        xx=vv[test];power=yy[test];rownum=np.arange(1,52561)[test]
        result=pd.DataFrame({'unit':unit,'row':rownum,'timestamp':tt[test].to_numpy(),'wind_mps':xx,'power_kW':power})
        for key,feature in [('B_LINEAR',xx),('B_CUBIC',xx**3)]:
            trainfeature=x if key=='B_LINEAR' else x**3
            fx=trainfeature.mean();fy=y.mean();b=np.sum((trainfeature-fx)*(y-fy))/np.sum((trainfeature-fx)**2)
            result[key]=fy+b*(feature-fx)
        result['M_CURVE']=np.interp(xx,bins.v.to_numpy(),bins.p.to_numpy())
        result['outside_training_wind']=(xx<x.min())|(xx>x.max())
        result['outside_knot_centres']=(xx<bins.v.iloc[0])|(xx>bins.v.iloc[-1])
        lookup=bins.n.to_dict();result['training_bin_count']=[lookup.get(int(np.floor(v/0.5)),0) for v in xx]
        result['rare_or_unseen_bin']=result.training_bin_count<20
        rebuilt.append(result)
allp=pd.concat(rebuilt,ignore_index=True)
assert len(allp)==len(stored)==69236
for key in ['unit','row','outside_training_wind','outside_knot_centres','training_bin_count','rare_or_unseen_bin']:
    assert np.array_equal(allp[key],stored[key]);checks['prediction_keys_flags']+=len(allp)
assert np.array_equal(pd.to_datetime(stored.timestamp,utc=True).to_numpy(),allp.timestamp.to_numpy())
for key in ['wind_mps','power_kW','B_LINEAR','B_CUBIC','M_CURVE']:
    close(stored[key],allp[key],1e-7,'prediction_'+key)
groups={'overall':np.ones(len(allp),bool)}
groups.update({f'unit_{u}':allp.unit==u for u in range(1,7)})
groups.update({f'month_{m:02d}':allp.timestamp.dt.month==m for m in [10,11,12]})
groups.update({'positive_power':allp.power_kW>0,'nonpositive_power':allp.power_kW<=0,
 'outside_training_wind':allp.outside_training_wind,'inside_training_wind':~allp.outside_training_wind,
 'rare_or_unseen_bin':allp.rare_or_unseen_bin,'supported_bin':~allp.rare_or_unseen_bin})
indmetrics={}
for group,mask in groups.items():
    q=allp[mask];assert metrics[group]['n']==len(q);mm={}
    for model in ['B_LINEAR','B_CUBIC','M_CURVE']:
        e=q[model].to_numpy()-q.power_kW.to_numpy()
        mm[model]=dict(zip(['mae_kW','rmse_kW','bias_kW','max_absolute_error_kW'],[float(np.mean(abs(e))),float(np.sqrt(np.mean(e*e))),float(np.mean(e)),float(np.max(abs(e)))])) if len(e) else {k:None for k in ['mae_kW','rmse_kW','bias_kW','max_absolute_error_kW']}
        for k,value in mm[model].items():
            if value is None:assert metrics[group]['models'][model][k] is None
            else:close([value],[metrics[group]['models'][model][k]],1e-7,'metric_kW')
    indmetrics[group]=mm
def better(g):
    d=indmetrics[g];return all(d['M_CURVE'][k]<d[b][k] for b in ['B_LINEAR','B_CUBIC'] for k in ['mae_kW','rmse_kW'])
gate={g:better(g) for g in ['overall']+[f'unit_{u}' for u in range(1,7)]+['positive_power']}
months={f'month_{m:02d}':better(f'month_{m:02d}') for m in [10,11,12]}
gate['at_least_two_months']=sum(months.values())>=2
assert gate==diag['checks'] and months==diag['month_comparisons'] and all(gate.values())==diag['gate_passed']
for k,mask in [('negative_source_power',allp.power_kW<0),('above_nominal_source_power',allp.power_kW>2050),('negative_curve_predictions',allp.M_CURVE<0),('above_nominal_curve_predictions',allp.M_CURVE>2050)]:assert diag[k]==int(mask.sum())
for model,worst in diag['worst_examples'].items():
    r=allp.loc[(allp[model]-allp.power_kW).abs().idxmax()]
    assert int(r.unit)==worst['unit'] and int(r.row)==worst['row']
dump(out/'receipt.json',{'status':'passed','scope':'Independent parsing/clock/sample/centred-moment coefficients/bin statistics/all test predictions/metrics/gate and exact two-run replay. Same physical source, not new measurement or external validation.',
 'source_rows':315360,'training_rows':234751,'test_rows':len(allp),'checks':dict(checks),'max_difference':dict(maxdiff),
 'protocol_sha256':sha(pp),'admission_sha256':sha(BASE/'runs/PREP_CURVE_01/admission.json'),
 'run_receipt_sha256':sha(run/'receipt.json'),'repeat_receipt_sha256':sha(repeat/'receipt.json'),
 'verifier_sha256':sha(Path(__file__)),'environment':{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__}})
print(json.dumps(load(out/'receipt.json'),indent=2))
