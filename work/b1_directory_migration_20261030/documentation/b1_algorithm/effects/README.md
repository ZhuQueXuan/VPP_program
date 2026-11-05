# B1正式离散效应组件

本组件接收外部事件结果，估计相对参考档的平均结果差。正式代码只依赖NumPy和scikit-learn，不从work目录导入研究脚本。标准多档AIPW是已有通用方法，本组件不宣称新的因果估计器或真实用户精度。

## 采用与保留

| 来源或方法 | 选择 | 依据 |
| --- | --- | --- |
| RIDE多档DR及支持诊断结构 | 吸收 | 适用于非随机多档任务，分开结果预测与分配概率，明确缺乏可比样本时拒答 |
| 已验证标准AIPW/APO | 多档默认 | 原生DoubleMLAPOS逐分数核对；默认是方法合同，不表示在所有数据上误差最小 |
| 共享辅助模型的Plugin、HT-IPW | 保留对照 | 原模拟中正确二次Plugin误差更小，不能自动用复杂方法替代 |
| 随机档均值 | 条件保留 | 仅在调用者声明随机且已知概率不随X改变时作为总体因果参照；分层随机需调整 |
| 原二元饱和G1 | 保留独立入口 | 两个原生二元X、两个处理档、完整单元支持时合法；不将连续条件中位数分箱冒充原方法 |
| 用户分折、用户聚类带 | 保留并强化 | 同一原始用户全部事件入同一折，用户为不确定性单位 |
| 非单调阈值候选与拒答 | 保留 | 不自动接受单调，也不强行将多候选变成唯一位置 |
| 连续剂量、森林、Lee界、原包单调带收紧 | 不纳入本版 | 超出本轮必要范围或尚有未修推断问题 |

本轮未重新运行20种子研究以追求更好成绩。正式数值默认在一个既有3600事件冻结小例上与原得分逐项完全一致，另经DoubleMLAPOS0.11.4同辅助预测核对。来源和变更见[SOURCES.json](SOURCES.json)。

## 公开接口

```python
from b1_algorithm.effects import fit_effects, EffectConfig

result = fit_effects(
    X, treatment, outcome, users,
    levels=[0, .4, .8, 1.2, 1.6, 2, 2.4],
    task={
        "task_id": "common_task_30min_1p5kw",
        "outcome_name": "net_delivery_ratio",
        "outcome_unit": "ratio",
        "window_minutes": [0, 30],
        "q_kw": 1.5,
        "target_population": "supplied_events_equal_weight",
        "task_pre_treatment": True,
        "reference_status": "provided_estimate",
        "reference_uncertainty": "not_propagated",
    },
    # 只有研究设计确实支持时才确认以下假设；省略则仅输出标准化关联。
    assumptions={
        "pre_treatment_X": True,
        "consistent_treatment": True,
        "no_interference": True,
        "same_outcome_definition": True,
        "conditional_exchangeability": True,
        "randomized_assignment": False,
    },
    config=EffectConfig(n_boot=999, seed=0),
)
```

`outcome`必须是同一定义、任务与单位的合法结果，不能混用功率、时长、参加者条件结果。程序不能判断X是否遗漏重要混杂因素、是否实际来自通知前，也不会自动修正与激励有关的参考/过程测量偏差。假设字段是调用者有依据的声明，不能作为程序已经证明因果可识别的标记。

平均值对输入事件等权。用户事件数不等时，该目标不等于每用户等权平均；用户ID用于分折与聚类，不会自动改变权重。参考档为levels中的第一个档位，阈值目标kappa的单位与outcome一致；比例结果下默认0.1表示增加10个百分点。返回的是网格首次跨越候选，不识别档间连续阈值。

## 状态与不确定性

输出schema为`b1.effects.v1`，可直接`json.dumps(result, allow_nan=False)`。

| status | 含义 | 可用结果 |
| --- | --- | --- |
| invalid_input | 输入、任务或参数合同不成立 | 结构化code/field/detail原因 |
| unsupported | 用户/处理单元不足、拟合失败或支持/平衡筛查失败 | 具体原因及可用诊断，不报告曲线或阈值 |
| association | 支持筛查通过，但因果假设未确认 | 标准化关联点估计与对照；无因果带/阈值 |
| causal | 支持筛查通过，调用者已声明所需因果假设 | 条件于所供结果的平均作用、用户聚类同时带与阈值候选 |

`support_pass`与`causal_assumptions_confirmed`分别返回，不使用`identified=True`。已知概率本身不能证明随机分配。声明随机时必须提供真实设计概率；若未声明随机，也未确认可忽略分配，不能仅凭known_pi取得因果输出。

默认3折、二次按档Ridge(alpha=1)、多项logit(C=1)、概率截断0.01、加权SMD筛查0.2、999次用户高斯乘子、95%同时带。设置均显式返回，SMD0.2是本版固定筛查规则，不等于无隐藏混杂的证据，也不是RIDE原默认0.1。不得根据测试成绩自动放宽筛查或选超参数。

区间仅涉及用户抽样及既定辅助方法下的采样不确定性，要求原始用户簇独立、簇内事件可相关，并满足相应辅助估计和大样本条件。共享站级冲击或用户间相关不能仅靠按用户聚类处理；无干扰假设也不等于用户簇独立。`reference_process_uncertainty_propagated`始终为false。预测参考窗口半宽不能转成逐格独立噪声。本模块拒绝用参数声明已经完成未实现的全链传播。

## 二元G1保留入口

`fit_binary_saturated(X_train, treatment, outcome, users_train, X_target, users_target, ...)`接受恰好两个0/1事前条件和两个处理档。训练与目标用户分离，以目标事件条件占比汇总完整四格的档内差，默认每格每档至少20个训练样本。任意单元不足则整体unsupported，不丢格后归一，也不对连续变量自动分箱。该兼容入口仅给点估计，不声称新增置信区间。

## 核验

必要核验代码位于`work/b1_formal_v1_20261029/effects/verify_formal_effects.py`，正式库运行不依赖它。覆盖状态语义、非有限/布尔/字符串/缺失ID、known_pi、正则化和重抽配置、稀疏单元、legacy二元域、同用户分折、非单调集合，以及独立得分和聚类SE。正式默认与既有冻结得分最大差0，原生DoubleML作用最大差约1.39×10⁻¹⁵；未使用其iid标准误冒充用户聚类推断。
