# 过程方法调研来源表

检索日：2026-10-31。均为原论文、作者/机构仓库、官方包元数据或官方文档；未依赖第三方排名作采用依据。只列支持实质判断的来源，不把检索失败链接作为证据。

| ID | 原始来源 | 支持内容/限制 |
|---|---|---|
| S01 | [Truong/Oudre/Vayatis，Selective review of offline change point detection methods](https://arxiv.org/abs/1801.00718) | 离线变点代价/搜索/约束分类；2020正式发表，arXiv起始2018。不能给EV反事实识别保证 |
| S02 | [作者ruptures库](https://github.com/deepcharles/ruptures)；[LICENSE](https://raw.githubusercontent.com/deepcharles/ruptures/master/LICENSE)；[发布入口](https://github.com/deepcharles/ruptures/releases) | BSD2；实现、测试与发布；本轮无法可靠读到最新commit日期 |
| S03 | [Van den Burg/Williams，An Evaluation of Change Point Detection Algorithms](https://arxiv.org/abs/2003.06222) | 37序列/5人工标注者/14算法；通用变点评价，不是EV全过程基准 |
| S04 | [TCPDBench作者库](https://github.com/alan-turing-institute/TCPDBench) | MIT，复现与多标注基准框架 |
| S05 | [Kim/Koh/Boyd/Gorinevsky，L1 Trend Filtering，2009](https://web.stanford.edu/~boyd/papers/l1_trend_filter.html)；[作者软件](https://web.stanford.edu/~boyd/l1_tf/) | 分段线性趋势、二阶差分L1；原作者软件2008 Beta、GPL2 |
| S06 | [Tibshirani，Adaptive piecewise polynomial estimation via trend filtering](https://arxiv.org/abs/1304.2986) | 趋势滤波性质；拟合值定义在输入网格，连续解释须说明 |
| S07 | [Tibshirani等，Sparsity and smoothness via the fused lasso，2005](https://web.stanford.edu/group/SOL/papers/fused-lasso-JRSSB.pdf) | L1幅度/相邻差分惩罚，局部常数基础 |
| S08 | [作者genlasso](https://github.com/ryantibs/genlasso)；[DESCRIPTION](https://raw.githubusercontent.com/ryantibs/genlasso/master/DESCRIPTION) | 广义lasso、fused lasso、趋势滤波；1.6.1/2022日期；GPL≥2；接口数值条件尚未运行核验 |
| S09 | [glmgen作者库](https://github.com/glmgen/glmgen) | 广义lasso实现，GPL2；不据旧库网页称当前高频维护 |
| S10 | [CVXPY项目](https://github.com/cvxpy/cvxpy) | 凸优化建模工具及Apache2许可；不是专用EV方法，求解器许可需另查 |
| S11 | [Killick/Fearnhead/Eckley，Optimal detection of changepoints with a linear computational cost](https://arxiv.org/abs/1101.1438) | PELT原文；线性期望复杂度有条件 |
| S12 | [ruptures PELT说明](https://github.com/deepcharles/ruptures/blob/master/docs/user-guide/detection/pelt.md) | min_size与jump影响可检测短段，代价影响复杂度；原生输出变点 |
| S13 | [CostCLinear](https://centre-borelli.github.io/ruptures-docs/user-guide/costs/costclinear/)；[KernelCPD](https://centre-borelli.github.io/ruptures-docs/user-guide/detection/kernelcpd/) | 线性代价/核空间分段的准确含义；核分段非kW响应恢复 |
| S14 | [Pein等，JULES，2018](https://arxiv.org/abs/1706.03671)；[机构论文记录](https://pure.mpg.de/pubman/item/item_2620164) | 多尺度检测+局部反卷积，短事件幅度/驻留；应用和滤波假设受限 |
| S15 | [Pein等，Heterogeneous Idealization of Ion Channel Recordings—Open Channel Noise](https://arxiv.org/abs/2008.02658) | HILDE异质噪声/多尺度/反卷积；不能外推15min稀疏电表超分辨率 |
| S16 | [作者clampSeg手册](https://florianpein.r-universe.dev/clampSeg/doc/manual.html)；[作者包入口](https://florianpein.r-universe.dev/clampSeg)；[CRAN镜像元数据](https://bioconductor.statistik.tu-dortmund.de/cran/web/packages/clampSeg/index.html) | GPL3、方法参数及输出；镜像1.2-0/2025并有检查提示。当前主CRAN状态未确认 |
| S17 | [Runge等，gfpop，JSS106(6)，2023](https://www.jstatsoft.org/article/view/v106i06)；[作者库](https://github.com/vrunge/gfpop)；[DESCRIPTION](https://raw.githubusercontent.com/vrunge/gfpop/master/DESCRIPTION) | 图约束、稳健损失、分段参数及状态；MIT、1.1.1、Rcpp。不是原生连续斜率平均观测模型 |
| S18 | [Johnson/Willsky，Bayesian Nonparametric Hidden Semi-Markov Models，2013](https://www.jmlr.org/papers/v14/johnson13a.html)；[作者pyhsmm](https://github.com/mattjj/pyhsmm) | 显式驻留、状态推断；MIT；作者明确停维护 |
| S19 | [statsmodels结构状态空间文档](https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.structural.UnobservedComponents.html)；[项目许可](https://github.com/statsmodels/statsmodels/blob/main/LICENSE.txt) | 背景动态、状态平滑器基础；BSD；不是现成EV响应识别器 |

针对未知参考+已知任务+全过程恢复的优先候选与限制为本审查的综合判断，不是上述任一论文原结论。没有检索到一套可直接覆盖全部条件、已证明优于原CPOP/RIDE的成熟EV开源库。
