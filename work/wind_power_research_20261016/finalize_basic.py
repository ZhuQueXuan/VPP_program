"""Add verified description and bounded six-item review; runtime unchanged."""
from common import *
import shutil
dest=ROOT/'resource_research_results/wind_power';out=BASE/'runs/PACKAGE_WIND_V1_1_01';out.mkdir(exist_ok=False)
old=load(dest/'results/release_validation.json')
for n,h in old['verified_files'].items():assert sha(dest/n)==h,(n,h)
shutil.copy2(dest/'README.md',out/'README_v1_0.md')
description=load(BASE/'runs/VERIFY_CHAR_CURVE_01/receipt.json');assert description['status']=='passed'
for n in ['observed_characteristics.json','power_curve_bins.json','power_curves.png','power_curves.svg']:
    shutil.copy2(BASE/'runs/CHAR_CURVE_01'/n,dest/'results'/n)
shutil.copy2(BASE/'characteristic_protocol_v1.json',dest/'results/characteristic_protocol_v1.json')
review={'decision':'D066','version':'1.1.0','date':'2026-10-16','status':'bounded_pass',
 'scope':'First wind basic package: original six-unit published wind/power characteristics and fixed SAME-ROW mixed-operation statistical power curve. Not full wind resource capability.',
 'criteria':[
 {'id':1,'passed':True,'evidence':'Original six MM92 units, wind m/s input, contemporaneous published10min activePower kW output, sourceUTC labels and no online/future claim defined. Fixed train/test months.'},
 {'id':2,'passed':True,'evidence':'Full six-panel/all-test observations and all280training knots; source static/nameplate, curve formula and support/range flags documented; turbine source and method paper distinct. No importing manufacturer thresholds.'},
 {'id':3,'passed':True,'evidence':'Original official2018 archive MD5/CRC/static/mapping and315360raw rows checked. Published measuredPower is appropriate target for bounded same-row problem. Event/state/independent physical calibration and availability truth gaps disclosed, not needed to claim those unvalidated uses.'},
 {'id':4,'passed':True,'evidence':'Frozen original protocol passed lowerMAE+RMSE than BOTH linear/cubic baselines pooled,each6units,positiveP and3of3heldoutmonths. No post-score tuning.'},
 {'id':5,'passed':True,'evidence':'All admitted negatives,over-nominal,rare-bin groups,worst and allmonths retained.81rarebins errors high,0out-of-trainingwind observations null. No inference of cause or healthy curve. Descriptive high-wind irregularity remains.'},
 {'id':6,'passed':True,'evidence':'Source/sample/algebra/all69236predictions/180metrics independent checks,5science-file exact rerun and final69236replay;9invalid/298constructedboundaries/twooutside-cwdexamples; independent303865pairs/1678description checks and3science-file exact rerun. Final stdlib code/parameters unchanged.'}],
 'checks_passed':6,'bounded_basic_package_complete':True,'runtime_or_parameters_changed':False,'new_fit':0,'new_independent_forecast_points':0,
 'not_validated':['healthy/certified manufacturer curve or physical cutin/cutout/Cp','independent available/adjustable wind capacity','causal or commanded response/physical ramp/latency','future wind forecast/online lead time','new sites/devices/full-year holdout','wholeP1 or10390percent'],
 'next':'Stop first wind basic stage. Sixth resource or specialised work selected by user. No automatic integration/advanced branch.'}
dump(dest/'results/basic_research_acceptance_v1_1.json',review)
dump(dest/'results/evidence_summary_v1_1.json',{'decision':'D066','version':'1.1.0','bounded_basic_package_complete':True,
 'new_fit':0,'new_predictions':0,'same_original_test_rows':69236,'all_year_admitted_description_rows':303987,
 'adjacent_600s_pairs':303865,'all_six_turbines_plotted':True,'all_test_observations_plotted':69236,
 'independent_description':description,'prior_runtime_verification':{'rows':old['test_rows_replayed'],'maximum_difference_kW':old['maximum_replay_difference_kW'],'receipt_sha256':sha(dest/'results/release_validation.json')},
 'same_source_not_independent_physical_validation':True})
f=dest/'README.md';s=f.read_text(encoding='utf-8')
assert s.count('# 风电首个有限成果：同期风速—功率统计曲线 v1.0')==1
s=s.replace('# 风电首个有限成果：同期风速—功率统计曲线 v1.0','# 风电首轮基础成果：运行特征与同期功率曲线 v1.1',1)
s=s.replace('2026-10-16，D065。已通过固定比较、原始数据独立复算和最终代码回放；**风电整体基础包仍在研究中**，尚未进行六项完整基础审查。','2026-10-16，D066。首轮基础包已按原定六项标准在“原六机组发布运行特征＋混合观察条件同期功率曲线”范围内有限收口。D065固定比较、参数、最终代码和成绩保持；新增完整曲线、回顾特征与六项审查，不是新增预测盲测。完整可调能力仍需专项。',1)
s=s.replace('## 文件与后续边界','''## 完整曲线与运行特征

![全部六台机组、全部评价记录与固定训练曲线](results/power_curves.png)

灰点为全部69236条留出观测，蓝线为原280训练节点形成的固定曲线，六面板坐标统一，负值与超名义额定值保留。高风速段存在明显起伏，反映当前统计样本的混合状态及局部支持情况；不能由这些起伏认定真实切出风速或制造商特性，也没有为了图形平滑修改曲线。SVG与PNG从同一张图导出，PNG已目检，SVG未另行渲染。

完整303987条准入记录的分布、正负功率计数，以及303865组原序连续600秒相邻对已汇总。相邻功率差只是两条十分钟均值的变化，不能当物理瞬时爬坡率、指令响应速度或可承诺容量。所有非空训练/评价风速箱均保存，评价箱均值只作描述，从未替换原训练节点。特征核验以独立标准库有序分位数与pandas/NumPy对照，1678项数值检查通过；描述/分箱/最差上下文三项产物复跑一致。

六项有限审查覆盖对象与输出、曲线公式和依据、原件与适用参照、固定正向组件、完整对照和失败边界、复算及可运行代码。控制或容量真值仍是后续相应用途的准入要求，本次没有用基础验收替代这些验证。

## 文件与后续边界''',1)
s=s.replace('- `results/evidence_summary.json`、`release_validation.json`：独立复算与发布核验范围。','- `results/evidence_summary_v1_1.json`、`release_validation_v1_1.json`：现用描述/复算与发布核验范围；`basic_research_acceptance_v1_1.json`为六项有限审查。\n- `results/observed_characteristics.json`、`power_curve_bins.json`、`power_curves.png/svg`：全机组描述、全部非空箱及图。\n- `results/evidence_summary.json`和`release_validation.json`为D065首组件v1.0历史；对应旧README快照保存在work的PACKAGE_WIND_V1_1_01目录，旧收据不用于声称现用README身份。',1)
s=s.replace('下一项是补全各机组运行特征与功率曲线证据，核查状态边界，再按既定六项标准审查风电基础包。','本轮基础阶段到此停止新增实验。下一类资源或专项由用户决定；当前五类基础包各有有限范围，至少六类目标还需一类，不自动启动第六类。',1)
f.write_text(s,encoding='utf-8')
unchanged=['code/wind_curve.py','parameters/kelmarsh_mixed_curve_v1.json','examples/constructed_inputs.json','run_example.py','运行示例.cmd','source_manifest.json','results/validation_metrics.json','results/diagnostics_summary.json','results/frozen_protocol.json']
for name in unchanged:assert sha(dest/name)==old['verified_files'][name]
release={'date':'2026-10-16','decision':'D066','version':'1.1.0','status':'passed','bounded_basic_package_complete':True,
 'scope':review['scope'],'checks_passed':6,'new_fit':0,'new_independent_forecast_points':0,
 'original_code_parameters_examples_metrics_unchanged':{n:sha(dest/n) for n in unchanged},
 'original_runtime_replay_rows':69236,'original_runtime_replay_difference_kW':0.,
 'original_invalid_boundary_and_example_verification_reused_by_exact_fingerprint':True,
 'previous_release_receipt_sha256':sha(dest/'results/release_validation.json'),
 'previous_README_snapshot_path':str((out/'README_v1_0.md').relative_to(ROOT)).replace('\\','/'),'previous_README_sha256':sha(out/'README_v1_0.md'),
 'description_verification_sha256':sha(BASE/'runs/VERIFY_CHAR_CURVE_01/receipt.json'),
 'independent_description_numeric_checks':1678,'all_original_adjacent_pairs_checked':303865,
 'all_test_plot_source_rows_checked':69236,'PNG_visually_reviewed':True,'SVG_separately_rendered':False,
 'cmd_launcher_interactively_double_clicked':False,'P1_or_103_passed':False,
 'verified_files':{str(f.relative_to(dest)).replace('\\','/'):sha(f) for f in sorted(dest.rglob('*')) if f.is_file() and f.name!='release_validation_v1_1.json'}}
dump(dest/'results/release_validation_v1_1.json',release);dump(out/'receipt.json',release)
print(json.dumps({'status':'bounded_basic_stage_complete','version':'1.1.0','checks_passed':6,'verified_files':len(release['verified_files']),'runtime_changed':False,'new_fit':0},indent=2))
