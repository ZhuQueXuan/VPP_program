"""Update only current status and append audit decisions; preserve historical protocols."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
pending = {}
NOTE = 'work/process_notes/2026-10-13_独立储能数据候选与容量测试线索核查.md'

def read(name):
    if name not in pending:
        pending[name] = (ROOT / name).read_bytes().decode('utf-8')
    return pending[name]

def put(name, text):
    pending[name] = text

def replace_line(name, prefix, new):
    text = read(name)
    lines = text.splitlines(keepends=True)
    matched = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(matched) != 1:
        raise ValueError((name, prefix, len(matched)))
    i = matched[0]
    ending = '\r\n' if lines[i].endswith('\r\n') else '\n'
    lines[i] = new + ending
    put(name, ''.join(lines))

def insert_before(name, marker, new):
    text = read(name)
    if text.count(marker) != 1:
        raise ValueError((name, marker))
    eol = '\r\n' if '\r\n' in text else '\n'
    put(name, text.replace(marker, new.replace('\n', eol) + marker, 1))

note_text = read(NOTE)
put(NOTE, note_text.replace('日期：2026-10-13；对应D018、DC-20261013-14。', '数据获取日期：2026-10-13；裁决与台账更新：2026-10-14。对应D018、DC-20261014-01。'))
replace_line('docs/DATA_CARD.md', '卡版本：', '卡版本：DC-20261014-01｜建立日期：2026年10月13日；更新日期：2026年10月14日')
insert_before('docs/DATA_CARD.md', '执行口径补充：', '''当前更新（D018）：新增候选来源核查，不改卡12输入协议或卡13探索结果。PPL全2017为87780条分钟记录、无设定，2025仅读8192字节前缀也未见设定字段，不准入一秒B_PHASE确认。新取得RWTH家用储能元数据包，CRC/发布者MD5通过，21系统参数与60条容量测试起始索引实际读取；未取得运行CSV或容量真值。LFP退回样本README有对象/选择偏差，亦不准入当前确认。下一单项核验RWTH容量测试方法与单系统原始窗口；独立B_PHASE确认缺口保留，继续P1。

## 新公开候选用途核验（2026-10-14，D018）

| 数据来源 | 实际核验与版本 | 当前用途/缺口 |
|---|---|---|
| [PPL电站记录](https://github.com/PPLResearch/BESS-Analysis) | 固定提交4aed423a120a86b4938552b3180bc13e1cc4c03f；2017完整87780行/20列，间隔全60秒、无重复/空值，Mode全Idle；8496543字节SHA256与固定Git LFS一致。2025仅HTTP206首8192字节/19列 | 已读列无功率设定，分钟数据不插值成秒确认；2025全年未核验，其他年份未读。计量边界、模式语义和许可待核验，API license=null不当禁止使用证明 |
| [RWTH家用储能](https://zenodo.org/records/12091223) | CC BY4.0，元数据包31123字节，CRC与发布MD5通过；两xlsx实际结构读取，21系统参数、60条Start Time/ID索引 | 发布说明1秒自然运行；未下载运行CSV，未证明设定/模式具备。测试索引和额定/数据表可用能量不是容量真值；优先核验单系统容量测试用途，不与M5BAT拼为同事件 |
| [28 LFP系统](https://zenodo.org/records/13715694) | 实读2257字节README及元数据，CC BY-NC4.0；24V便携退回样本、用途未知且非代表性 | 未下载运行包；未证实电站AC/设定/模式，不准入当前LMO确认。不按作者工具说明启动GP训练 |

来源指纹、列、时间、范围及收据见[过程核查](../work/process_notes/2026-10-13_独立储能数据候选与容量测试线索核查.md)。原文件在已忽略Git的downloads/independent_candidates_20261013；实际读取部分与未下载部分分别登记。本卡仅追加来源核验，不新增模型样本、划分或独立确认结果。

''')
insert_before('docs/DECISION_LOG.md', '## 追加模板', '''## D018｜新源未满足一秒独立确认，转查真实容量测试线索

- 日期：2026-10-14；数据获取2026-10-13。
- 状态：采用的用途/顺序裁决；无新模型实验，仍P1。
- 决定：本轮三个核查来源尚不满足B_PHASE独立确认，保留卡13探索结果及该缺口，不按April继续调参。下一主动单项核验RWTH家用储能容量测试方法与一个LMO/NMC系统原始窗口，确认参照后才讨论容量baseline；不是立即准入完整容量模型。
- 依据：[过程核查](../work/process_notes/2026-10-13_独立储能数据候选与容量测试线索核查.md)。PPL2017原CSV87780分钟行无设定，固定LFS指纹一致；2025仅前缀无设定，不能推广全年。RWTH小包校验通过、21系统参数及60条测试起点实际读取，但只有Start Time/ID、无测定值；LFP源为便携退回选择样本，字段/对象不满足当前电站确认。
- 理由：独立一秒确认没有取得，不把分钟值插成秒或跨站模式硬映射PQ。储能容量证据服务现用技术方案正式能力问题；单人继续围绕同类储能的数据准入推进，不长期重复已见数据探索，也不引入复杂方法替代证据。
- 影响：DC-20261014-01只新增源与用途状态；卡12输入、旧实验与协议均不变，B_PHASE确认待补。路线/第一阶段/导航同步，D017立即接续动作由本项替代，D017结果和边界保留。服务器规则D016不变，本轮无需GPU。
- 复查条件：核实测试起止、倍率、量测端口、温度、独立参照依据及原始文件；仅索引、数据表参数或同曲线积分不能自动称独立容量真值。没有合法参照则限定组件或保持未准入，不拼到M5BAT实体、不扩展后续阶段。未定位兼容确认源不等于证明公开数据不存在。

''')
replace_line('docs/EXPERIMENT_LOG.md', '用途：', '用途：回答“研究了什么、用了哪版数据和协议、实际结果是什么、下一步为什么这样做”。阶段回顾比较03/04通过复算但仍探索；D018新源核查未取得一秒独立确认，下一项容量测试方法与原始窗口准入。本轮仅数据核查，无新模型训练。')
text = read('docs/EXPERIMENT_LOG.md')
eol = '\r\n' if '\r\n' in text else '\n'
put('docs/EXPERIMENT_LOG.md', text + ('''\n## DATA-AUDIT-20261014-01｜外部储能源用途核查（非模型实验）

- 状态：实际下载/读取小文件及PPL全2017，未拟合或评价新模型；引用DC-20261014-01、D018。
- 证据：[候选核查](../work/process_notes/2026-10-13_独立储能数据候选与容量测试线索核查.md)，实际收据acquisition_receipt_01/02/03、field_audit_01、rwth_metadata_structure_01位于已忽略downloads/independent_candidates_20261013。沙箱失败和源文件超时保留，API content重试成功。
- 核查结果：PPL2017 87780行分钟数据/缺设定；固定Git LFS与实得SHA一致。2025仅前8192字节，不作全量质量结论。RWTH元数据包CRC/MD5通过，容量表60条测试起始索引，非容量标签。LFP README明确退回选择偏差与便携对象。
- 结论：无适配的一秒独立确认数据，原B_PHASE/B_SET及卡12协议不变；不造新得分或确认结果。下一项核验RWTH容量测试方法与单系统运行窗口，准入后再定义baseline。无重训练/服务器申请。
''').replace('\n',eol))
replace_line('outputs/ROADMAP_v2.md', '当前进展（', '当前进展（2026-10-14，D018）：阶段回顾比较及退化结论保持，DC-20261014-01新增来源核查。PPL2017分钟数据和2025前缀无设定，不准入一秒确认；RWTH元数据包已校验，发现60条容量测试起始索引但尚无容量真值/运行窗口。下一单项核验容量测试方法与一个LMO/NMC系统原始窗口，继续P1；B_PHASE独立确认保持缺口，不按April再调参。本轮未训练，无GPU申请。[候选核查](../work/process_notes/2026-10-13_独立储能数据候选与容量测试线索核查.md)。')
replace_line('outputs/第一阶段两周执行计划_v2_20261013.md', '当前状态：', '当前状态：D018/DC-20261014-01完成新源用途核查，但未取得兼容的一秒确认数据。PPL2017实际为分钟/缺设定；RWTH小包已校验，21系统参数和60条容量测试起点已读，尚非容量真值。下一项容量测试方法与单系统原始窗口准入，仍P1。阶段v2的03/04探索结果及退化保持，D016服务器规则不变。[候选核查](../work/process_notes/2026-10-13_独立储能数据候选与容量测试线索核查.md)。')
replace_line('outputs/第一阶段两周执行计划_v2_20261013.md', '| 独立时段数据准入 |', '| 独立时段数据准入 | 本轮来源核查完成，未取得兼容确认；保持待补证据 | 原始对象/设定/AC/模式/时点核验；不插值分钟为秒、不硬映射跨站模式或重分April |')
insert_before('outputs/第一阶段两周执行计划_v2_20261013.md', '当前工作顺序为：', '''当前主动单项（D018）：RWTH单系统容量测试准入。已取得测试起点索引，下一步核实方法、起止/倍率/量测端口、温度、参照独立性和原始窗口访问；通过后才冻结容量baseline，不把额定/数据表容量当真值。

''')
replace_line('outputs/第一阶段两周执行计划_v2_20261013.md', '当前下一项是', '当前下一项是核验RWTH家用储能容量测试方法与一个LMO/NMC系统原始窗口（D018）。只取得元数据包、系统参数和测试起点，运行数据与容量参照未准入；先核查再定义baseline。B_PHASE一秒独立确认缺口保持，原April探索结果/参数/划分不变，不开启复杂方法。')
replace_line('AGENTS.md', '- 2026-10-13状态快照：', '- 2026-10-14状态快照：首类型锂离子储能，当前卡DC-20261014-01、最新D018；03/04阶段探索结果和原协议保持，主MAE3.813732kW改善但次条/后续退化，01/02整数截断失败不采纳，April不作独立确认。本轮新源核查：PPL全2017分钟记录缺设定、2025仅8192字节前缀未见设定，不准入一秒确认；RWTH家用储能元数据包CRC/发布MD5通过，21系统参数及60条测试起始索引已读，运行CSV与容量真值未取得。下一单项核验RWTH一个LMO/NMC系统容量测试方法及原始窗口，仍P1；独立确认/真实时延/完整容量保持缺口，不能将新源参数拼到M5BAT。D016服务器规则不变，规格待连接核验，本轮无重训练。入口work/resource_sample_selection_20261013/README.md及work/process_notes/2026-10-13_独立储能数据候选与容量测试线索核查.md。')
replace_line('AGENTS.md', '| 1 | [docs/DECISION_LOG.md]', '| 1 | [docs/DECISION_LOG.md](docs/DECISION_LOG.md) | 先读D005持续推进、D006旧数据、D007—D015组件、D016服务器、D017探索边界及最新D018新源用途与容量测试核验 |')
insert_before('项目文件索引.md', '## 当前近期主线', '''''')
insert_before('项目文件索引.md', '- 2026-10-13最新进展：', '''- 2026-10-14最新进展：D018及[数据卡DC-20261014-01](docs/DATA_CARD.md)完成[新储能源用途核查](work/process_notes/2026-10-13_独立储能数据候选与容量测试线索核查.md)。PPL全2017分钟记录缺设定，2025仅前缀，不准入一秒确认；RWTH家用储能元数据包已校验、21系统参数与60条测试起始索引已读，但运行数据/容量真值未取得。下一单项单系统容量测试方法与原始窗口核验，仍P1；D017探索结果保持，独立确认缺口未补齐。本轮没有新训练。[运行与核查入口](work/resource_sample_selection_20261013/README.md)。

''')
replace_line('work/resource_sample_selection_20261013/README.md', '本目录保存', '本目录保存P1数据准备与组件baseline过程。当前DC-20261014-01/D018，阶段v2现用03/04的探索结果及原协议保持；新公开源未满足一秒确认，RWTH元数据包发现容量测试起始索引但运行窗口/容量真值未取得。下一项核验单系统容量测试方法与原始窗口，继续P1，无新训练/GPU申请。')
insert_before('work/resource_sample_selection_20261013/README.md', '- `sample_protocol_v1.json`', '''- 新源核查：[过程记录](../process_notes/2026-10-13_独立储能数据候选与容量测试线索核查.md)。`inspect_external_bess_candidates.py --receipt-id <唯一ID>`下载小文件并记录失败/指纹；`audit_external_bess_candidates.py`核验2017全CSV、固定LFS与2025有限前缀。当前audit固定field_audit_01、禁止覆盖，不直接重跑已有ID。
- `downloads/independent_candidates_20261013/`包含已忽略的原始文件和收据：PPL2017全CSV、2025前缀、RWTH元数据包与LFP README；不代表全部来源已准入，不执行发布者MATLAB或GP代码。

''')
replace_line('work/process_notes/2026-10-13_首个资源样板选择与网上数据核查.md', '后续状态：', '后续状态：以下为当时选择记录。当前DC-20261014-01/D018及[新源核查](2026-10-13_独立储能数据候选与容量测试线索核查.md)：未取得兼容独立一秒确认，下一项RWTH单系统容量测试方法与原始窗口准入；阶段03/04探索MAE3.813732kW及退化结论保持，失败01/02不采纳，完整容量/真实时延仍未验证。')
# Validate all requested edits before writing, never touch unrelated files.
for name, text in pending.items():
    path = ROOT / name
    if not path.is_file():
        raise FileNotFoundError(path)
for name, text in pending.items():
    (ROOT / name).write_bytes(text.encode('utf-8'))
    print(name)
