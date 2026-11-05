from study import *

development=json.loads((HERE/'development/summary.json').read_text(encoding='utf-8'))
a=development['aggregate'];smooth=a['smoothed_derivative_rmse']['mean'];direct=a['direct_derivative_rmse']['mean']
passed=direct<.95*smooth and a['direct_derivative_rmse']['outputs']==len(development['rows'])
decision=dict(pre_final=True,derivative_gain_at_least5percent=passed,
    default_marginal_effect='direct_derivative' if passed else 'retained_smoothed_derivative',
    development_smoothed_derivative_rmse=smooth,development_direct_derivative_rmse=direct,
    direct_retained_as_research_comparator=True,mean_curve_to_keep='existing_Kennedy_DR',
    no_parameter_change_after_development=True)
save(HERE/'development_selection.json',decision)
paths=[ROOT/'B1算法/b1_api.py',ROOT/'B1算法/research_cli.py',HERE/'data.py',HERE/'study.py',HERE/'protocol.json',HERE/'development_selection.json']
paths+=list((ROOT/'B1算法/b1_algorithm').rglob('*.py'))
save(HERE/'source_freeze.json',dict(before_final_generation=True,files={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))
print(json.dumps(decision))
