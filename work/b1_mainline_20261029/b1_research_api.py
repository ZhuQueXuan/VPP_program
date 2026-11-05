"""Separate B1 research entry. Does not replace the frozen b123_api default."""
from functools import lru_cache
from pathlib import Path
import importlib.util
import numbers
import sys
import numpy as np

ROOT=Path(__file__).resolve().parent

@lru_cache(maxsize=None)
def _load(name,relative,package=False):
 path=ROOT/relative
 spec=importlib.util.spec_from_file_location(name,path,
       submodule_search_locations=[str(path.parent)] if package else None)
 module=importlib.util.module_from_spec(spec)
 sys.modules[name]=module
 spec.loader.exec_module(module)
 return module

def _process_module():
 _load('_vpp_b1_process', 'process/__init__.py', True)
 return _load('_vpp_b1_process.api','process/api.py')

def identify_response(starts,ends,power,reference,sigma,*,method,request_kw=1.5):
 """Retrospective W30/q1.5 task; method is explicit, never test-selected.

 method: task_template or grid_average. Timing features describe observed
 thresholds, not uniquely identified physical times. No confidence interval.
 """
 if isinstance(request_kw,(bool,np.bool_)) or not isinstance(request_kw,numbers.Real) or not np.isclose(request_kw,1.5,atol=1e-12,rtol=0):
  raise ValueError('This finite research entry supports request_kw=1.5 only')
 result=_process_module().fit_average_process(starts,ends,power,reference,sigma,method=method)
 result['research_status']='finite_simulation_candidate; no universal superiority or real-resource validation'
 return result

def estimate_incentive_effects(X,d,y,users,*,levels=None,known_pi=None,seed=0,n_boot=999,alpha=.05,kappa=.1):
 """Standard multivalued AIPW for a common, predeclared event outcome.

 X must precede incentive assignment. This function cannot establish no hidden
 confounding or transfer reference calibration to full-chain inference.
 """
 if isinstance(n_boot,(bool,np.bool_)) or not isinstance(n_boot,numbers.Integral) or n_boot<100:
  raise ValueError('n_boot must be an integer >=100')
 for name,value in [('alpha',alpha),('kappa',kappa)]:
  if isinstance(value,(bool,np.bool_)) or not isinstance(value,numbers.Real) or not np.isfinite(value):
   raise ValueError(name+' must be a finite real number')
 if not 0<alpha<1 or kappa<=0:
  raise ValueError('require 0<alpha<1 and positive kappa')
 module=_load('_vpp_b1_causal','causal/api.py')
 result=module.fit_discrete(X,d,y,users,levels=module.LEVELS if levels is None else levels,
       known_pi=known_pi,seed=seed,n_boot=n_boot,alpha=alpha,kappa=kappa)
 result.pop('audit',None)
 # Diagnostic approval is only one necessary part of causal identification.
 result['identification_assumptions_status']='requires substantive verification; diagnostics cannot establish ignorability'
 result['uncertainty_scope']='user-cluster band conditional on supplied outcome; no full reference/process uncertainty guarantee'
 return result

def predict_reference(obs,train_users,*,seed=0):
 """Common SafeGBDT from completed historical and declared pre-notice inputs."""
 module=_load('_vpp_b1_reference','reference/reference_api.py')
 model=module.SafeGBDT(seed=seed).fit(obs,train_users)
 return dict(reference_kw=model.predict(obs),
       status='prediction; pseudo-to-event transport and true counterfactual not established',
       method='fixed_pre_notice_SafeGBDT')
