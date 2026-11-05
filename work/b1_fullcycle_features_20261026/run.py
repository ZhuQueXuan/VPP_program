"""One-shot frozen extraction study, estimator outputs before truth evaluation."""
from pathlib import Path
import json,hashlib,time,sys,importlib.util,math
import numpy as np
from methods import extract,segment
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
RAW=ROOT/'data/驱动因素解耦模拟数据集_B1_fullcycle_features_v1_20261026'
P=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,v):(BASE/name).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def micro():
    from itertools import product
    checks=0;worst=0.
    spec=importlib.util.spec_from_file_location('old_segment',ROOT/'work/b1_research_20261021/feature_segmentation.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    rng=np.random.default_rng(76001)
    for n in (3,6,9,12):
        for penalty in (0.,.05,.5):
            for repeat in range(3):
                y=rng.normal(size=n);fit,segs,obj=segment(y,penalty,1 if n==3 else 3)
                oracle=old.exhaustive_objective(y,penalty,1 if n==3 else 3)
                scalar=old.penalized_segment(y,penalty,1 if n==3 else 3)
                err=max(abs(obj-oracle['objective']),abs(obj-scalar['objective']));worst=max(worst,err)
                assert err<1e-10;checks+=1
    t=np.arange(0,3601,10);r=np.zeros(360);r[60:180]=1.5;r[180:300]=-1.5
    for method in ('F0_raw_rule','F1_segment_rule'):
        a,fit=extract(t,np.full(360,3),3-r,.05,method)
        assert a['onset_s']==600 and a['duration_s']==1200 and a['power_recovery_s']==3000;checks+=3
        assert abs(a['request_net_kwh']-.5)<1e-12 and a['balance']['status']=='within_margin';checks+=2
        missing=3-r.copy();missing[90]=np.nan
        a,fit=extract(t,np.full(360,3),missing,.05,method)
        assert a['request_net_kwh'] is None and a['onset_s'] is None and a['duration_s'] is None and a['balance']['status']=='unavailable';checks+=4
        assert np.isnan(fit[90]);checks+=1
        a,fit=extract(t,np.full(360,3),np.full(360,3.),.05,method)
        assert a['stage']=='no_response' and a['power_recovery_status']=='not_applicable';checks+=2
    return dict(passed=checks,failed=0,maximum_dp_objective_error=worst)

def main():
    command=sys.argv[1]
    if command=='freeze':
        if (BASE/'source_freeze.json').exists():raise RuntimeError('already frozen')
        source={n:sha(BASE/n) for n in ['protocol.json','methods.py','generate.py','run.py','evaluate.py','plot_results.py']}
        protected={}
        for folder in ['work/b1_research_20261021','work/b1_recovery_uncertainty_20261021','work/b1_crossing_uncertainty_20261026','资源能力模型']:
            for f in (ROOT/folder).rglob('*'):
                if f.is_file() and '__pycache__' not in f.parts:protected[str(f.relative_to(ROOT))]=sha(f)
        dump('source_freeze.json',dict(source=source,protected=protected));dump('micro_checks.json',micro());print('frozen, micro passed');return
    identity=json.loads((BASE/'source_freeze.json').read_text(encoding='utf-8'))
    assert all(sha(BASE/n)==h for n,h in identity['source'].items())
    if command=='generate':
        if (RAW/'observations.npz').exists():raise RuntimeError('raw already exists')
        import generate
        t=time.perf_counter();v=generate.main(P,RAW,BASE);v['elapsed_s']=time.perf_counter()-t;dump('generation_receipt.json',v);print(v);return
    if command!='extract':raise ValueError('freeze/generate/extract')
    if (BASE/'predictions.json').exists() or (BASE/'evaluation.json').exists():raise RuntimeError('predictions/truth already revealed; no overwrite')
    rows=json.loads((RAW/'observation_index.json').read_text(encoding='utf-8'));raw=np.load(RAW/'observations.npz');outputs=[];fits=[]
    tstart=time.perf_counter()
    for i,row in enumerate(rows):
        n=row['n'];dt=row['dt_s'];t=np.arange(n+1)*dt;power=raw['power_obs_kw'][i,:n]
        for method in ('F0_raw_rule','F1_segment_rule'):
            result,fit=extract(t,np.full(n,3.),power,row['sigma_effective_kw'],method)
            outputs.append(dict(observation_id=i,**result));pad=np.full(360,np.nan);pad[:n]=fit;fits.append(pad)
        if (i+1)%400==0:print('extract',i+1,'/',len(rows),flush=True)
    dump('predictions.json',outputs);np.savez_compressed(BASE/'fitted_reductions.npz',reduction_kw=fits)
    dump('extraction_receipt.json',dict(elapsed_s=time.perf_counter()-tstart,observation_count=len(rows),outputs=len(outputs),predictions_sha256=sha(BASE/'predictions.json'),fits_sha256=sha(BASE/'fitted_reductions.npz'),raw_sha256=sha(RAW/'observations.npz')))
    print('saved',len(outputs),time.perf_counter()-tstart)

if __name__=='__main__':main()
