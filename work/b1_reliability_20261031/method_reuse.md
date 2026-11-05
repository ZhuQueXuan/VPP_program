# 方法复用与比较口径

本轮继续固定既有Python环境，不安装新库、不改原CPOP源码或依赖版本。

- [scikit-learn作者仓库](https://github.com/scikit-learn/scikit-learn)提供成熟的Ridge、标准化和样条实现，[许可证](https://raw.githubusercontent.com/scikit-learn/scikit-learn/main/COPYING)为BSD三条款。本机已用版本1.7.2；新参考模型复用这些工具，保存原生数值参数与固定样条节点，不使用pickle。新模型是合法通知前前缀和历史形状到未来未调用功率的资源适配回归，不声称Ridge或样条本身是新算法。
- 评估了[MAPIE作者库](https://github.com/scikit-learn-contrib/MAPIE)及[校准文档](https://github.com/scikit-learn-contrib/MAPIE/blob/master/doc/content/conformal-prediction/regression.md)，[许可](https://raw.githubusercontent.com/scikit-learn-contrib/MAPIE/master/LICENSE)同为三条款BSD。它有通用共形区间/分类功能，但本轮需要的是固定任务统计量、同用户多事件最大值和原B1身份/时间合同。只实现标准上尾秩公式及本项目特定适配，复用NumPy即可；未复制该库源码，也未引入其依赖。独立核验了秩、ties和整用户而非逐行校准。
- 仓库与文档已在本轮访问；网页未给出完整提交时间，不据此宣称某分支是最新活跃版。为复现保留本机已验证版本，不自动升级依赖。
- 事件统计量扫描1/3/5/10/15/30分钟段；每个非事件用户的两次任务取最大值校准。对单事件的尾部秩只在校准/测试用户块可交换、相同块结构等前提下有统计解释；实际场景变化仍可能失效。它不是响应概率、物理反事实识别、B2承诺或控制许可。
- 因素模块继续复用[Kennedy等原方法](https://pmc.ncbi.nlm.nih.gov/articles/PMC5627792/)与原Python数值核心。新模块只在独立验证数据上选择回归复杂度和平滑倍数，测试按同一冻结配置运行。整用户留出平滑风险条件于固定交叉拟合伪结果，不冒称重训全部辅助模型的嵌套风险，也没有全链因果区间覆盖保证。

过程的四条比较路径具有相同观测、任务和独立校准信息：旧参考+CPOP、旧参考+修复模板、新参考+CPOP、新参考+修复模板。新参考同样供原CPOP使用，用来判断增量来自参考、校准还是过程模板。原始时长正值率与校准后的响应证据误报同时披露；弱响应证据不足及无法输出均保留。

连续作用阶段使用完全相同的新参考+CPOP测量结果供默认/选择配置的共享DR比较。不将采用CPOP本身或已有DR选参能力称为新估计器创新。
