"""Fine-grid two-sided persistence check before original CPOP, not a new DP.

Only applies to <=10s observations. Raw energy is never edited. One-fine-bin
true actions can be observationally identical to faults; explicit stress tests
are mandatory, and a flag is not a certified fault classification.
"""
from common import np
VERSION='fine-persistence-cpop-v3'

def refine(y,starts_s,command,sigma,kappa):
    y=np.asarray(y,float);s=np.asarray(starts_s,float);u=np.asarray(command,float)
    if y.ndim!=1 or y.shape!=s.shape or y.shape!=u.shape or len(y)<6:raise ValueError('matching complete vectors required')
    if not np.isfinite(y).all() or not np.isfinite(s).all() or not np.isfinite(u).all():raise ValueError('finite vectors required')
    if not np.isfinite(sigma) or sigma<=0 or kappa not in (3.,4.,5.):raise ValueError('fixed candidate family required')
    step=float(np.median(np.diff(s)))
    if step<=0 or not np.allclose(np.diff(s),step,atol=1e-8,rtol=0):raise ValueError('uniform observed grid required')
    corrected=y.copy();flags=[];protected=set()
    for edge in np.flatnonzero(abs(np.diff(u))>1e-12)+1:
        protected.update(range(max(0,int(edge)-1),min(len(y),int(edge)+2)))
    if step>10.+1e-8:
        return corrected,dict(flagged_indices=[],reason='coarse_only_passthrough',step_seconds=step,protected_indices=sorted(protected))
    for i in range(2,len(y)-2):
        if i in protected:continue
        left,right=y[i-2:i],y[i+1:i+3]
        lm,rm=float(np.median(left)),float(np.median(right));at=.5*(lm+rm)
        if abs(lm-rm)<=2.5*sigma and np.ptp(left)<=3*sigma and np.ptp(right)<=3*sigma and abs(y[i]-at)>kappa*sigma:
            corrected[i]=at;flags.append(int(i))
    return corrected,dict(flagged_indices=flags,reason='two_sided_fine_support',step_seconds=step,protected_indices=sorted(protected),
        raw_accounting_unchanged=True,observational_fault_certainty=False)

def features(pred,starts_s,end_s,tau,dwell_s=30.):
    y=np.asarray(pred,float);s=np.asarray(starts_s,float);delta=float(np.median(np.diff(s)))
    mask=(s>=-1e-8)&(s<end_s-1e-8)&(y>=tau)
    run=longest=0
    for value in mask:run=run+1 if value else 0;longest=max(longest,run)
    return dict(cumulative_seconds=float(mask.sum()*delta),
        longest_seconds=float(longest*delta) if longest*delta>=dwell_s-1e-8 else 0.,
        threshold_positive=bool(mask.any()))
