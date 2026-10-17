"""Document matched equipment source and a partial gain that failed fixed gate."""
from common import *
run=BASE/'runs/BL_HIL_POWER_01';v=load(run/'verification.json');assert v['status']=='passed'
summary=load(run/'summary.json');assert summary['predeclared_relative_success'] is False
protocol=sha(BASE/'hil_power_protocol_v1.json');admission=sha(BASE/'runs/PREP_HIL_POWER_01/admission.json')
assert protocol=='fec13b94cf0db70579a8f3a335bfc8cb0c06c6dd1c7246668ecedc5458f3d6f7'
source='''按D059继续寻找电功率—温度—控制对应原始来源，实际取得NLR官方目录246（DOI10.7799/2440214）、原许可、试验矩阵、五个2024年两级中央空调AC制冷CSV，以及平台说明NREL/CP-5500-82562全文14页。没有下载/拼接其热泵或供暖文件。元数据下载MATCHED_SOURCE_01、数据HIL_AC_SOURCE_01各文件大小/SHA256/MD5/单段S3 ETag保存，5CSV MD5均与响应ETag一致，不冒称发布者独立签名校验。五CSV共47856763字节、341639秒级行；文件名/日期与矩阵14个AC工况逐项一致。原许可是NREL专用许可，不猜CC-BY，全文2451字符notice已随本地HIL数据保存，引用署名DOE/NREL/ALLIANCE。'''
source=source.replace('47856763','47856763')
# Use actual file sizes rather than a transcribed total.
entries=[r for r in load(BASE/'downloads/HIL_AC_SOURCE_01/receipt.json')['files'] if r['name'].startswith('AC_')]
source=source.replace('47856763',str(sum(r['bytes'] for r in entries)))
evidence='''对照阅读并渲染核查两份论文。六建筑/Annex81原始发布Mendeley xztfbtsgys v3的目录/论文已取，但未下载原数据或准入：其FLEXLAB共用冷机和锅炉，制冷/供暖电功率由热量与COP=3.0/效率0.95换算，不能当独立电表真值检验真实冷机电功率。当前选择NLR HIL作为新设备研究来源：一台SEER21、2冷吨两级中央空调在五个室外舱温下试验，室内外机电功率是实测，Q为按空气侧测量计算的制冷量；建筑热响应/室温舱设定由EnergyPlus驱动，不是现场住户数据。82562验证的是平台及另一3冷吨热泵，未把论文误差转给2024两级AC；SEER21不等于瞬时COP21。'''
qa='''HIL_AC_QA_01全341639行/5文件核心字段有限，原序严格1秒、无重复/倒序/时步缺口。TimeStamp无时区，只按本文件相对时间，不称UTC或硬件同步已标定。负制冷量302行、负外机功率762行均保留，总设备P无负值；没有按目标符号、误差、启停瞬态或所谓稳态筛掉样本。温控器原5分钟数据重采样至1秒，文件中大量插值变化；矩阵起点只是大致时间，不能推成精确秒级指令/端到端时延或真实舒适授权。Q是热kW，P为电W，不混单位/不同对象。'''
sample='''拟合/误差前冻结[hil_power_protocol_v1.json](../work/air_conditioning_research_20261016/hil_power_protocol_v1.json)，SHA256 `'''+protocol+'''`，绑定5CSV/矩阵/论文/目录许可/QA。全部341639行按有限与原时钟条件准入，无排除。按设计温度交替整实验划分：75/95/115°F三文件训练211383点，85/105°F两整文件评价130256点。此为同一台设备跨环境温度插值检验，训练实验部分晚于评价实验，明确不是按时间提前预测、独立设备或跨站验证。不随机拆相邻秒；每个训练文件总权重相等。准入收据SHA256 `'''+admission+'''`先于拟合保存。'''
method='''新问题是**已知同一发布行空气侧计算制冷量Q及实测室外温度T时，重建同一行室内机＋室外机实测总电功率**。模型不读当前/未来电功率作输入，不用温控器插值信号或虚拟室温定运行状态；输入Q不是所求电P。B_COP=b0+b1Q为常斜率基线，M_TEMP=b0+b1Q+b2Q(T−35)为一阶环境温度修正；分别2/3系数、等整实验权重OLS、rcond1e-12。B_MEAN只是诊断，不事后换它作主基线；不夹预测/加约束/找参数/按分组路由。截距/斜率是统计映射，不作真实COP、物理最大功率或承诺保证。预设要求总体、两个评价文件分别MAE/RMSE均优于B_COP，且Q≥1kW输入诊断组双改善；Q阈值只分组，不删训练/评价点。'''
result='''实际总体130256点B_COP→M_TEMP：MAE174.273316→82.292264W，RMSE275.574281→179.664331W；Q≥1kW60356点也双改善，文件等权平均两指标改善。但是仅85°F/约29.4℃评价文件双改善：MAE211.385074→70.354556W、RMSE304.897446→162.842968W；105°F/约40.5℃文件反而MAE101.538252→105.688890W、RMSE206.352427→208.736857W，故**不通过事前完整相对标准**。不能只保留总体或改成85°F专用路由以补分。1238点超训练输入范围仍留，0负M_TEMP预测；最差仍3908.908160W。最差例85°F第673行2024-06-08 01:20:57，源Q−0.346200856kW/外机3606.13W/内机323.44W，总3929.57W，而M_TEMP20.661840W；保留负Q和上下文，不自行判故障/具体延迟或把同期统计模型当可调能力。'''
verification='''BL_HIL_POWER_01/02五科研产物逐字节相同。verify_hil_power.py以pandas原CSV/向量时钟独立于stdlib准备器，重核341639原行/4441307字段或标志、全部130256评价点；用按整文件等权的中心矩闭式解独立于lstsq求系数，66指标通过。系数最大差2.51e-10、预测3.12e-10W、指标2.70e-10W；独立解析器对参考P的最大二进制差4.55e-13W。核验器先遇pandas3只读数组写入问题，修为显式复制；随后范围端点精确相等及参考P精确相等断言分别被1.78e-15kW/4.55e-13W解析差触发，改用有单位的浮点容差，未改科学数据、模型或增益门槛；这些核验尝试在收据中保留，不称科学实验通过了失败门槛。'''
nextstep='''本轮补齐真实空调设备电表来源，并完成首轮跨舱温同期用电映射比较与独立复算；总体/部分工况正向，完整门槛未过，候选仍留work，不建立空调最终成果目录、不判六项有限验收完成。D059原温度ARX失败/所有留出和协议保持。当前接续集中于启停/档位状态与测量同步的证据和新的独立验证条件，先明确动态问题，不在这两个已见留出上改温度项/阈值/滤波/删瞬态/换路由补分。现有数据可作明确标注的描述/开发，不能再声称新盲测。现场真实温控、用户授权、可用/可承诺容量、端到端时延、全体P1/103仍未验证；不启动整合/高级模型/GPU，不上传/提交，不改教师稿/handoff或新建正式outputs报告。'''
text='\n\n'.join('- '+x for x in (source,evidence,qa,sample,method,result,verification,nextstep))
changes={}
def edit(name,fn):
    p=ROOT/name;s=p.read_text(encoding='utf-8');assert 'D060' not in s,name;changes[p]=fn(s)
edit('docs/DECISION_LOG.md',lambda s:s+'\n\n## D060｜空调HIL真实电表来源与同期功率温度修正的有限增益/门槛失败\n\n- 日期：2026-10-16；状态：新源/样本/比较/复算完成，资源基础包未验收。\n\n'+text+'\n\n- 卡DC-20261016-06新增同设备HIL同期映射用途，D059与旧03—05用途保持；[研究入口](../work/air_conditioning_research_20261016/README.md)、[过程记录](../work/process_notes/2026-10-16_空调资源研究.md)。\n')
card='## 空调：独立NLR HIL设备同期电功率重建限定准入（D060）\n\n'+'\n\n'.join('- '+x for x in (source,evidence,qa,sample,method))+'\n\n- 结果总体改善但105°F评价文件退步，未达完整相对门槛，见实验台账。来源/特定样本准入不代表控制/容量或模型验收。当前卡06新增此用途，旧05的PLEIA原温度实验按原协议保留。\n\n'
edit('docs/DATA_CARD.md',lambda s:s.replace('卡版本：DC-20261016-05','卡版本：DC-20261016-06',1).replace('## 空调：PLEIAData来源与约10分钟温度预测限定准入',card+'## 空调：PLEIAData来源与约10分钟温度预测限定准入',1))
experiment='## BL-HVAC-HIL-POWER-20261016｜跨舱温同期电功率映射：总体改善，105°F退步（D060）\n\n'+'\n\n'.join('- '+x for x in (sample,method,result,verification,nextstep))+'''\n\n- 实际顺序：MATCHED_SOURCE_01目录/许可/六建筑论文→HIL_AC_SOURCE_01仅5AC/矩阵/平台论文→HIL_AC_QA_01全量与HIL_DOCUMENT_CHECK_01文件/日期对应→freeze_hil_power.py→PREP_HIL_POWER_01→BL_HIL_POWER_01/02→verify_hil_power.py。PDF阅读技能只读源文、两关键页渲染核对，没有生成交付PDF。原许可全文随下载保留，原表/主文/图不作指令执行。核验器三次技术断言修正见HIL_VERIFIER_ATTEMPTS_01，不影响实验门槛。\n\n'''
edit('docs/EXPERIMENT_LOG.md',lambda s:s.replace('## BL-HVAC-TEMPERATURE-20261016',experiment+'## BL-HVAC-TEMPERATURE-20261016',1))
status='''最新执行（2026-10-16，D060）：空调新增NLR246真实设备电表/HIL来源，5原AC制冷CSV341639行，1台两级中央空调，室内外机实测P与空气侧计算Q分别使用。5MD5与单段响应ETag一致，矩阵14工况/5文件日期对应；时钟原序严格1s、无缺口，302负Q/762负外机P均保留。温控器5分钟重采样，HIL建筑热响应并非现场室温；FLEXLAB固定COP推算的制冷电P不作独立真值。协议fec13b94cf0db70579a8f3a335bfc8cb0c06c6dd1c7246668ecedc5458f3d6f7误差前固定，75/95/115°F整文件训练211383，85/105°F评价130256，为跨温度同期插值而非时间预测。B_COP→M_TEMP总体MAE174.273316→82.292264W/RMSE275.574281→179.664331W，但105°F两项退步，完整门槛未过，最差3908.908W/1238域外点保留。独立原CSV/4441307标志字段/中心矩拟合/130256预测/66指标及五产物复跑通过。卡DC-20261016-06，[研究入口](../work/air_conditioning_research_20261016/README.md)。空调基础包未验收/不归集最终候选；当前补启停/档位/同步及新的独立验证依据，不在已见留出调参补分。D059失败与原三类最终成果保持，不整合/高级分支/GPU/handoff/新报告，P1/103未通过。以下D059及更早为历史时点。

'''
old='现用D059：已选空调，完成首轮来源/样本/透明baseline核验，ARX未过相对增益，资源基础包未验收。当前接续核对有设备电功率、温度及明确控制时点的匹配来源，已见留出不用于调参补分；不自动整合或高级分支。下列D058及更早为历史时点。'
nextstatus='现用D060：新NLR HIL实测电表来源及固定同期功率映射已核验，整体/85°F改善但105°F退步，完整门槛未过。当前补启停/档位与同步证据及新的独立验证条件，不在已见留出调参/删瞬态补分；空调基础包仍未验收，不整合/高级分支。下列D059及更早为历史时点。'
for name in ('outputs/ROADMAP_v2.md','outputs/第一阶段两周执行计划_v2_20261013.md'):
    edit(name,lambda s:s.replace('最新执行（2026-10-16，D059）',status+'前序执行（2026-10-16，D059）',1).replace(old,nextstatus,1).replace('当前按D059推进空调来源/样本与baseline','当前按D060完成新HIL来源/同期功率首轮比较，补动态状态/同步与独立验证依据',1))
snapshot='''- 2026-10-16现用D060：空调新增NLR246/HIL真实设备电表来源，5AC制冷CSV341639秒级行/1台两级中央AC，5MD5对响应单段ETag一致、14矩阵工况日期对应。源Q是空气侧计算热kW、室内外机P实测电W，HIL建筑热响应非现场，温控器5min重采样不作秒级指令。FLEXLAB冷机P固定COP推算不作真值。协议fec13b94cf0db70579a8f3a335bfc8cb0c06c6dd1c7246668ecedc5458f3d6f7，原341639行全留含302负Q/762负外机P，75/95/115°F整文件训练211383，85/105°F评价130256，非时间预测。B_COP→M_TEMP总体MAE174.273316→82.292264W/RMSE275.574281→179.664331W，但105°F两项退步，完整相对门槛未过；最差3908.908W、1238域外点不删。独立原CSV/4441307字段标志/中心矩拟合/130256预测/66指标和5产物复跑通过，卡DC-20261016-06。空调基础包未验收/不建最终目录，当前补启停/档位/同步与新的独立验证条件，不在已见留出调项/阈值/删瞬态/换路由补分。D059失败、三类最终成果/教师稿/handoff保持；不整合/高级分支，无GPU/上传/提交，P1/103未通过。入口work/air_conditioning_research_20261016/README.md。\n'''
edit('AGENTS.md',lambda s:s.replace('先读D059用户选空调/新源样本与ARX失败边界','先读D060 HIL真实设备电表/同期温度修正局部增益与105°F失败，再读D059用户选空调/新源样本与ARX失败边界',1).replace('- 2026-10-16现用D059：',snapshot+'- 2026-10-16前序D059：',1))
index='''- 2026-10-16现用D060：[空调过程入口](work/air_conditioning_research_20261016/README.md)、[HIL固定同期功率协议](work/air_conditioning_research_20261016/hil_power_protocol_v1.json)、[过程记录](work/process_notes/2026-10-16_空调资源研究.md)。新增真实设备室内外机电P及空气侧计算Q，341639原行/5温度实验同一台两级AC；训练211383/评价130256。总体误差改善但105°F退步，门槛未过，独立复核/5产物复跑通过；卡DC-20261016-06。HIL/重采样边界明确，空调基础包未验收、不建最终目录、不调旧留出或整合。

'''
edit('项目文件索引.md',lambda s:s.replace('\n\n','\n\n'+index,1).replace('2026-10-16现用D059','2026-10-16前序D059',1))
edit('resource_research_results/README.md',lambda s:s+'\n2026-10-16 D060：空调新取得HIL实测设备电表，固定同期功率映射总体有增益但高温评价退步、未过完整标准，候选仍留[过程目录](../work/air_conditioning_research_20261016/README.md)，不新增最终成果类型或改原三类成绩。\n')
edit('work/process_notes/2026-10-16_空调资源研究.md',lambda s:s.replace('现用D059','现用D060（D059前序保留）',1)+'\n\n## D060｜新设备电功率准入、同期重建局部增益及高温失败\n\n'+text+'\n')
intro='''## 当前D060：新HIL设备电表准入与同期功率比较

- 原始[官方目录246](https://data.nlr.gov/submissions/246)/DOI10.7799/2440214，数据HIL_AC_SOURCE_01含五AC制冷CSV、Test_Matrix.xlsx及平台论文82562。五CSV共341639原行，1台SEER21/2冷吨两级中央空调，源P为实测电W、Q为空气侧计算热kW；不拼PLEIA/其他热泵。许可为NREL专用许可，完整notice随原件保存；5文件MD5与下载响应单段ETag对应，非发布者独立签名。
- 论文两关键页已渲染目检：HIL是真设备＋模拟建筑，温控器5min数据重采样至1s，不能作秒级指令/现场舒适度真值。六建筑论文FLEXLAB冷机/锅炉用电按固定COP/效率换算，不用于独立验证真实设备P；未取得该来源原始数据。平台论文验证另一3冷吨热泵，不转用其精度。
- HIL_AC_QA_01核心全量/时钟，HIL_DOCUMENT_CHECK_01核14矩阵工况的5文件名/日期；原序严格1秒、无缺口，302负Q/762负外机P保留。TimeStamp无时区，不称UTC。全部341639行进入PREP_HIL_POWER_01，无按输出/瞬态/残差删点。
- [误差前协议](hil_power_protocol_v1.json)SHA256 `'''+protocol+'''`；75/95/115°F整文件训练211383点，85/105°F两整实验评价130256点，为环境条件插值，训练时间部分晚于评价，不是时间外推预测。各训练文件总权重相等，统计模型只用同期Q、实测室外T，不用当前/未来P作输入。

| 评价条件 | 常斜率基线MAE→温度修正MAE（W） | RMSE（W） | 双改善 |
|---|---:|---:|---|
| 全部130256点 | 174.273316→82.292264 | 275.574281→179.664331 | 是 |
| 85°F/约29.4℃ | 211.385074→70.354556 | 304.897446→162.842968 | 是 |
| 105°F/约40.5℃ | 101.538252→105.688890 | 206.352427→208.736857 | 否 |

B_COP=b0+b1Q（2参数），M_TEMP=b0+b1Q+b2Q(T−35)（3参数），都是等整文件权重OLS，系数非物理COP/保证。Q≥1kW60356点及文件等权也改善，但预定标准要求两个评价工况均双改善，故完整门槛未过；不临时换B_MEAN诊断或限定85°F补分。1238训练输入域外点、最差3908.908W保留。最差源负Q−0.3462kW但总P3929.57W，模型仅20.66W，不能自动判原因/响应延迟。

`run_hil_power.py --run-id <新的唯一ID>`已完成BL_HIL_POWER_01/02五产物相同；`verify_hil_power.py`独立pandas原CSV/向量时钟、按整文件等权中心矩闭式解（不导入核/运行器），341639原行/4441307字段标志/全部130256预测/66指标通过，预测最大差3.12e-10W。核验器的只读数组/浮点精确相等断言技术修正见HIL_VERIFIER_ATTEMPTS_01；不改变科学协议/模型或失败裁决。既有核验脚本拒覆盖收据。

当前空调基础包未验收，不新建最终目录。下一项补启停/档位、测量同步及新的独立验证依据，不在这批已见留出上改温度项、阈值、滤波、删瞬态或换路由。原PLEIA ARX失败保持。下面D059为历史首轮温度研究，现用卡DC-20261016-06；无整合/高级分支/GPU/handoff或新增正式报告。

'''
edit('work/air_conditioning_research_20261016/README.md',lambda s:s.replace('现用决定D059','现用决定D060',1).replace('## 已实际完成的首轮比较（D059）',intro+'## 前序首轮温度比较（D059，历史时点）',1))
attempt=BASE/'runs/HIL_VERIFIER_ATTEMPTS_01';attempt.mkdir(exist_ok=False)
dump(attempt/'receipt.json',{'date':'2026-10-16','status':'technical_verifier_repairs_then_passed',
 'attempts':[{'stage':'vector clock','error':'ValueError assignment destination is read-only','repair':'to_numpy(copy=True)'},
  {'stage':'training input ranges','error':'exact float equality assertion; maxQ difference1.776e-15kW','repair':'absolute tolerance1e-12 for range numbers; domain flags still exactly verified'},
  {'stage':'target exact equality','error':'independent source parser/reference difference4.547e-13W','repair':'require absolute reference difference<1e-9W; report actual max'}],
 'model_protocol_sample_not_changed':True,'relative_gate_still_failed':True,'completed_verification_sha256':sha(run/'verification.json')})
for p,s in changes.items():p.write_text(s,encoding='utf-8')
print('D060 source/use limits, fixed comparison,105F failure and reproduction recorded in',len(changes),'existing records; no handoff/final-package promotion.')
