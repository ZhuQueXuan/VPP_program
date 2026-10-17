"""D046 six-item review: bounded first basic package, no new model or gate."""
from common import *
import shutil
pkg=ROOT/'resource_research_results/air_conditioning';original=load(pkg/'results/release_validation_v1_0.json')
assert all(sha(pkg/n)==h for n,h in original['verified_files'].items())
v=load(BASE/'runs/CHAR_AIR_01/verification.json');assert v['status']=='passed'
model=load(BASE/'runs/BL_DUAL_ZONE_01/summary.json');assert model['predeclared_relative_success']
backup=BASE/'runs/PACKAGE_AIR_V1_1_01';backup.mkdir(exist_ok=False)
shutil.copyfile(pkg/'README.md',backup/'README_v1_0.md');assert sha(backup/'README_v1_0.md')==original['verified_files']['README.md']
for src,dst in [(BASE/'runs/CHAR_AIR_01/characteristics.json',pkg/'results/characteristic_summary_v1_1.json'),(BASE/'runs/AIR_CURVES_01/test_temperature_curves.png',pkg/'results/test_temperature_curves_v1_1.png'),(BASE/'runs/AIR_CURVES_01/test_temperature_curves.svg',pkg/'results/test_temperature_curves_v1_1.svg')]:
    assert not dst.exists();shutil.copyfile(src,dst)
items=[
 {'id':1,'criterion':'固定对象、输入输出和时域','passed_in_scope':True,'evidence':['README.md','source_manifest.json','parameters/dual_zone_temperature_v1.json'],'finding':'Original2room test bed, current/previous5min roomT,current outsideT/current same-room publishedW/current other-roomT -> next published5min roomT. Conditional current-row availability only; same object parameters,not arbitrary devices.'},
 {'id':2,'criterion':'曲线、主公式、参数与约束依据','passed_in_scope':True,'evidence':['results/characteristic_summary_v1_1.json','results/test_temperature_curves_v1_1.svg','parameters/dual_zone_temperature_v1.json','README.md'],'finding':'All8days*2rooms original-value and287within-file neighbouring-pair summaries; all4testdays*2rooms curves, no smoothing/best-case selection. Fixed5term temperature-increment formula,10training-only coefficients/ranges,300s source windows,finite inputs. Heat balance/temperature memory motivates statistical baseline; no identifiedR/C/COP or physical capacity constraints claimed.'},
 {'id':3,'criterion':'实际数据和适合该输出的参照','passed_in_scope':True,'evidence':['source_manifest.json','results/evidence_summary.json'],'finding':'8originalCSV,2304time rows,publisherSHA256/size match; indoor temperature observed by source sensors and source-reported smart-meterW. Actual next temperature labels valid for conditional offline comparison, not truth for commands/comfort/capacity. Raw clock naive and data-availability timing unknown.'},
 {'id':4,'criterion':'至少一个有正向证据的简单组件','passed_in_scope':True,'evidence':['code/room_temperature.py','results/validation_metrics.json'],'finding':'D062frozen gate unchanged; first4days train2288/later4days test2288. M_HEAT5beats BOTH persistence and trend MAE/RMSE pooled,each2rooms,positiveP425points,and4/4days. No new fitting or prediction experiment inD063.'},
 {'id':5,'criterion':'公平对照、误差、覆盖、最差及失败','passed_in_scope':True,'evidence':['results/validation_metrics.json','results/evidence_summary.json','README.md'],'finding':'ZeroP1863rows MAE worsens thoughRMSEimproves;154outside-training-range rows retained;overall worst3.566679918C,day8worst exceeds persistence. D059PLEIA ARX andD060HILpower mapping failed gates, kept as failures,not included as usable models. Every held-out room/day visible, no state route/threshold changes.'},
 {'id':6,'criterion':'固定版本复现、适用范围与后续接口','passed_in_scope':True,'evidence':['results/release_validation_v1_0.json','code/room_temperature.py','examples/constructed_inputs.json','run_example.py','README.md'],'finding':'Five scientific artifacts deterministic; independent raw/window/SVD2288forecasts/204metrics passed. Original final2288row replay0difference,7invalid cases rejected and outside-directory constructed example executed; exact runtime/coefficients unchanged. New descriptive4592pairs/2304curve labels/2288target-time predictions independently checked. No cross-resource integration/interface assumed.'}
]
acceptance={'date':'2026-10-16','decision':'D063','version':'1.1.0','status':'limited_basic_package_complete','scope':'First air-conditioning basic package: observed operation characteristics and conditional next5min temperature-label predictor of original2experimental rooms, plus fair failed alternatives. Resource-wide capabilities/real control or capacity are not complete.',
 'criterion_basis':'Existing ROADMAP D046 six bounded basic criteria, unchanged. No new or relaxed prediction gate. Measurements required depend on declared output; delivered command/comfort truth needed for those later outputs,not substituted by temperature-prediction validation.',
 'six_checks':items,'model_and_gate_unchanged':True,'new_fitted_parameters':0,'new_forecast_validation_points':0,'new_observational_description_only':True,
 'mandatory_for_this_scope':{'object_input_output_horizon':True,'temperature_truth_and_source_identity':True,'pre_frozen_fair_baselines_and_holdout':True,'positive_component':True,'failure_coverage_and_full_reproduction':True},
 'deferred_research_tasks_not_removed':['Original power aggregation/publication timing and true online lead time','Actual delivered control/stage/actuation and physical sensor-clock calibration','PhysicalR/C/COPidentification and robust power conversion','Comfort constraints,occupancy,user authorisation/willingness and available/firm capacity','Device/site/season generalisation and source-conditioned negative results','Cross-resource integration and all further formal tasks'],
 'not_claimed':['Independent physical test or new blind test from retrospective curves','Command success,latency,actual compressor on/off from reported zero/positiveP','Energy integration/real on-duration or counterfactual load shedding','Exact full-paper MPC reproduction/peak or cost gains','All-typeP1or10390percent acceptance'],
 'SHIFDR':{'purpose':'Candidate independent control/power evidence only','raw_data_or_readme_obtained':False,'admitted':False,'source_subset_doi':'10.7302/vmwh-ek70','metadata_findings':'Official subset description says fanpower computed from current;2021BAS interpolated1min. Need actual measurement/calculation dictionary,reference time and licence before use.','access':'Collection earlier403; exact subset and author publication page each403,stopped. DataCiteandCrossref registry obtained,not full paper or raw files.','license':'DataCite rightsList empty; ORNL ODbL not inherited into unopened subset.'},
 'source_protocol_sha256':sha(BASE/'dual_zone_protocol_v1.json'),'descriptive_protocol_sha256':sha(BASE/'air_characteristic_protocol_v1.json'),'independent_description_verification_sha256':sha(BASE/'runs/CHAR_AIR_01/verification.json'),'all_type_P1_passed':False,'formal103_passed':False,
 'next':'Stop this bounded basic-resource stage. Next resource or specialised capability study chosen with user; no automatic new type,integration,advanced methods,handoff or report.'}
ap=pkg/'results/basic_research_acceptance_v1_1.json';assert not ap.exists();dump(ap,acceptance)
readme=(pkg/'README.md').read_text(encoding='utf-8')
readme=readme.replace('# 空调研究成果 v1.0：首个有限室温预测组件','# 空调研究成果 v1.1：首轮基础包有限收口',1)
readme=readme.replace('日期：2026-10-16；D062。','日期：2026-10-16；现用D063，预测代码/参数保持D062 v1.0。',1)
readme=readme.replace('尚未宣布空调整体基础包验收，不用于计算可调容量或下达控制。','本轮基础研究按既定六项标准在上述范围内收口；完整空调调节能力、可调容量及真实控制未验证。',1)
section='''## 本轮完成范围与曲线

[六项有限验收](results/basic_research_acceptance_v1_1.json)确认对象/输入输出、曲线公式参数、按用途参照、正向简单组件、公平失败/覆盖及固定复现均有证据。验收覆盖原双区试验的发布值特征和条件室温预测，控制时延、舒适授权和可用容量仍是后续专项，没有从正式研究任务删除。此处“完成”不表示任意空调设备或全部功能可用。

[完整曲线PNG](results/test_temperature_curves_v1_1.png)与[可编辑SVG](results/test_temperature_curves_v1_1.svg)展示全部4评价日×2房间。蓝线为原室温，黑虚线为固定模型预测（按目标时刻对齐），灰色为该房间原发布W；原2304房间温度/功率标签及2288预测全部核对，没有挑最好片段、平滑或拟合新模型。图是回顾展示，不构成新增独立验证；SVG保留矢量和文字，PNG已目检，SVG未另行浏览器渲染。

[特征摘要](results/characteristic_summary_v1_1.json)包含8天×2房间共4608标签及4592组原相邻5分钟温差。发布正功率931、零功率3677；相邻零→正480、正→零480、正→正451、零→零3181。它们是原读数模式，不能当作480次真实启动/停止或控制成功；温差除以5分钟是观察变化率，不是控制后的因果冷却速度。未按不明计量区间积分电量或推物理开机时长。

v1.1只新增上述特征/图和六项验收，预测公式、10系数、输入范围、原2288评价成绩及失败不改。现用发布收据为[release_validation_v1_1.json](results/release_validation_v1_1.json)；v1.0发布收据和D062的evidence_summary.json保留为历史时点，后者“整体未宣告验收”由本次限定验收替代，其他未验能力不变。

'''
readme=readme.replace('双击`运行示例.cmd`',section+'双击`运行示例.cmd`',1)
readme=readme.replace('最终代码对所有2288点回放及目录外构造例结果以[发布核验](results/release_validation_v1_0.json)为准。','原最终代码对所有2288点回放及目录外构造例见[v1.0回放](results/release_validation_v1_0.json)；代码/参数指纹不变与新增证据以[现用v1.1发布核验](results/release_validation_v1_1.json)为准。',1)
(pkg/'README.md').write_text(readme,encoding='utf-8')
dump(backup/'receipt.json',{'status':'curated_pending_release_audit','old_README_sha256':sha(backup/'README_v1_0.md'),'old_release_receipt_sha256':sha(pkg/'results/release_validation_v1_0.json'),'new_acceptance_sha256':sha(ap),'no_model_or_gate_change':True})
print('Curated v1.1 retrospective characteristics/allheldoutcurves and six-item bounded review; final audit pending.')
