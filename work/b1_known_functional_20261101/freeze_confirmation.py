from common import *

grid=read('validation_grid_extended.json')
# The strict validation screen passed no configuration. Keep that outcome.
# Independently confirm the most promising SAFE configuration, without claiming
# it passed that screen or adopting it on validation results.
safe=[r for r in grid if all(v for k,v in r['checks'].items() if k!='weak10percent_gain')]
chosen=min(safe,key=lambda r:r['weak']['candidate']['primary_seconds'])
chosen['validation_passed_all_gates']=False
chosen['purpose']='Independent confirmation of a promising but not yet adopted candidate; strict validation outcome preserved.'
write('selected.json',chosen)
write('confirmation_plan.json',dict(
    no_final_test_generated=True,config=chosen['config'],
    validation_weak_gain=1-chosen['weak']['candidate']['primary_seconds']/chosen['weak']['retained']['primary_seconds'],
    final_adoption_requires=dict(weak_gain_at_least=.1,main_noninferiority_seconds=2,
        fewer_false_positives=True,no_extra_short_local_misses=True,no_extra_whole_misses=True,
        gap_longest_noninferiority_seconds=5,short_duration_noninferiority_seconds=5),
    no_selection_or_retuning_on_final_tests=True,
    duration_predictions_are_functionals_not_a_fabricated_new_state_curve=True))
paths=list(HERE.glob('*.py'))+[HERE/'protocol.json',HERE/'selected.json',HERE/'confirmation_plan.json',HERE/'physical_event_model.json']+list(HERE.glob('*_leaves*.json'))
paths += [p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
write('freeze.json',dict(source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in paths},
    final_test_not_generated=True,validation_screen_failed=True,independent_confirmation_only=True))
print('Confirmation frozen',chosen['config'],flush=True)
