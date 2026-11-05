"""Independent resource-neutral integrated algorithm run on new audit inputs."""
from pathlib import Path
import json
import sys
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'runtime/site-packages'))
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.research import fit_response_research,query_research_point_one,save_research_point_one,load_research_point_one

source=json.loads((HERE/'audit_new_nonlinear_model.json').read_text(encoding='utf-8'))['payload']
X=np.asarray(source['X']);d=np.asarray(source['dose']);y=np.asarray(source['outcome']);users=source['users']
task=dict(task_id='independent-integrated-audit',outcome_name='duration_seconds',outcome_unit='seconds',
          target_population='independent new constructed mathematical cohort',window_minutes=[0.,30.],q_kw=1.5,
          task_pre_treatment=True,reference_status='provided',reference_uncertainty='known_reference')
assumptions=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,same_outcome_definition=True,
                 conditional_exchangeability=True,randomized_assignment=True)
cfg=dict(source['configuration'])
model=fit_response_research(X,d,y,users,covariate_names=['deadline_slack','demand_urgency'],
    task=task,incentive_unit='yuan/kWh',dose_domain=[0.,2.4],reference_dose=.4,assumptions=assumptions,
    known_density=np.full(len(d),1/2.4),config=cfg,
    groups={'slack_below_zero':dict(covariate='deadline_slack',threshold=0.,side='below'),
            'slack_nonnegative':dict(covariate='deadline_slack',threshold=0.,side='above')},
    discover_structure=True,structure_max_users=48)
q=query_research_point_one(model,[.4,.73,1.17,1.65,2.])
assert q['mean_curve']['status']=='causal'
assert q['direct_marginal_effect']['status']=='ok'
assert set(q['structure'])=={'fci_kci','pc_kci'}
assert all(g['selected_users']==48 and g['input_events']==480 for g in q['structure'].values())
assert q['refitted'] is False
save_research_point_one(model,HERE/'audit_integrated_model.json')
loaded=load_research_point_one(HERE/'audit_integrated_model.json')
q2=query_research_point_one(loaded,[.4,.73,1.17,1.65,2.])
assert q['mean_curve']['curve']==q2['mean_curve']['curve']
assert q['direct_marginal_effect']['estimates']==q2['direct_marginal_effect']['estimates']
with (HERE/'audit_integrated_query.json').open('x',encoding='utf-8') as f:json.dump(q,f,ensure_ascii=False,indent=2)
result=dict(status='passed',input_events=480,users=240,structure_subsample_users=48,
    chain=['new scalar features','FCI/KCI and PC/KCI','continuous mean','direct marginal derivative','subgroups','target and bias-corrected threshold','JSON save-load'],
    saved_loaded_queries_identical=True,group_statuses={k:v['mean_curve']['status'] if 'mean_curve' in v else v['status'] for k,v in q['group_effects'].items()},
    old_test_reuse=False,physical_raw_extraction_validated_in_this_audit=False)
with (HERE/'audit_research_result.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=False))
