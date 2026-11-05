# B1算法源码

这里保留运行源码和必要依赖配置；实验、核验、日志、来源说明及历史版本放在项目根目录的 `work/`。**当前研究范围、五个分点、推进顺序与质量验收以[研究点一最终框架（2026-11-04）](RESEARCH_FRAMEWORK.md)为准。** 已有整链接口见[研究点一原型说明](RESEARCH_POINT_ONE.md)，通过程序接口调用。全过程特征、结构诊断、连续作用、人群差异、敏感性与阈值已经接通，研究完成度按最终框架逐项判断；下文各日期保留当时研究状态。

**2026-10-31选型纠正：** 下文记录的“新参考＋原CPOP”是上一轮实验测量路径，由助手自行选入后续连续曲线研究，未经用户确认替换现有B1研究路线；现不将其作为已确定的正式B1方案。现有融合B1/修复模板仍是研发对象，原CPOP保留为独立主对照。新参考与任务证据模块继续保留，且公平比较时也提供给CPOP；旧参考+CPOP到新参考+CPOP的改善仅支持参考模块收益，不能证明模板改进或正式B1完成。后续是否转为基于CPOP的实质改进研究，应先明确改进内容和比较方案，再与用户决定。以下实验结果、原始决策记录及源码保持，历史“采用/优先”表述不作为当前路线授权。

## 连续激励曲线（2026-10-30）

推荐的连续入口是 `estimate_event_curve`：输入同一时长、同一请求功率下的事件结果、通知前条件、各事件事先告知的补偿单价，以及用户标识所对应的事件记录。补偿可为0.73、0.85、1.17等连续值，不需要匹配固定档位。输出任意支持金额处的平均响应与相对参考金额的增量，可用 `export_incentive_curve(result, "...png")` 保存图。

`estimate_metered_curve` 使用原始电表记录，省去参考预测和过程拟合，只估相对用电减少的作用；其绝对均值不能当作净交付比例。低层 `fit_continuous_effects` 接受已计算的事件结果值。旧 `estimate_event_effects/estimate_metered_effects` 默认保留离散AIPW，供离散数据与原对照使用；同一函数也可显式传 `dose_mode="continuous"`。连续金额不切成七档。

核心在 `effects/continuous.py`：沿用RIDE连续分支的成熟Kennedy DR伪结果＋局部线性思路，按原用户交叉拟合，结果模型使用连续样条；条件密度和其人群边缘量保持同一模型定义。金额范围、查询点和带宽可配置，不保留原包固定0—1.2网格、跨事件留一选带宽及强制单调投影。局部线性是在每个金额附近拟合，整条曲线可以弯曲、趋缓或下降。它属于通用连续DR方法适配，不宣称发明新的因果估计器。

调用示意（变量来自调用方的数据）：

```python
from b1_api import estimate_event_curve, export_incentive_curve

result = estimate_event_curve(
    event_results, X_before_notice, offered_incentive,
    dose_domain=(0.0, 2.4),
    grid=[0.0, 0.73, 0.85, 1.17, 2.4],
    incentive_unit="元/千瓦时",
    continuous_assignment=True,
    assumptions=assumptions,
)
export_incentive_curve(result, "新的输出路径.png")
```

`grid`是想查询的金额，不是训练档位；每个点直接重新计算局部估计，不依赖此前绘图的插值。可只查询一个金额，绘图至少需要两个。预测对象为当前同类任务人群的平均结果，不是逐车未来执行保证，也不是一次任务中随时间改变奖励。

输入及边界：

- `offered_incentive` 必须是事前告知的奖励标准，单位通过 `incentive_unit` 明确声明；事后结算总额不能代替它。每条曲线内计价与结算定义须一致。
- `continuous_assignment=True` 明确声明连续分配模型；唯一金额数只是数据量筛选，不能证明连续性。七档等离散设计继续用离散接口，按分取整只能在明确连续近似适用时使用。
- 新调用默认估计有界logit-normal条件密度，属于具体模型假设。已知设计接口首版只支持随机均匀分配：完整声明随机机制，并传每事件 `known_density=1/(上限-下限)`。其他已知密度设计尚未接入，不能冒充均匀分配。
- 每个查询金额检查局部事件、用户、有效样本和平衡；缺乏支持时不报告整条曲线。不允许超范围外推，不强制修成上升曲线，不截断异常权重以制造结果。
- 纯连续分配下，端点查询是单侧光滑极限。大量精确零奖励加正值连续奖励属于混合设计，本版明确拒绝这种输入；不能把零点群体直接塞进连续密度模型。
- 因果假设未确认时只返回调整后的关联；阴影仅为条件于当前拟合与带宽的用户抽样近似带，未包括平滑偏差、密度/结果模型及参考/过程的全部不确定性。没有验证真实连续因果曲线的完整覆盖率。

本轮新模拟和验收见 `../work/b1_continuous_incentive_20261030/README.md`。12次新重复×5场景，保留曲线拟合及直线、通用回归、未调整平滑的比较；负结果完整保留。全部图都标模拟，未产生现场验证或新方法普遍优势结论。

2026-10-30按用户最新要求优中选优：老师RIDE是现用算法组成，过程默认改为按计量分辨率选择。1分钟和15分钟使用老师原RIDE区间平均模板及原拟合实现；10秒使用已有比较中更好的CPOP组合。1分钟预测参考下RIDE曲线误差较低，但误检/漏检略多；15分钟仅返回依赖模板假设的区间平均曲线，物理时点与阶段参数仍未识别，原始格及原始电量保留。这是依据已有比较作出的新默认选择，数值迁移与接口检查已通过，尚未做新路由的独立主性能试验。

统一入口 `analyze_event(..., process_method="cpop")` 或 `analyze_events(..., process_method="cpop")` 可显式运行通用CPOP；`"ride_template"` 运行老师原模板，`"guarded"` 运行此前组合，`"conservative"` 保留旧保守策略。省略该参数采用上述新默认。原RIDE数值代码在 `b1_algorithm/process/_ride_identify.py` 与 `_ride_template.py`；本地适配在 `_ride_fit.py`，来源、采用理由与核验保留于 `../work/b1_ride_adoption_20261030/`。

可选接口 `from b1_api import estimate_metered_effects` 实现于 `b1_algorithm/metered_effects.py`。它直接接收完整原始电表记录，调用既有标准AIPW估计激励档位的相对用电作用，不要求参考功率预测或过程拟合。输入记录含 `task`、`starts_min`、`ends_min`、`power_kw`；另传事前条件 `X`、激励 `treatment` 和因果假设。现支持下表的EV任务和计量间隔；缺测、切格、重复物理窗口或单个坏事件整体拒绝，不隐删事件。正作用表示相对参考激励档减少了实际用电；各档绝对均值不是净交付比例、响应容量或过程特征。原 `analyze_events → estimate_event_effects` 入口继续使用。

新增接口的协议、模拟比较和独立核验放在 `../work/b1_metered_effects_20261030/`。本轮未知参考过程比较与未准入的参考校正候选放在 `../work/b1_unknown_reference_20261030/`；预测参考下组合版未稳定优于CPOP，不能沿用给定参考试验的优势结论。通知前校正降低平均误差却增加误检，未纳入正式源码或默认流程。

## 充电桩功能范围（2026-10-30）

本轮按用户确认先做单个单向交流充电资源。连续空调及其他资源适配后置。任务可省略 `resource_type` 以兼容旧输入；若显式声明，只接受 `EV`。原始负功率、超额定功率和不可能的请求保留并标记，不用它们筛掉失败记录；这不表示已经支持V2G。

| 项目 | 当前支持 |
|---|---|
| 恒定任务时长 | 按用户输入的起止时点计算正时长，计量格需完整对齐；已补测20、37、45、75、120分钟及5.5分钟细计量例 |
| 请求减载幅度 `request_kw` | 0.1—22kW，与设备最大功率分开 |
| 电表区间平均功率 | 每10秒、1分钟或15分钟一条；完整、连续、任务边界对齐 |
| 提前通知 | 15、30、60分钟 |
| 分析前窗/后窗 | 前15/30/60分钟，后15/30分钟 |
| 设备最大充电功率 | 可选；0.1—22kW，供约束诊断使用 |

电表间隔与任务时长是两件事。例如30分钟任务，可以有180条10秒记录，或30条1分钟记录。前后观察记录另计。默认方法根据实际电表间隔选择，不根据记录总条数猜测。

统一入口新增可选 `ev_config=EVAnalysisConfig(...)`，可设置最大功率、前后窗、起点/达标/恢复阈值比例、驻留秒数和模板参数上界；不必修改分析核心。批量入口支持统一配置，单条记录中的非空 `ev_config` 优先。RIDE求解方法沿用已有版本并参数化边界；其初始化仍是启发式初值。旧30分钟/1.5kW配置的数值保持已核对，不能再将当前整个参数化源码描述为原文件逐定义完全相同。

`analyze_event(..., ev_requirement=...)` 额外返回 `ev_service_recovery`。声明内容如下，时间统一使用与任务相同的绝对分钟时钟：

| 字段 | 含义 |
|---|---|
| `task_id/user_id/meter_id` | 必须与当前任务对应 |
| `power_boundary` | 必须是 `single_ev_ac_meter`，不能拿站级总电表代替单车 |
| `state_as_of_min` | 剩余需求对应的状态时点，不晚于通知 |
| `available_at_min` | 该声明何时已知，不晚于通知，也不早于状态时点 |
| `remaining_ac_kwh` | 状态时点起还需要充入的交流侧电量；不是电池SOC差 |
| `deadline_min` | 事前声明的需求截止时点，不用事后实际离站回填 |

计算只对实测功率积分。现有 `资源能力模型/03_电动汽车充电设施` 的 `prepare` 用于声明合法性检查，不调用最优计划来替代实测。设备最大功率未知时，仍可核对电量和期限。

返回 `met/unmet` 表示在完整截止窗口内，已充入电量达到/未达到声明需求；`right_censored` 表示观察结束早于期限；`unavailable` 表示缺声明、计量边界不符或时间切入电表区间；非法声明返回 `invalid_input`。服务资料缺失不阻断合法的功率分析。该结果是声明条件下的网侧电量核算，不证明电池状态，也不表示欠充由本次任务造成。功率恢复、电量差补回、需求满足分别保留。

现有参考模型的输入仍为完整1分钟记录，只用通知前可得的历史、历史均值及外部条件。EV任务时长已自由化，但旧预测模型仍限定任务相对[-120,+90]分钟的已支持窗口；长任务连同后窗超过此范围时，不能用旧模型静默外推，可使用有合法来源的外部参考。没有把1分钟预测自动细化为10秒曲线，也没有新增模型训练。新任务不能自动继承旧任务的误差半宽；校准元数据检查任务时长、请求幅度和提前量，即使匹配也只是原混合校准样本的经验结果，不保证真实反事实覆盖。

两条激励入口都要求同一组中的任务时长与请求幅度一致，按用户组织交叉拟合和不确定性计算。多种任务分别估计；同一电表同一窗口即使改了任务名或用户名也拒绝重复计入。原始净交付仍按实际格宽积分，不用拟合曲线替换。

功能检查、旧配置数值核对及构造数据联调见 `../work/b1_ev_functional_20261030/`。这轮验证程序与计算正确性；新功率/时长下的误检率、区间覆盖和相对CPOP/标准AIPW的精度优势尚未验证，现场效果也未验证。

```text
B1算法/
├── b1_api.py                  对外统一调用入口
├── requirements.txt           Python依赖
└── b1_algorithm/
    ├── api.py                 事件分析与效应计算衔接
    ├── contracts.py           输入输出与任务绑定
    ├── reference/             未调节参考功率
    ├── process/               响应过程识别与特征提取
    ├── effects/               激励效应估计
    ├── resources/             EV配置与声明电量/期限核对
    └── runtime.json           本机R运行依赖配置
```

在本目录启动Python后，可直接 `from b1_api import analyze_event, analyze_events, estimate_event_effects`。其他目录调用时，把本目录加入Python搜索路径。统一入口是供研究程序调用的接口，不是双击运行程序。

当前Python环境：`../work/ride_b1_v02_reproduction_20261029/.venv/Scripts/python.exe`。依赖见 [requirements.txt](requirements.txt)。原RIDE模板使用Python、SciPy、pandas；1分钟和15分钟默认不需要R。10秒CPOP组合及显式CPOP比较需要原生R依赖，因此保留 `b1_algorithm/process/cpop_batch.R` 与 `runtime.json`。配置路径以项目根目录为起点，运行日志写入根目录 `work/b1_runtime/`。

算法说明与来源保留于 [开发资料](../work/b1_directory_migration_20261030/documentation/b1_algorithm/README.md)，实验与验收见 [研究证据](../work/b1_formal_v1_20261029/README.md)。迁移记录及检查见 [目录整理记录](../work/b1_directory_migration_20261030/README.md)。

## EV研究点一的贯通入口（2026-10-30，步骤1—3）

现在可在同一条链上完成：历史未调用参考预测、实际任务过程分析、结构假设核查、合法事前条件调整，以及连续激励对累计减载时长或原始η的总体/分组作用分析。新增源码为 `b1_algorithm/factors.py` 和 `reference/ev_selection.py`，均通过 `b1_api.py` 导出。完整新实验与修正记录见 [本轮开发证据](../work/b1_ev_mainline_20261030/README.md)。

`EVFactorStudy` 声明研究对象、因素、激励单位、结果及假设图。默认事前因素为期限余量 `deadline_slack` 和需求紧迫度 `demand_urgency`；默认观察设计中，两者均影响激励、参加和响应。`describe_ev_study` 按声明图核查合法后门集合，参加属于激励后的中介，不放入总作用的调整条件。声明图不等于已从真实数据证明的因果结构。

```python
from b1_api import (
    EVFactorStudy, describe_ev_study,
    analyze_ev_factor_study, fit_ev_factor_curve,
)

study = EVFactorStudy("ev-duration-study", "元/千瓦时")
design = describe_ev_study(study)

# records 是已有任务/功率/绑定参考记录；factor_records 与它逐任务对应。
# 在本轮累计时长研究中显式选CPOP，避免把历史通用默认误当最优结论。
run = analyze_ev_factor_study(
    records, factor_records, study,
    process_method="cpop",
    dose_domain=(0.0, 2.4),
    grid=[0.4, 0.73, 1.17, 1.6, 2.0], reference_dose=0.4,
    assumptions=assumptions,
    continuous_assignment=True,
)
events = run["events"]
curve = run["factor_analysis"]

# 已有事件分析结果时，只运行因素侧，无需再拟合过程：
curve = fit_ev_factor_curve(
    events, factor_records, study,
    dose_domain=(0.0, 2.4), grid=[0.4, 0.73, 1.17, 2.0],
    reference_dose=0.4, assumptions=assumptions,
    continuous_assignment=True,
)
```

代码中的 `assumptions` 沿用连续接口对一致性、无干扰、事前条件、可比性和无遗漏混杂的显式声明；不能因为填了它就证明因果条件成立。未确认时返回调整关联，支持不足时拒绝整条曲线，坏事件不静默删除。

每条 `factor_records` 需要以下字段：

| 字段 | 要求 |
|---|---|
| `task_id/user_id/meter_id` | 与对应已完成事件一致；同表同窗口禁止改名重复 |
| `offered_incentive` | 事前告知的连续补偿标准，非事后结算额 |
| `deadline_slack/demand_urgency` | 本研究声明的事前数值条件；本轮模拟均为标准化量[-1,1]，实际调用需固定自己的计算与单位 |
| `treatment_set_min` | 激励实际形成时点，不晚于通知 |
| `available_at_min` | 字典，含奖励与每个条件的可得时点；条件不晚于激励形成，奖励不早于形成且不晚于通知 |
| `state_as_of_min` | 字典，含每个条件所对应的状态时点；不晚于该条件可得时点和激励形成时点 |

默认结果为 `cumulative_response_seconds`，来源 `selected_curve`：任务窗内所有减载达到0.1×请求功率的计量格累计时长；30秒驻留只约束最长连续时长。可通过新建/替换研究声明选择 `raw_observed`，或选择 `eta_raw` 加 `raw_observed`。η继续用原始有符号积分。方法、阈值、计量格、任务时长和请求幅度必须一致，不能隐式混合。

可选历史参考选择：

```python
from b1_api import select_ev_reference
chosen = select_ev_reference(model, reference_window, historical_non_event)
reference = chosen["reference"]
selection_diagnostics = chosen["selection"]
```

该接口用最近3个已完成历史非事件片段比较 `gbdt/prev10`，每个历史伪任务仅用更早的至少2段历史作为均值参照。它不使用本次响应作标签，不重新训练，不作此前未通过的通知前偏移校正。至少需5段完整对齐的1分钟历史。当前任务历史均值及来源ID必须与所传历史吻合。

每段历史必须显式包含 `source_id/user_id/meter_id/non_event/starts_min/ends_min/power_kw/available_at_min/temperature_c`，以及 `reference_context` 内的 `clock_hour/weekday/calendar_available_min/temperature_available_min`。对象必须与当前单车一致，标签须在当前通知前完成，历史环境与日历须在各自伪通知前已知。通用接口不会根据任意绝对分钟原点推算日历，也不补造历史可得性；缺失时拒绝这项选择，可另用合法来源参考。

`screen_incentive_parents` 仅在显式指定的训练用户内，对标准化logit激励作有限BIC父集筛选。它不学习完整EV图，不读结果值，也不因漏筛一项就删除声明图要求的调整条件。

本轮新模拟中，累计时长测量的CPOP明显优于RIDE模板；原始阈值时长的下游作用误差与CPOP接近，仍保留为简单对照。因此本研究调用显式使用CPOP。已有通用事件接口的1分钟RIDE默认保持兼容，不再把这一历史默认描述为所有EV过程的最优选择；整体最终路由需在步骤6用新数据独立验证。历史参考选择只略降平均误差，真无动作仍有约13%—15%误检，未校准成可靠检测器。

这轮已接通步骤1—3，完成有限模拟核验；连续阈值/敏感性与冻结查询、目标匹配的时序用途、最终独立全链比较仍是后续步骤4—6。当前没有现场验证，也没有把通用Kennedy DR称为新的效应估计器。

## 模板初始化、回补与求解修复（2026-10-30）

新增 `process_method="ride_revised"`，正式代码位于 `b1_algorithm/process/_ride_revised.py`。原 `ride_template`、原CPOP及默认路由继续保留，可复现原比较。新版目前只研究了完整1分钟计量；其他计量间隔会明确降级为原始曲线，不能当作新版拟合成功。

新版沿用原正响应模板和精确区间平均，新增释放结束后的独立等待时间，使“内部间断”和“结束后等待回补”能同时表示；初值从当前提供的实际功率差构造，没有读取模拟真值或调用CPOP。两幅度作带边界的线性求解，非线性时间参数使用固定的确定初值及零爬坡/零释放分支。每个起点记录终止状态；耗尽或失败解不进入选择，全部失败则保留诊断并明确回退到原始曲线。成功终止仍不等于全局最优或物理时点已识别。

回补上界通过 `EVAnalysisConfig.revised_rebound_bound_policy` 明确选择：

| 设置 | 行为 |
|---|---|
| `configured_ratio`（默认） | 尊重 `template_rebound_max_ratio`，不自动覆盖用户上限 |
| `declared_headroom` | 已知最大充电功率时，用最大功率减去所提供参考功率的最大值作为保守幅度界；未知最大功率时明确回退到配置比例 |

本轮新测试使用显式 `declared_headroom`，对应调用如下：

```python
events = analyze_events(
    records,
    process_method="ride_revised",
    ev_config={
        "max_charge_kw": 7.2,
        "revised_rebound_bound_policy": "declared_headroom",
    },
)
```

单条记录中非空的 `ev_config` 仍优先于批量配置，采用本设置时需同步更新记录中的配置。7.2kW是本轮模拟设备声明值，实际调用须填对应设备的已知值。该上界只是拟合幅度约束，不证明整条响应物理可行。原始η、实际电量和过程特征的计量定义均保持。

候选冻结后的8个新模拟块、2048个正/零配对事实变体中，时长MAE为修复版104.21秒、原CPOP119.56秒、旧模板280.75秒；修复版比CPOP低12.84%，达到预定综合门槛。这个优势有边界：正作用机制单独的时长改善很小，部分曲线和37分钟高噪声压力场景仍不如CPOP；本轮累计批次耗时约为CPOP的20.8倍。它不支持普遍优势或真实现场效果结论，也没有改变原始η或共享因果估计器。

开发/验证/新测试、失败起点、反例、冻结源码及合同等价复放见 [本轮研究与核验](../work/b1_template_repair_20261030/README.md)。本轮保留显式新版供继续开发，未将限定结果推广为所有任务的新默认，未生成报告或算法压缩包。

## 连续模型保存、查询与B1历史表示（2026-10-30）

步骤4新增 `effects/frozen.py`。它把既有连续DR的伪结果、样本、带宽和任务定义保存为不可变JSON；查询直接计算连续曲线，既不重新训练，也不把金额切档。模型对应拟合时的固定人群与同类任务，不能用来预测新单车的可承诺交付。

```python
from b1_api import (
    EVFactorStudy, fit_ev_factor_model, save_continuous_model,
    load_continuous_model, query_continuous_model,
    find_incentive_threshold, export_incentive_curve,
)

# events来自实际analyze_events；factor_records包含每次任务合法事前因素。
# identification_assumptions按研究依据填写，缺失时只给调整后的关联。
study = EVFactorStudy("EV30-q1.5", "元/千瓦时")
model = fit_ev_factor_model(
    events, factor_records, study,
    dose_domain=[0.0, 2.4], reference_dose=0.8,
    continuous_assignment=True,
    assumptions=identification_assumptions,
)
save_continuous_model(model, "D:/myDocu/project_postg/VPP_program/work/my_ev_model.json")

model = load_continuous_model("D:/myDocu/project_postg/VPP_program/work/my_ev_model.json")
result = query_continuous_model(model, [0.73, 0.85, 1.17])
export_incentive_curve(result, "D:/myDocu/project_postg/VPP_program/work/my_ev_curve.png")
threshold = find_incentive_threshold(
    model, target_contrast=120.0,
    search_domain=[0.4, 2.0], mesh_step=0.04,
)
```

上例范围、金额单位和“提高120秒”的目标都是本轮模拟设定，实际研究须先声明自己的范围、单位和目标。文件保存和图片导出均拒绝覆盖已有路径。

- `result["curve"]` 给出金额、平均响应和相对参考金额的增量。
- `result["sensitivity"]` 给出冻结平滑曲线的导数。默认时长结果的单位为“秒/金额单位”，不是价格弹性，也不保证处处为正。
- `threshold` 给出声明搜索范围内、指定网格分辨率下的首达点和候选格；可能返回左截断、多个上穿点、未达或支持不足。它不是最优定价，也不是连续因果阈值的置信区间。
- 条件抽样带只描述固定伪结果/带宽下的用户聚类波动，未传播平滑偏差、辅助模型、参考和过程测量的全部不确定性。声明因果假设不等于已用数据证明这些假设。
- 超出金额域直接拒绝；域内仍须通过原有局部事件数、用户数、有效样本和可比性检查。少量不同金额不自动构成合法连续分配；零奖励原子与连续正金额混合仍须另建模型。

步骤5新增 `history.py`：三次已完成的30分钟/1分钟历史整理、六维手工统计/PCA/小型AE、冻结保存和只编码查询。所有历史记录须与当前用户及电表匹配，观察端点和可得时点不晚于当前任务通知。缺历史明确返回不足；未来、异对象或坏记录拒绝。

六块新模拟没有支持把历史表示加入默认因素流程，验证选择先冻结为C0，测试不改选。当前主线继续保留事前期限与需求条件；三种历史表示作为可选研究模块，不把过去B2预测的结果代替这次B1用途验证。源码、固定选择、完整拒答及独立复核见 [步骤4—6证据入口](../work/b1_finish_ev_20261030/README.md)。

步骤6八个新独立模拟块已完成：修复版/CPOP的正零等权时长MAE为134.209/147.261秒，改善约8.86%；正作用场景差距很小，部分曲线仍较差，下游激励作用曲线尚无稳定优势。新版批耗时约18.26倍、无动作误检约14.8%，不能称为可靠现场检测器。三过程原始η与η作用完全相同。112份冻结查询与同输入Kennedy数值差0；主研究结束后的输入合同修复又经全部有效模型精确复放。此处完成的是EV限定机制下的算法流程与研究比较，不是全部资源或真实验收。

## 参考误差与任务响应证据（2026-10-31）

新增可选模块 `reference/reliable.py`、`response_evidence.py` 和 `effects/tuning.py`，继续通过 `b1_api.py` 导出。当前新模型限定完整1分钟、30分钟/1.5kW、提前15分钟通知；其他任务不能直接继承它的可靠性结论。

新参考仅使用通知前完整60分钟的四段功率及合法历史均值形状。模型训练数据是明确未发任务的非事件观测；通知后的功率不回填为事前输入。模型保存为不可变原生JSON，预测不重训。

独立非事件校准将完整任务扫描及同用户两事件相关性计入分数。输出 `evidence`（有响应证据）或 `inconclusive`（证据不足）；后者不等于确认无响应。`rank_p_value`是相对于非事件用户最大分数的秩，不是响应概率。时长和原始η均保留，因素总作用分析仍使用全部事件。

```python
import json
from b1_api import (
    ReferenceWindow, load_ev_reliable_reference_model,
    predict_ev_reliable_reference, analyze_events,
    load_ev_event_calibration, assess_ev_event_evidence,
)

# 模型与校准路径须为实际已训练/校准并与本任务匹配的产物。
model = load_ev_reliable_reference_model(reference_model_path)
reference = predict_ev_reliable_reference(model, ReferenceWindow(**reference_window))
record = dict(task=task, starts_min=starts_min, ends_min=ends_min,
              power_kw=power_kw, noise_sigma_kw=0.05, reference=reference,
              ev_config={"max_charge_kw": 7.2,
                         "revised_rebound_bound_policy": "declared_headroom"})
event = analyze_events([record], process_method="cpop")[0]
calibration = load_ev_event_calibration(event_calibration_path)
policy = json.loads(calibration.payload_json)["reference_policy_id"]
evidence = assess_ev_event_evidence(event, calibration, reference_policy_id=policy)
```

代码中的7.2kW和0.05kW为本轮模拟声明，实际应用需使用真实设备上限与噪声声明，并取得匹配的新校准。参考模型、校准和当前通知时点必须有合法先后；校准用户不能复用于独立评价。模型/流程/口径不匹配会拒绝使用。

连续配置选择先在独立验证用户上调用 `select_continuous_tuning`，保存后以 `fit_tuned_continuous_effects` 或 `fit_tuned_continuous_model` 应用。选择保留必要L/U，不用模拟真值选参，不按未知的正/零机制分别调配置；查询和绘图仍复用原冻结接口。

本轮四路径比较、弱响应代价和最终采用限制见 [新研究入口](../work/b1_reliability_20261031/README.md)。原CPOP同样使用新参考和独立校准作强对照，CPOP本身保持原样。新的参考会改变估计η；在相同参考下，过程拟合仍不改变原始积分。

最终八块新测试中，旧参考+CPOP到新参考+CPOP的无动作正时长误检为169/1024→15/1024，弱响应原始时长漏检185/690→38/690；但校准任务证据仍有414/690弱响应不确定。原CPOP在同一新参考下比模板更适合本轮弱响应测量，故研究路径显式选CPOP，兼容默认不静默改变。连续选择配置的正作用曲线均值误差73.60→49.38秒，但八块配对区间含零；零作用59.66→34.86秒且八块均改善。选参器保留可选，不能称整体稳定胜出或真实现场可靠。
# CPOP持续时间改进入口（2026-11-01）

`analyze_event`、`analyze_events` 新增 `process_method="duration_fusion"`。输入沿用原入口，参照仍需与同一任务、电表和计量格绑定。返回的原始净电量、交付比例与CPOP结构曲线保持；只更新累计响应时长和最长连续响应时长。`duration_state_curve_kw` 是判时长用的状态表达，不能拿来替代物理功率、速度或电量积分。起变、速度、达标、恢复等其余特征继续来自原版CPOP，输出 `features.sources` 说明来源。

当前模型仅支持30分钟任务、1.5kW请求、声明噪声标准差0.05kW、10秒或1分钟计量、前后各15分钟观察及默认阈值/30秒驻留。超范围明确返回不可用。旧默认入口保留，选用新版本时显式指定上述方法。

冻结后的2016条同条件模拟输入上，按采样与噪声条件等权，累计时长MAE由19.76降至17.22秒，最长连续时长MAE由43.23降至37.91秒，二者平均降低12.5%；12个种子块中10个改善。短响应位置漏检同为1次，整任务误检同为79次，没有宣称误检改善。这是已知参照的受控模拟收益，尚非未知参照或现场故障分类验证。实验与失败轮次入口：[本轮记录](../work/b1_duration_release_20261101/README.md)。

# 未知参考功率的新增入口（2026-11-01）

`analyze_event(s)(..., process_method="reference_tracked_duration")` 在原有时长提取前增加背景偏差校正：利用任务开始前15分钟的实测，估计参考功率的慢变误差。任务30分钟、请求1.5kW、原生1分钟量测、噪声声明0.05kW，前后观察各15分钟；指令执行从任务起点开始。任务期间及回补期间的量测不用于估计这段背景偏差。

这是回顾性特征提取步骤；原通知时刻参考预测与原始电量积分保留。新输出 `conditional_reference_interval_kw` 是分析时的条件背景估计。原 `duration_fusion` 入口与模型继续可用，旧默认策略不变。

独立模拟中，未知参考场景的综合时长误差由58.29降至41.07秒，降低29.55%；256个真短响应漏检仍为4个。原CPOP与LABS共享相同校正后，误差分别44.26/79.38秒。新旧公共入口均已与冻结结果核对。详见[试验记录](../work/b1_unknown_adaptation_20261101/README.md)。

# 实测状态更新（2026-11-01）

下文约30%的提升是模拟测试结果。新参考校正在真实普通交流充电背景中未通过迁移检验：11个完整窗口的正响应输出由原保留版3个增加至6个。算法与模拟记录保留供研究，当前不能称新校正已通过真实数据验证或适合作现场默认。数据来源、原件路径和逐窗结果见[真实数据验证](../work/b1_real_validation_20261101/README.md)。

# 当前第一部分主线（2026-11-01）

按用户最新确认，优先已有指令和实测的特征提取；净减载类指标先在参考已给定的条件下比较。使用已保留入口 `process_method="duration_fusion"`，不把参考预测或 `reference_tracked_duration` 作为这条路径的必经步骤。

三批已有独立已知参照模拟的时长主误差均低于原CPOP，分别改善12.46%、4.67%、16.80%；主要收益为累计与最长连续时长，误检未降，其他特征仍需逐项研究。本次没有新训模型，当前公共入口已与冻结结果重放核对。详见[已知条件效果复核](../work/b1_known_scope_review_20261101/README.md)。

# 已知条件时长与异常的后续改进（2026-11-01）

本轮第一部分采用入口为 `analyze_event(s)(..., process_method="known_response_duration")`，原 `duration_fusion` 保留可用。新版本根据整段已知量测校正累计和最长连续时长，并加入整任务变化证据；原始点与电量保留，原CPOP结构曲线仍返回。`duration_estimates` 是直接估计的时长特征，`retained_duration_support_curve_kw` 仅为旧版状态支持，二者不能冒称同一条新物理功率曲线。其余过程特征仍来自原CPOP。支持范围与上文 `duration_fusion` 一致，全局兼容默认不变，不加入参考预测。

冻结后1872条同条件模拟中，时长主误差原CPOP38.68、LABS86.77、上一保留版35.65、本版21.82秒；无动作误报89→80/168，短响应位置漏检仍为2/264。低幅压力弱子集185.13→152.75秒，但弱短响应仍漏86/121，没有新增也没有解决原有漏检；误报改善有限。新增连续弱幅度检查亦保持时长收益，没有据其调参。本轮仅支持有真值模拟结论，完整结果及开发失败保留在[试验记录](../work/b1_known_functional_20261101/README.md)。

# 当前弱短动作补检入口（2026-11-02）

第一部分新增采用入口 `analyze_event(s)(..., process_method="known_local_response")`。上一版 `known_response_duration` 保留。新分支从原始量测独立确认弱短脉冲，能够给原先零有效时长的任务补出位置与时长；原来已报正的任务维持上一版数值，原始点、电量及结构功率不改，不加入参考预测。

最终连续弱幅度模拟的165条真正短动作，旧版位置漏67条、本版59条，原CPOP66、LABS116；短动作时长主误差15.38→13.27秒。补回8条来自6基础轨迹，四个种子块都有补回。完整弱面板误报482→482，普通936条面板时长与误报保持原结果。还有59/165没找回，本次主要是小幅补检收益，不能称整体时长全面改善或现场验证成功。曾经补检更积极但多2误报的版本未采用，失败结果完整保留。

输入范围同上一版，针对安静背景中的1格至60秒弱脉冲。新输出 `localized_response_intervals_seconds`、`rescued_response_intervals_seconds`、`features.localized_response` 给出计量格位置；`localized_threshold_state`是定位状态，不能当物理功率或电量积分。旧正任务仍保留直接时长特征，两类输出来源分别标注。新旧公共/native路径已实际重放，详见[实验记录](../work/b1_local_rescue_v2_20261102/README.md)。

# 当前连续时长改进入口（2026-11-02）

新增采用入口 `analyze_event(s)(..., process_method="gap_duration_refined")`，上一版 `known_local_response` 保留。给时长估计补入连续段和停顿信息，修正累计/最长两个直接时长特征；任务判定、定位、原始点、电量和其他既有特征保持。`duration_calibration`标明校正来源，不宣称改变了物理功率曲线或起止定位。

同一批新2808条模拟，时长主误差上一版71.54→本版55.84秒，下降21.94%；原CPOP101.94、LABS157.82秒。真正长响应93.35→72.39秒；误报、整任务漏检和位置漏检逐条相同。普通与弱两个面板均改善，仍有已有漏检和误报，不称所有特征全面改善。输入范围继承已知参照30分钟/q1.5/sigma0.05、十秒或一分钟、前后15分钟默认物理口径，未展开参考预测、第二部分、报告。新旧公共native入口已重放核同，详见[诊断与实验记录](../work/b1_duration_joint_20261102/README.md)。

# 当前有效响应核验入口（2026-11-02）

新增采用入口 `analyze_event(s)(..., process_method="effective_response_refined")`，上一版 `gap_duration_refined` 保留。将实际存在弱变化与达到有效响应标准分开；对持续弱背景中少量正时长作整任务核验，原始点、物理变化证据、结构曲线、电量与η保留。`effective_verification`给出有效资格；判不达标准的任务仍是完整历史记录，不是无物理动作或故障判定，不应被直接筛出后续因素分析。

同批新2808条有真值模拟，整任务判断准确率79.56%→82.19%，误报518→444，整漏56、局部漏126、真实短动作漏85/300均旧新一致；原CPOP准确率78.95%、LABS79.02%。仍有效的任务时长不改，同批时长误差62.48→61.95秒。74个修正全部是未达有效标准的真实弱变化，物理无动作/异常误报尚未改善。阈值0.05是模型分数而非5%误报保证。适用输入范围继承上一版，全局兼容默认不改，原有方法/对照保留，详见[实验与备选方法记录](../work/b1_effective_gate_20261102/README.md)。

# 研究点一整链第一版入口

已将全过程特征、因素结构、连续补偿作用、事前人群差异、敏感性与目标阈值接通。直接使用见[研究点一使用说明](RESEARCH_POINT_ONE.md)，双击`运行研究点一.cmd`可回放本轮模拟模型并生成结果和曲线。新增原始输入运行、保存查询、两结构算法、直接导数及可选整用户重拟合均已实际核验；当前验证范围为充电资源已知参照模拟，原第一部分与连续DR保留。完整结果见[本轮记录](../work/b1_research_point1_20261103/README.md)。以下保留各历史阶段说明。

