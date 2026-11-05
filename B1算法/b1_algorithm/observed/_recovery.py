"""Retained state-v2 observed recovery calibration."""
import numpy as np
from . import _event as P
B=P.B

def state_points(a,cp,onset):
    if a is None or onset is None:return []
    c=B.context(a);base_p=float(np.median(a['p'][c['pre']]));base_i=float(np.median(a['i'][c['pre']]));direction=c['direction'];cp=np.asarray(cp,float)
    sp=max(.03,2*c['sigma_p']);si=max(.15,2*c['sigma_i']);peak_p=0.;peak_i=0.;out=[]
    for j,t in enumerate(a['t']):
        if t<onset:continue
        dp=direction*(cp[j]-base_p);di=direction*(a['i'][j]-base_i)
        if t>onset:
            x=np.array([min(5.,abs(cp[j]-base_p)/max(sp,peak_p)),min(5.,abs(a['i'][j]-base_i)/max(si,peak_i))])
            eligible=peak_p-dp>=sp and peak_i-di>=si
            out.append(dict(index=j,time=float(t),features=x,eligible=bool(eligible)))
        peak_p=max(peak_p,dp);peak_i=max(peak_i,di)
    return out

def infer(row,cp,parent_model,state_model):
    base=P.infer(row,cp,parent_model);a=B.arrays(row)
    base['branch']='real_observed_v2_state_recovery';base['recovery_state_score']=None
    if base['status']!='ok' or not base['detected'] or a is None:return base
    for point in state_points(a,cp,base['onset_seconds']):
        if not point['eligible']:continue
        score=P.probability(state_model['model'],point['features'])
        if score>=state_model['threshold']:
            before=base['recovery_seconds'];base['recovery_seconds']=point['time'];base['recovery_state_score']=score;base['recovery_calibrated']=before!=point['time'];base['observed_span_seconds']=max(0.,point['time']-base['onset_seconds']);break
    return base
