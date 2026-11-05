# B1恢复观测不确定性研究入口

2026-10-21。先读[结果与适用边界](结果与适用边界.md)，再读[方法与冻结说明](方法与冻结说明.md)。身份仅为新模拟观测方法研究，原D106结果不覆盖。

- protocol.json：计算前冻结的噪声/偏差假设、ε敏感性、样本和评价。
- recovery.py：可调用assess/profile/classify；已知差值协方差及偏差界下的欠量点值、固定点区间、路径同时带和三状态。
- observe.py、run.py：新观测生成与公共观测区间计算；main已执行，不覆盖本轮已见评价。
- evaluate.py、evaluator_truth.npz：区间保存后才读的隐藏评价材料，不作算法输入。
- intervals.npz、metrics.csv、decisions.csv、evaluation.json：持久区间/全部指标/结果。
- verify_recovery.py、independent_verification.json：独立复核；micro_checks.json、run_receipt.json、source_freeze.json为阶段及身份收据。

原始模拟在[data说明](../../data/驱动因素解耦模拟数据集_B1_recovery_v1_20261021/README.md)，过程在本目录。研究代码不提供CMD/页面。可复算micro或独立验证；新增实验必须新冻设计，不覆盖本轮数据追分。

本轮条件区间不等于真实恢复能力或服务验收。真实噪声/参考不具备依据时，不应直接套默认IID；接口须由使用者提供明确误差假设，输出附该假设。阶段门/10390%与全局主稿状态均不改变。
