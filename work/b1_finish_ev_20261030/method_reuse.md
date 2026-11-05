# 本轮方法复用核对

本轮沿用已经实现并验证的原生CPOP、Kennedy连续DR、scikit-learn的PCA与小型AE；未安装第三方包或引入另一套运行框架。

- 连续作用核仍依据[Kennedy等论文](https://arxiv.org/abs/1507.00747)。作者[npcausal仓库](https://github.com/ehkennedy/npcausal)及[ctseff原实现](https://github.com/ehkennedy/npcausal/blob/master/R/ctseff.R)可作方法对照；[DESCRIPTION](https://raw.githubusercontent.com/ehkennedy/npcausal/master/DESCRIPTION)声明0.1.0、GPL、R实现。它不是本轮新增Python依赖，本轮未复制其R源码。维护活跃度无法由网页未返回的提交时间判断，不据此称其正在活跃维护。现有连续核心保持字节相同，新模块只冻结已有伪结果、提供直接查询和数值导数。
- [TS2Vec作者库](https://github.com/zhihanyue/ts2vec)有通用时序表征实现，[许可证](https://github.com/zhihanyue/ts2vec/blob/main/LICENSE)为MIT，README给出的依赖包括PyTorch及早期版本Python/NumPy。引入它需要额外框架与适配成本；当前用途尚无证据要求扩大到该框架，因此继续固定现有PCA/小型AE作一次B1用途比较。没有因为AE不胜出而重训更大模型。
- 新敏感性为冻结高斯局部线性均值的解析导数，并以常数/仿射再现、非线性数值微分与货币单位缩放独立核对。不是把局部斜率直接当成整个平滑曲线的导数。
- 新阈值仅在声明网格上判首达及细化符号变化区间。它没有解决连续因果阈值的完整统计覆盖，不声称形成新的阈值识别理论。

查询、图、检查数量不作为新估计器创新。新增算法价值须从同信息过程测量或经验证的表示增量中说明；本轮保留CPOP胜出、表示无稳定增量与支持拒答的情况。
