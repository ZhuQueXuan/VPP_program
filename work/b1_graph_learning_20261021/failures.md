# 失败及修复

首次evaluate_graph.py已计算指标，但在evaluation.json落盘时遇NumPy布尔对象不可JSON序列化错误（TypeError: Object of type bool is not JSON serializable）。失败原脚本保存为evaluate_graph_serialization_failed.py；科学学习输出和原始观测未改，metrics.csv已写，是同一冻结学习输出的指标。

修复仅将独立oracle协方差/d-separation比较的agrees显式转Python bool；未改结构、样本、alpha、条件独立容差、图学习规则、真值或指标定义。source_freeze.json保留原时点评价器SHA，最终独立收据另记录修复后评价器身份，不追写旧收据。
