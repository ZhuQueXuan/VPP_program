"""Inspect the current dependency graph by querying copies of a saved DEV fit.

No fitting, parameter selection, outcome relabeling or evaluation-set opening.
One artificial linear perturbation demonstrates numerical dependence only.
"""
from pathlib import Path
import sys,json,copy,hashlib
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.research import load_research_point_one,query_research_point_one

source=ROOT/'work/b1_research_point1_20261103/development/90331001-randomized/model.json'
model=load_research_point_one(source)
amounts=np.array([.4,.73,1.17,1.65,2.])
def query(m):return query_research_point_one(m,amounts,include_bias_correction=False)
def main_values(q):return np.asarray(q['mean_curve']['curve']['contrasts'])
def slope(q):return np.asarray(q['retained_smoothed_derivative']['values'])
original=query(model)
without_graph=copy.deepcopy(model);without_graph['structure']={}
without_groups=copy.deepcopy(model);without_groups['groups']={}
qgraph=query(without_graph);qgroup=query(without_groups)
assert np.array_equal(main_values(original),main_values(qgraph))
assert np.array_equal(main_values(original),main_values(qgroup))
assert np.array_equal(slope(original),slope(qgraph))
assert original['target_threshold']==qgraph['target_threshold']
assert original['target_threshold']==qgroup['target_threshold']

perturbed=copy.deepcopy(model)
p=json.loads(perturbed['mean_model']['payload_json']);delta=10.
p['pseudo_outcome']=(np.asarray(p['pseudo_outcome'])+delta*np.asarray(p['dose'])).tolist()
payload=json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
perturbed['mean_model']=dict(payload_json=payload,sha256=hashlib.sha256(payload.encode('utf-8')).hexdigest())
qchanged=query(perturbed)
expected=delta*(amounts-p['reference_dose'])
curve_error=float(np.max(abs(main_values(qchanged)-main_values(original)-expected)))
slope_error=float(np.max(abs(slope(qchanged)-slope(original)-delta)))
assert curve_error<1e-8 and slope_error<1e-8
assert original['direct_marginal_effect']==qchanged['direct_marginal_effect']
assert original['group_effects']==qchanged['group_effects']
assert qchanged['structure']==original['structure']

result=dict(status='passed_read_only_dev_state_dependency_probe',source=str(source.relative_to(ROOT)),
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),fits=0,
    graph_removed_mean_change=float(np.max(abs(main_values(qgraph)-main_values(original)))),
    graph_removed_default_sensitivity_or_threshold_change=False,
    groups_removed_mean_change=float(np.max(abs(main_values(qgroup)-main_values(original)))),
    groups_removed_default_sensitivity_or_threshold_change=False,
    artificial_linear_perturbation=dict(coefficient_seconds_per_amount=delta,
        curve_change_matches_linear_function_max_error=curve_error,
        default_derivative_change_matches_constant_max_error=slope_error,
        threshold_before=original['target_threshold'].get('first_point_crossing'),
        threshold_after=qchanged['target_threshold'].get('first_point_crossing'),
        independent_direct_derivative_changed=False,independent_group_curves_changed=False,
        interpretation='artificial numerical dependence demonstration only; not an improvement, fitted comparison or accuracy claim'),
    current_links=dict(graph2='diagnosis only; declared adjustment precedes the fitted graph',
        mean3_to_default_sensitivity5=True,mean3_to_threshold6=True,
        global_mean3_to_separately_refitted_groups4=False,
        groups4_to_mean3_or_graph2=False,
        shared_estimated_nuisance_configuration='global and subgroup branches use the same specification but independent fitted states'),
    old_or_new_final_test_data_read=False,formal_source_files_changed=False)
with (HERE/'dependency_probe.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=False))
