"""Reuse frozen B1 extraction and the current-safe B2 query without old-file writes."""
import importlib.util,sys
import numpy as np
from io_utils import ROOT

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
loader=module('_history_legacy_loader',ROOT/'work/b2_b3_integration_20261028/legacy_loader.py')
saved=sys.modules.get('legacy_loader');sys.modules['legacy_loader']=loader
try:guardmod=module('_history_current_guards',ROOT/'work/b2_b3_integration_20261028/guards.py')
finally:
    if saved is None:sys.modules.pop('legacy_loader',None)
    else:sys.modules['legacy_loader']=saved
b1=module('_history_b1_f0',ROOT/'work/b1_research_20261021/features.py')
safe_b2=guardmod.predict_b2
_model=None

def base_forecast(o):
    global _model
    with loader.legacy('b2') as old:
        if _model is None:_model=old.joblib.load(ROOT/'work/b2_completion_20261027/dynamic/models.joblib')[0][1]
        old.valid_input(o)
        pa=old.predict(_model['choice'],o);states=_model['dynamic'].predict_proba(old.features_exec(o))
        probs=np.column_stack([1-pa,pa[:,None]*states])
    probs[~o['eligible']]=[1.,0,0,0,0,0]
    return probs

def templates():
    with loader.legacy('b2') as old:return old.templates()

def b1_event(reference,power,q):
    # Generic original B1 explicitly accepts interval boundaries and task timing.
    r=b1.extract(np.arange(121)*60,np.asarray(reference),np.asarray(power),t0=0.,t1=1800.,q=float(q),dwell_samples=1)
    onset=r['onset_delay_interval_s'];target=r['target_interval_s']
    return np.array([r['Y'],onset[1]/1800 if onset is not None else 1.,target[1]/1800 if target is not None else 1.,float(target is not None)])
