"""Finalize this bounded release and rolling navigation; no old scientific writes."""
import re
from core_io import BASE,ROOT,RAW,read,write,sha,integrity

def main():
    integrity();assert read(BASE/'independent_checks.json')['status']=='passed';assert read(BASE/'prefix_checks.json')['status']=='passed';assert read(BASE/'numeric_boundary_checks.json')['status']=='passed';assert read(BASE/'public_initialization_checks.json')['status']=='passed'
    p=ROOT/'docs/DECISION_LOG.md';text=p.read_text(encoding='utf-8')
    if '## D124｜' not in text:
        old=text.splitlines()[2];new='现用研究接续：D124（2026-10-28），用户限前三算法连续性及稳定性，已补B1原二元校验/合法旧值相同、B2固定模型SHA、剩余需求与状态绑定、原B2学习产物连续消费、B3防护完整回放及只读新目录复核。根b123_api.py为现用函数入口；站180/EV期限120、两任务0及60/90，欠账与T30不外推。240新配对运行，声明范围内168接项服务/160运行恢复通过，范围外服务失败与4未恢复保留；369旧文件同。有限稳定性包收口，不扩研究/第四算法，不称任意任务/现实/正式90%；D123历史不默认采用、真实冻结/同事代码/旧报告及主稿未迁01保持。条目按ID追加在文末。'
        text=text.replace(old,new,1)+'''

## D124｜前三算法连续性与稳定性逐项收口

- 用户明确不考虑第四，只完善前三个的连续性和各自稳定性。根b123_api.py为当前统一函数入口，保留旧科学包原件供复现；B1拟合/查询/图筛选先查原二元值、合法旧输出同，F0显式时标/累计连续/缺测、多次任务恢复不强作唯一归因。B2固定D122继承的命名rep0/pop1、模型和选择SHA，不对外选重复号，D123历史负结果不默认采用。
- 新站180min/EV原离站120min，两30min站级任务0及60/90到来；每次B2输入E=bT/60+实际欠账，不重置；剩余T120/60可查、欠账和T30/180不外推。B3读取原五模板/概率/期望作为预测记录及最坏轨迹，准入用保守分量见证，许可/实际接受分开。授权早回补可不同于B2原恒定预测，EV120与站180恢复分别核。声明/站点/资源/任务/方案/许可时点绑定，不支持的重叠/重复任务拒绝。
- 生成前21项新源/协议及369旧项冻结，20种子×两余量×两时刻×三机制=240配对变体/20基础/43200分钟。理想/范围内各80运行160请求接84拒76，已接84/84服务且80/80恢复；严重降额80接44拒116、0/44服务、76/80恢复，4未恢复及失败保留。238实际EV方案/128接受，78次正欠账查询阻断、157第二EV查询受支持，不把查询数当接受。最大共享残差3.11e−15kW，主13.50sCPU。
- 旧D120前两种子24场景/864步新防护完整回放，不改旧三策略成绩；理想/范围内各8运行9已接均完成，严重降额8运行8服务发生故障前、末端2/8恢复，另活动服务故障退出/阻新专项。早期严格native检查误拒NumPy状态实数，改有限Real兼容，拒布尔/字符串/非有限；原源文件/初始开发失败及原冻结保留，corrective_identity记录3文件含审计兼容，主240输出SHA同无重跑。两处测试预期错误均留说明。
- 两轮56微型、独立1128976数值/状态项、147前缀/并发、13数值边界及根入口使用/隔离回归通过，非等量独立试验。只读verify_cli写新work目录、拒覆盖已有目录，不执行旧复核脚本。原件data/B1_B3_continuity_v1_20261028，过程[入口](../work/b1_b3_stability_20261028/README.md)/[逐项收口](../work/b1_b3_stability_20261028/review_closure.md)。原369项含74模型v15/会议报告同，无新依赖/GPU/训练/UI/上传/提交。
- 此轮只完成当前支持域稳定性与连续性，不宣告任意设备/多任务/真实可靠性或正式90%通过。时序正式路线、跨机制和现实证据/90口径保留在完整研究层，不以此自动新开实验或第四算法；真实冻结/同事代码/旧报告/待审主稿未迁01保持，承诺null。
'''
        p.write_text(text,encoding='utf-8')
    write(BASE/'stage_gate.json',dict(status='passed_bounded_B1_B2_B3_stability_and_continuity',current_entry='b123_api.py',B1_raw_binary_guard=True,fixed_B2_version_and_model_SHA=True,actual_remaining_demand_and_deadline=True,learned_B2_native_paths_probabilities_consumed=True,B3_full_guarded_replay=True,read_only_new_directory_audit=True,old_protected_files_unchanged=369,
      scoped_results=read(BASE/'results.json')['groups'],B1_history_default_adopted=False,B2_T180_or_debt_extrapolated=False,arbitrary_task_support=False,real_world_validation=False,formal90_pass=False,committed_kw=None,remaining_formal_scope=['different resource mechanisms','formal temporal research positioning beyond current study','real behavior/control and calibrated reliability','agreed formal90 evaluation'],new_followup_experiment_started=False))
    correction=read(BASE/'corrective_identity.json');assert sha(BASE/'runs.json')==correction['primary_run_sha_before'] and sha(BASE/'results.json')==correction['primary_results_sha_before'];integrity()
    files={str(p.relative_to(ROOT)):sha(p) for p in BASE.iterdir() if p.is_file() and p.name not in ['final_snapshot.json','final_checks.json','audit_entry_checks.json']}
    for p in [ROOT/'b123_api.py',RAW/'cases.json',RAW/'executor_private.npz',RAW/'README.md']:files[str(p.relative_to(ROOT))]=sha(p)
    write(BASE/'final_snapshot.json',dict(files=files,source_freeze_unchanged=True,corrective_identity='corrective_identity.json',primary_outputs_unchanged_after_numeric_fix=True,old369_files_unchanged=True))
    print('release snapshot',len(files),'files',flush=True)

if __name__=='__main__':main()
