from common import *
def once(s,a,b):assert s.count(a)==1,(a,s.count(a));return s.replace(a,b,1)
snapshot='2026-10-16现用D067：用户选储热式电热水器／电锅炉配水箱为第六类；实际以150L/3kW卧式电阻水箱的发布温度特征与条件后续5分钟标签估计按六项有限收口，electric_water_heating v1.0，工业锅炉未实证。原Mendeley七JSON/187682487字节/130438原条目大小及SHA全核，分钟/无日期/单位行/缺测及三留出电能全0保留，不估真实效率容量。协议5f75213a7d757989ee3f73e47194a4098827bc80bb5bf6aa5d240776e131bfa0，卡DC-20261016-13；16751分钟候选/16636准入，4整文件训练9305/3留出7331，重叠日期同留出侧，非顺时间/独立物理事件。B_P→M_LAYER6 MAE0.219087→0.120595℃、RMSE0.472491→0.197518℃，总体/3文件/标记1组较两基线双改善；标记0两项退步、316域外及最差2.295133℃保留。独立样本/SVD/全7331预测/96指标和五产物复跑、74462描述数值/全图目标对齐、最终全点回放通过。原五包88文件不变。六类有限基础覆盖达到，本轮停止；工业对象/容量/控制及P1/103未验，不自动整合/高级分支/GPU/handoff/教师稿或新正式报告。'
failure=BASE/'runs/SOURCE_QA_01/failure.json'
assert not failure.exists();dump(failure,{'status':'failed_historical_attempt','error':'ValueError: YYYY-MM-DDTHH:mm:ss','cause':'Initial source clock parser did not accept unit/header row embedded in originalTrace. Subsequent inspection also found alternateTraceCollection/TimeStamp casing/time-only/minute formats.',
 'partial_artifacts_preserved':['dictionary.json','data_paper.txt'],'superseded_by':'SOURCE_QA_02','changes':'Explicit source schemas and literal formats,invalid-time counts. No source editing,scientific filtering relaxation or fit; prediction protocol frozen only afterQA02.'})
f=ROOT/'docs/DECISION_LOG.md';s=f.read_text(encoding='utf-8');assert '## D067｜' not in s
s+='''

## D067｜储热式电热水器第六类基础研究与条件温度标签模型有限收口

- 日期：2026-10-16；用户选择“储热式电热水器／电锅炉配水箱”，由第六类待选转为当前研究，近期至少六类覆盖目标保持。实际公开源为150L/名义3kW卧式Kwikot Superline电阻水箱，不把家用参数当工业锅炉/泵/换热器组合已验证。对应正式任务一运行特征/因素的基础证据与任务二后续温度参照，不替代容量/控制或103正式验收。
- 网上核原Mendeley v1 DOI10.17632/ddmv4w434g.1、CC-BY-4.0；元数据74文件65373字节，按文件名预选全部7heatingreg JSON共187682487字节/130438条目，大小及发布者SHA256全一致。取原字典/测点图并只读核验，DataBrief10.1016/j.dib.2024.110082全文XML实际读取；出版社403/PMC交互校验未绕过，正常公开EuropePMC全文可取。Buechler等2312.04102v1给热平衡/分层/OLS方法类别，另一立式设备参数/控制/节费不转用；2024状态空间论文仅登记/原摘要，不称复现。
- 首QA01遇嵌入时间单位行失败，保留部分产物/失败记录；QA02适配源Trace/TraceCollection及字段大小写和显式时刻格式，不改原件。3单位时刻行、分钟截断、无日期跨午夜、−127和元数据采样10s而实见约5s等均披露，不补日期或秒。三个留出电能PowerConsumed全0且有加热标记，原单位Wh/采样；不补名义功率作实测，不准入真实电热效率/热容/可调量。本轮转为以发布温度为参照的局部温度标签估计，运行标记非控制送达或真实功率。
- 拟合前冻结协议`5f75213a7d757989ee3f73e47194a4098827bc80bb5bf6aa5d240776e131bfa0`、准入`6ac8efa82f80c18e2106db02dcaf4ee8df9f5e4713fe16025aad4d6332ab9e06`。原序每文件/时钟块每分钟末原行锚定，不择最后有效行；前后5分钟和中间11标签完整，相关温度0—100℃宽质量范围、标记0/1。16751候选，100窗缺/15温度失格，16636准入；四整文件9305训练/三个7331评价。日期重叠的三文件同留出侧，含训练晚于测试及两训练无日期，不称顺时间部署/独立物理事件；跨两侧连续三全信号行精确重复0亦不证明独立。
- M_LAYER6为当前局部T加六系数统计修正：常数、历史5标签温差、当前加热标记、两环境传感器均值与T差、B0上/下温与T差；各训练文件等权OLS/rcond1e-12/秩6。当前完整分钟数据可得为条件，只预测+5发布分钟标签，不保证精确300s物理提前量；无未来标记/P/用水/设定输入，系数非R/C/效率。未剪裁、平滑、搜索、正则或改状态路由。
- 实际7331点B_P/B_TREND/M_LAYER6 MAE0.219086755/0.191718183/0.120594568℃，RMSE0.472491055/0.365369432/0.197517784℃；总体、三文件各自及当前标记1的593点均较两基线双改善，原标准通过。标记0的6738点较B_P MAE0.105494→0.109108/RMSE0.171468→0.175434℃退步保留；316特征域外、最差2.295132845℃不删不路由。没有以小温差误差换算90%或独立校准真实温度精度。
- BL01/02五科研产物字节一致，独立向量时钟/锚点/SVD对照逐行准备/lstsq，全16636样本/7331预测/96指标通过，预测差1.43e-14℃；JSON解码器共享、同一物理源。误差已见后描述协议`8f5b3e0995bc9a4e58eb45f35889068df8993dc736b0d64f18a69ac26e68464a`仅补全七文件16751分钟温度特征和三留出完整曲线，灰带为上下测点跨度非置信区间；两描述产物复跑、74462独立数值/7331目标对齐通过，PNG目检、SVG同图未另渲染，无新拟合/盲测。
- 最终electric_water_heating v1.0全7331回放差7.11e-15℃、8非法/不完整输入、2边界/目录外两构造例通过，cmd未UI双击实测。原五类88发布文件身份不变。按D046六项对对象输出、曲线公式/依据、源参照、固定正向比较、全组退步/域外/最差及复算可运行代码审查，**仅在原水箱温度特征/条件后续标签估计范围有限收口**；工业锅炉、真实能量/可调容量、供水舒适约束、现场控制和跨设备仍专项。
- 六类近期限定基础覆盖已达到，本轮停止新增实验。卡DC-20261016-13和五文档/AGENTS/导航同步，既有五类成果/教师稿/handoff保持，不新建正式报告/自动整合、自监督、多智能体或GPU。P1/103未通过；下一专项或整合由用户明确决定。见[最终成果](../resource_research_results/electric_water_heating/README.md)、[过程入口](../work/electric_water_heating_research_20261016/README.md)、[过程记录](../work/process_notes/2026-10-16_储热式电热水器研究.md)。
''';f.write_text(s,encoding='utf-8')
f=ROOT/'docs/DATA_CARD.md';s=f.read_text(encoding='utf-8');s=once(s,'卡版本：DC-20261016-12','卡版本：DC-20261016-13')
section='''## 储热式电热水器：温度特征与条件后续5分钟标签估计限定准入（D067）

- 用户选第六类储热式电热水器／电锅炉配水箱。实际对象Mendeley DOI10.17632/ddmv4w434g.1的一台Kwikot Superline卧式150L/名义3kW电阻水箱，CC-BY-4.0。官方74文件元数据/配套DataBrief全文/字段XLSX/测点图已核；预选全部7加热保温JSON共187682487字节、130438原条目（含3时间单位行），官方大小/SHA256逐一通过。字典只读，不编辑。另取对照CSV/两小放水JSON，仅源质量，不混模型。原件/逐点及收据见work下载/runs，已忽略Git。
- 时刻有完整日期秒、无日期时分秒、分钟截断；Trace/TraceCollection和时间字段大小写不同，−127及元数据周期与实见时步不一致保留。先QA01因占位单位行失败，现用QA02记录源格式和全部计数。无时区不称UTC；不补日期/秒，原序坏时间或倒退重开块，每块每分钟取最后原行而非较老有效值。三个日期范围重叠文件全部置同一留出侧；两个训练缺日期、部分训练晚于测试，不称顺时间或独立物理事件。跨两侧连续三全信号精确重复0，仅诊断。
- 原PowerConsumed为Wh/采样，E05/E06/E07全0但存在加热标记，不能算实测电功率/真实效率/容量；也不以3kW×标记填补。发布局部NTC温度可作当前条件标签估计的观测参照，未独立校准物理真温。B0上/下测点与NTC不同位置，不能当整箱平均温度或储热量。工业锅炉/完整放水控制/供水需求等用途未准入。
- 误差前协议`5f75213a7d757989ee3f73e47194a4098827bc80bb5bf6aa5d240776e131bfa0`、准入`6ac8efa82f80c18e2106db02dcaf4ee8df9f5e4713fe16025aad4d6332ab9e06`。16751分钟末锚点候选，同文件/块前后5分钟全部11标签完整，相关温度有限0—100℃、当前标记0/1；100时钟窗/15温度失格，16636合格。4整文件9305训练、3整文件7331评价。条件当前完整分钟数据可得，输出+5发布分钟末局部温度，不保证精确300s物理提前量。无未来输入/回填/启停或误差筛点。
- 模型/完整曲线及分组比较已独立核验，六项仅在原温度用途有限收口。标记0两指标退步、316域外和最差保留；本卡不扩大源用途。回顾描述协议8f5b3e0995bc9a4e58eb45f35889068df8993dc736b0d64f18a69ac26e68464a，七文件16751锚点与全部7331图源/目标标签对齐，无新拟合或盲测。六类基础覆盖达到不代表整个P1/103验收。
- [研究入口](../work/electric_water_heating_research_20261016/README.md)、[最终代码](../resource_research_results/electric_water_heating/README.md)、[原协议](../work/electric_water_heating_research_20261016/temperature_protocol_v1.json)。旧五类数据卡/冻结协议与用途保持，下节D066为前序状态。

'''
s=once(s,'## 风电：完整发布运行特征的回顾描述（D066）',section+'## 风电：完整发布运行特征的回顾描述（D066）');f.write_text(s,encoding='utf-8')
f=ROOT/'docs/EXPERIMENT_LOG.md';s=f.read_text(encoding='utf-8')
section='''## BL-WATER-TEMPERATURE-20261016｜第六类条件温度标签模型及有限基础审查（D067）

- 实际SOURCE_01/DICTIONARY_01/NATIVE_CLOCK_01/CLOCK_CANDIDATES_01/REGULATION_01下载，7主JSON187682487字节/130438条目（3单位行），官方大小/SHA全部一致；SOURCE_QA_01未接受单位时间行失败，部分产物与failure保留，QA02适配源结构/时间格式记录完成。无原件改写或科学放宽，冻结模型在QA02之后。配套全文XML/字典/原图已读，未执行作者程序。CPU，无GPU/远程传输。
- 卡DC-20261016-13，协议5f75213a7d757989ee3f73e47194a4098827bc80bb5bf6aa5d240776e131bfa0/拟合前准入6ac8efa82f80c18e2106db02dcaf4ee8df9f5e4713fe16025aad4d6332ab9e06。16751分钟候选/100窗缺/15温度失格/16636合格；4整文件9305训练/3文件7331评价。日期重叠3文件同留出侧，部分训练晚于测试/两训练无日期；文件工况留出，不是顺时间部署/独立物理事件。保留最后原分钟行，不补秒日期/选较老有效行/跨午夜块。
- 6系数当前温度+历史温差/当前加热标记/环境差/上下测点差，整文件等权OLS、rcond1e-12、秩6。没有未来输入、剪裁/调参/路由。能量列三个留出全零，当前标记不作真实功率；模型仅对+5发布分钟局部NTC标签，非精确300s物理提前量/能量容量。
- B_P/B_TREND/M_LAYER6总体MAE0.219086755/0.191718183/0.120594568℃，RMSE0.472491055/0.365369432/0.197517784℃；原总体、各3文件和标记1的593点均优于两基线。标记0的6738点较B_P MAE0.105494→0.109108、RMSE0.171468→0.175434℃退步；316特征域外、最差2.295132845℃（E06行3161，当前59.187/目标61.424/预测59.128867）全部保留，不事后换路由。非正式90%或独立校准真温精度。
- BL_TEMPERATURE_01/02五科研产物字节同；VERIFY_TEMPERATURE_01向量时钟/锚点构建与逐行独立、显式SVD与lstsq独立，117257键/标志、全部16636样本/7331预测/96指标通过，系数差3.78e-15、预测1.43e-14℃。原JSON解码器/测量源共享。跨两侧3原全信号行重复0只作诊断，不证明物理独立。
- 已见误差后描述协议8f5b3e0995bc9a4e58eb45f35889068df8993dc736b0d64f18a69ac26e68464a；CHAR01/02全7文件16751锚点分布/三留出完整曲线，灰带为B0上/下测点跨度，非置信区间。两科研描述产物字节同、VERIFY_CHAR74462数值/全部图源及7331目标对齐通过，最大差7.11e-15℃，PNG目检、SVG同图未另渲染。0新拟合/0新盲测。
- PACKAGE_TEMPERATURE_01最终标准库7331回放差7.11e-15℃、8非法/缺输入/2边界/目录外两例通过，cmd未界面双击测试。原五包88发布文件指纹保持。最终electric_water_heating v1.0只最终核/参数/例子/来源/聚合/图与六项发布核验，无原件或过程代码。
- 六项有限审查仅原150L水箱温度特征/条件后续标签估计通过，六类近期基础覆盖达到，本轮停止。工业锅炉/实际热量容量/供水舒适/控制时延/完整用水/迁移仍专项，P1/103未过。不整合/高级分支/GPU/handoff/教师稿或新建正式报告。[过程入口](../work/electric_water_heating_research_20261016/README.md)、[最终成果](../resource_research_results/electric_water_heating/README.md)。

'''
s=once(s,'## CHAR-WIND-20261016｜',section+'## CHAR-WIND-20261016｜');f.write_text(s,encoding='utf-8')
for name in ['outputs/ROADMAP_v2.md','outputs/第一阶段两周执行计划_v2_20261013.md']:
    f=ROOT/name;s=f.read_text(encoding='utf-8')
    s=once(s,'最新执行（D066）：','最新执行（D067）：'+snapshot+'[第六类成果](../resource_research_results/electric_water_heating/README.md)、[六项有限审查](../resource_research_results/electric_water_heating/results/basic_research_acceptance.json)。\n\n前序执行（D066）：');f.write_text(s,encoding='utf-8')
f=ROOT/'AGENTS.md';s=f.read_text(encoding='utf-8')
s=once(s,'先读D066风电六项限定收口/v1.1与健康容量缺口，','先读D067第六类电热水箱六项有限收口/分钟时钟与电能零值及工业锅炉缺口，再读D066风电六项限定收口/v1.1与健康容量缺口，')
s=once(s,'- 2026-10-16现用D066：','- '+snapshot+'\n- 2026-10-16前序D066：')
s=once(s,'、`air_conditioning/`及`wind_power/`（','、`air_conditioning/`、`wind_power/`及`electric_water_heating/`（热水器仅150L水箱温度特征/条件后续标签估计有限收口，工业锅炉/真实容量控制未验；')
f.write_text(s,encoding='utf-8')
f=ROOT/'项目文件索引.md';s=f.read_text(encoding='utf-8')
s=once(s,'- 2026-10-16现用D066：','- '+snapshot+'[第六类使用](resource_research_results/electric_water_heating/README.md)、[六项审查](resource_research_results/electric_water_heating/results/basic_research_acceptance.json)、[完整曲线](resource_research_results/electric_water_heating/results/test_temperature_curves.png)、[过程入口](work/electric_water_heating_research_20261016/README.md)。\n\n- 2026-10-16前序D066：');f.write_text(s,encoding='utf-8')
f=ROOT/'resource_research_results/README.md';s=f.read_text(encoding='utf-8')
row='| 储热式电热水器 | [使用说明](electric_water_heating/README.md)：原150L卧式电阻水箱温度特征与条件后续5发布分钟标签估计，v1.0六项有限收口；三整文件正向及独立复算，标记0退步/316域外/最差保留；真实电能容量/工业锅炉配水箱未验 |'
s=once(s,'\n完成相应范围的基础研究并验证保留组件后，','\n'+row+'\n\n完成相应范围的基础研究并验证保留组件后，')
s=s.replace('提前预测未验 |\n\n| 储热式电热水器 |','提前预测未验 |\n| 储热式电热水器 |',1)
s+='\n2026-10-16 D067：储热式电热水器v1.0按原150L设备温度用途完成六项有限基础审查，近期六类覆盖达到。本轮停止新增实验；工业电锅炉配水箱仍待专项，不把它另计已完成类型。原五类保持，跨资源整合待用户明确要求，全体P1/103未过。\n';f.write_text(s,encoding='utf-8')
print('D067 applied. Six bounded basic packages; no integration or handoff changes.')
