"""Retained real-observation event calibration; unchanged numerical functions."""
import numpy as np
from scipy.ndimage import median_filter
from ..process import _duration_fusion as DF
from . import _common as B

def raw50(a):
    c=B.context(a);y=c['direction']*(a['p']-np.median(a['p'][c['pre']]));sigma=c['sigma_p'];step=float(np.median(np.diff(a['t'])))
    # Exact retained numeric feature block, with recorded geometry/scale.
    base=DF._model_features(y,np.zeros(len(y)),sigma,step)
    out=[base[:,[0,4,5]+list(range(6,42))]]
    for width in [3,5,9,17,31,61]:out.append((median_filter(y,size=width,mode='nearest')/sigma)[:,None])
    after=y[a['t']>=0]
    for q in [.05,.25,.5,.75,.95]:out.append(np.full((len(y),1),np.quantile(after,q)/sigma))
    features=np.column_stack(out).astype(np.float32);assert features.shape==(len(y),50)
    return features,base

def event_features(a,cp):
    if a is None or len(a['p'])<4:return None
    cp=np.asarray(cp,float)
    if cp.shape!=a['p'].shape or not np.isfinite(cp).all():return None
    c=B.context(a)
    if c['direction']==0:return None
    raw,legacy=raw50(a);use=(a['t']>=0)&(a['t']<=24);direction=c['direction']
    def peak(v):return float(np.log1p(np.clip(np.max(np.asarray(v)[use]),0.,100.)))
    current=direction*(a['i']-np.median(a['i'][c['pre']]))/c['sigma_i']
    cpz=direction*(cp-np.median(cp[c['pre']]))/c['sigma_p']
    headroom=(c['prior_pilot']-float(np.median(a['i'][c['pre']])))/max(1.,abs(a['pilot'][a['j0']]-c['prior_pilot']))
    past=(a['t']>=-60)&(a['t']<=-12)
    trend=0.
    if np.sum(past)>=3:
        slope=np.polyfit(a['t'][past],a['p'][past],1)[0]
        trend=float(np.clip(direction*slope*24/c['sigma_p'],-20.,20.))
    return np.array([peak(raw[:,0]),peak(legacy[:,6]),peak(legacy[:,14]),peak(raw[:,39]),peak(current),peak(cpz),float(np.clip(headroom,-20.,20.)),trend],float)

def probability(payload,x):
    z=(np.asarray(x,float)-np.array(payload['mean']))/np.array(payload['scale'])
    score=float(np.dot(z,np.array(payload['coef']))+payload['intercept'])
    return float(1/(1+np.exp(-np.clip(score,-700,700))))

def adaptive_return(a,cp,onset):
    if onset is None or a is None:return None
    c=B.context(a);p=np.asarray(cp,float);i=a['i'];direction=c['direction']
    plo,phi=np.quantile(a['p'][c['pre']],[.1,.9]);ilo,ihi=np.quantile(i[c['pre']],[.1,.9])
    tol_p=max(.03,2*c['sigma_p']);tol_i=max(.2,2*c['sigma_i'])
    p0=float(np.median(a['p'][c['pre']]));i0=float(np.median(i[c['pre']]))
    active=False
    for j,t in enumerate(a['t']):
        if t<onset:continue
        outside_p=p[j]>phi+tol_p if direction>0 else p[j]<plo-tol_p
        outside_i=i[j]>ihi+tol_i if direction>0 else i[j]<ilo-tol_i
        if outside_p and outside_i:active=True
        if active and t>onset and plo-tol_p<=p[j]<=phi+tol_p and ilo-tol_i<=i[j]<=ihi+tol_i:return float(t)
    return None

def infer(row,cp,payload):
    a=B.arrays(row);original=B.estimate(a,cp)
    info=dict(parent_method='effective_response_refined',branch='real_observed_v1',old_simulation_weights_used=False,effective_qualification=None,cumulative_effective_response_seconds=None,longest_continuous_effective_response_seconds=None,observed_span_seconds=None,supervision='provisional_single_assistant_observation_labels',input_points_changed=False)
    if a is None or original['status']!='ok':return dict(original,**info,adaptation_status='not_applicable_or_unsupported',event_score=None,rescued=False,recovery_calibrated=False)
    x=event_features(a,cp)
    if x is None:return dict(original,**info,adaptation_status='feature_unavailable',event_score=None,rescued=False,recovery_calibrated=False)
    score=probability(payload['event_model'],x);out=dict(original);rescued=False
    raw=B.estimate(a,a['p'],k=3,current=True)
    # This is the old-positive preservation/local rescue principle from LR.
    # The real-trained qualifier constrains only new candidate evidence.
    if not original['detected'] and raw['detected'] and score>=payload['rescue_threshold']:
        out=dict(raw);rescued=True
    proposed=adaptive_return(a,cp,out['onset_seconds']) if out['detected'] else None
    before=out['recovery_seconds'];mix=payload['recovery_mix'];after=before
    if mix>0 and proposed is not None:
        value=proposed if before is None else (1-mix)*before+mix*proposed
        valid=a['t'][a['t']>out['onset_seconds']]
        if len(valid):after=float(valid[np.argmin(abs(valid-value))])
    out['recovery_seconds']=after
    if out['onset_seconds'] is not None and after is not None:info['observed_span_seconds']=max(0.,after-out['onset_seconds'])
    return dict(out,**info,adaptation_status='real_feature_calibration',event_score=score,event_score_calibrated=False,rescued=rescued,rescue_threshold=payload['rescue_threshold'],recovery_candidate_seconds=proposed,recovery_calibrated=after!=before,raw_feature_columns=50,event_feature_columns=8)
