"""Adapter for the teacher's original RIDE interval-template implementation."""
import numpy as np


def fit_original_ride(data):
    try:
        from . import _ride_identify as identify
        from . import _ride_template as template
        event=identify.EventInput(s=data['starts'],e=data['ends'],r=data['y'],q=1.5,W=30.,obs_end=45.,
            a_max=1.5,b_max=1.,sigma=data['sigma'],sB=0.,delta=data['delta'],is_ev=1,event_id=0)
        output=identify.identify_event(event,structures=(0,1,2),n_starts=3,ci_method='none',lr_crit=None,seed=711)
        detected=bool(output['A_hat'])
        if not np.isfinite(output['bic0']):raise ValueError('nonfinite null BIC')
        theta=np.asarray([output['th_'+name] for name in template.PARAM_NAMES_M2],float)
        if not np.isfinite(theta).all():raise ValueError('nonfinite RIDE parameters')
        if detected:
            selected_bic=output['bic'+str(output['struct'])]
            if not np.isfinite(selected_bic):raise ValueError('nonfinite selected BIC')
            curve=1.5*template.interval_average(theta,30.,data['starts'],data['ends'])
        else:curve=np.zeros(len(data['y']))
        if not np.isfinite(curve).all():raise ValueError('nonfinite RIDE curve')
        return dict(status='ok',prediction=curve,structure=int(output['struct']),detected=detected,
            n_starts_minimum=3,original_optimizer_convergence_certified=False,
            selection='original_BIC_and_amplitude; no_pseudo_event_LR_or_parameter_CI_claim')
    except (ImportError,ValueError,RuntimeError,FloatingPointError,OverflowError,np.linalg.LinAlgError) as exc:
        return dict(status='unavailable',reason=type(exc).__name__+': '+str(exc))
