# B1首轮研究入口

2026-10-21接续D107：[恢复不确定性与图学习汇总](../b1_recovery_uncertainty_20261021/本轮汇总与接续.md)。新面板/独立小图另冻协议，本目录科学代码和旧结果不回写；G2降对照保持。下一转多档激励的非线性/阈值/敏感性设计。

**状态：独立评估及首个冻结模拟工作包完成；B1整体未完成。** 依据本对话用户授权自主确定局部方案并研究，非全局待审主稿获批。

先读[结果与下一步](首轮研究结果与后续路线.md)，需要审查方案时读[独立评估](独立评估与实施裁决.md)，具体参数与时点见[实施协议](实施协议.md)、[protocol.json](protocol.json)。

本轮：F0观测特征和反例核查；F1精确分段开发核查；四场景×20重复的透明回归/直接标准化/正交AIPW平均作用比较。G2没有显示增量，降为对照；能量恢复精确零判据受噪声影响，下一轮先处理观测不确定性。图学习、激励阈值、深度时序表示及其他机制仍待独立研究。

## 文件与复核

| 内容 | 文件 |
| --- | --- |
| 原始模拟观测 | ../../data/驱动因素解耦模拟数据集_B1_v1_20261021/main_observations.npz |
| 主实现 | simulation.py、estimators.py、run_research.py、evaluate.py |
| 特征与微型反例 | features.py、feature_checks.py/json、feature_segmentation.py、development_protocol.json、segmentation_development.json |
| 观测及因素结果 | observed_panel_features.json、predictions.npz、metrics.csv、evaluation.json |
| 隐藏评价材料 | truth.npz、evaluator_curves.npz；不作训练输入 |
| 模型与收据 | models/、fit_diagnostics.json、micro_checks.json、generation_checks.json、fit_receipt.json、run_receipt.json |
| 独立复核 | verify_research.py、independent_verification.json、verification_recomputed_metrics.csv |
| 边界/目录检查 | contract_checks.py/json、published_identity_check.json |
| 失败/版本身份 | failures.md、source_freeze_before_evaluation.json |

这是研究代码，不提供双击CMD或平台页面。现有收据已覆盖实际运行；需要复查现有产物，可在项目根运行`python work/b1_research_20261021/verify_research.py`（覆盖同一复核报告，科学结果不变）。`feature_checks.py`和`feature_segmentation.py`只复算开发检查。主流程是micro→generate→fit→evaluate，已有truth后fit会主动拒绝；扩展研究应新冻协议和评价，不覆盖本轮测试追分。

函数：features.extract接受n+1个时间边界与n个功率，返回观测特征/状态；estimators.EffectStudy.fit只读事实事前字段、处理和观测结果，effect(new_X)是训练结果模型差，主要G2平均作用还需已观测事件的AIPW分数。它不等于已训练独立CATE模型。

当前仅适用于声明模拟研究，不支持真实EV心理、现场恢复/承诺容量、G2阶段门或103正式90%验收。原模型和四算法主稿位置保持。
