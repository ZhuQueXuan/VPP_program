"""Publish aggregate evidence only; raw/diagnostic scripts stay in work."""
from crossseason_common import *
P=frozen();run=BASE/'runs/BL_CROSSSEASON_01';prep=BASE/'runs/PREP_CROSSSEASON_02'
DEST=ROOT/'resource_research_results/distributed_photovoltaic/results'
assert json.loads((run/'verification.json').read_text())['status']=='passed'
def publish(name,obj):
    file=DEST/name;assert not file.exists();dump(file,obj)
def publish_table(name,rows):
    file=DEST/name;assert not file.exists();table(file,rows)
summary=json.loads((run/'summary.json').read_text())
summary['interpretation']='Predeclared relative test passed on observed published records only. Four months have power limited to 0/20W, so healthy all-season generation prediction remains unverified.'
publish('crossseason_forecast_summary.json',summary)
publish('crossseason_forecast_bins.json',json.loads((run/'metrics.json').read_text()))
publish_table('crossseason_forecast_group_metrics.csv',[r for r in read(run/'group_metrics.csv') if r['group_type']!='date'])
publish('crossseason_coverage.json',json.loads((prep/'coverage.json').read_text()))
publish_table('crossseason_source_profile.csv',read(run/'source_monthly_profile.csv'))
acceptance={'date':'2026-10-16','release_version':'1.2.0','decision':'D055',
 'stage':'分布式光伏基础研究、固定组件比较与复现归集阶段',
 'decision_text':'六项基础研究检查在列明范围内完成，保留组件DC重建与条件离线下一标签预测代码；停止本轮模型/月份搜索。不是完整健康场站跨季节或调控验收。',
 'checks':[
  {'item':'对象及输入输出','status':'complete_with_scope','evidence':'IEA匿名单晶硅组件同期G/T→DC Pmax；独立PVDAQ1239当前功率/时间/几何→下一发布标签AC；不是同一设备。'},
  {'item':'特性、公式与参数依据','status':'complete_with_scope','evidence':'IEA/SUPSI实验室P0/gamma，PVWatts型DC关系；NREL晴空持续基线家族，pvlib0.16.1 SPA/Ineichen/isotropic；没有完整论文精确复现或参数泛化声明。'},
  {'item':'数据、参照及边界','status':'complete_with_scope','evidence':'组件12月34751主样本/34763全有限；预测新8月2931，预选后续9月26304目标/23286共同样本。10月23天缺；DST歧义排除。发布值不是可用容量真值。'},
  {'item':'正向简单组件','status':'complete_with_scope','evidence':'DC MAE15.447978→7.575081W、RMSE23.551939→17.047254W；新8月及本轮固定跨季节观察组相对持续双指标改善，0新增功率拟合。'},
  {'item':'公平比较、失败及覆盖','status':'complete_with_scope','evidence':'同样本双指标；旧AC重建/AR2失败保留，DC冬季退步；本轮5/9月及91/251日双改善，4月段仅0/20W，最差/低出力/事后变化分箱全报；不定义103精度。'},
  {'item':'复现、最终代码及接续','status':'complete_with_scope','evidence':'本轮252原CSV指纹、26304样本独立时区重建、23286逐点核、7209指标及5产物复跑一致；最终代码未变，必要参数/构造样例/聚合结果可复用。'}],
 'retained_capabilities':[
  {'component':'dc_power.py','use':'已知适用组件P0/gamma与同期POA/背温时计算条件DC功率','unsupported':'其他组件直接沿用参数、整站AC或未来天气预测'},
  {'component':'clear_sky_forecast.py','use':'当前记录完整可得、几何适用及时间语义假设下的离线下一15分钟发布标签基线','unsupported':'健康场站全年正常发电、真实在线提前量、可承诺出力或调度指令'}],
 'not_validated':['独立健康场站及气候迁移','四个0/20W月份的设备/计量状态及机制','实际平均区间与上传时刻','完整逆变器/电站AC物理模型','最大可用/可调容量、控制时延及授权','多类资源整合','103正式90%精度'],
 'source_evidence':{'protocol_sha256':sha(BASE/'crossseason_protocol_v1.json'),'admission_sha256':sha(prep/'admission.json'),
  'verification':json.loads((run/'verification.json').read_text())},
 'next':'达到用户要求的大阶段节点后停止；下一类型由用户决定，跨资源整合仍待用户明确授权。教师稿及handoff不更新。'}
publish('basic_research_acceptance.json',acceptance)
print('Published six aggregate result files; compute code, parameters and earlier results unchanged.')
