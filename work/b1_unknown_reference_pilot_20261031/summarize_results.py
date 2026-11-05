"""Make reviewable block-level results; no estimator calls or selection."""
from collections import defaultdict
import numpy as np
from pilot_common import HERE,ROOT,read,write_new,sha

main=read(HERE/'test_assessment.json');supp=read(HERE/'sensitivity_test_assessment.json')
ref=read(HERE/'reference_selection.json');sel=read(HERE/'process_selection.json')
methods=['tf_gls','cpop','cpop_meter_sigma'];groups={}
for r in main['groups']:groups[(r['variant'],r['method'])]=r
for r in supp['groups']:groups[(r['variant'],'cpop_meter_sigma')]=r
compact=[]
for m in methods+['tf_standard']:
    row=dict(method=m)
    for v in ['strong','weak','null']:
        g=groups[(v,m)];row[v+'_duration_mae_seconds']=g['duration_mae_seconds']
    weak=groups[('weak',m)];null=groups[('null',m)]
    row.update(weak_misses=weak['missed_positive_duration'],weak_positive=weak['threshold_positive'],
        weak_inconclusive=weak['positive_inconclusive'],null_duration_false=null['false_positive_duration'],
        null_n=null['no_action'],null_false_evidence=null['no_action_false_evidence'],
        scenario_equal_duration_mae_seconds=float(np.mean([groups[(v,m)]['duration_mae_seconds'] for v in ['strong','weak','null']])))
    compact.append(row)
timing=read(HERE/'test_completed.json')['timings'];timing_sum=defaultdict(float)
for r in timing:timing_sum[r['method']]+=r['seconds']
timing_sum['cpop_meter_sigma']=sum(r['seconds'] for r in read(HERE/'sensitivity_test_completed.json')['timings'])
metrics=read(HERE/'test_metrics.json')+read(HERE/'sensitivity_test_metrics.json')
by=defaultdict(list)
for r in metrics:by[(r['seed'],r['variant'],r['method'])].append(r['duration_error_seconds'])
supp_diffs={v:[float(np.mean(by[(s,v,'tf_gls')])-np.mean(by[(s,v,'cpop_meter_sigma')])) for s in [7610500,7610501,7610502,7610503]] for v in ['strong','weak','null']}
evidence_users=[]
for m in methods+['tf_standard']:
    ub=supp['user_blocks'] if m=='cpop_meter_sigma' else [r for r in main['user_block_evidence'] if r['method']==m]
    for v in ['strong','weak','null']:
        rr=[r for r in ub if r['variant']==v]
        evidence_users.append(dict(method=m,variant=v,users=sum(r['users'] for r in rr),evidence_users=sum(r['evidence_users'] for r in rr)))
out=dict(status='small_reproduction_complete_formal_selection_deferred',formal_adoption=False,
    selected_internal_reference=ref['selected'],reference_internal_rows=ref['rows'],
    process_parameters=sel['chosen'],sigma_effective=read(HERE/'development_error_model.json')['sigma_effective'],
    test_base_tasks=256,test_variants=768,main_outputs=2304,sensitivity_outputs=768,
    compact=compact,batch_elapsed_seconds_sum=dict(timing_sum),user_block_evidence=evidence_users,
    tf_gls_minus_original_meter_cpop_seed_differences_seconds=supp_diffs,
    conclusion='Do not adopt TF_GLS as formal B1: weak miss count is lower, but null false durations and strong/weak MAE have counterexamples against original-meter-sigma CPOP. No tuning on this test.',
    actual_implementation=['Four fixed mature reference configurations, native serialization and internal non-event validation choice',
        'Native-bin TF convex dual reproduction, scalar/full development-residual covariance and numerical certificates',
        'One feature-extraction block comparison with shared frozen reference and independent user-block task calibration',
        'CPOP sensitivity pre-test frozen after validation, both configurations fully retained'],
    not_implemented=['No new general prediction or extraction estimator','No validated feature confidence intervals or GP posterior-path propagation',
        'No actual departure/natural stopping/missing-window/15min validation','No second response-analysis changes',
        'No production default/API/source change'],
    interpretability_limits=['Prediction internal choice is not a separate formal baseline benchmark',
        'TFstandard vsTFGLS changes both covariance treatment and selected penalty; not a pure covariance causal ablation',
        'CPOP original/effective sigma comparison is a fixed sensitivity, not a test-selected weaker baseline',
        'Timing sums are observed batch elapsed including native startup, not exclusive core per-event latency'])
write_new(HERE/'pilot_summary.json',out)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
plt.rcParams['axes.unicode_minus']=False
fig,axes=plt.subplots(1,3,figsize=(12.3,3.7))
names=['趋势滤波\n完整协方差','CPOP\n共同总误差尺度','CPOP\n原计量噪声尺度']
colors=['#d98b3a','#54748a','#2e8575']
for ax,values,title,ylabel in [
    (axes[0],[groups[('weak',m)]['duration_mae_seconds'] for m in methods],'弱响应时长误差','MAE（秒）'),
    (axes[1],[100*groups[('weak',m)]['missed_positive_rate'] for m in methods],'弱响应漏检','比例（%，分母176）'),
    (axes[2],[100*groups[('null',m)]['false_positive_duration_rate'] for m in methods],'无动作正时长误检','比例（%，分母256）')]:
    ax.bar(names,values,color=colors,width=.6);ax.set_title(title);ax.set_ylabel(ylabel)
    ax.spines[['top','right']].set_visible(False)
    for i,val in enumerate(values):ax.text(i,val+max(values)*.03,f'{val:.2f}',ha='center',fontsize=9)
    ax.set_ylim(0,max(values)*1.22)
fig.suptitle('未知参考EV小规模复现｜相同冻结参考，4个配对种子块｜非现场验证',fontsize=11)
fig.tight_layout();fig.savefig(HERE/'block_comparison.png',dpi=170);plt.close(fig)
print(__import__('json').dumps(dict(compact=compact,timing=dict(timing_sum),sigma=out['sigma_effective'],paired_original=supp_diffs),ensure_ascii=False))
