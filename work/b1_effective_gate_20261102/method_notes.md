# 有效性核验与备选论文核查

目前先实施同条件有效性核验。使用已安装scikit-learn1.7.2标准HGB；[官方实现与BSD3许可](https://github.com/scikit-learn/scikit-learn)已核，不安装新依赖。实际代码增加的是“存在物理变化”与“达到既定有效响应标准”的分开判断，不把分类器本身当新发明。

为独立测试若失败准备了两项近期原始来源，尚未实施，不能借其保证给当前HGB核验背书：

- [Tightening Control in Neyman–Pearson Linear Classification](https://arxiv.org/abs/2607.03590)，2026-07-03预印本，Yijian Huang。优先约束一类准确性，再优化另一类，并讨论有限样本控制偏乐观问题。与“保住真实响应再压误报”的取舍相关，但研究线性分类和相应理论，未核成熟EV实现，不能直接移植保证。
- [Conformal Risk Training: End-to-End Optimization of Conformal Risk Control](https://proceedings.neurips.cc/paper_files/paper/2025/file/6559542f75b4452ebaaf82094c7defb7-Paper-Conference.pdf)，NeurIPS2025，Christopher Yeh等。将风险控制纳入训练，含漏检率控制与尾风险目标，区别于只在训练后调整阈值。若当前后处理压误报会伤真响应，可研究训练与判别一起考虑代价；论文并非当前EV任务验证，也不是本版已经完成的实现。

CRC/风险约束不创造额外量测，也不是零现场漏检保证。配对噪声变体不应当独立校准用户；若未来复现，仍须保持当前有效功率定义、以新数据同条件计分，不能只输出更宽区间或不确定拒判充作收益。

检索中的ReCIRC二手条目未取得可核的arXiv原件，未当可靠方法依据，也未用于选型。以上是技术备选记录，不是报告或采用声明。
