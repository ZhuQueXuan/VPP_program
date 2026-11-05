from study import *

final=json.loads((HERE/'final/summary.json').read_text(encoding='utf-8'))
verify=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
physical=json.loads((HERE/'physical/score.json').read_text(encoding='utf-8'))
refit=json.loads((HERE/'refit_summary.json').read_text(encoding='utf-8'))
selection=json.loads((HERE/'development_selection.json').read_text(encoding='utf-8'))
save(HERE/'decision.json',dict(
    status='integrated_research_point_one_EV_simulation_prototype_complete',
    accepted_engineering_integration=True,mean_method='existing_Kennedy_continuous_DR',
    default_marginal_effect=selection['default_marginal_effect'],
    adopt_direct_derivative_as_replacement=False,direct_derivative_research_interface_available=True,
    structure_role='diagnostic_equivalence_class_not_automatic_adjustment',
    first_block_original_weights_and_default_preserved=True,
    final_cohorts=16,final_fact_variants=16*360,final_independent_seed_blocks=4,
    final_curve_rmse_seconds=final['aggregate']['curve_rmse_seconds']['mean'],
    final_smoothed_derivative_rmse=final['aggregate']['smoothed_derivative_rmse']['mean'],
    final_direct_derivative_rmse=final['aggregate']['direct_derivative_rmse']['mean'],
    grouped_full_grid_differences_available=final['aggregate']['group_effect_difference_rmse_seconds']['outputs'],
    grouped_full_grid_differences_requested=16,
    target_truth_reached=verify['true_target_reached'],false_target_reached=verify['false_target_reached'],
    missed_target_reached=verify['missed_target_reached'],
    raw_physical_events=physical['events'],raw_physical_duration_mae=physical['first_block_duration_mae'],
    raw_physical_curve_rmse=physical['curve_rmse_seconds'],
    nuisance_refit_draws=refit['all_draws_attempted'],complete_refit_cohorts=refit['complete_cohorts'],
    incomplete_refit_cohorts=refit['incomplete_cohorts'],
    full_real_mechanism_validation=False,multi_resource_adapters_empirically_validated=False,
    formal_90percent_acceptance=False,no_post_final_parameter_tuning=True,
    next='Use this integrated version. Improve subgroup/structure evidence through justified new data or hypothesis; do not chase this final panel.'
))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
folder=HERE/'final/90332001-observed_confounding'
q=json.loads((folder/'query.json').read_text(encoding='utf-8'));t=json.loads((folder/'truth.json').read_text(encoding='utf-8'))
fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
def label(ax,title,y):
    ax.set_title(title,fontproperties=font);ax.set_xlabel('补偿金额（元/千瓦时）',fontproperties=font)
    ax.set_ylabel(y,fontproperties=font);ax.grid(alpha=.2)
c=q['mean_curve']['curve'];x=c['incentive_values']
axes[0,0].plot(x,c['contrasts'],label='现有连续DR')
axes[0,0].plot(x,t['contrasts'],'--',label='模拟机制真值（仅评价）')
axes[0,0].axhline(120,color='grey',ls=':',label='示例目标：增加120秒')
label(axes[0,0],'连续补偿作用：固定目标人群','平均累计响应增量（秒）')
axes[0,1].plot(x,q['retained_smoothed_derivative']['values'],label='保留平滑导数（默认）')
axes[0,1].plot(x,q['direct_marginal_effect']['estimates'],alpha=.75,label='直接DR导数（研究对照）')
axes[0,1].plot(x,t['derivative'],'--',label='模拟机制真值')
label(axes[0,1],'边际作用：多补一点能多响应多少','秒 / 金额单位')
for name,title in [('slack_below','期限余量较低'),('slack_above','期限余量较高')]:
    g=q['group_effects'][name]['mean_curve']['curve']
    if g:axes[1,0].plot(g['incentive_values'],g['contrasts'],label=title)
label(axes[1,0],'事前人群差异：组内补偿作用','平均累计响应增量（秒）')
values=[final['aggregate'][key]['mean'] for key in ['smoothed_derivative_rmse','direct_derivative_rmse','shared_epanechnikov_quadratic_derivative_rmse']]
axes[1,1].bar(range(3),values,color=['#3976b9','#d98242','#7d8c97'])
axes[1,1].set_xticks(range(3),['原平滑导数','直接DR导数','同紧支撑核对照'],fontproperties=font)
axes[1,1].set_title('全部16条新终验：导数误差比较',fontproperties=font)
axes[1,1].set_ylabel('RMSE（秒 / 金额单位），越低越好',fontproperties=font)
for j,value in enumerate(values):axes[1,1].text(j,value+8,f'{value:.1f}',ha='center')
for ax in axes.ravel()[:3]:ax.legend(prop=font,fontsize=8)
fig.suptitle('研究点一已接通：结构诊断＋特征＋连续作用＋敏感性＋目标阈值\n上三图展示预定首个观测混杂队列；下右图为全部终验；均为模拟',fontproperties=font,fontsize=13)
fig.savefig(HERE/'algorithm_results.png',dpi=150);plt.close(fig)
print(json.dumps(dict(decision='saved',final=final['aggregate'],refit_complete=refit['complete_cohorts'],refit_incomplete=refit['incomplete_cohorts'])))
