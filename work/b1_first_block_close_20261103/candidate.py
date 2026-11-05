from common import *
def points(a,cp,onset):
    out=A.state_points(a,cp,onset)
    if a is None:return out
    c=B.context(a);bp=float(np.median(a['p'][c['pre']]));bi=float(np.median(a['i'][c['pre']]))
    for r in out:
        j=r['index'];r['features']=np.r_[r['features'],np.log1p(abs(cp[j]-bp)/max(.03,2*c['sigma_p'])),np.log1p(abs(a['i'][j]-bi)/max(.15,2*c['sigma_i']))]
    return out
def infer(row,cp,parent_model,model):
    out=P.infer(row,cp,parent_model);out['branch']='closing_absolute_and_relative_recovery';out['recovery_state_score']=None
    a=B.arrays(row)
    if out['status']!='ok' or not out['detected'] or a is None:return out
    for r in points(a,cp,out['onset_seconds']):
        if not r['eligible']:continue
        score=P.probability(model['model'],r['features'])
        if score>=model['threshold']:
            before=out['recovery_seconds'];out['recovery_seconds']=r['time'];out['recovery_state_score']=score;out['recovery_calibrated']=before!=r['time'];out['observed_span_seconds']=max(0.,r['time']-out['onset_seconds']);break
    return out
