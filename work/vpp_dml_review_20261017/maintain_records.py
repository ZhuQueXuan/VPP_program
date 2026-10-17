"""Write the completed run assessment to the project's existing records."""
from pathlib import Path
import json
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
NOTE='work/process_notes/2026-10-17_同事DML成果运行与适用性检查.md'

def replace_once(path,old,new):
    text=path.read_text(encoding='utf-8-sig')
    if text.count(old)!=1: raise ValueError((str(path),old,text.count(old)))
    path.write_text(text.replace(old,new,1),encoding='utf-8')

def insert_after_title(path,block):
    text=path.read_text(encoding='utf-8-sig')
    first,rest=text.split('\n',1)
    path.write_text(first+'\n\n'+block+'\n'+rest,encoding='utf-8')

def main():
    c=json.loads((HERE/'comparison.json').read_text(encoding='utf-8'))
    r=json.loads((HERE/'full_repaired_run_receipt.json').read_text(encoding='utf-8'))
    if r.get('returncode')!=0: raise RuntimeError('run incomplete')
    d=pd.read_csv(HERE/'run_full_repaired/results/benchmark.csv')
    original=pd.read_csv(HERE/'vpp_dml_framework/results/benchmark.csv').set_index('method')
    selected=d[d.method.str.startswith(('S0 ','S5 ','修订稿-线性','修订稿-神经'))]
    table='| 方法 | 原附带涨价效应nRMSE | 本次nRMSE | 本次补贴时段调节量偏差 | 本次聚类ARI |\n| --- | --- | --- | --- | --- |\n'
    for _,row in selected.iterrows():
        table+=f'| {row.method} | {original.loc[row.method,"nrmse_tau_up"]:.6f} | {row.nrmse_tau_up:.6f} | {row.response_bias_event_pct:+.3f}% | {row.cluster_ari:.6f} |\n'
    full=f'''## 完整实跑结果

修复副本全量成功退出（returncode=0），40资源×2159小时=86360行；实际耗时{r['elapsed_s']:.2f}秒。两传统回归、S0—S5、当日历史反例、线性/森林/神经网络最终阶段、安慰剂、分时电价失败诊断及调频子模型全部运行。生成8个结果文件，不包括另外两个coverage文件。

{table}
nRMSE越小越好，ARI衡量模拟资源聚类与模拟真值聚类的一致性，不能换算成正式90%准确率。调节量偏差的负号为低估、正号为高估。

逐列比较排除runtime_s，事前容差atol=1e-8、rtol=1e-6。7个CSV全部通过的状态为 **{c['all_csv_within_tolerance']}**，summary.json全部通过为 **{c['summary_within_tolerance']}**。具体差异见[comparison.json](../vpp_dml_review_20261017/comparison.json)。生成数据规模/真值可核，主要改善趋势可见；存在未达到逐数值一致的结果，**不能宣称原成绩精确复现**。作者未锁版本，平台、依赖或数值实现的具体影响未定位；未通过调参或更换数据追齐成绩。

全量与quick均为同一模拟机制的新执行，不能当新增实测样本或独立物理源。原交付及解压源指纹保持，评价修复差异在运行收据中记录。
'''
    replace_once(ROOT/NOTE,'<!-- FULL_RUN_RESULTS -->',full)
    link=f'[检查说明](../{NOTE})'
    brief='用户授权读取并试跑同事DML交付；仅作全合成方法复核和项目适用性审查，不接入六类实测、不跨资源整合或升级研究阶段。原样quick/full评价除零失败，单独副本只修画像标准化分母后两入口完整成功；全量40资源/90天有效86360行，原附带数值未全部达到事前容差，不称精确复现。缺识别阻断、完整未来留出、公布/状态时点与严格真实数据接口；归任务一候选，容量/可靠性/自监督和P1/103未通过。'
    dec=ROOT/'docs/DECISION_LOG.md'
    text=dec.read_text(encoding='utf-8-sig')
    if '## D068｜' in text: raise ValueError('D068 exists')
    dec.write_text(text+f'''\n\n## D068｜同事DML成果读取、隔离实跑与候选用途审查

- 日期：2026-10-17。用户明确要求查看根目录vpp_dml_framework并尝试运行、判断用途和出入；授权范围为外来成果检查，不自动开启跨类整合、自监督、多智能体或正式阶段升级。
- {brief}
- 原ZIP SHA256 `17d45d81bf1427d61f7e8dbcd3ca599b83fa2a49f989457b63d3cee3671cc109`；23文件CRC/字节核对，原文件保持。独立env安装econml，实际版本/运行收据在work；未使用GPU/服务器、未上传项目数据。
- 原代码全部随机生成天气/激励/设备/问卷，按全合成准入，不按实测半合成或山东证据准入。已有150行覆盖实验结果独立复算65个数值通过，无新30轮训练。保留去偏93.33%与真值33.33%涨价段覆盖率差别。
- 本方法可服务正式任务一激励条件响应分析；六类物理/统计组件仍各自有限有效，不能拼成同实体行为面板。下一步若采用，先补准入闸门/外层留出/时钟和信号时点、同特征透明对照，再选一个真实行为来源准入。本次只修运行阻碍，没有替换现用科学模型或承诺采用。
- 原D067六类有限收口、P1/103未过及其他限制保持，D068仅增加本次候选评估。见{link}及[复现入口](../work/vpp_dml_review_20261017/README.md)。\n''',encoding='utf-8')
    card=ROOT/'docs/DATA_CARD.md'
    replace_once(card,'卡版本：DC-20261016-13｜建立日期：2026年10月13日；更新日期：2026年10月16日',
        '卡版本：DC-20261017-01｜建立日期：2026年10月13日；更新日期：2026年10月17日')
    replace_once(card,'## 储热式电热水器：温度特征与条件后续5分钟标签估计限定准入（D067）',f'''## 同事DML交付：仅全合成方法核验（D068）

- ZIP49376字节，SHA256 `17d45d81bf1427d61f7e8dbcd3ca599b83fa2a49f989457b63d3cee3671cc109`；23文件CRC及解压字节核对通过，原附带结果不改。无实测底座、无外部校准或真实合同/调查/激励记录，不能按实测行为数据准入。
- 原生成器40资源（工业12/空调12/EV8/储能8）、90天加8天预热，raw94080行；特征后86360行/2159小时。参考价、设备状态及全部true_*均为生成值；真值只作评价。不与六类来源拼同一实体。全量严格划分/时点不是本项目已批准真实协议。
- 用途：核对代码、合成效应和接口；真实激励响应、容量、可靠性与行为心理参数用途待准入。README最低字段缺rtp等，缺小时静默跨间隔shift，未来激励没有公布时间校验，当前状态可能受提前公布激励影响；均记录为未解决准入条件。
- 原30轮coverage150行只是交付结果，65数值重算一致，没有新30轮训练；版权/再发布许可未提供。六类实测卡DC-20261016-13及此前冻结版本保留，未因本卡降级或合并。见{link}和[独立核查](../work/vpp_dml_review_20261017/independent_audit.json)。

## 储热式电热水器：温度特征与条件后续5分钟标签估计限定准入（D067；原卡DC-20261016-13）''')
    experiment=f'''## REVIEW-DML-20261017｜同事全合成方法实跑与接口核验（D068）

- {brief}
- 事前范围及容差见work/vpp_dml_review_20261017/review_protocol.json，数据卡DC-20261017-01。原quick/full均ValueError(infinity)退出；quick_repaired53.31秒、full_repaired{r['elapsed_s']:.2f}秒成功。只修评价常数画像std≤1e-12分母，原数据/拟合/划分/参数不改；原失败和原附带结果保持。
- 全量生成8结果，7CSV全容差通过={c['all_csv_within_tolerance']}，summary全通过={c['summary_within_tolerance']}；原未锁依赖，差异具体原因未定位。主要指标表/逐列差在comparison；不调参追齐，不称精确重现或真实有效性通过。
- ZIP23文件CRC/字节、全量规模、缺字段/缺时钟行为、5折外层未来结果依赖独立检查完成；原150行coverage重算65数最大差2.22e-16，0新30轮训练。全量后20%只最终阶段留出，不当完整未来盲测；无GPU/上传/提交，原六类发布包未修改。见{link}及[运行收据入口](../work/vpp_dml_review_20261017/README.md)。
'''
    # Logs are newest-first, preserve the existing title and all historical entries.
    insert_after_title(ROOT/'docs/EXPERIMENT_LOG.md',experiment)
    for fn,heading in [('outputs/ROADMAP_v2.md','## 2. 对v1的审查'),('outputs/第一阶段两周执行计划_v2_20261013.md','## 1. 本期单一研究样板与范围')]:
        p=ROOT/fn
        replace_once(p,heading,heading+f'\n\n最新补记（D068，2026-10-17）：{brief}见[本次检查](../{NOTE})和[实跑入口](../work/vpp_dml_review_20261017/README.md)。六类有限基础覆盖仍按D067，下一项采用/真实行为源须另满足准入，不因本次模拟复跑开放后续分支。')
        stale='现用D061：完成事后描述/候选QA，当前先核新Mendeley原文件/字典与论文，空调未验收、不改原失败。以下D060为历史时点。'
        new=f'当前D068：同事DML交付只作候选审查/全合成实跑，实测适用仍待准入；D067六类有限收口及P1未过保持。见[本次检查](../{NOTE})。\n\n历史D061：完成事后描述/候选QA，当时先核新Mendeley原文件/字典与论文，空调当时未验收、不改原失败。以下D060为历史时点。'
        replace_once(p,stale,new)
    agents=ROOT/'AGENTS.md'
    replace_once(agents,'| 1 | [docs/DECISION_LOG.md](docs/DECISION_LOG.md) | 先读D067',
                 '| 1 | [docs/DECISION_LOG.md](docs/DECISION_LOG.md) | 先读D068同事DML全合成隔离实跑/候选用途与未精确复现，再读D067')
    anchor='- 2026-10-16现用D067：'
    content=agents.read_text(encoding='utf-8-sig')
    if content.count(anchor)!=1: raise ValueError('snapshot anchor')
    content=content.replace(anchor,f'- 2026-10-17现用D068：{brief}卡DC-20261017-01，原交付与六类成果保持。入口work/vpp_dml_review_20261017/README.md及{NOTE}。\n- 2026-10-16前序D067：',1)
    agents.write_text(content,encoding='utf-8')
    insert_after_title(ROOT/'项目文件索引.md',f'- 2026-10-17 D068：[同事DML检查]({NOTE})、[运行及复算入口](work/vpp_dml_review_20261017/README.md)。原包保留；原样运行评价除零失败、隔离副本仅修评价后全量跑通，原数值未全部精确重现；只作全合成方法候选，不整合六类或改变P1状态。\n')
    print('Updated report and seven current records; preserved historical entries.')

if __name__=='__main__': main()
