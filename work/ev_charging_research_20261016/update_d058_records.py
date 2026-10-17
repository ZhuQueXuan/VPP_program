"""Record completed, bounded KIT characterisation and EV basic package closure."""
from mapping_common import *

package=ROOT/'resource_research_results/ev_charging'
release=load(package/'results/release_validation_v1_1.json');assert release['status']=='passed'
assert all(sha(package/n)==h for n,h in release['verified_files'].items())
protocol=sha(BASE/'kit_step_protocol_v1.json');assert protocol=='ad7b9f2dc4a99f7808c61e124394d3766ff6e0cb0b07bb782934d51f5862f9e8'
admission=sha(BASE/'runs/PREP_KIT_STEPS_01/admission.json')
assert admission=='ad0818de524bca0d226200c1e3ed29fe4965c4c2d0051ea521ce1d2d7b776f11'
changes={}
def edit(name,fn):
    p=ROOT/name;s=p.read_text(encoding='utf-8');assert 'D058' not in s,name
    changes[p]=fn(s)

sources='''本轮重新网上检索匹配秒级动态问题的原始来源，取得KIT官方目录、Zenodo17866847元数据及LF原件；不是沿用旧Dortmund状态码。Beichter等数据v1.0.0，2026-02-09发布，明确CC-BY-4.0。charging.csv1252字节及LF Parquet422470722字节MD5分别d31d686929a10ed78f5b74fcf036c504/0327dae2664c79ecde0bd07166bf6b1d，与发布者一致；LF SHA2566156dc885ffd3066d5e2229c51dd49a5ceadf4e9c3c2c25adf0168d6583b2df1。未下载22GB HF或导出巨大CSV。作者预印本摘要可读，公开全文PDF一次403后停止，未取得全文或确认同行评审，不称全篇精确复现。'''
qa='''全量24,474,687行，18套记录、16品牌车型组合/12品牌、9547次相邻指令变化；核心时间/电流/指令无空值、无重复/倒序时间，一处966ms间隙。字段timestamp_ns实际Parquet TIMESTAMP_MICROS，isAdjustedToUTC=false，不能按整数纳秒解释或据此称仪器微秒精度；仅同记录相对时间，时区/网络送达/传感器同步未知。前五套间隔中位20ms、其余21ms，按实际采样时刻计算而不强置50Hz。官方单项目录2025-10-28报1331504/实1328301、11-11报1054758/实1054757；目录总数与实读总数24474687一致但单项合计有差，保留差异、不补行。'''
rules='''特征计算前冻结自定记录级协议，SHA256 `'''+protocol+'''`，绑定来源/QA。每次指令变化分L1/L2/L3候选；两指令均≥6A、变化≥2A，前[-5,0)秒旧指令恒定/后[0,15)秒新指令恒定、覆盖两端≤50ms、原序严格递增/间隙≤50ms，该相事前电流中位数≥1A、窗口电流有限。阈值是研究筛选，不是IEC合规判据；事前有负荷不是接口状态真值，完整后窗仅回顾用途。28,641候选冻结后准入4928条分相观察/1875次变化，2446上调/2482下调，L1/L2/L3分别1875/1708/1345；未按响应速度、终值或残差筛。排除标志可重叠：步幅不足11178、低于研究指令11322、事前低负荷9324、前指令不恒定2145、后不恒定2547、后窗不足3。一处全源间隙未落入合格窗口。准入收据SHA256 `'''+admission+'''`在特征计算前保存。'''
definition='''进度=sign(Δ指令)×(相电流−事前5秒中位数)/abs(Δ指令)，分母为指定变化幅度，不取未来实测终值；10%/90%首次连续≥100ms达到时记最初采样时间与相邻采样区间，起点≤10s、确认可至10.1s，不插值。末[10,15)秒电流中位数与新指令比较。未观测到90%幅度返回空值/删失，不填0或10秒，原因未确认；可能达不到该幅度，不能直接称延迟>10秒。10/90是幅度，不是103模型精度或实际调节可靠性。全部18记录作描述性特征提取，0新增拟合，不存在本轮动态预测留出增益。'''
results='''4928条中4263条在10秒内观测到90%指定幅度、665条未观测到（上调352/下调313）。仅在已观测者中，总体t90中位0.777s/95分位4.935s；上调2094条中位1.113s/95分位5.712s，下调2169条中位0.420s/95分位2.500s，不能推广为全部事件的时间分布。全部4928条末5秒绝对偏差中位0.420A/95分位1.210A/最差10.890A，未删最差或无越限记录。相别/同记录内事件相关，4928不是独立车辆数；18记录也不是18次独立充电会话。'''
verification='''CHAR_KIT_STEPS_01/02四科研产物完全相同。verify_kit_steps.py独立bisect/标量窗口重建全部28641候选准入、独立布尔连续段分解复算4928条特征及汇总，113866数值或空值检查通过、最大差2.22e-16；共享DuckDB文件解码器，不称第二解析器或物理真值。最终verify_packaged_steps.py全4928条/88704字段回放差0、4类非法或不完整输入拒绝、无越限构造例空值保持、两个目录外构造例实际运行通过。原D057代码/参数/结果指纹不变，原159003点回放收据保留为历史v1.0，现用发布收据release_validation_v1_1.json；PV v1.2全部发布指纹不变。'''
closure='''依D046六项有限基础验收，EV首轮基础包在“Dortmund共同指令同期功率静态映射＋独立KIT记录级分相阶跃特征”范围内收口。正向baseline证据来自D057原冻结留出比较，本轮新增描述性动态特征，不虚构新预测模型或增益；D057仅8/15组及14/28实验双改善、最差11.524kW等失败原样保留。两来源车辆/站点不拼接，不把A与kW或15个统计截顶点迁移。完成对象/输入输出、依据、按用途参照、正向简单组件、公平失败与覆盖、可复现最终代码六项，不等于EV完整功能/真实容量/全体P1或103验收完成。'''
limits='''仍未验证：现场调度请求到设备动作端到端时延、传感器/时钟标定、Dortmund STATE/接口枚举和数据许可、全启动停止/未载相位、可用或可承诺容量、需求/离站/授权/意愿、V2G/站级共享约束及跨站独立实体泛化。下一资源由用户选择；跨资源整合仍待明确授权，不自动开始。无GPU需求、上传或提交，不改教师稿/handoff，不新建outputs报告；本轮在此有意义节点停止。'''
alternative='''EPFL官方GitHub目录/README/LICENSE已取得，工作簿只检查字段及开头记录，未完整QA或新准入，未称本地文件身份已重新核验。其Measurement_data分钟网格/空闲占位不适合本轮秒级观察，Ctrl_s为整会话回顾状态、离站/Pmax含未来信息，不作因果输入。根MIT文本不转用于KIT或Dortmund，EPFL不进入本轮结果。'''

decision='\n\n## D058｜独立KIT记录级阶跃特征与EV首轮基础包有限收口\n\n- 日期：2026-10-16；状态：实际计算、独立复算及最终归集完成，限定范围收口。用户要求继续，沿单一充电资源问题推进。\n\n'+ '\n\n'.join('- '+v for v in (sources,qa,alternative,rules,definition,results,verification,closure,limits))+'''

- 证据：[过程入口](../work/ev_charging_research_20261016/README.md)、[协议](../work/ev_charging_research_20261016/kit_step_protocol_v1.json)、[现用EV v1.1](../resource_research_results/ev_charging/README.md)、[六项有限验收](../resource_research_results/ev_charging/results/basic_research_acceptance_v1_1.json)。卡DC-20261016-04新增KIT用途，旧03/旧数据与D057原结论保持。正式任务一设备行为/动态特征与任务二响应基础得到局部证据，尚未进入后续整合与智能分类。
'''
edit('docs/DECISION_LOG.md',lambda s:s+decision)
data='## KIT记录级电流阶跃特征限定准入（D058；独立对象，非端到端时延真值）\n\n'+'\n\n'.join('- '+v for v in (sources,qa,rules,definition,alternative,limits))+'''\n\n- 实际结果/复核见EXPERIMENT_LOG；现用最终包v1.1。用途是记录级特征提取，完整后窗筛选与时间分布仅可用于相应回顾样本；不把这些记录当独立车辆，不把本轮描述统计当训练/留出预测。以下D057同期静态映射及更早各用途按原协议保留。\n\n'''
edit('docs/DATA_CARD.md',lambda s:s.replace('卡版本：DC-20261016-03','卡版本：DC-20261016-04',1).replace('## EV共同指令同期功率映射限定准入',data+'## EV共同指令同期功率映射限定准入',1))
experiment='## CHAR-EV-KIT-20261016｜记录级分相阶跃特征与成果v1.1（D058）\n\n'+'\n\n'.join('- '+v for v in (sources,qa,rules,definition,results,verification,closure,limits))+'''\n\n- 实际顺序：EV_NEXT_SOURCE_01元数据/候选→KIT_LF_SOURCE_01下载/MD5→KIT_SOURCE_QA_01完整核验→freeze_kit_steps.py→PREP_KIT_STEPS_01固定准入→CHAR_KIT_STEPS_01→02确定性复跑→verify_kit_steps.py→collect_kit_results.py→verify_packaged_steps.py。KIT_PAPER_01全文403收据保留。科学计算/最终回放已实际完成，无拟合/调参/GPU。源/代码/协议/输出指纹及独立核验见各run收据，当前卡DC-20261016-04。\n\n'''
edit('docs/EXPERIMENT_LOG.md',lambda s:s.replace('## BL-EV-MAPPING-20261016',experiment+'## BL-EV-MAPPING-20261016',1))
status='''最新执行（2026-10-16，D058）：EV首轮基础研究在有限范围内收口，[最终包v1.1](../resource_research_results/ev_charging/README.md)保留原D057静态映射及新增KIT记录级分相阶跃特征。新CC-BY-4.0原LF24474687行/18记录/16品牌车型组合核验；字段名ns实为微秒时间类型，实际20/21ms时步，目录两项计数差保留。特征前冻结协议ad7b9f2dc4a99f7808c61e124394d3766ff6e0cb0b07bb782934d51f5862f9e8，9547变化/28641分相候选→1875合格变化/4928观察；4263观测到90%幅度、665未观测不补值。仅已观测者上调t90中位1.113s、下调0.420s，不是现场调度端到端时延。独立28641准入/4928特征/113866数值或空值检查、4产物复跑及最终4928回放通过；0新增拟合。卡DC-20261016-04。六项基础检查限定完成，正向baseline来自原D057，完整容量/授权/离站/真实控制/泛化未验，全体P1及103未通过。下一类型与整合由用户决定；教师稿/handoff不更新，不新建正式报告。以下D057及更早按历史时点阅读。

'''
next_status='现用D058：EV首轮基础包六项有限检查完成，现有静态映射＋独立记录级分相阶跃特征代码/结果/复现。当前收口等待用户选择下一资源；真实控制/容量另需专门准入，不以旧留出调参补分，不自动整合或进入高级模型。下列D057及更早均为历史时点。'
edit('outputs/ROADMAP_v2.md',lambda s:s.replace('最新执行（2026-10-16，D057）',status+'前序执行（2026-10-16，D057）',1).replace('现用D057：共同指令静态映射首个组件完成，EV整体仍进行中；后续动态响应需补接口状态及物理时点/独立执行参照，可另寻匹配原始来源。不能在已见28留出实验继续改截顶/阈值；不自动跨类型整合。下列D056及更早均为历史时点。',next_status,1))
edit('outputs/第一阶段两周执行计划_v2_20261013.md',lambda s:s.replace('最新执行（2026-10-16，D057）',status+'前序执行（2026-10-16，D057）',1).replace('现用D057：已有共同指令静态映射/对照/复现/最终代码，整体EV验收尚未通过。动态及能力需补状态/物理时点、需求授权等对应证据；旧留出不改协议重调。下列D056等按原时点。',next_status,1).replace('当前按D057完成EV首个静态映射组件，完整技术响应用途仍待准入','当前按D058有限收口EV首轮基础包，完整现场控制/容量用途仍待准入',1))
process='\n\n## D058｜新KIT来源、记录级动态特征与首轮基础包收口\n\n'+'\n\n'.join((sources,qa,alternative,rules,definition,results,verification,closure,limits))+'''

复现：原始下载及失败请求在downloads/各独立收据；QA在runs/KIT_SOURCE_QA_01/，准入在runs/PREP_KIT_STEPS_01/。run_kit_steps.py --run-id <新的唯一ID>可重跑至新目录（需原LF及DuckDB/NumPy）；CHAR_KIT_STEPS_01/02为已完成记录，不能覆盖。verify_kit_steps.py及verify_packaged_steps.py是一次核验入口，会拒绝覆盖收据；复核既有结果应读取verification.json与发布收据。最终计算只需标准库，两构造例不替代真实数据验证。收据v1.0历史保留、v1.1现用；对象/依据/参照/正向简单组件/公平失败覆盖/复现代码六项有限验收详见resource_research_results/ev_charging/results/basic_research_acceptance_v1_1.json。
'''
edit('work/process_notes/2026-10-16_电动汽车充电设施研究.md',lambda s:s.replace('现用D057静态映射首轮闭环（整体EV研究未完成），D056为前序来源核验','现用D058首轮基础包有限收口（静态映射＋记录级阶跃特征，完整容量/现场控制未验），D057/D056为前序',1)+process)
intro='''## 当前D058：首轮基础包有限收口

- [最终EV v1.1](../../resource_research_results/ev_charging/README.md)包含独立Dortmund静态映射和KIT记录级分相阶跃特征；[六项范围](../../resource_research_results/ev_charging/results/basic_research_acceptance_v1_1.json)。二者不同对象、不拼接。真实控制时延/容量/需求授权及全体P1未验，下一类型与整合等待用户决定。
- 新源[Zenodo17866847](https://zenodo.org/records/17866847)/[KIT目录](https://publikationen.bibliothek.kit.edu/1000190660)，CC-BY-4.0；422470722字节LF原件MD5通过，24474687行/18记录/16品牌车型组合，9,547变化。名为ns的字段实际TIMESTAMP_MICROS/非UTC调整，按实际20/21ms间隔计算；一处966ms间隙、两目录行数差异保留。
- [冻结协议](kit_step_protocol_v1.json)SHA256 `'''+protocol+'''`，准入在特征计算前冻结。PREP_KIT_STEPS_01保留28,641候选和全部排除，1,875变化/4,928分相观察，不按速度或误差删点。完整前5后15秒、恒定指令、事前负荷等条件仅允许回顾记录级特征，不是全工况或在线可用性。
- `run_kit_steps.py --run-id <新的唯一ID>`实际完成CHAR_KIT_STEPS_01/02四产物一致；所需原LF在downloads/KIT_LF_SOURCE_01，DuckDB依赖位于work/python_packages/pv_metadata_20261015，路径由kit_common.py管理。4263条观测到90%幅度、665未观测返回空值；仅已观测者上调中位1.113s/下调0.420s，末窗全样本偏差最差10.89A保留。0新增拟合，非预测留出实验或103精度。
- `verify_kit_steps.py`独立准入/布尔连续段及汇总复算113866值或空值通过，共享Parquet解码器。`verify_packaged_steps.py`最终全部4928回放差0、4类非法输入拒绝、无越限空值及两个目录外构造例通过。原D057代码/参数/结果与PV v1.2指纹保持。现用成果results/release_validation_v1_1.json，release_validation.json为v1.0历史（旧README指纹不对应现用版）；核验脚本均拒覆盖原收据。
- 过程记录见work/process_notes/2026-10-16_电动汽车充电设施研究.md文末D058；卡DC-20261016-04。原Dortmund字典/接口/许可缺口并未补齐；KIT作者全文PDF403未取得，不称精确论文复现。EPFL仅字段/开头记录候选审查，分钟级来源不入本轮秒级结果。无GPU/高级模型/整合，新正式报告及handoff不自动更新。

'''
edit('work/ev_charging_research_20261016/README.md',lambda s:s.replace('日期：2026-10-16；现用D057、数据卡DC-20261016-03。首个有限静态映射/比较/复现组件已完成；EV完整动态响应及能力仍待准入。储能、光伏最终成果保持。','日期：2026-10-16；现用D058、数据卡DC-20261016-04。EV首轮基础包限定收口；完整现场控制及容量仍待准入。储能、光伏成果保持。\n\n'+intro,1).replace('## 当前D057：','## 前序D057（历史时点）：',1).replace('当前发布收据在成果results/release_validation.json','当时发布收据在成果results/release_validation.json（v1.0历史）',1))
snapshot='''- 2026-10-16现用D058：EV首轮基础包在静态映射＋独立KIT记录级分相阶跃特征范围内六项有限验收收口，成果v1.1/现用release_validation_v1_1.json，原v1.0历史。新KIT CC-BY-4.0 LF422470722字节MD5一致、24474687行/18记录/16车型组合；timestamp_ns实际微秒类型非UTC调整，实际20/21ms，一处966ms间隙、两目录单项计数差保留。协议ad7b9f2dc4a99f7808c61e124394d3766ff6e0cb0b07bb782934d51f5862f9e8特征前固定，9547变化/28641分相候选→1875变化/4928观察；完整前5后15秒/恒定指令/事前负荷等回顾条件，不按输出速度或误差删样。4263观测到90%指定幅度、665未观测不补值；仅已观测者上调t90中位1.113s/下调0.420s，非实际调度端到端时延。独立28641准入/4928特征/113866值或空值、四产物复跑及最终4928回放通过。0新增拟合，正向baseline保留D057原证据与失败，两来源不拼同一对象。卡DC-20261016-04，研究入口work/ev_charging_research_20261016/README.md；全文PDF403/预印本仅摘要，不称全篇复现；EPFL仅候选字段审查。完整容量/现场时延/需求授权/泛化、Dortmund字典许可仍待专项，P1/103未通过。当前节点停止，下一资源与整合由用户决定；储能/PV及教师稿/handoff保持，不自动高级分支，无GPU/上传/提交。\n'''
edit('AGENTS.md',lambda s:s.replace('先读D057共同指令静态映射与v1.0范围','先读D058 KIT记录级阶跃特征及EV v1.1首轮基础包有限收口，再读D057共同指令静态映射与v1.0范围',1).replace('- 2026-10-16现用D057：',snapshot+'- 2026-10-16前序D057：',1).replace('（EV仅首个有限组件，整体仍进行中）','（EV首轮基础包限定收口，现场控制/容量未验）',1))
index='''- 2026-10-16现用D058：[EV成果v1.1](resource_research_results/ev_charging/README.md)、[现用发布核验](resource_research_results/ev_charging/results/release_validation_v1_1.json)、[六项有限验收](resource_research_results/ev_charging/results/basic_research_acceptance_v1_1.json)、[过程入口](work/ev_charging_research_20261016/README.md)、[特征前协议](work/ev_charging_research_20261016/kit_step_protocol_v1.json)。新增独立KIT记录级分相阶跃特征1875变化/4928观察，665未观测90%幅度不补值；仅已观测者上调中位1.113s/下调0.420s，非现场端到端时延。原D057静态成绩不变，首轮基础包限定收口/卡DC-20261016-04，完整容量/现场控制/P1未验；下一类型及整合由用户决定，不更新handoff。

'''
edit('项目文件索引.md',lambda s:s.replace('\n\n','\n\n'+index,1).replace('2026-10-16现用D057','2026-10-16前序D057',1))
edit('resource_research_results/README.md',lambda s:s.replace('首个共同指令→同期网侧P静态研究映射，统计截顶参数非物理上限；有分组退步，状态/动态/可用容量未验，整体研究仍进行中','v1.1首轮基础包六项限定收口：共同指令→同期网侧P静态映射＋独立KIT记录级分相阶跃特征；统计截顶非物理上限，665未观测90%幅度保留；现场控制端到端时延/容量/需求授权未验',1)+'''\n2026-10-16 D058：EV v1.1新增KIT记录级阶跃特征计算、派生结果及六项有限验收，首轮基础包在限定范围内收口；不同对象组件分别使用，整体P1/正式103未通过。下一资源及整合仍待用户决定，教师稿/handoff保持。\n''')

notes=BASE/'runs/KIT_SOURCE_QA_01/publication_consistency_notes.json';assert not notes.exists()
dump(notes,{'date':'2026-10-16','decision':'D058','supplement_to_original_QA_not_a_replacement':True,
 'publication_count_differences':[{'date':'2025-10-28','catalog_rows':1331504,'actual_rows':1328301},
  {'date':'2025-11-11','catalog_rows':1054758,'actual_rows':1054757}],
 'observed_total_rows':24474687,'treatment':'Preserve downloaded source and report differences; do not fabricate or fill rows.',
 'time':'timestamp_ns is physical INT64 TIMESTAMP_MICROS/isAdjustedToUTC=false; relative time only. Actual median20ms for first5sets,21ms thereafter. No claim of calibrated physical timing or fixed50Hz.',
 'EPFL_candidate':'Official metadata/README/root MIT inspected; local workbook headers/initial rows only, no full QA/current identity or new admission. Minute grid, retrospective session fields not used.'})
for p,s in changes.items():p.write_text(s,encoding='utf-8')
print('D058 recorded in',len(changes),'existing ledgers/navigation/process files; no handoff/teacher/new formal report.')
