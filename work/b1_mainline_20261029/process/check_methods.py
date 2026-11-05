from pathlib import Path
import json
import numpy as np
from models import design,fit,cache
from run_process import truth_average,shape,features,ride_fit,assess

checks=[]
def record(name,fun):fun();checks.append(name)
def analytic():
    # f(t)=2+3(t+15)/60, no knots: interval mean equals midpoint.
    s=np.array([-15.,0.,20.]);e=np.array([-14.,15.,30.])
    np.testing.assert_allclose(design(s,e,[],True),design(s,e,[],False))
    # Hinge crossing zero: integral over [-1,1] is 1/2, mean 1/4.
    np.testing.assert_allclose(design(np.array([-1.]),np.array([1.]),[0],True)[0,-1],.25/60)
    assert design(np.array([-1.]),np.array([1.]),[0],False)[0,-1]==0
record('analytic interval operator and midpoint equality on linear bins',analytic)
def noiseless_linear():
    for delta in [1/6,1,15]:
        s=np.arange(-15,45-1e-8,delta);e=s+delta
        y=design(s,e,[],True)@np.array([.2,.5])
        for average in [False,True]:
            pred,info=fit(y,delta,.05,average)
            np.testing.assert_allclose(pred,y,atol=1e-10)
            assert len(info['knots'])==0
record('exact linear recovery for all resolutions and both operators',noiseless_linear)
def family():
    for delta in [1/6,1,15]:
        point=cache(delta,False)[2];average=cache(delta,True)[2]
        assert [a[0] for a in point]==[a[0] for a in average]
record('identical full-rank model subsets in matched ablation',family)
def exhaustive():
    rng=np.random.default_rng(5);y=rng.normal(size=4)
    for average in [False,True]:
        pred,info=fit(y,15,.5,average)
        s,e,entries,*_=cache(15,average)
        scores=[]
        for ks,_,_ in entries:
            X=design(s,e,ks,average);coef=np.linalg.lstsq(X,y,rcond=None)[0]
            scores.append(np.sum((y-X@coef)**2)/.25+2*np.log(4)*len(ks))
        np.testing.assert_allclose(info['cost'],min(scores),atol=1e-9)
record('QR enumeration agrees with independent lstsq objective for all coarse models',exhaustive)
def rejects():
    for y,sigma in [(np.array([0,1,np.nan,2]),.1),(np.ones(4),0)]:
        try:fit(y,15,sigma,True)
        except ValueError:continue
        raise AssertionError('invalid observations accepted')
record('missing data and invalid noise rejected',rejects)
def dgp():
    for mech in ['none','step','partial','slow','early_exit','dropout','curved','multiplateau']:
        sh=shape(2026102800,mech)
        assert np.all(np.diff(sh['knots'])>0)
        fine_s=np.arange(-15,45,.001);fine=truth_average(sh,fine_s,fine_s+.001)
        coarse_s=np.arange(-15,45,15)
        coarse=truth_average(sh,coarse_s,coarse_s+15)
        np.testing.assert_allclose(coarse,fine.reshape(4,-1).mean(1),atol=2e-8)
record('DGP exact integrals aggregate across all eight mechanisms',dgp)
def features_check():
    y=np.zeros(60);y[15:45]=1.5
    f=features(y,1)
    assert f['onset_s']==0 and f['target_s']==0 and f['recovery_s']==1800
    assert features(np.zeros(4),15)['stage']=='no_response'
record('frozen threshold+dwell targets and no-response status',features_check)
def ride_api():
    pred,info=ride_fit(np.zeros(60),1,.05)
    assert info['ride_structure']==0 and np.all(pred==0)
record('read-only RIDE import and no-response projection',ride_api)
out=dict(passed=True,n_groups=len(checks),checks=checks)
Path(__file__).with_name('checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
