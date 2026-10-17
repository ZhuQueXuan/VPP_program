"""Synchronize research priority after D023; keep all data/protocol/results unchanged."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; pending={}
def read(name):
    if name not in pending: pending[name]=(ROOT/name).read_bytes().decode('utf-8')
    return pending[name]
def line(name,prefix,new):
    rows=read(name).splitlines(keepends=True); found=[i for i,v in enumerate(rows) if v.startswith(prefix)]
    if len(found)!=1: raise ValueError((name,prefix,len(found)))
    i=found[0]; ending='\r\n' if rows[i].endswith('\r\n') else '\n'; rows[i]=new+ending; pending[name]=''.join(rows)
def insert(name,marker,new):
    text=read(name)
    if text.count(marker)!=1: raise ValueError((name,marker))
    ending='\r\n' if '\r\n' in text else '\n'; pending[name]=text.replace(marker,new.replace('\n',ending)+marker,1)

line('outputs/ROADMAP_v2.md','当前进展（','当前进展（2026-10-14，D023）：按最新会议纪要及原逐字稿核验，锂离子储能选型和单类推进符合方向，但细粒度资源特性研究仅部分完成。D022最小baseline闭环/数据卡04结果保留，不等于老师要求完成。立即下一项改为补齐典型曲线→物理关系/约束→参数依据→调节指标→计算样例的单体研究样板，跨期扩样本后置；未进入市场/组合，无新实验。[会议对照与handoff](../work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md)。')
line('outputs/第一阶段两周执行计划_v2_20261013.md','当前状态：','当前状态：D023核验最新会议要求，选类型已落实、单体特性研究部分完成。D022容量代理最小baseline流程通过，输入卡03/结果卡04不变；不能将其视为老师要求全部完成。下一项先补曲线、物理关系/约束、参数、指标与完整样例，跨期扩样本后置，无新实验。[核验与交接记录](../work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md)。')
line('outputs/第一阶段两周执行计划_v2_20261013.md','当前主动单项（D022/D020）：','当前主动单项（D023）：补齐锂离子储能单体特性研究样板。直接呈现有来源的典型实测曲线和物理模型，解释从曲线/状态到可计算调节指标的转换，再给一条完整样例；未知SOC、时延、持续/恢复边界不补造。')
line('outputs/第一阶段两周执行计划_v2_20261013.md','当前下一项是','当前下一项是按D023补齐锂离子储能单体特性研究样板，与老师最新会议的曲线/公式/参数/指标要求衔接。阶段总结与handoff已增加逐项核验；容量跨期验证后置保留，不改已有协议、结果或正式任务，不开启复杂模型。')
line('AGENTS.md','- 2026-10-14状态快照：','- 2026-10-14状态快照：最新技术裁决D023；当前数据/结果卡DC-20261014-04，容量实验输入卡03，阶段协作D020。已核对最新会议纪要（10-10为整理日期）与原逐字稿，选锂离子储能和先单类符合方向，但资源特性研究仅部分完成；老师未指定首类型必须储能。D022完成受限baseline比较/复现流程，不代表会议要求全部完成或90%精度。下一项先补典型实测曲线→物理关系/约束→参数依据→调节指标→计算样例的单体研究样板；原跨期扩样本建议后置。已有转换/日志预测/单事件容量代理与复现结论保持；B_PHASE方法独立确认、完整SOC/电芯净收支、真实时延/持续恢复/VPP可承诺量未验证。旧评分/模拟整改本轮未专项核验，不能当已经完成。无新数据/模型/训练，不进入市场适配/组合，GPU按D016。本人能否讲清须由用户沿样例核验。入口work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md（新增会议对照表）及work/resource_sample_selection_20261013/README.md。')
line('AGENTS.md','| 1 | [docs/DECISION_LOG.md]','| 1 | [docs/DECISION_LOG.md](docs/DECISION_LOG.md) | 先读最新D023会议符合性与研究顺序、D020交接、D021代理协议与量测更正、D022受限闭环，再追溯前序决定 |')
insert('项目文件索引.md','- 2026-10-14最新进展（D022）：','''- 2026-10-14最新进展（D023）：已核对最新会议纪要与原逐字稿，[handoff新增会议要求对照](work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md)。选锂离子储能及单体推进符合方向，但资源特性研究仅部分完成；D022流程闭环不等于老师要求完成。下一项先补实测曲线、物理关系/约束、参数、指标与计算样例，跨期扩样本后置；卡04/输入03及已有实验不变，无新训练。

''')
line('work/resource_sample_selection_20261013/README.md','本目录保存','本目录保存P1组件baseline过程。最新D023会议核验：储能选型已落实，资源特性研究部分完成，下一项先补曲线/物理关系/参数/指标/完整样例，跨期扩样本后置。结果卡04/容量输入03不变；D022最小baseline流程闭环保留，不等于老师要求完成。无新模型或训练，会议对照见阶段handoff。')
insert('docs/DATA_CARD.md','## 本次真实实验使用状态','''执行顺序补充（D023）：最新会议核验认为选型已落实、资源特性研究部分完成；下一项先补典型曲线、物理模型/约束与指标计算样例，跨期扩样本后置。本次仅改变研究顺序，不改卡04的数据/样本/结果或冻结机器协议。[会议对照](../work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md)。

''')
line('docs/EXPERIMENT_LOG.md','用途：','用途：回答研究对象、输入协议、真实结果与后续理由。D022受限最小baseline闭环保持；D023会议核验将下一项调整为单体特性曲线/物理关系/参数/指标样板，跨期扩样本后置。本轮只核验会议符合性，无新实验；结果卡04、输入03与历史成绩不变。')
for name,text in pending.items():
    if not (ROOT/name).is_file(): raise FileNotFoundError(name)
for name,text in pending.items(): (ROOT/name).write_bytes(text.encode('utf-8')); print(name)
