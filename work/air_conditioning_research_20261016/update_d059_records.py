"""Record user-selected HVAC, original QA and first frozen failed ARX baseline."""
from common import *
run=BASE/'runs/BL_TEMPERATURE_02';v=load(run/'verification.json');assert v['status']=='passed'
summary=load(run/'summary.json');assert not summary['predeclared_relative_success']
pp=BASE/'temperature_protocol_v1.json';protocol=sha(pp)
assert protocol=='adc0deb406665804b7e87955a41b2869216d637c7c220cf00ed2544ff1a6016a'
admission=sha(BASE/'runs/PREP_TEMPERATURE_01/admission.json')
changes={}
def edit(name,fn):
    p=ROOT/name;s=p.read_text(encoding='utf-8');assert 'D059' not in s,name;changes[p]=fn(s)
source='''用户在蓄热锅炉/冷库讨论后明确选择“先做推荐的空调”，由候选建议转为当前单个主动资源。仅逐类基础研究，储能/PV/EV原最终包和成绩保持；不启动跨资源整合。网上回溯PLEIAData Scientific Data2023论文及原始发布Zenodo7620136，取回官方元数据/完整论文HTML与Data_Nature.zip。283086145字节，MD5 3a65b744ce960c0bced4285c7cc6d3d4与发布者一致，SHA256 3e1c3a4a40213ab99ecdc92d71c8c59e9ecf0ff802e19a278f009c6a28d4fd03，原始数据CC-BY-4.0；37个ZIP成员（含目录）完整CRC通过。作者notebook只审阅，未执行。'''
qa='''原始温度9857796行/191ID、HVAC4339076行/88ID、分块电表154833行/3ID。房间温度关系90ID/61房间、其中64ID在温度文件实际出现；HVAC关系87行/86ID/79房间，335545193对应两房间。全部原时序按设备反向时间排列，无反向顺序中的时间增量；温度/HVAC同时间重复119/517，电表无重复。显式+01/+02等偏移由原文解析为UTC，天气无明确偏移不拼。原始截至12月31日；作者notebook因天气可得将处理后数据截到12月18日，保留解释而不裁原始。全191ID不能自动认作室内温度，映射子集仍有极端值；不把未映射读数全称房间故障。初始QA模板“type0未核”不是实见：原V26仅1/2；主notebook明示V5为0未设/1供热/2制冷/3干燥/4送风，V6风档但细码不猜，补充说明见PLEIA_SOURCE_VERIFY_01。'''
boundary='''对象为论文所述Toshiba VRF末端与房间；一个末端不等于独立室外机/独立电表。V22是楼块累计kWh，不是单机kW，原累计差分无负值但有0和大跳值，未据此分摊或计算单机容量。开关/模式/设定温度是观测状态，不是核实的调度送达；当前记录可得只是离线研究假设。室温短时预测不等于因果控制响应、舒适授权或可承诺降载。热平衡仅为机制依据，ARX系数不解释为热容/传热/COP参数。'''
sample='''在模型/误差前冻结temperature_protocol_v1.json，SHA256 `'''+protocol+'''`。仅房间内恰一个有实录温度ID和一个无跨房间歧义HVAC ID，共36房间，1857911原温度候选；不按成绩选房。逐设备按原行倒序还原观测先后，前/当前/后原相邻三记录时间唯一，两个间隔均540—660秒、温度0—60℃宽质量范围；不补值/平均/插值。HVAC取原时间不晚于当前温度的最后记录，龄≤600秒，重复键拒绝不跳到更老有效值；状态0/1、模式0/1/2、开机仅供热或制冷、设定5—40℃。质量范围不是用户舒适区间。天气时间偏移未核，不用天气；不使用任何未来控制/时间间隔作输入。目标是下一约10分钟发布采样温度，非精确600秒物理预测。'''
split='''固定2021-01-01至09-01前目标作训练，09-01后起点至2022-01-01前目标作评价；相同房间/场站的时间外推，不是独立场站验证。各房间至少1000训练/1000评价，36均合格：训练1037755点、评价548660点；目标区间不交叠，评价可用先前历史观测。准入收据SHA256 `'''+admission+'''`在拟合前保存。全部候选/重叠排除保留：窗口缺72、温度唯一性144、节拍1378、温度有效性72（端点缺失也计入）、状态过旧/不可得88933、控制键歧义181、状态/设定超研究范围186206，split范围外288；这些数字重叠不能相加作剔除数。36实际所用温度ID原值均在0—60℃，没有靠极端温度筛掉大预测误差。'''
method='''B_P为当前温度保持；B_TREND为当前值加上次温差；M_ARX为当前值加6项线性统计回归：[常数、上次温差、开机供热×设定温差、开机制冷×设定温差、开机供热、开机制冷]。每房间训练OLS rcond1e-12，共216系数，0超参搜索，不夹输出、不改房间/阈值/路由。事前标准要求总体/房间等权及开机子集MAE/RMSE均优于B_P，且至少一半房间双改善；趋势法次要完整报告，不根据分数临时换基线。'''
result='''实际548660评价点：B_P MAE0.079317963℃/RMSE0.158697522℃，B_TREND0.111607049/0.226342287℃，M_ARX0.090149351/0.208922223℃，整体退步；房间等权也退步，仅9/36房间双改善。开机58528点（10.6674%）B_P0.134676854/0.229367885℃，ARX0.236599431/0.475165324℃，也失败。仅9月双改善，10/11/12月退步全部保留。ARX最差8.556828978℃、B_P最差6.027503967℃，未剪掉极端误差。训练设计秩分布2:14、4:10、5:1、6:11，25/36房间不足满秩，限制参数识别；该诊断不证明退步的单一因果原因，未据此删房/正则/重拟合。小总体MAE且约89.33%关机不能换算103的90%精度，也不能证明调节能力完成。'''
verify='''BL_TEMPERATURE_01在结果导出时因DuckDB1.4/pandas3字符串类型不兼容失败，failure与部分结果保留；只将导出文本列显式转为Python对象，协议/模型/样本未改。02首次完整完成，03五科研产物逐字节复跑相同。独立stdlib CSV/datetime核全原始温度/HVAC/电表计数及原时钟；模型核验独立读1857911原温度及1772236关联HVAC行，重建13005377准入标志、全部548660评价点，显式SVD对照lstsq拟合、558指标检查通过；系数最大差2.49e-14、预测1.07e-14℃、指标3.55e-15℃。原始解析器独立，派生Parquet解码器共享，不是新的独立物理实验。'''
nextstep='''本轮完成空调原始来源核验、受限样本/协议和首轮baseline比较；ARX候选明确失败，保留B_P为研究参照，不将失败候选归入最终成果项目、不宣称空调基础包六项验收或全体P1通过。当前单个接续问题是寻找/准入同时具备设备电功率、室温与明确控制/实验时点的空调来源，进一步检验温度惯性及控制关系；已见本批留出不再调参补分，新方法需先有相应依据/新冻结协议与适合独立验证证据。既有观测可做如实标注的诊断，不自动转高级控制/自监督/市场分支。无GPU需求，不上传/提交；不改教师稿/handoff，不新建outputs交付报告。'''
alltext='\n\n'.join('- '+s for s in (source,qa,boundary,sample,split,method,result,verify,nextstep))
edit('docs/DECISION_LOG.md',lambda s:s+'\n\n## D059｜用户选空调，原始数据准入与首轮ARX失败保留\n\n- 日期：2026-10-16；状态：初次数据/样本/baseline比较完成，资源研究继续，未验收。\n\n'+alltext+'\n\n- 现用[过程入口](../work/air_conditioning_research_20261016/README.md)、[固定协议](../work/air_conditioning_research_20261016/temperature_protocol_v1.json)、[过程记录](../work/process_notes/2026-10-16_空调资源研究.md)。D058的EV有限收口与原三类成果保持，下一类型待选的旧状态由本次用户选择替代；不替代103正式任务。\n')
data='## 空调：PLEIAData来源与约10分钟温度预测限定准入（D059；不开放容量/控制因果用途）\n\n'+'\n\n'.join('- '+s for s in (source,qa,boundary,sample,split))+'\n\n- 实际结果/失败见实验台账，当前ARX未达预定增益。来源与协议限定合格不等于模型正向或空调研究验收。下列DC-20261016-04及更早用途按原协议保留。\n\n'
edit('docs/DATA_CARD.md',lambda s:s.replace('卡版本：DC-20261016-04','卡版本：DC-20261016-05',1).replace('## KIT记录级电流阶跃特征限定准入',data+'## KIT记录级电流阶跃特征限定准入',1))
exp='## BL-HVAC-TEMPERATURE-20261016｜空调温度首轮冻结比较，ARX未通过（D059）\n\n'+'\n\n'.join('- '+s for s in (sample,split,method,result,verify,nextstep))+'''\n\n- 原始阶段PLEIA_METADATA_01/PLEIA_RAW_01实际下载，PLEIA_ARCHIVE_01全部CRC，PLEIA_SOURCE_QA_01全字段/关系/时钟，PLEIA_SOURCE_VERIFY_01独立原CSV计数/时钟及字典补充。PREP_TEMPERATURE_01保留全部候选；BL_TEMPERATURE_02当前，03复跑，01失败不覆盖。TEMPERATURE_SUPPORT_01只描述支持/秩，未再拟合。各收据含数据/代码/协议/输出指纹，卡DC-20261016-05。\n\n'''
edit('docs/EXPERIMENT_LOG.md',lambda s:s.replace('## CHAR-EV-KIT-20261016',exp+'## CHAR-EV-KIT-20261016',1))
status='''最新执行（2026-10-16，D059）：用户已选择空调，当前单项为温度/状态与控制关系基础。新PLEIAData原始包283086145字节/MD5及37成员CRC通过，来源CC-BY-4.0；原温度9857796/HVAC4339076/电表154833行，房间映射歧义及极端值、反向时间/重复均保留。36明确单温度—单末端房间1857911候选，协议adc0deb406665804b7e87955a41b2869216d637c7c220cf00ed2544ff1a6016a误差前固定，训练1037755/评价548660点，卡DC-20261016-05。B_P MAE0.079318/RMSE0.158698℃，ARX0.090149/0.208922℃未达增益，仅9/36房间双改善；开机58528点也退步、25/36训练欠满秩，全部失败保留。独立原CSV/13005377标志/全部评价预测/558指标及5产物复跑通过。空调基础包未验收，未新建最终目录；当前接续寻找设备功率—温度—控制时点匹配来源，不在已见留出调参补分，容量/因果/端到端时延未验。[过程入口](../work/air_conditioning_research_20261016/README.md)。原三类有限成果保持，P1/103未通过，不整合/高级分支/GPU/handoff或新报告。以下D058等为历史时点。

'''
nextstatus='现用D059：已选空调，完成首轮来源/样本/透明baseline核验，ARX未过相对增益，资源基础包未验收。当前接续核对有设备电功率、温度及明确控制时点的匹配来源，已见留出不用于调参补分；不自动整合或高级分支。下列D058及更早为历史时点。'
old='现用D058：EV首轮基础包六项有限检查完成，现有静态映射＋独立记录级分相阶跃特征代码/结果/复现。当前收口等待用户选择下一资源；真实控制/容量另需专门准入，不以旧留出调参补分，不自动整合或进入高级模型。下列D057及更早均为历史时点。'
for name in ('outputs/ROADMAP_v2.md','outputs/第一阶段两周执行计划_v2_20261013.md'):
    edit(name,lambda s:s.replace('最新执行（2026-10-16，D058）',status+'前序执行（2026-10-16，D058）',1).replace(old,nextstatus,1).replace('当前按D058有限收口EV首轮基础包，完整现场控制/容量用途仍待准入','当前按D059推进空调来源/样本与baseline；EV首轮基础包限定收口保持，完整现场控制/容量用途仍待准入',1))
snapshot='''- 2026-10-16现用D059：用户明确选空调，原PLEIAData7620136包283086145字节MD5/37成员CRC及全原始QA通过，CC-BY-4.0。温度9857796/HVAC4339076/电表154833行，房间关联含歧义/未覆盖，原时间倒序/重复保留；天气偏移未核不拼，楼块累计kWh非单机kW。协议adc0deb406665804b7e87955a41b2869216d637c7c220cf00ed2544ff1a6016a误差前固定，36一温度—一末端房间1857911候选，训练1037755/评价548660，卡DC-20261016-05。B_P MAE0.079318/RMSE0.158698℃、ARX0.090149/0.208922℃未过增益，仅9/36双改善，开机58528点也退步、25/36训练欠满秩；最差8.556829℃保留。01导出类型兼容失败，02完整/03五产物复跑同；独立原CSV/13005377准入标志/全部评价预测/558指标通过。空调首轮基础包未验收、不建最终空目录；当前问题转向匹配设备电功率、室温及明确控制时点的来源准入，不在已见留出调参补分。研究入口work/air_conditioning_research_20261016/README.md；温度预测非容量/因果控制/真实时延，三类旧最终成果与教师稿/handoff保持，不整合/高级分支，P1/103未通过，无GPU/上传/提交。\n'''
edit('AGENTS.md',lambda s:s.replace('先读D058 KIT记录级阶跃特征及EV v1.1首轮基础包有限收口','先读D059用户选空调/新源样本与ARX失败边界，再读D058 KIT记录级阶跃特征及EV v1.1首轮基础包有限收口',1).replace('- 2026-10-16现用D058：',snapshot+'- 2026-10-16前序D058：',1))
index='''- 2026-10-16现用D059：用户选空调，当前[过程入口](work/air_conditioning_research_20261016/README.md)、[冻结温度协议](work/air_conditioning_research_20261016/temperature_protocol_v1.json)、[过程记录](work/process_notes/2026-10-16_空调资源研究.md)。新源/时钟/关系/质量核验与36房间首轮时间留出比较完成，B_P MAE0.079318℃、ARX0.090149℃未达增益；548660评价点与5产物复跑/独立复算通过。卡DC-20261016-05，空调基础包未验收，当前补查功率—温度—控制对应来源，不在已见留出调参、不预建最终目录；原三类有限成果保持。

'''
edit('项目文件索引.md',lambda s:s.replace('\n\n','\n\n'+index,1).replace('2026-10-16现用D058','2026-10-16前序D058',1))
edit('resource_research_results/README.md',lambda s:s+'\n2026-10-16 D059：用户选空调作为下一类，过程见[研究入口](../work/air_conditioning_research_20261016/README.md)。已做原始准入与首轮温度baseline比较，ARX候选未通过，未作为最终成果归集，暂不建立空调成果目录；当前三类最终代码与成绩保持。\n')
process=ROOT/'work/process_notes/2026-10-16_空调资源研究.md';assert not process.exists()
changes[process]='# 空调资源研究过程记录\n\n日期：2026-10-16；现用D059。直接分析、过程记录照常保存，不生成正式outputs报告。\n\n'+alltext+'\n\n过程入口：work/air_conditioning_research_20261016/README.md；冻结协议、样本准入、失败与复现均在该目录。此次是空调研究启动和第一轮失败比较，尚未完成基础包，不更新handoff。\n'
# This README already identifies D059 by design; update through an exact current-status insertion.
readme=BASE/'README.md';s=readme.read_text(encoding='utf-8');assert '## 已实际完成的首轮比较' not in s
intro='''## 已实际完成的首轮比较（D059）

原始包MD5/37成员CRC通过。原温度9857796行、HVAC4339076行、电表154833行；源解析/时钟/字典补充见runs/PLEIA_SOURCE_QA_01及PLEIA_SOURCE_VERIFY_01。191温度字段ID不能全当房间温度；关系表90温度ID中64实际出现，HVAC87行/86ID有1ID跨房间。主notebook解释模式3干燥/4送风；V26实际仅1/2，初始QA模板type0不代表实见。原始截至12月31日、作者处理后因天气截12月18日，见独立核验说明。

[固定协议](temperature_protocol_v1.json)SHA256 `'''+protocol+'''`在拟合/误差前保存，样本见PREP_TEMPERATURE_01。36明确单温度—单末端房间，1857911候选；原序逐设备反转/不修钟、不补值，约10分钟原相邻温度、≤10分钟历史末端状态，状态唯一/字段质量条件全部固定。2021年1—8月训练1037755点、9—12月评价548660点，非随机行拆分。天气与楼块用电均未作房间模型输入。

首次BL_TEMPERATURE_01在导出时遇DuckDB1.4/pandas3字符串类型兼容失败，保留failure和部分结果；仅转导出文本为Python对象，未改协议/样本/模型。02完整完成、03五产物相同。运行`run_temperature.py --run-id <新的唯一ID>`可复跑（需要原始下载、PREP样本及本机NumPy/pandas/DuckDB，默认依赖由脚本定位）；不要覆盖旧ID。

| 方法 | MAE（℃） | RMSE（℃） |
|---|---:|---:|
| B_P 当前温度保持 | 0.079318 | 0.158698 |
| B_TREND 上次温差延续 | 0.111607 | 0.226342 |
| M_ARX 六项线性统计模型 | 0.090149 | 0.208922 |

ARX未达预定标准，房间等权及开机58528点也退步，仅9/36房间双改善、仅9月双改善。最差ARX8.556829℃/B_P6.027504℃保留，不夹预测或改房间。开机仅占评价10.6674%，不能拿总体小误差当能力已验。TEMPERATURE_SUPPORT_01只诊断：25/36训练设计欠满秩，不据此删房/调参/改用正则补分。

`verify_temperature.py`独立读原CSV、datetime时间/向量准入与历史asof，核1857911候选/13005377标志、全部548660预测，显式SVD对照lstsq训练/558指标通过，预测最大差1.07e-14℃。五科研产物复跑同，现用核验在runs/BL_TEMPERATURE_02/verification.json。两个verify脚本及prepare/archive/QA均为一次运行，拒覆盖旧目录或收据，既有证据读收据即可。

当前只完成来源/样本/第一轮比较，空调基础包未验收；失败ARX留work，不新建最终目录。下一项核对设备电功率—室温—明确控制时点匹配来源；本批留出不再用于改协议调参。需求授权/物理控制时延/真实可用容量仍未验。此前研究问题与候选说明如下，固定实验以现用协议为准。

'''
changes[readme]=s.replace('## 研究问题与完成方向',intro+'## 研究问题与完成方向',1)
for p,s in changes.items():p.write_text(s,encoding='utf-8')
print('D059 current status, raw/sample admission, failure and independent verification recorded in',len(changes),'records; no handoff/new formal report/final package.')
