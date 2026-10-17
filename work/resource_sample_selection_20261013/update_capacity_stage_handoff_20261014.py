"""Record actual limited baseline closure and handoff; leave machine protocols unchanged."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; pending={}
NOTE='work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md'
def read(name):
    if name not in pending: pending[name]=(ROOT/name).read_bytes().decode('utf-8')
    return pending[name]
def line(name,prefix,new):
    entries=read(name).splitlines(keepends=True); ids=[i for i,v in enumerate(entries) if v.startswith(prefix)]
    if len(ids)!=1: raise ValueError((name,prefix,len(ids)))
    i=ids[0]; eol='\r\n' if entries[i].endswith('\r\n') else '\n'; entries[i]=new+eol; pending[name]=''.join(entries)
def replace(name,old,new):
    text=read(name)
    if text.count(old)!=1: raise ValueError((name,old,text.count(old)))
    pending[name]=text.replace(old,new,1)
def insert(name,marker,new):
    text=read(name)
    if text.count(marker)!=1: raise ValueError((name,marker))
    eol='\r\n' if '\r\n' in text else '\n'; pending[name]=text.replace(marker,new.replace('\n',eol)+marker,1)
def append(name,new):
    text=read(name); eol='\r\n' if '\r\n' in text else '\n'; pending[name]=text+new.replace('\n',eol)

line('docs/DATA_CARD.md','卡版本：','卡版本：DC-20261014-04｜建立日期：2026年10月13日；更新日期：2026年10月14日')
line('docs/DATA_CARD.md','当前更新（D021）：','当前更新（D022）：按输入卡03完成单系统容量代理baseline比较、复跑和原始独立复算。B_HIST_SPAN本次容量/电量相对误差1.007028%/0.132706%，额定为9.879629%/8.391411%，数据表电量1.462354%；仅一个受控测试，不是准确率或稳定效果确认。样本8份、baseline5份产物分别复跑一致，未拟合参数；1个B_DS容量输出明确不可用，运行失败0。达到受限最小闭环交接点，按D020先总结/handoff，未完成整体能力/90%验证。输入协议与旧M5BAT结果不变。')
insert('docs/DATA_CARD.md','## 当前容量样本协议：','''## 本次真实实验使用状态（D022）

- 输入仍为卡03、样本v1，卡04只补结果/使用状态，不改来源、阈值、48h、配对/划分。BL_HOME_CAP_20261014_01/02现用；[阶段总结与handoff](../work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md)。
- 容量Ah：B_NOM 15，绝对误差1.348698Ah（9.879629%）；B_HIST_SPAN 13.513829，绝对误差0.137472Ah（1.007028%）。B_DS没有Ah值，保留不可用，不换算或补填。
- 电量kWh：B_NOM 2.2/B_DS 2.0/B_HIST_SPAN 2.032375，绝对误差0.170319/0.029681/0.002694kWh，相对误差8.391411%/1.462354%/0.132706%。仅一事件，净区间积分非真正满循环或VPP能力真值。
- 两次5份产物指纹相同，VERIFY_BL_HOME_CAP_20261014_01原始区间I/UI及出版方XLSX独立复算全部6行预测/指标/不可用情况，最大预测差1.315e-13、指标差1.247e-12，容差1e-9。数值复现不是方法独立确认。
- 该测试已用于本次比较；阈值/端点/隔离不得据误差重选。其他三次作者参照曾见、原始月未取。下一研究建议为同系统跨期复核，但先完成本阶段总结/handoff，不开启复杂方法。

''')
replace('docs/DATA_CARD.md','baseline评分尚未运行。','冻结时baseline尚未评分；现在的实际运行见上文D022。')
replace('docs/DATA_CARD.md','DC侧量测含BMS供电。','DC侧端口量测，内部供电/均衡未直接测得的分量待识别。')
insert('docs/DECISION_LOG.md','## 追加模板','''## D022｜容量代理最小baseline闭环完成，进入阶段总结与handoff

- 日期：2026-10-14。
- 状态：采用；真实比较、复跑及原始独立复算通过，受限流程闭环完成。
- 决定：单系统单事件DC可用量代理的最小baseline闭环完成，作为本轮储能样板的重要阶段节点，按D020主动通知并先总结/handoff。本轮不继续新增实验，不宣称整个P1/课题、真实VPP能力或独立方法确认完成。
- 证据：BL_HOME_CAP_20261014_01/02及VERIFY_BL_HOME_CAP_20261014_01，样本PREP_HOME_CAP_20261014_01/02及其独立复核。[阶段总结与handoff](../work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md)。8份样本/5份实验产物分别一致；原始1002219行重新识别锚点/配对，原始历史区间与XLSX重新复算全部6行预测/指标/不可用，预定1e-9容差通过。
- 结果：容量相对误差B_NOM 9.879629%、B_HIST_SPAN 1.007028%；电量B_NOM 8.391411%、B_DS 1.462354%、B_HIST_SPAN 0.132706%。仅一个受控事件，本次代理较接近参照；不是准确率、90%达标或稳定增益。B_DS容量无数据而不可用，运行失败0，未调阈值/端点/隔离或拟合参数。
- 限制：电压代理不保证满空SOC，自然倍率和最大功率测试不同，内部损耗/温度/降额未知；同系统/共享量测链，参照已见，不称盲测。旧B_PHASE独立确认仍缺，旧M5BAT协议/结果不变。
- 影响：结果卡DC-20261014-04，实验输入仍卡03，机器协议不改。路线、第一阶段计划、AGENTS/导航更新交接节点；尚不开放自监督/协同/市场适配，无服务器申请。
- 交接后建议：取得同系统后续受控测试的原始历史，保持算法阈值/积分与诚实测试使用状态，另冻结日期/历史窗/来源，检验跨期稳定性。暂不实施；阶段总结和现用入口已在handoff记录中准备。

''')
line('docs/EXPERIMENT_LOG.md','用途：','用途：回答研究对象、输入协议、真实结果与后续理由。D022单系统容量代理最小baseline比较/复现闭环完成，当前进入阶段总结/handoff；一事件不证明稳定效果或VPP可承诺量。实验输入卡03，当前结果卡04；旧组件结果/缺口保持。')
replace('docs/EXPERIMENT_LOG.md','- 状态：计划，尚未评分；依据D021','- 状态：运行前计划（登记时尚未评分），实际结果见BL_HOME_CAP记录；依据D021')
append('docs/EXPERIMENT_LOG.md','''
## BL_HOME_CAP_20261014_01/02｜容量代理单事件回顾比较

- 状态：真实运行与独立原始复算通过；D022，输入卡DC-20261014-03，结果卡04。run_home_capacity_baselines.py，无参数拟合、CPU总耗时0.291/0.246秒，运行失败0。
- 数据/协议：PREP_HOME_CAP_20261014_01，样本与baseline v1；特征/标签分开，48h隔离不改。PREP重复02八份产物一致，VERIFY_HOME_CAP_20261014_01从原始历史独立重建全部静置/配对/选窗/积分，最大差1.19e-12。
- 容量Ah：作者13.6513019678，B_NOM 15/B_HIST_SPAN 13.5138294783，绝对误差1.3486980322/0.1374724894Ah，相对9.879629%/1.007028%。B_DS的Ah无依据，1个不可用输出明确保留，非运行错误。
- 电量kWh：作者2.0296811140，B_NOM 2.2/B_DS 2.0/B_HIST_SPAN 2.0323746277；绝对误差0.1703188860/0.0296811140/0.0026935137kWh，相对8.391411%/1.462354%/0.132706%。有符号误差与逐条预测/失败保留，不作跨单位总分。
- 复现：两次predictions/metrics/failures/protocol_snapshot/input_snapshot五份指纹一致。VERIFY_BL_HOME_CAP_20261014_01独立原始区间I/UI与出版方XLSX复算全6行预测/指标/可用性，最大预测差1.315e-13、指标差1.247e-12，容差1e-9。
- 局限/裁决：一个系统/一个测试，历史区间非SOC真满循环，标签已见、同量测链，只有回顾流程闭环；不得换成90%准确率或正式能力证明。无新增OCV/偏置拟合，不进入高级方法/市场适配。按D020结束新增实验，先做[阶段总结与handoff](../work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md)，交接后建议跨期复核，不立即实施。
''')
line('outputs/ROADMAP_v2.md','当前进展（','当前进展（2026-10-14，D022）：单系统容量代理最小baseline闭环完成，输入卡03/结果卡04，BL_HOME_CAP_20261014_01/02及原始独立复算通过。容量/电量相对误差B_HIST_SPAN 1.007028%/0.132706%，本次低于额定，但只有一个受控测试，非稳定效果或VPP真容量确认。按D020达到阶段交接节点，先总结/handoff，本轮不新增实验；完整能力与旧B_PHASE独立确认缺口保留，不开放高级方法。[阶段总结与handoff](../work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md)。')
line('outputs/ROADMAP_v2.md','当前G1状态：','当前G1状态：转换、日志功率预测两个组件及本次单事件DC容量代理对照在各自受限用途下完成最小流程核验。D022不证明真实SOC满空、最大VPP容量或方法独立确认；D017分阶段模型仍缺新时段确认。当前为可交接的储能样板节点，按D020先总结/handoff；整体课题与后续模型须各自准入。')
line('outputs/第一阶段两周执行计划_v2_20261013.md','当前状态：','当前状态：D022/DC-20261014-04（实验输入03）完成容量代理单事件baseline真实比较/复跑/原始独立复算，达到可总结交接节点；样本8份/实验5份产物分别一致。只有一个测试，不是稳定容量效果/90%验收；按D020先总结/handoff，不新增实验。[阶段记录](../work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md)。')
line('outputs/第一阶段两周执行计划_v2_20261013.md','当前主动单项（D019）：','当前主动单项（D022/D020）：阶段总结与handoff。容量样本协议和baseline比较/复现已完成，交接记录已备好；先明确完成范围、可用入口、失败/未验证部分及下一问题，不自动进入复杂模型。')
line('outputs/第一阶段两周执行计划_v2_20261013.md','当前下一项是','当前下一项是按D020做首轮储能样板阶段总结与handoff（D022）。容量代理单事件闭环已完成；交接后建议扩充同系统后续受控测试的原始历史作跨期复核，保持阈值/积分、重新冻结时段与来源，暂不实施。完整能力与B_PHASE独立确认仍缺，不开启复杂方法。')
line('AGENTS.md','- 2026-10-14状态快照：','- 2026-10-14状态快照：当前结果卡DC-20261014-04、最新技术裁决D022；容量实验输入卡03，阶段协作D020。本轮单系统容量代理最小baseline闭环已完成，进入阶段总结/handoff，不新增实验。RWTH家用系统01首测一个评价事件；48h隔离、1002219历史行、高低压静置仅端点代理，2个合格区间，最近区间13.513829Ah/2.032375kWh。B_HIST_SPAN相对误差1.007028%/0.132706%，额定9.879629%/8.391411%，数据表电量1.462354%；只有一事件，不是准确率/90%或VPP可承诺量。PREP_HOME_CAP_20261014_01/02八份产物一致、原始历史独立重建通过；BL_HOME_CAP_20261014_01/02五份产物一致、原始区间/XLSX全预测/指标独立复算通过，1个B_DS Ah不可用，运行失败0。内部BMS/均衡未测分量待识别，不视DC交换为电芯净收支。旧M5BAT卡12/阶段03/04结果保持，早01/02无效；B_PHASE独立确认仍缺。交接后建议同系统跨期复核，其他三测试只见公布值、原始月未取，暂不实施。D016服务器约定不变，本次CPU足够。入口work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md及work/resource_sample_selection_20261013/README.md。')
line('AGENTS.md','| 1 | [docs/DECISION_LOG.md]','| 1 | [docs/DECISION_LOG.md](docs/DECISION_LOG.md) | 先读D020阶段总结/handoff、D021代理协议与量测更正、D022容量闭环及限制，再追溯D005—D019前序决定 |')
insert('项目文件索引.md','- 2026-10-14最新进展（D019）：','''- 2026-10-14最新进展（D022）：[阶段总结与handoff](work/process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md)及[结果卡04](docs/DATA_CARD.md)。容量代理单事件baseline真实比较、重复运行与原始独立复算通过；历史/额定容量相对误差1.007028%/9.879629%，电量0.132706%/8.391411%。仅受限流程闭环，不是稳定能力/正式精度确认。按D020先总结交接，交接后建议跨期复核，暂不新增实验。[代码与复现入口](work/resource_sample_selection_20261013/README.md)。

''')
line('work/resource_sample_selection_20261013/README.md','本目录保存','本目录保存P1组件baseline过程。当前结果卡DC-20261014-04/D022（容量输入卡03）：单系统容量代理最小baseline比较/复现闭环完成，按D020先总结/handoff，不新增实验。旧M5BAT结果/独立确认缺口保持，只有一个容量测试，非稳定能力/90%证明，无GPU申请。')
insert('work/resource_sample_selection_20261013/README.md','- 当前容量核查：','''- 当前交接：[首轮储能样板总结与handoff](../process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md)。容量现用PREP_HOME_CAP_20261014_01（重复02），BL_HOME_CAP_20261014_01（重复02）；独立收据VERIFY_HOME_CAP_20261014_01、VERIFY_BL_HOME_CAP_20261014_01。
- [容量样本v1](home_capacity_sample_protocol_v1.json)与[baseline v1](home_capacity_baseline_protocol_v1.json)已冻结。prepare/verify_home_capacity_samples.py负责历史候选和独立原始重建；run/verify_home_capacity_baselines.py负责比较及独立原始I/UI/XLSX复算。样本/实验目录已忽略Git；既有ID拒绝覆盖。

''')
append('work/resource_sample_selection_20261013/README.md','''
## 单系统容量代理baseline实际命令与范围

以下为已成功运行的现用ID，复跑时更换新run-id和verification-id，并对应改引用。脚本拒绝覆盖，Python环境同前文。

```powershell
python prepare_home_capacity_samples.py --run-id PREP_HOME_CAP_20261014_01
python prepare_home_capacity_samples.py --run-id PREP_HOME_CAP_20261014_02
python verify_home_capacity_samples.py --first-run PREP_HOME_CAP_20261014_01 --repeat-run PREP_HOME_CAP_20261014_02 --verification-id VERIFY_HOME_CAP_20261014_01
python run_home_capacity_baselines.py --run-id BL_HOME_CAP_20261014_01 --sample-run PREP_HOME_CAP_20261014_01
python run_home_capacity_baselines.py --run-id BL_HOME_CAP_20261014_02 --sample-run PREP_HOME_CAP_20261014_01
python verify_home_capacity_baselines.py --first-run BL_HOME_CAP_20261014_01 --repeat-run BL_HOME_CAP_20261014_02 --sample-run PREP_HOME_CAP_20261014_01 --sample-verification VERIFY_HOME_CAP_20261014_01 --verification-id VERIFY_BL_HOME_CAP_20261014_01
```

样本目录home_capacity_sample_runs/包含features与references分文件、历史静置/配对/缺锚点/替代锚点、划分和收据。实验目录home_capacity_baseline_runs/包含全部6行预测/指标（含B_DS Ah不可用）、失败记录、输入/协议快照和运行收据。

样本8份/实验5份产物分别复跑一致，原始历史流式锚点/积分重建及原始区间/XLSX预测/指标重算通过1e-9容差。单个受控测试、无拟合，1个明确不可用输出、运行失败0。代理不是厂家SOC端点、真实满循环或VPP容量，不以百分比误差推90%验收；当前交接后才决定跨期复核。
''')
replace('work/process_notes/2026-10-14_RWTH单系统容量参照与原始窗口准入核查.md','传感器在逆变器与电池之间的DC侧，包含电池内BMS供电。','传感器在逆变器与电池之间的DC侧；补充说明另指出内部供电/均衡可有未直接量测的电流，因此不能将端口电流视为电芯净收支（D021更正）。')
insert('work/process_notes/2026-10-14_RWTH单系统容量参照与原始窗口准入核查.md','## 研究用途与依据','''后续状态（D021/D022）：样本/baseline协议已冻结，原始独立复算与回顾比较/复现完成；当前结果卡04，进入[阶段总结与handoff](2026-10-14_首轮储能样板阶段总结与handoff.md)。以下未拟合/下一协议等为D019当时状态，不作为当前实验状态。

''')
for name,text in pending.items():
    if not (ROOT/name).is_file(): raise FileNotFoundError(name)
for name,text in pending.items(): (ROOT/name).write_bytes(text.encode('utf-8')); print(name)
