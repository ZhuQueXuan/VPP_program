from pathlib import Path
import json, hashlib, shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
old=json.loads((ROOT/'work/b1_continuous_dml_pilot_20261103/freeze.json').read_text(encoding='utf-8'))['files']
formal={p:h for p,h in old.items() if p.startswith('B1算法/')}
for p,h in formal.items():
    assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
for name in ['B1算法/b1_algorithm/factors.py','B1算法/b1_api.py','B1算法/requirements.txt','B1算法/README.md']:
    target=HERE/'production_before'/name
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as f:f.write((ROOT/name).read_bytes())
with (HERE/'production_before.json').open('x',encoding='utf-8') as f:json.dump(formal,f,ensure_ascii=False,indent=2)
protocol=dict(
    objective='可运行的研究点一：原始任务特征→因素结构→连续总作用/事前人群差异→直接边际作用→目标交点及区间',
    baseline='保留现Kennedy连续DR，第一部分effective_response_refined不改',
    development=dict(seeds=[90331001,90331002],mechanisms=['randomized','observed_confounding','zero_effect'],users=180,events=2),
    final=dict(seeds=[90332001,90332002,90332003,90332004],mechanisms=['randomized','observed_confounding','zero_effect','nonmonotone'],users=180,events=2),
    latent_stress=dict(seed=90333001,users=180,events=2,mechanism='hidden_confounding',claim='结构歧义与观测调整偏差，仅研究诊断，不称已识别真实作用'),
    physical=dict(seed=90334001,users=120,events=2,mechanism='observed_confounding',recipe='先连续补偿/状态→是否响应和格数→10s实际功率，30min/q1.5/known3kW/sigma.05；全部240事件原生公共API不筛'),
    variables=['deadline_slack','demand_urgency','negative_control','offered_incentive','cumulative_response_seconds'],
    domain=[0.,2.4],query_grid=[round(.4+i*.1,10) for i in range(17)],reference=.4,
    outcome='全人群累计有效时长秒，含0及满时长；真实函数独立积分，仅评价器可读',
    amounts='连续生成和任意实数直接查询，不分档后插值',
    derivative='Eq8 Epanechnikov，原splineRidge/GPS/user3fold；现Gaussian导数及共享紧支撑局部多项式控制',
    primary=['continuous_contrast_RMSE_seconds','derivative_RMSE_seconds_per_amount','output_coverage'],
    secondary=['L预定负/非负组补偿作用差异RMSE','target120s首次/多上穿误差和未达','zero_effect条件带误识别','graph骨架及负控假邻接/未定端点'],
    target_seconds=120.,graph='FCI+KCI/PCstable+KCI；每user首事件最多120user，固定seed子抽，与全量效果输出分母分开；无强BK',
    selection='开发只选导数展示默认：预定直接导数相对现有导数RMSE至少5%且覆盖不损失才可代默认；否则两者并列且保留旧默认。阈值偏差修正仅可选，今日不声称完整TW重拟合覆盖理论。',
    no_test_tuning=True,no_old_test_reuse=True,main_source_freeze='实现完成、首个终验生成前另存source_freeze.json',
    independence='同user各事件同fold；同seed不同机制为配对，不冒称独立重复。最终只有4独立随机块。',
)
with (HERE/'protocol.json').open('x',encoding='utf-8') as f:json.dump(protocol,f,ensure_ascii=False,indent=2)
print('Protocol saved; preserved',len(formal),'formal identities')
