# 指令与实测功率全过程特征：近期文献核验及有限取舍

核验截至2026-10-31。本件只做文献与作者代码静态核验，未安装库、未执行算法、未改变既有源码、数据或冻结结果。遵循academic原则A5/B6/B7/C3。最新任务以已知指令与实测信号提取过程特征为主，未知未调节参考单列。

## 建议

本轮新增一个文献候选：**LABS作者原生R实现的SIC配置M=5、retest_M=2**。它可直接重建实测序列，输出斜率变点与连续分段线性曲线，代码独立、许可明确、复现成本低。它是2026新预印本的可复现候选，长期维护和EV场景优势尚无证据。成熟强对照保留原CPOP；既有TF、旧/修复RIDE应按相同输入和共同特征规则比较。近期论文的发表时间不能代替本场景证据。[LABS原文](https://arxiv.org/abs/2608.21122)、[作者代码及使用说明](https://github.com/pfryz/LABS)。

不建议本轮同时移植MOSUM_linear和skchange。前者能同时识别跳变与斜率变化，理论匹配很好，但作者代码需Rcpp且仓库未核到许可；后者是维护较好的算法框架，尚需额外确定检测器、代价与重建规则。增加二者会扩张工程与选参范围，未必增加当前小规模比较的辨识力。[MOSUM作者仓库](https://github.com/Joonpyo-Kim/MovingSumLin)、[skchange作者仓库](https://github.com/NorskRegnesentral/skchange)。

## 少量方法的适配与反证

| 方法与原始来源 | 能解决什么 | 关键限制与本轮取舍 |
|---|---|---|
| Fryzlewicz，LABS，2026-08-21预印本[arXiv2608.21122v1](https://arxiv.org/html/2608.21122v1) | look-ahead二分分割修正父节点斜率断点，得到连续分段线性拟合；作者提供完整代码与结果 | 连续信号假设不能保证真实阶跃、短中断的最佳表达；MAD估噪不等于对异常点稳健的损失。新增唯一近期候选；不预承诺胜CP |
| Kim、Oh、Cho，2024，Technometrics66(3):358–367，[DOI](https://doi.org/10.1080/00401706.2024.2308202)、[作者机构记录及接受稿入口](https://research-information.bris.ac.uk/en/publications/moving-sum-procedure-for-change-point-detection-under-piecewise-l/) | 相邻窗口局部线性参数差，检测跳变及斜率变化；容许重尾的渐近FWER理论 | 带宽限制短阶段分辨率，显著性水平不是有限EV小样本5%保证。作者仓库仅11提交，需Rcpp/C++，未核到开源许可；留后续备选 |
| Fearnhead、Grose，2024，JSS109(7)，[DOI](https://doi.org/10.18637/jss.v109.i07) | CPOP最小化加权残差平方和与L0斜率变化惩罚；软件已有非等距、异方差及CROPS | 已有成熟对照必须保留；换加权残差或扫描惩罚不能自动称新通用方法。原CP与LABS都受连续线性结构限制 |
| Tveten、Kolstø、Moen，2026-08-20，[arXiv2608.19767](https://arxiv.org/abs/2608.19767)及[skchange](https://github.com/NorskRegnesentral/skchange) | 统一PELT、moving-window、seeded segmentation、异常段及阈值校准等工具 | 软件库不是一个新全过程提取算法；检测点也不是恢复/持续时长标签。BSD-3，仓库有CI/文档/迁移说明及2052提交；当前额外移植无必要 |

LABS论文自己的比较没有证明准确率全面优于CPOP。汇总精确变点数命中率，CP为0.844、LABS(M5R2)为0.827；Hausdorff误差接近。CP只做50次而其余法500次，论文速度受实现、硬件与序列长度影响。这些表格不能外推成1min或15min EV时长优势；应保留阶跃、短中断、斜坡等本场景反例。[原文§4及表格](https://arxiv.org/html/2608.21122v1)。

## LABS公式到代码及固定调用边界

LABS在候选区间内，用剔除常数与线性趋势后的归一化铰链向量检测斜率改变；子递归返回的候选限制父节点复检区间。静态核对的作者函数为`labs_sic_fast`，**默认M=2，必须显式写M=5、retest_M=2**。固定调用建议为：

```r
labs_sic_fast(x, initial_test=TRUE, M=5L, retest_M=2L,
              multipliers=seq(.50,1.50,by=.05), alpha=1.01)
```

其中x为原生等间隔实测信号，n为观测数，K为候选内部斜率断点数。作者以

\[
\widehat\sigma=\operatorname{MAD}\{\Delta^2x/\sqrt6\},\qquad
\tau_a=a\widehat\sigma\sqrt{2\log n},\quad a\in\{.50,.55,\ldots,1.50\}
\]

构造候选路径，以

\[
\operatorname{sSIC}(K)=n\log(\operatorname{RSS}/n)+(2K+3)(\log n)^{1.01}
\]

选择模型。R默认MAD含正态一致性常数；`alpha=1.01`是sSIC指数。拟合调用`splines::bs(...,degree=1,intercept=TRUE)`与`stats::lm.fit`，输出`fit/cpts/threshold/multiplier/ic/path`。对应本地作者原文代码：`LABS_functions.R.txt`第706—797行（路径与噪声）、806—865行（参数/选模/返回）。[固定提交的代码](https://github.com/pfryz/LABS/blob/0bb0524dec39336a2e0d032287ce092e2968145a/code/LABS_functions.R)。

原生函数不接收实测时间向量，不应将不等距丢测点删掉后假装等间隔。代码拒绝NA/Inf；n≤2直接原样返回，不能据此声称识别成功。无噪声仿射信号RSS=0可产生`ic=-Inf`；序列化须透明标记，不能为输出JSON而改曲线/悄悄加噪。输入为区间平均值时，作者代码将其当网格观测；它不实现精确区间平均算子，也不提供格内变化识别保证。特别是四个15min均值不能凭该算法唯一恢复分钟级全过程。

核心文件只用R基础函数、`stats`与`splines`，没有运行时library/require/source/Rcpp调用。仓库`run_all.R`另需多个比较库且会下载MOSUM，不能把全工作流的安装要求误当LABS核心必需，也不应为这次小比较运行全论文基准。[作者README](https://github.com/pfryz/LABS)。

代码固定提交`0bb0524dec39336a2e0d032287ce092e2968145a`，时间2026-08-21T13:33:27Z，仅核到1次提交。MIT仅覆盖作者原创代码，不覆盖数据、外部MovingSumLin及单独安装的R包。当前未核到LABS已同行评审版本或长期维护承诺。[作者许可](https://github.com/pfryz/LABS/blob/0bb0524dec39336a2e0d032287ce092e2968145a/LICENSE)。

## 领域论文对特征语义的约束

Imanaka与Baba的IEEJ论文2025-09-27在线、2026卷21(2):307–315，直接同步测量指令、功率和ICT。其§2用5%起变、95%全激活，FAT从指令发送到物理变化，ICT回执可能先于功率变化。项目若采用10/90须标为项目定义。论文设备和测量协议不能充当已有通用特征提取开源算法；本次未核到作者算法仓库。[原文DOI10.1002/tee.70176](https://onlinelibrary.wiley.com/doi/full/10.1002/tee.70176)。

Esser等2025的Scientific Data12:1192提供142条、8辆EV的单/双向及动态充电实验，含充电侧setpoint与同步grid active power。多数动态setpoint间隔60s，部分30s，可支持指令响应分析。不同充电器命令通道有功率与电流两种单位，必须读参数字典。数据论文没有给出每阶段人工真值，不应将算法生成边沿当已知真值。[DOI10.1038/s41597-025-05524-5](https://doi.org/10.1038/s41597-025-05524-5)、[作者机构全文](https://repository.tudelft.nl/file/File_3b38135f-01b7-4c8a-84f8-6d9a8b5e5aeb)。

KIT2026的20ms高频数据包含电压阶跃扰动，其电流A不能直接改名功率kW；电压扰动也不能自动当充电功率指令。若没有合法同步功率与相应指令，应仅支持电气扰动信号的限定验证，不能包装为生产充电响应API或净减载证据。[作者数据记录](https://zenodo.org/records/22965111)。

## 共同提取规则与最小实施范围

以下是本项目比较建议，不冒称论文原有EV算法。所有方法共享指令时间、相同实测通道、预先固定的本地基准与目标、同一持续/恢复判据；拟合算法只改变重建曲线。先保存原始积分，再从曲线提取起变、到达、持续、恢复、间断及未完成/右删失标记。阶段不存在时允许缺省，不能硬凑四阶段。原始电量积分保持各法一致，曲线更平滑不直接意味着电量或后续因果作用更准。

指令前局部水平可定义这次操作的幅度和达标比例，但它只支持操作响应描述。未知“若未调用”的功率仍是反事实问题，须单列参考模型、误差与识别假设；不能把局部基准换名为真实净减载。提前离站/观测终止须区分恢复完成与删失。

小规模比较只需新增固定版本LABS；原CP、TF、旧/修复RIDE及透明raw阈值参照保持。事前固定样本划分和特征定义；只在开发数据定参数，验证/测试不得按某法弱漏检再改条件。真实数据无阶段真值时，报告命令对应/重建误差/敏感性与逐例图，避免报“阶段识别准确率”。本件未开始复现，作者源核验成功与项目实际复现成功分别记录。

## 核验文件

下载仅为文本静态检查，均位于本目录；SHA见`sources.json`。`LABS_functions.R.txt`保留作者源码文本且带`.txt`，本次未执行。MIT许可与CITATION一并保存。未下载实验数据大包、未改原始模型或结果。
