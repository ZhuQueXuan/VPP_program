from pathlib import Path
import importlib.util,sys,json
import numpy as np
PARENT=Path(__file__).resolve().parent.parent
_spec=importlib.util.spec_from_file_location('real_adapter_parent',PARENT/'adapter.py');P=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(P)
B=P.B
CENSORED={'right_censored_by_window','interrupted_by_new_limit','taper_without_return_to_old_level','taper_without_return_to_pre_anchor_level','right_censored_with_later_power_shift','later_stop_without_return_to_old_level','later_unrelated_drop_no_unique_recovery'}
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
