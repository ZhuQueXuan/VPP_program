# 新候选筛选依据

2026-11-05，候选开发结果产生前的总管主源筛查。目的为决定是否有值得验证的新假设，不证明任何方法本任务更优。

| 主源 | 对当前问题的判断 |
| --- | --- |
| Zhang、Kong、Yang，*Towards R-learner with Continuous Treatments*，2022首稿、2025-04-17 v3，[原论文](https://arxiv.org/abs/2208.00872)、[作者库](https://github.com/yichistat/Continuous-treatment-R-learner) | 与相对固定补偿的条件增量目标相符；函数正则化和末端参照变换给出新的可比较路线。保留唯一候选，小容量独立实现，不称完整复现或本任务已验证更优。 |
| Lundberg、Brand，2026，*Causal Inference with a Continuous Treatment: Addressing Positivity Constraints, Nonlinearity, and Effect Heterogeneity*，[正式论文](https://journals.sagepub.com/doi/10.1177/00811750261459364) | 在价格支持不足时，转向每个对象原有处理量上的加性位移有价值，但会改变“固定0.4参照补偿的曲线”问题。不能拿目标更换当作同目标误差改进，本轮不采用。 |
| Doss，2025预印本，*Doubly robust pointwise confidence intervals for a monotonic continuous treatment effect curve*，[作者预印本](https://arxiv.org/abs/2508.08415) | 针对单调曲线的点区间，所需单调性尚未由充电数据建立，且主要解决区间而非当前分组增量稳定性。本轮不以强制单调来压低误差。 |

此前已比较的连续DML、两部结构、样条和组合不因换术语而重新列为新方法。2026论文不自动优于2025修订；本轮选择依据是问题、假设和可执行比较的匹配程度。仍然无法从公开资料中识别真实EV补偿作用的缺口，由数据设计解决，不由上述任何估计器替代。
