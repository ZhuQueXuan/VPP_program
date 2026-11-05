from common import *
grid=read('validation_grid_pulse_margin.json')
safe=[r for r in grid if all(v for k,v in r['checks'].items() if k!='weak_genuine_short_recovery10percent')]
selected=min(safe,key=lambda r:r['weak']['genuine_short_n']['candidate']['genuine_short_miss'])
selected['validation_all_gates_passed']=False
selected['status']='Safe but modest development gain; independent confirmation required. Strict validation screen failure is retained.'
write('selected.json',selected)
write('confirmation_plan.json',dict(selected_configuration=selected['config'],
    validation_recovery=6,validation_misses_before=108,validation_misses_after=102,
    original10percent_validation_screen_failed=True,
    final_adoption_still_requires_original_gates=True,
    fresh_weak_amplitudes='Uniform0.07..0.30kW, six equal-width strata per shape/seed, independent randomized assignment. Continuous amplitude generalization, not selective replay.',
    no_new_final_draws_exist=True,no_tuning_on_new_final=True))
paths=list(HERE.glob('*.py'))+[HERE/'protocol.json',HERE/'selected.json',HERE/'confirmation_plan.json',HERE/'raw31.json',HERE/'raw63.json']
paths += [p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
write('freeze.json',dict(source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in paths},final_not_generated=True,strict_validation_screen_passed=False))
print('Safe candidate frozen for independent confirmation',selected['config'],flush=True)
