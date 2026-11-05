# 正式效应组件的实现与核验

本目录仅保存正式代码的选择依据、必要小例和核验收据，不是研究报告。运行库位于`b1_algorithm/effects/`，无work运行依赖。

- [代码取舍与使用说明](../../../b1_algorithm/effects/README.md)
- [来源与变更身份](../../../b1_algorithm/effects/SOURCES.json)
- [核验脚本](verify_formal_effects.py)
- [21组核验收据](verification_receipt.json)
- [公开JSON结果样例](causal_example.json)
- [首次核验日志](verification.log)、[数值域修正后核验日志](verification_after_scalar_fix.log)

核验结果：因果输出要求支持通过与调用者假设声明同时成立；未知假设只输出标准化关联，支持失败不报告结果。9类坏数据、12项配置、超出float64的请求量/正则化数值、known_pi、随机均值合法性、完整legacy二元域、非单调候选、用户分折与聚类算术均通过。正式默认在原先保存的一个3600事件小例上与冻结得分逐项差0，原生DoubleMLAPOS0.11.4作用差1.39×10⁻¹⁵。该核验没有重跑20种子研究或选方法追分。

平均目标为输入事件等权，区间条件于外部所供结果，不宣称参考/过程全链误差已传递。程序无法验证无遗漏混杂，输出中的causal_assumptions_confirmed仅记录调用者完整声明。
