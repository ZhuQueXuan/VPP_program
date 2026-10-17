"""Curate final recorded-step calculation and derived results, not raw series."""
from mapping_common import *
import shutil
run=BASE/'runs/CHAR_KIT_STEPS_01';prep=BASE/'runs/PREP_KIT_STEPS_01';package=ROOT/'resource_research_results/ev_charging'
assert load(run/'verification.json')['status']=='passed'
file=package/'code/recorded_step_response.py';assert not file.exists();shutil.copyfile(BASE/'recorded_step_kernel.py',file)
def save(path,obj):assert not path.exists();dump(path,obj)
for name,source in (('recorded_step_summary.json',run/'summary.json'),('recorded_step_recording_metrics.json',run/'recording_metrics.json'),
                    ('recorded_step_coverage.json',prep/'summary.json')):
    save(package/'results'/name,load(source))
features=read(run/'phase_step_features.csv')
omit={'car_battery_size','edge_index','source_file_row','edge_time_us','pre_start_index','post_end_index','status','flags'}
curated=[{k:v for k,v in r.items() if k not in omit} for r in features]
dest=package/'results/recorded_step_phase_features.csv';assert not dest.exists();table(dest,curated)
save(package/'parameters/recorded_step_definition_v1.json',{'date':'2026-10-16','definition_only':'Fixed settings described here are implemented in the code; editing this file does not change the verified algorithm.',
 'input_units':{'relative_time':'integer microseconds representing source elapsed times, not microsecond instrument accuracy','current':'A'},
 'command_conditions':{'old_and_new_min_A':6,'minimum_absolute_step_A':2,'preceding_observed_phase_median_min_A':1},
 'windows_s':{'pre':[-5,0],'post':[0,15],'steady':[10,15],'crossing_start_max':10,'crossing_confirmation_max':10.1},
 'maximum_adjacent_gap_s':.05,'minimum_persistent_crossing_s':.1,'levels':[.1,.9],
 'crossing_reference':'sign(du)*(I-I_pre_median)/abs(du), requested command step, not future measured final response',
 'missing_crossing':'null/censored, not substituted with0/10s','protocol_sha256':sha(BASE/'kit_step_protocol_v1.json'),
 'source':{'doi':'10.5281/zenodo.17866847','version':'1.0.0','license':'CC-BY-4.0','LF_sha256':'6156dc885ffd3066d5e2229c51dd49a5ceadf4e9c3c2c25adf0168d6583b2df1'}})
accept={'date':'2026-10-16','decision':'D058','release_version':'1.1.0','status':'six_basic_checks_complete_with_scope',
 'scope':'EV first basic research package: Dortmund common-command static mapping and separate KIT recorded phase-current step characteristics. No end-to-end control/capacity or full EV functionality acceptance.',
 'checks':[
  {'item':'对象与输入输出','status':'complete_with_scope','evidence':'Dortmund三指令相同→同期网侧P；KIT指令变化/相电流时间序列→记录级阶跃特征。不同场站/车辆，未拼同一实体。'},
  {'item':'特性、关系与依据','status':'complete_with_scope','evidence':'已记录连接/接受功率/需求截止/共享容量边界，来源含Scientific Data2025及KIT公开数据/作者预印本摘要；静态截顶及记录级10/90特征为自定透明方法，非全篇精确复现或标准合规测试。'},
  {'item':'数据与适用参照','status':'complete_with_scope','evidence':'原包/新KIT LF官方校验，单位/时钟/元数据/缺项按用途准入。KIT24474687行/18记录/16品牌车型组合，1875已观察完整指令变化/4928分相观察；物理时钟/网络到达未知。'},
  {'item':'正向简单组件','status':'complete_with_scope','evidence':'D057静态映射在28留出实验相对B_SET总体/AC/DC MAE/RMSE改善；D058新增已实算的记录级特征提取，不把描述性步骤冒称预测增益或端到端时延验证。'},
  {'item':'公平比较、覆盖与失败','status':'complete_with_scope','evidence':'D057仅8/15组及14/28实验双改善、最差11.524kW保留；D0589547候选变化/28641分相候选/4928准入，665未观察90%变化不补值，全部18记录/升降/相别汇总，未知原因不补造。'},
  {'item':'复现与最终计算包','status':'complete_with_scope','evidence':'D057独立算术及159003最终点回放；D05828641准入/4928特征/113866值或空值与汇总独立复算、4科研产物重跑一致。计算核/必要设置/构造例/派生结果归集，原始/清洗/拟合/核验留work。'}],
 'not_complete':['现场调度请求到设备响应的端到端时延','传感器/时钟物理标定','Dortmund官方STATE/接口枚举','全启动/停止/未载相位行为','最大可用或可承诺容量','用户需求/离站/授权/意愿与完整移时约束','V2G/站级共享约束','跨站或独立实体泛化','全体P1或103正式90%指标'],
 'next':'首轮基础研究在列明范围内收口；后续动态预测、真实控制和容量另行准入，不在已有留出调参。下一资源及跨资源整合由用户决定，handoff/教师稿不自动更新。',
 'verification':load(run/'verification.json')}
save(package/'results/basic_research_acceptance_v1_1.json',accept)
print('Final step kernel, fixed definition, derived features/aggregates and bounded acceptance collected.')
