"""Old discrete numerical parity and generic plot-label regression."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,importlib.util
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'B1算法'))
from verify import task_record
from b1_api import analyze_events,estimate_event_effects
from b1_algorithm.effects.plotting import _ylabel

records=[task_record(i,45.,15.,.2+.2*(i%2)+.03*np.sin(i//4)) for i in range(480)]
events=analyze_events(records,process_method='conservative');x=np.sin(np.arange(480)//4)[:,None];d=np.arange(480)%2
options=dict(levels=[0.,1.],known_pi=np.full((480,2),.5),effect_config=dict(n_boot=99,seed=17,return_audit=True),
 assumptions=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,same_outcome_definition=True,randomized_assignment=True))
spec=importlib.util.spec_from_file_location('_b1_compat_before',HERE/'before_source/b1_algorithm/__init__.py',submodule_search_locations=[str(HERE/'before_source/b1_algorithm')])
old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)
before=old.estimate_event_effects(events,x,d,**options);after=estimate_event_effects(events,x,d,**options)
assert before['status']==after['status']=='causal'
assert np.array_equal(before['audit']['aipw_scores'],after['audit']['aipw_scores'])
assert before['inference']==after['inference']
assert before['causal_curve']==after['causal_curve']
assert '净交付' in _ylabel({'task':{'outcome_name':'eta_raw'}},{'outcome_unit':'ratio'})
assert '净交付' not in _ylabel({'task':{'outcome_name':'participation'}},{'outcome_unit':'ratio'})
assert '用电' in _ylabel({'metered_pipeline':{},'task':{'outcome_name':'anything'}},{'outcome_unit':'ratio'})
assert 'kWh' in _ylabel({'task':{'outcome_name':'energy'}},{'outcome_unit':'kWh'})
result=dict(passed=True,checks=8,discrete_events=480,old_discrete_scores_difference=0.,old_curve_and_inference_equal=True,
            plot_ratio_outcomes_labeled_by_actual_meaning=True,source_changes_since_study='plot axis label only, no estimation changes')
(HERE/'compatibility_receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
