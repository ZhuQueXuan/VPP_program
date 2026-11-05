"""Task-edge-protected isolated-point weighting for existing native CPOP.

Adaptation of local robust screening and CPOP's existing heteroscedastic loss;
not a novel global changepoint solver or a calibrated sensor-fault classifier.
Observations and raw accounting are never replaced, deleted or clipped.
"""
import numpy as np
VERSION='cpop-isolated-point-weight-v1'
def observation_weights(y,sigma,command,*,kappa=3.0,radius=2):
    original=np.asarray(y,dtype=object);cmd=np.asarray(command,dtype=object)
    if original.ndim!=1 or cmd.shape!=original.shape or len(original)<7:raise ValueError('matching1d complete signal and command required')
    if any(isinstance(v,(bool,np.bool_)) for v in original) or any(isinstance(v,(bool,np.bool_)) for v in cmd):raise ValueError('bool is not measurement')
    y=np.asarray(y,dtype=float);command=np.asarray(command,dtype=float)
    if not np.isfinite(y).all() or not np.isfinite(command).all():raise ValueError('finite observations/command required')
    if isinstance(sigma,(bool,np.bool_)) or not np.isfinite(sigma) or sigma<=0:raise ValueError('positive finite declared sigma required')
    if kappa not in (3.,4.,5.) or radius!=2:raise ValueError('outside fixed bounded candidate family')
    n=len(y);protected=np.zeros(n,bool)
    changes=np.flatnonzero(np.abs(np.diff(command))>1e-12)+1
    for j in changes:protected[max(0,j-1):min(n,j+2)]=True
    effective=np.full(n,float(sigma));records=[]
    for j in range(radius,n-radius):
        if protected[j]:continue
        left=y[j-radius:j];right=y[j+1:j+radius+1]
        ml,mr=float(np.median(left)),float(np.median(right))
        # A continuing ramp or a level change with different sides is not an
        # isolated point under this deliberately limited screening rule.
        if abs(ml-mr)>2.5*sigma or np.ptp(left)>3*sigma or np.ptp(right)>3*sigma:continue
        neighbors=np.r_[left,right];center=float(np.median(neighbors))
        local=max(float(sigma),1.482602218505602*float(np.median(np.abs(neighbors-center))))
        residual=float(y[j]-center)
        if abs(residual)<=kappa*local:continue
        effective[j]=max(float(sigma),abs(residual)/kappa)
        records.append({'index':j,'observed':float(y[j]),'local_center':center,'local_scale':local,
            'residual':residual,'effective_sigma':float(effective[j]),'weight_ratio':float((sigma/effective[j])**2),
            'interpretation':'isolated_change_ambiguous_sensor_spike_or_real_short_action'})
    return {'version':VERSION,'sigma_vector':effective,'flagged_points':records,'protected_indices':np.flatnonzero(protected).tolist(),
        'kappa':float(kappa),'radius':radius,'source_values_preserved':True,
        'noise_variance_interpretation':'data-dependent fitting weights, not a physical noise-variance estimate or calibrated confidence interval',
        'short_action_disambiguation_available':False}
