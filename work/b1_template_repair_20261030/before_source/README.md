# B1算法源码

后续B1算法在本目录内开发。这里保留运行源码和必要依赖配置；实验、核验、日志、来源说明及历史版本放在项目根目录的 `work/`。不打包，不设双击示例，报告后置。

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
