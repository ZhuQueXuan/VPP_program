"""Apply D065 to existing authorised ledgers/navigation; no new report."""
from common import *
snapshot='2026-10-16现用D065：用户选风电为第五类，首个同期风速—功率曲线组件v1.0已独立核验归集，整体风电基础包仍进行中。官方Kelmarsh2018六台MM92/各2050kW，ZIP发布者MD5/12成员CRC通过；315360原行/303987准入，前9月训练234751/后3月评价69236。协议6dd7e842d6b4da7d6332526021f30bdfbbeaee73d8e8d03eac012cf99343a475，卡DC-20261016-11。固定0.5m/s训练节点曲线较直线MAE150.473447→55.175509kW、RMSE200.830358→100.046282kW，总体/6机/3月/正P组均较直线及立方双改善；最差2044.636561kW、稀疏81条和负P保留。69963事件60301缺结束，采用混合观察条件，不认健康状态/可用容量。原ZIP独立样本/中心矩/全部69236预测/180指标及五产物复跑、最终69236回放通过；原四包69文件不变。下一项补运行特征/曲线及大误差上下文，再审六项基础包；不在已见留出调参。第六类未选，不整合/高级分支/GPU/handoff/教师稿，P1/103未过。'
def replace_once(s,old,new):
    assert s.count(old)==1,(old[:90],s.count(old));return s.replace(old,new,1)

f=ROOT/'docs/DECISION_LOG.md';s=f.read_text(encoding='utf-8');assert '## D065｜' not in s
s+='''

## D065｜用户选风电及首个同期功率曲线有限组件

- 日期：2026-10-16；用户明确“可以，我们先研究风电吧”。第五类由候选转为当前主动研究，D064至少六类目标保持；第六类未选。先做风速—同期有功功率关系，不自动进入未来预测/容量/整合。对应正式任务一运行特征的基础证据，供任务二后续参照，不改103任务与验收。
- 实际取官方Kelmarsh DOI10.5281/zenodo.16807551原元数据、2018ZIP262157463字节、静态表/映射；大小及发布者MD5一致，ZIP全部12成员CRC通过。六台Senvion MM92/各2050kW，原静态直径92m与部分论文92.5m差异保留，不用于拟合。原CSV299字段、315360十分钟UTC行，严格600s，无倒序/重复/缺口；聚合边界/物理同步仍未知。核心有限303987条，风速/功率无效计数重叠，不按目标/残差/额定值筛选。
- 69963事件60301无结束时刻，不能完整重建健康/停机采样状态。准入仅混合观察条件的同期曲线，设定值非已核送达，Potential power非独立容量真值。Kolumbán等1707.06497v2支持分段线性方法类别，Fiocchi等10.1002/we.70012提供来源/事件背景；原文经web读，本地出版社403/arXiv SSL失败收据保留，未绕过。0.5m/s节点是本研究事前选择，不是IEC认证/论文全复现，不转用V80阈值/故障前筛选/神经网络。
- 拟合前协议SHA256`6dd7e842d6b4da7d6332526021f30bdfbbeaee73d8e8d03eac012cf99343a475`；准入`5787ad36b02a4b3574a3f8630a8d80815cd67d6f2bb2587ac01621f861eebb20`。前9月234751训练、后3整月69236评价，同六机、不随机相邻拆分。B_LINEAR=a+bv、B_CUBIC=a+bv³各机OLS2系数，M_CURVE固定0.5m/s全非空训练箱均值节点共280个，线性插值/端点常数；不平滑/剪裁/单调约束/搜索，少于20只诊断。
- 实际B_LINEAR→M_CURVE总体MAE150.473447→55.175509kW、RMSE200.830358→100.046282kW；立方262.829208/353.104135kW。原定总体/各六机/正P65829条双指标均低于两基线，至少2/3月要求实际3/3满足。分段模型更灵活，只认本次固定比较增益；不宣称最优或正式90%。非正P3407/稀疏81条/全部负源P及947超名义额定P保留，域外风速0条无指标。最差2044.636561kW，4号2018-11-28 15:50UTC、13.607419m/s而源P−0.933625kW，具体原因未确认；不据此判故障/限电或删除。
- BL_CURVE_01/02五科研产物字节一致；独立pandas原ZIP/原时钟标志与stdlib准备器对照、中心矩回归与lstsq对照、groupby节点及np.interp与bisect对照，全69236预测/180指标/门槛通过。预测最大差1.46e-11kW、指标1.37e-11kW；是计算独立，非新物理源。最终标准库核69236回放差0、9非法/298构造边界、两个目录外Python命令样例通过，cmd未UI双击实测；原四包69发布文件指纹保持。
- 新增`resource_research_results/wind_power/`v1.0仅最终同期统计核/必要参数/例子/聚合与来源/发布收据，不存下载/拟合/逐点数据。首组件正向不自动视为风电基础包六项验收；下一项补全六机运行特征/功率曲线和大误差上下文，核查状态边界后按D046审查。已见留出不得调分箱/阈值/删停机补成绩，新增模型另定依据与独立评价。完整健康曲线/可用可调量/控制时延/提前预测/独立站点仍未验，全体P1/103未过。
- 过程/卡/台账/现用路线计划及导航同步；原四类成果、教师稿/handoff保持，不新增outputs报告/整合/高级分支/GPU或上传提交。见[研究入口](../work/wind_power_research_20261016/README.md)、[过程记录](../work/process_notes/2026-10-16_风电资源研究.md)、[最终组件](../resource_research_results/wind_power/README.md)。
''';f.write_text(s,encoding='utf-8')

f=ROOT/'docs/DATA_CARD.md';s=f.read_text(encoding='utf-8');s=replace_once(s,'卡版本：DC-20261016-10','卡版本：DC-20261016-11')
section='''## 风电：混合观察条件同期风速—功率曲线限定准入（D065）

- 用户已选风电为第五类，替代下节D064等待选择；第六类未定。官方原始Kelmarsh DOI10.5281/zenodo.16807551，Plumley/Takeuchi、CC-BY-4.0；原ZIP262157463字节/发布者MD5一致、12成员CRC全通过，静态表/映射大小与MD5均核。ZIP SHA256`38be7dd50b7f5dfe5642df33117482b06c12602153af7566a9acaa2cfcf85cd7`，实际收据见downloads/KELMARSH_2018_01。仅2018，不混二次修复版本或其他年份。
- 六台Senvion MM92，各2050kW；原静态叶轮直径92m，论文部分92.5m差异未统一，模型不读几何。原运行各299字段/52560行，总315360；UTC十分钟原序严格600s，无重复/倒序/间隔异常，不代表聚合边界或物理同步已核。只用同一发布行Wind speed(m/s)→Power(kW)，不声称提前预测。
- 准入风速有限且≥0、P有限、时间唯一/原序连续/2018范围；无效风速11373、无效P11002，重叠并集11373，合格303987。负P/超2050/大残差/事件记录均不筛，不补值/排序/平滑。69963事件60301无结束，状态不能完整重建，限定混合观察条件；不把无事件当健康，不用Potential power作独立可用容量真值或设定值作已核指令。
- 事前协议`6dd7e842d6b4da7d6332526021f30bdfbbeaee73d8e8d03eac012cf99343a475`，准入`5787ad36b02a4b3574a3f8630a8d80815cd67d6f2bb2587ac01621f861eebb20`。1—9月训练234751、10—12月整月评价69236，同六机时间留出，不是新站点。每机训练39126/39130/39127/39119/39126/39123，评价11629/11615/11297/11624/11444/11627。已见评价只能保留原冻结用途，不再选择分箱/筛选补分。
- 原Power列可作该同期统计目标的观测参照，但测量链未独立校准，不延伸为健康标准曲线/真实可用容量/控制真值。新结果曲线相对两固定基线正向并复算，整体风电六项基础包仍进行中；域外风速评价0条，不宣称域外/迁移已验。卡11仅新增此用途，旧四类全部协议与成绩保持。
- [过程入口](../work/wind_power_research_20261016/README.md)、[固定协议](../work/wind_power_research_20261016/curve_protocol_v1.json)、[过程记录](../work/process_notes/2026-10-16_风电资源研究.md)、[最终使用](../resource_research_results/wind_power/README.md)。后续先做全机特征/曲线及状态边界审查，能力/未来预测另需证据。

'''
s=replace_once(s,'## 后续资源候选池（D064，未准入）',section+'## 后续资源候选池（D064历史初筛，风电现用见D065）');f.write_text(s,encoding='utf-8')

f=ROOT/'docs/EXPERIMENT_LOG.md';s=f.read_text(encoding='utf-8');marker='## CHAR-HVAC-20261016｜'
section='''## BL-WIND-CURVE-20261016｜同期功率曲线首个有限组件（D065）

- 实际完成：SOURCE_01/KELMARSH_2018_01下载、ARCHIVE_QA_01/SOURCE_QA_01、PREP_CURVE_01；BL_CURVE_01/02比较复跑，VERIFY_CURVE_01原ZIP独立复算，PACKAGE_CURVE_01最终回放。卡DC-20261016-11；来源/样本/时点见数据卡及[研究入口](../work/wind_power_research_20261016/README.md)。全本机CPU，无GPU/远程传输。
- 315360原行/303987准入；前9整月训练234751、后3整月评价69236。原始源Power(kW)为同期目标，仅同发布行wind输入，六机分别拟合。协议`6dd7e842d6b4da7d6332526021f30bdfbbeaee73d8e8d03eac012cf99343a475`误差前冻结、准入先保存。0.5m/s训练均值分段线性曲线280节点；直线与立方OLS各机2系数，rcond1e-12。没有训练/评价筛负P/超额定/事件/残差，没有剪裁/平滑或调参。
- 实际69236点B_LINEAR/B_CUBIC/M_CURVE：MAE150.473447275/262.829207892/55.175509427kW，RMSE200.830358308/353.104134560/100.046282479kW。总体/6机/3评价月/正P65829条均较两基线双改善，原至少2/3月门槛满足。非正P3407条M_CURVE66.608836/273.708691kW，稀疏81条346.644032/576.771188kW；0域外组保持null。最差2044.636561kW、负P/947超名义额定源值和模型1733负/1超额定输出均保留，不诊断故障或作保证。
- 01/02参数/预测/指标/诊断/协议五产物逐字节一致。verify_curve.py独立pandas解析原ZIP/重建全部源时钟/准入及划分、中心矩独立于lstsq回归、groupby节点对照和np.interp独立于bisect；315360原行、全部69236评价预测、180指标及全门槛通过。最大系数差4.10e-12、预测1.46e-11kW、指标1.37e-11kW。是独立算术实现，不是新物理来源。
- 最终`wind_power`v1.0标准库核全69236点回放差0、9非法输入/298节点端点构造检查、两个目录外Python命令示例通过；cmd未UI双击实测。原四类发布69文件指纹不变。全源/逐点/过程代码仍work，成果仅最终核/参数/例子/聚合/来源，发布收据`results/release_validation.json`。
- 裁决：首个有限同期功率曲线组件完成并归集，风电整体基础包尚未六项验收。混合运行、69963事件60301缺结束，未验证健康曲线/可用容量/限功率响应/提前预测/跨站迁移。下一项补全运行特征/功率曲线与大误差上下文，再审六项；已见留出不改规则补分。P1/103未过，不整合/高级分支、教师稿/handoff或新增outputs报告。

'''
s=replace_once(s,marker,section+marker);f.write_text(s,encoding='utf-8')

for name in ['outputs/ROADMAP_v2.md','outputs/第一阶段两周执行计划_v2_20261013.md']:
    f=ROOT/name;s=f.read_text(encoding='utf-8')
    s=replace_once(s,'最新执行（D064）：','最新执行（D065）：'+snapshot+'[风电首组件](../resource_research_results/wind_power/README.md)、[过程入口](../work/wind_power_research_20261016/README.md)。\n\n前序执行（D064）：')
    s=s.replace('前序执行（D063）：2026-10-16现用D064：','D064前序范围快照：2026-10-16当时D064：',1)
    f.write_text(s,encoding='utf-8')
f=ROOT/'AGENTS.md';s=f.read_text(encoding='utf-8')
s=replace_once(s,'先读D064至少六类覆盖目标/第五类待选与候选状态，','先读D065风电原件/同期曲线首组件与整体未验边界，再读D064至少六类覆盖目标/原候选状态，')
s=replace_once(s,'- 2026-10-16现用D064：','- '+snapshot+'\n- 2026-10-16前序D064：')
s=replace_once(s,'`ev_charging/`及`air_conditioning/`（','`ev_charging/`、`air_conditioning/`及`wind_power/`（风电仅首个有限同期曲线组件，整体基础包仍进行中；')
f.write_text(s,encoding='utf-8')
f=ROOT/'项目文件索引.md';s=f.read_text(encoding='utf-8')
s=replace_once(s,'- 2026-10-16现用D064：','- '+snapshot+'[风电使用](resource_research_results/wind_power/README.md)、[发布核验](resource_research_results/wind_power/results/release_validation.json)、[过程入口](work/wind_power_research_20261016/README.md)。\n\n- 2026-10-16前序D064：');f.write_text(s,encoding='utf-8')
f=ROOT/'resource_research_results/README.md';s=f.read_text(encoding='utf-8')
line='| 风电 | [使用说明](wind_power/README.md)：v1.0首个有限同期风速—功率统计曲线，原六台MM92/后3月留出双改善及独立复算通过；混合观察运行条件，最差/稀疏误差保留；整体风电基础包仍在研究，健康曲线/容量/提前预测未验 |\n'
s=replace_once(s,'\n完成相应范围的基础研究并验证保留组件后，','\n'+line+'\n完成相应范围的基础研究并验证保留组件后，')
# Keep the new parallel row contiguous with the existing table.
s=s.replace('未验 |\n\n| 风电 |','未验 |\n| 风电 |')
s+='\n2026-10-16 D065：用户选风电为第五类，新增首个独立核验的有限同期曲线组件，整体基础包仍进行中。当前四类基础包有限收口＋第五类首组件；第六类未选，不能按五个目录认定六类目标完成。原四包文件与成绩保持，不自动整合或更新handoff。\n'
f.write_text(s,encoding='utf-8')
print('Updated D065 ledgers, roadmap/plan and navigation. No handoff/teacher artifact changed.')
