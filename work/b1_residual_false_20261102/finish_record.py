from common import *
d=read('confirmation_decision.json');initial=read('assessment.json');adopted=d['adopted'];last=d['combined_summary']['pooled'];conf=d['confirmation_summary']['pooled'];audits=[read('final_audit.json'),read('confirmation_audit.json')]
def table(s):
    lines=['|方法|整任务准确率|误报任务|全漏任务|真短位置漏检|时长主MAE(s)|','|---|---:|---:|---:|---:|---:|']
    for method,label in [('cpop','原CPOP'),('labs','LABS'),('retained','现用有益版'),('candidate','本轮候选')]:
        r=s[method];lines.append(f"|{label}|{r['task_accuracy']*100:.4f}%|{r['null_false_positive']}|{r['whole_miss']}|{r['genuine_short_miss']}/{r['genuine_short_n']}|{r['primary_seconds']:.5f}|")
    return '\n'.join(lines)
paragraphs=['# 第一部分：剩余误报诊断与多窗口证据核验（2026-11-02）',
    ('当前采用入口：`process_method="effective_response_evidence"`，旧`effective_response_refined`及全部旧方法保留。' if adopted else '本轮候选未采用。现用入口仍为`process_method="effective_response_refined"`，生产算法、权重和默认不变。'),
    '## 原因\n上批2808任务剩444误报：123真实无动作、321有弱物理变化但未达0.15kW。405来自带注入干扰条件，其中314在同一基础轨迹的纯高斯配对中判对。443条原CPOP已经给出正时长，主要不是后续时长校正把负任务变正。安静背景区有283误报，也包含全部300真实短动作，不能统一压孤立点。详见diagnosis/paired_diagnosis/evidence_audit。',
    '## 实际改动\n保留已有426维描述，增加101维单采样格、60/120/300/600秒窗口证据，包括均值分位数、临界功率占比、连续段及超阈面积。标准HGB31叶、300轮，正任务权重5、有效短任务50、负任务1。观察中位数低于0.20kW且原有正资格时复核；quiet阈0.05、weak阈0.001。分数不是校准概率，阈值不代表误报率。拒绝是明确的有效资格负预测，C/L及有效状态清零，全部样本照常计入误判；原测量、物理变化证据、CPOP曲线、support曲线、其他物理过程特征及原电量/η保留。不改CPOP求解器、不删点填缺口、不设最短真实动作时长。',
    '## 数据与选择\n23668旧已知模拟任务明确作开发，其中10747原正且低背景任务用于拟合，7243正任务、527维；当前验证/最终样本不参与训练。新7801验证1404比较3模型与quiet/weak分数切点，冻结选择31叶/.05/.001后才生成7802测试。弱场景每形状×seed独立随机六连续幅度层0.07—0.30kW；1min与10s，同原生CPOP/LABS输入、sigma与物理判据。',
    '## 首次冻结测试：不抹去未达门结果\n2808输入、792基础轨迹、四法11232输出。误报414→373，减少9.90338%，无新增真拒/短漏，但未过原先10%收益门；assessment.adopted=false保留。没有按本批调参或降低门槛。\n\n'+table(initial['summary']['pooled']),
    '## 一次扩大独立确认\n在任何7803数据生成前留confirmation_plan与freeze；相同模型、阈值和输入，不重训，不再选型，只允许这一次确认。5616输入、1584基础、四法22464输出；要求确认单独与合并都过原10%降误报门以及全部安全门。\n\n'+table(conf),
    '## 两批合并（同时列出，不能替换首批）\n8424输入、2376基础轨迹、四法33696行。配对干扰变体不是独立车辆。\n\n'+table(last),
    '## 决定与复核\n'+('确认单独和合并的全部门通过，接入新显式入口；初次10%门未过的记录仍保留。' if adopted else '确认或合并门未全部通过，不接入，保留现用有益版。')+
    f" 合并误报减少{100*(last['retained']['null_false_positive']-last['candidate']['null_false_positive'])/last['retained']['null_false_positive']:.4f}%。新真有效误拒{sum(a['newly_rejected_true_tasks'] for a in audits)}条。详见confirmation_decision、final/confirmation_audit、confirmation_scalar_audit、baseline_replay与preservation。",
    '## 被误拒的真实任务\n扩大确认有1条真实弱振荡响应被整任务误拒：真实峰0.1594008kW，实际达标60s，观察中位0.06940kW，分类分数0.0035903低于quiet的0.05。旧版恰好估出60s但位置已错；本版改为0，新增整任务漏检，不能用“局部漏检数没变”掩盖。原量测在真实达标位置也未过0.15，分类器误把有短暂达标的弱过程当成全程未达标，非删除孤立点。详见rejected_true_diagnosis。',
    '## 后续方向\n不按已见样本下调分数追分。下一候选应把局部功率水平估计及其量测干扰证据与整任务资格联动，先保留短片段候选，再做局部达标复核；当前整任务分类器无法指出应当保留的真实位置。可评估method_notes中的多尺度区间方法作为候选来源，但统计异常不能当故障真值，也不能直接删掉短区间。尚未实现或证明该方向有益。',
    '## 适用范围\n这里只是已知参照、30分钟任务、q1.5kW、sigma.05kW、前后15分钟、10s/1min采样的有真值模拟。准确率仅指整任务是否达到有效响应标准，不是全特征准确率，也非现场结果。仍存在大量误报与漏检，特别是无动作受干扰样本改善有限。报告、参考预测与第二部分未改。近期论文与开源取舍见method_notes；只作为备选，未借用理论保证。']
(HERE/'README.md').write_text('\n\n'.join(paragraphs)+'\n',encoding='utf-8')
if adopted:assert read('public_checks.json')['all_passed']
paths=['README.md','diagnosis.json','paired_diagnosis.json','evidence_audit.json','protocol.json','training_receipt.json','selected.json','freeze.json','assessment.json','confirmation_plan.json','confirmation_freeze.json','confirmation_decision.json','final_audit.json','confirmation_audit.json','confirmation_scalar_audit.json','baseline_replay.json','method_notes.md','rejected_true_diagnosis.json','preservation_before.json']
for stage in ['main_test','weak_test','main_confirmation','weak_confirmation']:
    paths += [stage+'/'+p for p in ['facts.json','curves.json','metrics.json','assessment.json','baseline.json','effective_X.npy']]
    for panel in ['minute','10s']:paths += [stage+'/'+panel+'/'+p for p in ['truth.json','mixed_truth.json']]
if adopted:paths+=['public_checks.json','production_before.json','release_build.json','preservation_after.json']
write('completion_receipt.json',dict(status='complete',adopted=adopted,entrypoint='effective_response_evidence' if adopted else 'effective_response_refined',
    initial_gate_failed_preserved=True,one_fixed_larger_confirmation=True,no_threshold_or_model_changes_after_initial_test=True,
    initial_inputs=2808,confirmation_inputs=5616,combined_inputs=8424,base_trajectories=2376,four_method_rows=33696,
    combined_summary=last,confirmation_summary=conf,all_original_qualification_thresholds_and_raw_points_preserved=True,
    previous_versions_and_scientific_results_preserved=True,controlled_simulation_not_field_data=True,
    no_prediction_report_or_second_block_changes=True,no_new_dependency_GPU_deletion_or_external_submission=True,
    result_sha256={p:sha(HERE/p) for p in paths}))
print('Completed; adopted=',adopted,'combined accuracy',last['retained']['task_accuracy'],last['candidate']['task_accuracy'],'FP',last['retained']['null_false_positive'],last['candidate']['null_false_positive'],flush=True)
