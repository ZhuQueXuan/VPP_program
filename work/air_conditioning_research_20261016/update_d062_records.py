"""Record real new-source positive component, limits and final-code navigation."""
from common import *
run=BASE/'runs/BL_DUAL_ZONE_01';s=load(run/'summary.json');v=load(run/'verification.json');pkg=ROOT/'resource_research_results/air_conditioning'
assert s['predeclared_relative_success'] and v['status']=='passed'
release=load(pkg/'results/release_validation_v1_0.json');assert release['status']=='passed' and release['full_test_rows_replayed']==2288
assert all(sha(pkg/n)==h for n,h in release['verified_files'].items())
protocol=sha(BASE/'dual_zone_protocol_v1.json');admission=sha(BASE/'runs/PREP_DUAL_ZONE_01/admission.json')
previous=load(BASE/'control_candidate_status_v1.json');previous['decision']='D062';previous['source_metadata_only']=False;previous['supersedes']='control_candidate_status_v1.json remains D061 historical snapshot'
previous['dual_zone_experimental'].update({'raw_downloaded':True,'raw_files':8,'publisher_sha256_all_match':True,'raw_rows':2304,'paired_paper_verified':'Crossref journal identity and author title/abstract direction only; full methods unavailable','journal_doi':'10.1016/j.enbuild.2026.118112','admitted':'conditional offline next5min record-label temperature prediction only','control_response_admitted':False,'next':'Keep original holdout fixed; supplement independent control/stage/power evidence and finite basic-package coverage review.'})
previous['not_implemented']='No distributed MPC/advanced control; one new simple5coefficient-per-room statistical baseline actually fitted and verified.'
newstatus=BASE/'control_candidate_status_v2.json';assert not newstatus.exists();dump(newstatus,previous)
source='''取得[Choi等双区域试验原发布v1](https://data.mendeley.com/datasets/7tzkdhgpfs/1)，DOI10.17632/7tzkdhgpfs.1，CC-BY-4.0。官方public-api根文件列表[]是根文件夹无文件，不代表数据不存在：完整dataset.json实际列8个子文件，按其明确URL取回94326字节、8CSV/2304时点，全部大小与发布者SHA256逐项一致。每天288行、原序严格300秒、无重复/倒序/缺口、7字段全有限；2房间温度17.2—28.2℃/18.7—28.1℃（按房间见QA），功率分别0—1133/0—1129W，字段单位直接来自CSV。QA_01解析器未接受源单数字小时“0:00”，改显式%Y-%m-%d %H:%M后QA_02通过，原始数据不改，失败收据保留。'''
# Ensure byte count and room temperature ranges come from actual QA/metadata, not prose transcription.
metadata=load(BASE/'downloads/DUAL_ZONE_METADATA_01/dataset.json');source=source.replace('94326',str(sum(f['size'] for f in metadata['files'])))
source=source.replace('2房间温度17.2—28.2℃/18.7—28.1℃（按房间见QA）','房间1温度18.7—28.1℃、房间2温度17.2—28.2℃')
paper='''Crossref原注册和作者机构页面核对配套期刊文Choi等[10.1016/j.enbuild.2026.118112](https://doi.org/10.1016/j.enbuild.2026.118112)，登记2026-08-22、标注11月卷期，非把未来卷期当已到日期。SSRN10.2139/ssrn.6828065公开摘要说明实测RC网络方向，但本地下载一次403后停止；期刊全文方法/参数未获取。数据元数据articles/related_links为空，配套关联依作者/题名/同双区试验说明，未冒称元数据给出论文链接。新模型是自行固定的简单热平衡/温差记忆统计对照，不是论文参数/MPC/峰荷费用成绩复现；不开发高级控制。'''
sample='''本批新来源仅准入“当前发布行全部输入已可得”条件下的下一5分钟室温标签预测，不准入现场控制响应或容量。Timestamp无时区；电表边界、功率平均区间/上传延迟未明，因此不称实际提前5分钟在线预报。7字段未含设定、送达指令/档位；太阳字段MJ/m²累计区间未明，不转为瞬时辐照、不用作输入。温度标签真实观测不等于用户舒适授权，当前P不是控制设定，也不推因果效果。'''
experiment=f'''拟合/新误差前冻结dual_zone_protocol_v1.json，SHA256 `{protocol}`；原文件逐日、每房间前/当前/后三原相邻行均须有限、两个间隔300秒，温度0—60℃仅宽QC，不填补/排序/跨文件。4608候选→4576样本；32首末边界排除，nonfinite标志32是缺窗口，不是原源32坏读数，原因可重叠。前4天08-08—11训练2288房间点，后4天08-12/13/19/20评价2288，非随机或独立场站；准入收据SHA256 `{admission}`在拟合前保存。B_P温度保持、B_TREND上次温差延续。M_HEAT5输出T_now+β·[1,上次温差,当前室外减室内温差,本房间当前电W/1000,另一房间当前温差]，每房间5系数共10、等整训练日权重OLS/rcond1e-12，两个设计均满秩5；0调参/约束/正则/裁剪。另一房间当前实测是输入，不是跨资源整合；不读未来P/天气/房间温度。系数不认作R/C/COP。事前标准要求总体、两房间、当前正功率组均较两个基线MAE/RMSE双改善，并至少2/4评价日双改善。'''
result='''实际2288评价点B_P/B_TREND/M_HEAT5分别MAE0.320326923/0.464603147/0.285883291℃，RMSE0.631909295/0.970872117/0.528019323℃；总体、两房间、4/4评价日及当前正功率425点均较两个基线双改善，达到预定相对标准。当前零功率1863点相对B_P的MAE却0.179658615→0.201626072℃恶化（RMSE0.402176983→0.384128245℃）；零/正功率只是发布读数，非已证关/开机。154域外点保留，无状态路由；M_HEAT5总体最差3.566679918℃，08-20最差3.564587919℃高于B_P3.3℃，不能称逐点/逐状态全优，更不能按1−MAE换算103精度。'''
verification='''BL_DUAL_ZONE_01/02五科研产物逐字节相同。独立pandas原CSV/向量shift时钟相对stdlib准备器重建4608候选、23040标志及71428字段检查；显式SVD对照lstsq拟合、全部2288预测和204数值指标通过，系数最大差8.89e-16、预测7.11e-15℃、指标3.56e-15℃。不是第二物理仪器或独立场站。最终标准库代码全部2288点/9152字段标记回放差0，7类非法输入拒绝、域外标记及目录外构造例实际执行通过；未做桌面双击UI测试。'''
delivery='''新增resource_research_results/air_conditioning/成果v1.0，仅首个有限室温预测组件：最终计算代码、两房间参数/范围、构造例、可双击示例入口、聚合结果、署名来源与边界及发布收据；下载/清洗/拟合/诊断/核验脚本和原数据仍在work，未复制进去。模型预测需当前/前5min本房间温度、当前室外温度/本房间P/另一个原房间温度，不能迁移到任意新空调，不以构造例当实测成绩。第一组件通过不自动宣布空调整体基础包六项验收，现场时点、控制关系、可调容量/舒适授权仍待独立证据；下一单项补控制/档位—功率证据并核基础包覆盖，不在已见留出改模型或零功率路由。D059/D060/D061科学文件/失败及原三类最终包保持，P1/103未过；不整合/高级分支/GPU训练/上传提交，不改handoff或教师稿、不新建正式报告。'''
parts=[source,paper,sample,experiment,result,verification,delivery];body='\n\n'.join('- '+x for x in parts)
short='''2026-10-16现用D062：空调新增双区域实测温度/用电来源，8原CSV/2304时点、大小及发布者SHA256全部一致；仅条件于当前发布行可得的下一5分钟室温预测。协议32dc0d8a57e4dad8ce84eface039daff5226eb4ca3671d1608e151dd7533cca4，前4整日训练2288/后4日评价2288，2房间各5系数。B_P→M_HEAT5总体MAE0.320326923→0.285883291℃、RMSE0.631909295→0.528019323℃，两房间/4日/正P425点均较B_P及趋势法双改善，原定标准通过；零P1863点MAE退步、154域外/最差3.566680℃保留。独立23040标志/2288预测/204指标及5产物复跑、最终2288回放通过。卡DC-20261016-08，新air_conditioning v1.0仅首个有限预测组件，空调整体基础包未宣告验收。配套期刊Crossref登记可核，全文方法未获，不称复现MPC/论文成绩；时区/平均与上传/真实控制容量未验。下一项补控制/档位—功率独立证据及基础覆盖，不在已见留出调参/状态路由。D059—61失败/描述及原三类成果、handoff/教师稿保持，不整合/高级分支/GPU，P1/103未过。'''
changes={}
def edit(name,fn):
    q=ROOT/name;t=q.read_text(encoding='utf-8');assert 'D062' not in t,name;changes[q]=fn(t)
edit('docs/DECISION_LOG.md',lambda t:t+'\n\n## D062｜双区域实测室温预测正向对照及首个有限空调组件\n\n- 日期：2026-10-16；状态：新源/样本/固定比较/独立核验/组件归集完成，整体空调基础包未宣告验收。\n\n'+body+'\n\n- [过程入口](../work/air_conditioning_research_20261016/README.md)、[最终代码与用法](../resource_research_results/air_conditioning/README.md)。\n')
card='## 空调：双区域下一5分钟发布室温标签限定准入（D062）\n\n'+'\n\n'.join('- '+x for x in [source,paper,sample,experiment])+'\n\n- 卡08新增此用途；旧07事后诊断与候选暂缓状态保留为历史，现用候选状态为control_candidate_status_v2.json，v1不改。此准入和相对比较不替代现场时点、控制或真实能力准入。\n\n'
edit('docs/DATA_CARD.md',lambda t:t.replace('卡版本：DC-20261016-07','卡版本：DC-20261016-08',1).replace('## 空调：事后误差分组与SplitSmart候选核查（D061）',card+'## 空调：事后误差分组与SplitSmart候选核查（D061）',1))
entry='## BL-HVAC-DUAL-ZONE-20261016｜新来源5分钟室温标签正向对照（D062）\n\n'+'\n\n'.join('- '+x for x in [experiment,result,verification,delivery])+'\n\n- 实际次序：DUAL_ZONE_METADATA_01（根files空、dataset含8文件）→DATA_01全量身份→PAPER_01（Crossref/作者页成功，SSRN403）→QA_01解析技术失败/QA_02通过→freeze_dual_zone.py→PREP_DUAL_ZONE_01→BL_DUAL_ZONE_01/02→verify_dual_zone.py→最终组件/verify_packaged_dual_zone.py。源与论文边界见卡08，不是直接复现论文控制器。\n\n'
edit('docs/EXPERIMENT_LOG.md',lambda t:t.replace('## DIAG-HVAC-20261016',entry+'## DIAG-HVAC-20261016',1))
for name in ['outputs/ROADMAP_v2.md','outputs/第一阶段两周执行计划_v2_20261013.md']:
    edit(name,lambda t:t.replace('最新执行（D061）：','最新执行（D062）：'+short+'[空调最终有限组件](../resource_research_results/air_conditioning/README.md)。\n\n前序执行（D061）：',1).replace('现用D061：','现用D062：首个有限5分钟室温标签组件正向核验/归集，零P退步及旧失败保留，整体空调未验收。下一项补控制/档位—功率独立证据与基础覆盖，不调已见留出。\n\n前序D061：',1).replace('当前按D061完成事后描述/候选QA，先核新Mendeley原文件/字典与论文以补独立验证依据','当前按D062完成新双区室温对照和首个有限组件归集，接续补控制/档位—功率独立证据与基础覆盖',1))
edit('AGENTS.md',lambda t:t.replace('先读D061事后','先读D062新双区实测室温标签/首个有限组件与零P失败边界，再读D061事后',1).replace('- 2026-10-16现用D061：','- '+short+'\n- 2026-10-16前序D061：',1).replace('`distributed_photovoltaic/`与`ev_charging/`（EV首轮基础包限定收口，现场控制/容量未验）','`distributed_photovoltaic/`、`ev_charging/`及`air_conditioning/`（EV首轮基础包限定收口；空调仅首个有限室温预测组件，整体仍进行中；现场控制/容量未验）',1))
edit('项目文件索引.md',lambda t:t.replace('\n\n','\n\n- '+short+'[空调最终代码](resource_research_results/air_conditioning/README.md)、[过程入口](work/air_conditioning_research_20261016/README.md)。\n\n',1).replace('2026-10-16现用D061','2026-10-16前序D061',1))
edit('resource_research_results/README.md',lambda t:t.replace('\n完成相应范围','\n| 空调 | [使用说明](air_conditioning/README.md)：v1.0首个有限组件，原双区试验当前行可得条件下下一5分钟室温标签预测；2房间/4留出日双改善，零功率组MAE退步保留；整体基础包、真实在线提前量/控制/容量未验 |\n\n完成相应范围',1)+'\n2026-10-16 D062：新增空调首个有限室温预测组件及参数/构造例/聚合结果/发布核验，整体空调基础包仍进行中；原三类最终成果保持，第四类目录不代表四类完整功能验收。\n')
edit('work/process_notes/2026-10-16_空调资源研究.md',lambda t:t.replace('现用D061（D060/059前序保留）','现用D062（D061/060/059前序保留）',1)+'\n\n## D062｜双区域实测下一室温标签与首个最终组件\n\n'+body+'\n')
intro='''## 当前D062：双区域实测室温标签对照与首个有限组件

- 新[Mendeley原发布v1](https://data.mendeley.com/datasets/7tzkdhgpfs/1)/10.17632/7tzkdhgpfs.1，8CSV/2304时点，发布者SHA256/大小全匹配。根files接口空是无根文件，完整dataset含8子文件；两房间各温度/用电，原每天288行/严格5min，核心无缺失或时钟异常。QA_01单数字小时解析失败，QA_02按源格式解析通过，数据不改。
- [固定协议](dual_zone_protocol_v1.json)SHA256 `'''+protocol+'''`；4608候选/4576准入（32首末窗口边界），前4整日训练2288、后4整日评价2288，每房间5系数，共10，无调参。当前/历史温度＋当前室外温度、本房间P及另一房间温度，预测下一300秒发布温度标签；不使用未来输入。
- 总体B_P/B_TREND/M_HEAT5 MAE0.320327/0.464603/0.285883℃、RMSE0.631909/0.970872/0.528019℃；2房间/4日/正P425点均较两基线双改善，事前标准通过。零P1863点MAE0.179659→0.201626℃退步、154域外及最差3.566680℃保留，无状态路由；不称真实开关/可调能力。
- BL_DUAL_ZONE_01/02五产物相同；[独立核验](runs/BL_DUAL_ZONE_01/verification.json)重建23040准入标志/71428字段、显式SVD/2288预测/204指标通过。首个[最终组件v1.0](../../resource_research_results/air_conditioning/README.md)仅标准库，全部2288回放差0/9152检查，7类非法输入、域外标记与目录外构造例通过；未做桌面双击UI测试。下载/准备/拟合/核验仍留本目录。
- Crossref核到配套期刊10.1016/j.enbuild.2026.118112（8月22登记，11月卷期）及作者页，全文方法/参数未获，SSRN403后停止。这里是自定简单对照，不是论文MPC/成绩复现。原Timestamp无时区，电表平均/边界/上传未知，只条件于当前发布行可得，不认真实提前5分钟。太阳MJ/m²累计间隔未知，本模型不使用。

现用卡DC-20261016-08；[候选用途状态v2](control_candidate_status_v2.json)替代v1当前入口，v1保留为D061历史。空调整体基础包未宣告验收，下一项补控制/档位—功率独立证据并核基础覆盖，不在已见留出调参/改路由。D059—61科学记录和原三类最终包保持，不整合/高级分支/GPU/handoff/教师稿或新正式报告。

运行`run_dual_zone.py --run-id <新的唯一ID>`可复跑（NumPy/pandas、原CSV及PREP需在）；freeze/prepare/QA/verify均拒覆盖旧目录或收据。以下D061及更早为历史时点。

'''
edit('work/air_conditioning_research_20261016/README.md',lambda t:t.replace('现用决定D061','现用决定D062',1).replace('## 当前D061：事后误差分布与新候选用途核查',intro+'## 前序D061：事后误差分布与新候选用途核查',1))
for path,text in changes.items():path.write_text(text,encoding='utf-8')
print('Updated',len(changes),'existing records; final air component only, no full-resource/online/control acceptance.')
