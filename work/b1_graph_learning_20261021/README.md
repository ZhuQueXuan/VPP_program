# B1连续SCM图学习研究入口

状态：冻结的小型工作包完成，有限样本错误保留；不代表B1图学习全覆盖或真实EV机制验证。

先读[首轮结果与边界](图学习首轮结果与边界.md)，实现范围见[方法说明](方法与冻结说明.md)及[计算前协议](protocol.json)。PC-stable骨架、保守碰撞和单列时间先验均为透明小规模实现，没有Meek闭包，非完整CPDAG。

| 内容 | 文件 |
| --- | --- |
| 原始模拟X | ../../data/驱动因素解耦模拟数据集_B1_graph_v1_20261021/observations.npz |
| 生成/学习/评价 | generate.py、graph_learner.py、run_study.py、evaluate_graph.py |
| oracle/有限学习 | oracle_covariance.npy、oracle_learned.json、learned.json |
| 指标及边界控制 | metrics.csv、evaluation.json |
| 独立复核 | verify_graph.py、independent_verification.json |
| 版本及失败 | protocol.json、source_freeze.json、run_receipt.json、failures.md、evaluate_graph_serialization_failed.py |

在项目根运行`python work/b1_graph_learning_20261021/verify_graph.py`可独立复算现有观测和输出的检查，未拟合或调参。主run_study.py在已有输出时主动拒绝覆盖；后续实验另冻协议/新评价，不覆盖本轮追分。

接口graph_learner.learn(cov,names,n=None,alpha=.01,tiers=None)接收协方差/变量顺序，n=None为oracle零判据，有n为Fisher-z近似检验；返回skeleton、separators、colliders、data_directions、tier_only_directions、conflicts、CI traces。时间层方向来源为先验，不能计作独立数据发现；冲突时不强行给单一DAG。

40有限数据集/120000行，120oracle顺序、200有限顺序运行。3061独立检查通过。N=1000/5000各19/20骨架完全恢复，两条额外边及一次方向冲突保留，不按正式90%验收解释。
