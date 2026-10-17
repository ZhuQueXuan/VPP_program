"""Append D019 evidence and update current handoff, without changing old experiments."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
pending={}
NOTE='work/process_notes/2026-10-14_RWTH单系统容量参照与原始窗口准入核查.md'
def read(name):
    if name not in pending: pending[name]=(ROOT/name).read_bytes().decode('utf-8')
    return pending[name]
def line(name,prefix,new):
    rows=read(name).splitlines(keepends=True)
    match=[i for i,v in enumerate(rows) if v.startswith(prefix)]
    if len(match)!=1: raise ValueError((name,prefix,len(match)))
    i=match[0]; ending='\r\n' if rows[i].endswith('\r\n') else '\n'
    rows[i]=new+ending; pending[name]=''.join(rows)
def insert(name,marker,new):
    text=read(name)
    if text.count(marker)!=1: raise ValueError((name,marker))
    ending='\r\n' if '\r\n' in text else '\n'
    pending[name]=text.replace(marker,new.replace('\n',ending)+marker,1)
def append(name,new):
    text=read(name); ending='\r\n' if '\r\n' in text else '\n'
    pending[name]=text+new.replace('\n',ending)

line('docs/DATA_CARD.md','卡版本：','卡版本：DC-20261014-02｜建立日期：2026年10月13日；更新日期：2026年10月14日')
line('docs/DATA_CARD.md','当前更新（D018）：','当前更新（D019）：已取得RWTH系统01/2017年6月CSV及作者Fig.2现场容量测试参照，60条测试键与索引完全匹配。所选CSV长度/CRC/指纹通过，2592000条秒记录、35条发布插值；固定24h窗86400条/3插值，起点唯一，P与UI存在瞬时差异。准入回顾诊断及单系统容量样本协议准备，目标限受控条件DC可用Ah/kWh；未拟合模型，未验证VPP最大/可承诺容量。下一单项冻结历史自然完整循环与后续受控测试的样本/baseline协议；B_PHASE独立确认仍缺。')
insert('docs/DATA_CARD.md','## 新公开候选用途核验', '''## 当前新增容量来源：RWTH-HOME-ID01-JUN2017（D019，限定准入）

| 字段/依据 | 当前核验与边界 |
|---|---|
| 来源 | [Zenodo](https://zenodo.org/records/12091223)，原始数据CC BY4.0；[作者Fig.2测试源数据](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41560-024-01620-9/MediaObjects/41560_2024_1620_MOESM4_ESM.xlsx)和补充说明另保留出版方许可信息 |
| 对象 | 家用系统01，LMO/NMC，元数据40串1并、15Ah/2.2kWh、2kW逆变器；不是M5BAT单元，元数据不当硬边界或测定真值 |
| 参照 | 作者60个受控测试的ID/Excel时间与原索引唯一匹配。系统01首测2017-06-14 14:23:39，13.6513019678Ah、2.0296811140kWh；后三次公布值已见、运行数据未取得 |
| 测试/端口 | 现场充满后关闭PV、附加负荷维持最大放电，EMS停止/界面SOC0结束；DC侧量测含BMS供电。容量积分I，电量积分UI；与自然运行估计共享量测链，不称独立传感器真值 |
| CSV | 7列Time/P_in_W/V_in_V/I_in_A/T_Bat_in_C/T_Room_in_C/Interpolated；P/I充电为正，单位W/V/A/℃；没有SOC、指令、模式或授权，温度为外壳 |
| 本月质量 | 2592000行，6月1日至30日、所有相邻间隔1秒；无缺单元格/非有限数，插值35条。发布源已过滤/插值，不称未处理原始传感器流 |
| 固定诊断窗 | 6月14日12:00—15日12:00半开，86400条/3插值；发布起点恰一行但电流/功率为0，不等同实际放电开始。时区不擅自推定 |
| P/UI差异 | 窗内绝对平均1.2353115W、最大942.10296W；不平移/删行或凭误差选口径，不把两列混作同一参照 |
| 用途准入 | 原始质量、受控参照对应、回顾诊断和容量样本/baseline协议准备；尚无容量模型实验/G1验收。自然完整循环的端点/截点/参照隔离仍待冻结 |
| 禁止推断 | 不把一天总放电当容量，不据已见标签搜索终点；不直接验证SOC条件VPP可承诺量、真实响应时延或授权。选择已见参照，非盲测 |

所选CSV142125801字节，SHA256 c26ab1469238eeb164a0fbbef23356f319d2d09f9e337749e6de5e17e4dcb237，CRC32 2ce00115；只HTTP Range读取该月成员，未校验全973MB ZIP的MD5。来源、方法、指纹与核查收据见[过程核查](../work/process_notes/2026-10-14_RWTH单系统容量参照与原始窗口准入核查.md)。全部原始/诊断数据在已忽略Git的downloads/rwth_home_capacity_20261014。既有卡12协议与模型结果不变。

以下D018候选表是此前读取范围；RWTH最新状态以上表为准，其余不自动准入。

''')
insert('docs/DECISION_LOG.md','## 追加模板', '''## D019｜取得可对应现场容量参照，准入单系统容量样本准备

- 日期：2026-10-14。
- 状态：采用；真实下载/读取及局部复核完成，无新模型训练，仍P1。
- 决定：RWTH家用系统01/2017年6月准入原始质量、受控测试对应、回顾诊断及容量样本/baseline协议准备；目标限测试条件下DC可用Ah/kWh。下一单项冻结截点前自然完整循环与后续受控测试的样本及透明对照，先核验是否可识别端点，不直接编码完整VPP容量模型。
- 依据：[准入核查](../work/process_notes/2026-10-14_RWTH单系统容量参照与原始窗口准入核查.md)。作者Fig.2表60条ID/时间与起点索引全匹配。系统01首测参照13.6513019678Ah/2.0296811140kWh；最低ID/最早测试在CSV读取前选定，但公布值已见，不称盲测。
- 原始质量：仅取一个月ZIP成员，142125801字节CSV CRC/长度/SHA通过，2592000秒行、35插值、无缺失/非有限。固定24h窗86400条、3插值，stdlib另读核对计数/唯一/起点/P−UI最大差；没有全ZIP MD5或全月第二次解析证明。
- 限制：DC传感器含BMS，作者测试与自然估计共享量测链；外壳温度和末端降额依现场。没有门户SOC/终止日志，P与UI瞬时有差异；不把日放电量当容量、不据标签挑终点，不与M5BAT拼对象。额定、数据表可用和实测量分开。
- 影响：DC-20261014-02追加用途，不改原M5BAT输入卡12/协议/结果；D018容量方法/原始窗口核查完成，其立即下一项由样本协议替代。B_PHASE独立确认缺口保持，不扩展P2/自监督/协同/市场适配；无需GPU。
- 复查条件：明确事前窗口、完整循环资格与时点、端点依据、插值/缺失、P/UI口径、评价参照和不可计算情况后冻结协议。若端点无法支持对应输出，缩小组件/保持缺口；取得标签不自动证明可调功率、能量余量或90%指标。

''')
line('docs/EXPERIMENT_LOG.md','用途：','用途：回答“研究了什么、用了哪版数据和协议、实际结果是什么、下一步为什么这样做”。D019取得单系统受控容量参照和原始月窗口，下一项容量样本/baseline协议；本轮仅数据核查，无新模型训练。阶段03/04仍为探索，独立方法确认/VPP容量未验证。')
append('docs/EXPERIMENT_LOG.md','''
## DATA-AUDIT-20261014-02｜系统01容量参照与原始窗口（非模型实验）

- 状态：实际取得作者Fig.2参照及一个月CSV，未拟合/预测容量；DC-20261014-02、D019。
- 执行：prepare_home_capacity_evidence.py、acquire_home_system01_month.py、audit_home_system01_month.py；脚本按自身路径定位，原文件/收据不覆盖。PDF方法页/流程图已核对，未执行作者MATLAB。早次文本打印编码错误后以UTF8重读成功，未改数据。
- 结果：60个测试索引与参照全匹配；系统01首测13.6513019678Ah/2.0296811140kWh。仅HTTP Range取11004641字节压缩成员，142125801字节CSV CRC/长度/SHA通过；全月2592000秒行、35插值，固定24h窗86400行/3插值，无缺失。P−UI窗内最大942.10296W，机制待核。
- 复核：[过程核查](../work/process_notes/2026-10-14_RWTH单系统容量参照与原始窗口准入核查.md)。本地method_acquisition_01、published_test_reference_check_01、selected_member_acquisition_01、selected_month_quality_01及stdlib selected_window_verification_01收据位于已忽略downloads/rwth_home_capacity_20261014。后者限窗口，不称全月独立重跑；全ZIP未下载/MD5未核验。
- 限制/下一项：准入单系统受控DC可用量样本准备，尚无容量baseline结果/误差。选择已见公布值、同量测链，不能当盲测/VPP最大量。冻结事前自然完整循环、参照隔离和透明对照协议；无法识别端点则报告不可计算，不匹配标签调终点。旧模型/结果不变，无GPU申请。
''')
line('outputs/ROADMAP_v2.md','当前进展（','当前进展（2026-10-14，D019）：DC-20261014-02取得RWTH系统01现场容量参照与2017年6月原始CSV；60测试键全对应，所选成员CRC/SHA/质量通过，2592000秒行含35条发布插值。准入单系统受控DC可用量的样本/协议准备，尚无容量模型结果；下一单项冻结事前自然完整循环与后续测试对照协议，端点不足时报告不可计算。既有B_PHASE探索与独立确认缺口保持，仍P1，无GPU训练。[准入核查](../work/process_notes/2026-10-14_RWTH单系统容量参照与原始窗口准入核查.md)。')
line('outputs/第一阶段两周执行计划_v2_20261013.md','当前状态：','当前状态：D019/DC-20261014-02完成RWTH系统01受控容量参照、方法和原始月窗口核查；所选CSV CRC/SHA通过，2592000秒行/35插值，固定24h窗86400行/3插值。准入容量样本与协议准备，未运行容量模型；下一项冻结自然完整循环与后续受控测试的样本/baseline协议。继续P1，B_PHASE独立确认缺口保持。[核查](../work/process_notes/2026-10-14_RWTH单系统容量参照与原始窗口准入核查.md)。')
line('outputs/第一阶段两周执行计划_v2_20261013.md','当前主动单项（D018）：','当前主动单项（D019）：冻结容量样本与透明baseline协议。目标仅受控条件DC可用Ah/kWh，明确截点前历史窗口、自然完整循环资格、端点/插值和P/UI口径、作者参照隔离及失败；不据已见13.6513Ah标签调端点，不把日总放电当容量。')
line('outputs/第一阶段两周执行计划_v2_20261013.md','当前下一项是','当前下一项是冻结“截点前自然运行完整循环 → 后续受控测试DC可用量”的容量样本与透明baseline协议（D019）。先核验完整循环可识别性，再选对照；容量参照/原始窗口已取得不等于容量模型闭环。保留旧M5BAT探索/缺口，不补造SOC或真实时延，不开启复杂方法。')
line('AGENTS.md','- 2026-10-14状态快照：','- 2026-10-14状态快照：当前DC-20261014-02、最新D019，首类型锂离子储能。RWTH家用系统01/2017年6月CSV142125801字节，所选成员CRC/SHA通过，2592000秒行/35插值；作者Fig.2的60个受控测试ID/时间与起点索引全匹配，ID01首测13.6513019678Ah/2.0296811140kWh。固定24h诊断窗86400行/3插值，P与UI瞬时差异、门户SOC/停止日志不足，不据标签调终点。准入回顾诊断及单系统容量样本/baseline协议准备，下一项冻结事前自然完整循环与后续受控测试的协议；未运行容量模型/G1验证，不当VPP可承诺量。仅下载所选月成员，全ZIP MD5未核；后续三测试只见公布值、运行月份未取。旧阶段03/04探索MAE3.813732kW及次条/后续退化保留，01/02不采纳，B_PHASE独立确认仍缺；M5BAT卡12协议/结果不变。仍P1，无GPU申请，D016服务器规则不变。入口work/resource_sample_selection_20261013/README.md及work/process_notes/2026-10-14_RWTH单系统容量参照与原始窗口准入核查.md。')
line('AGENTS.md','| 1 | [docs/DECISION_LOG.md]','| 1 | [docs/DECISION_LOG.md](docs/DECISION_LOG.md) | 先读D005/D006持续推进与旧数据边界、D007—D017组件/服务器/探索、D018新源用途及最新D019容量参照与协议准备 |')
insert('项目文件索引.md','- 2026-10-14最新进展：','''- 2026-10-14最新进展（D019）：[DC-20261014-02](docs/DATA_CARD.md)及[RWTH容量准入核查](work/process_notes/2026-10-14_RWTH单系统容量参照与原始窗口准入核查.md)。系统01首个受控DC容量参照与2017年6月原始CSV已取得，60测试键全匹配，所选成员CRC/SHA通过，全月2592000秒行/35插值。下一项容量样本与透明baseline协议，未训练容量模型，仍P1；旧M5BAT结果/独立确认缺口保持。[数据入口](work/resource_sample_selection_20261013/README.md)。

''')
line('work/resource_sample_selection_20261013/README.md','本目录保存','本目录保存P1数据准备与组件baseline过程。当前DC-20261014-02/D019，已取得RWTH系统01受控容量参照和原始月CSV并限定准入；下一项自然完整循环与后续受控测试容量样本/baseline协议，尚未运行容量模型。旧M5BAT卡12协议与03/04探索结果保持，B_PHASE独立确认仍缺；无GPU申请。')
insert('work/resource_sample_selection_20261013/README.md','- 新源核查：','''- 当前容量核查：[过程记录](../process_notes/2026-10-14_RWTH单系统容量参照与原始窗口准入核查.md)。`prepare_home_capacity_evidence.py`获取方法/图源及远程ZIP目录；`acquire_home_system01_month.py`只下载系统01首测所在月成员并核对CRC/SHA；`audit_home_system01_month.py`核验全月和固定诊断窗，不拟合模型。三入口已运行、拒绝覆盖现有收据；直接重跑会报已有文件，需另设运行版本。
- `downloads/rwth_home_capacity_20261014/`保存所选CSV、出版方参照/补充说明、诊断窗及核查收据，已忽略Git；没有全ZIP/全库校验、其他三测试月份或独立容量模型结果。

''')
insert('work/process_notes/2026-10-13_独立储能数据候选与容量测试线索核查.md','## 1. 实际取得与用途裁决','''后续更新（D019/DC-20261014-02）：以下表格为D018当时状态。现已取得作者Fig.2容量参照及RWTH系统01首个测试所在月CSV，参照对应/质量通过；当前范围与下一协议准备见[最新核查](2026-10-14_RWTH单系统容量参照与原始窗口准入核查.md)。不是VPP容量模型或独立B_PHASE确认完成。

''')
for name,text in pending.items():
    if not (ROOT/name).is_file(): raise FileNotFoundError(name)
for name,text in pending.items():
    (ROOT/name).write_bytes(text.encode('utf-8')); print(name)
