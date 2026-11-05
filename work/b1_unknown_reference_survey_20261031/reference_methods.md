# 未知未调节功率：参考预测方法重新调研与建议

2026-10-31｜一手论文、作者资料与官方开源核查。仅调研，没有安装、下载新数据、实现新算法或运行实验；旧源码、科学记录均未修改。

**问题口径：已知任务时间和要求，未知同一充电对象在“没有本次调节”时会怎样用电。** 本文按root已找回的旧截图所示含义讨论。它属于B1测量链的参考估计；不预测B2单车可行容量或参加策略。新用户授权重新选路线和匹配基线，因此本文不要求保留旧模板、RIDE或CPOP作主线。

## 1. 推荐先研究什么

**建议优先验证“会话条件化的多步参考预测＋独立非事件轨迹误差校准”这个问题结构，将成熟提升树和现代前缀时序模型列为有限候选，配可解释加性模型及概率动态模型作同信息对照，再据验证选型。** 将整次任务及恢复观察期作为一个预测对象，不能只优化逐点平均RMSE。此项是本文的方案建议，尚未验证其优于现有Ridge、GBDT或其他模型，也不因组合现成方法就构成算法创新。

具体先回答三个问题：通知时车辆还在怎样充电；没有本次调节时是否会自然降功率、充满或离开；未来参考误差会不会持续偏高/偏低，从而混成响应。输入优先使用通知前功率前缀、会话已持续时间、当时连接/充电状态、已声明需求/预计离开时间、合法个人历史、时点/日历等。不存在的SOC、已实现离站时刻和未来完整电量不能补成已知量。若缺少会话字段，应明确返回较宽不确定性或不适用，而非用聚合住宅预测结论保证单车可识别。

提升树适合作为第一强对照和首个有限候选，是因为它能利用这类不规则条件和交互，已有直接EV站反事实应用，也有维护成熟、分位数实现现成的库。它并不天然保证轨迹连贯、物理性或反事实正确。GP/状态空间擅长描述动态相关误差，但单车开停和提前离开不是自然的平滑高斯过程，不能只因为能画概率带就优先。

## 2. 领域依据：评估对象比模型名称重要

[2022综述：Demand Response Impact Evaluation: A Review of Methods for Estimating the Customer Baseline Load，Energies 15(14),5259](https://www.mdpi.com/1996-1073/15/14/5259)按日匹配、回归、控制组、概率方法等整理基线；强调应按用户负荷与业务选择，没有统一最优方法。

[2024综述：Review of data-driven models for quantifying load shed by non-residential buildings in the United States，RSER 206,114870](https://www.sciencedirect.com/science/article/abs/pii/S1364032124005963)聚焦非住宅建筑，说明实务仍常用平均/回归，适当选择的简单方法可有竞争力。它不能证明单EV也适用相同日规律。

更新核对了Li Zhiwei、Li Hangxin、Wang Shengwei的 **Customer baseline load estimation in incentive-based demand response programs: Requirements, solutions, challenges and future perspectives**：[出版社](https://www.sciencedirect.com/science/article/pii/S1364032125010561)正式卷期为RSER **226 Part C，2026年1月，116383**，DOI10.1016/j.rser.2025.116383；[作者大学元数据](https://research.polyu.edu.hk/en/persons/hangxin-li/)同。DOI带2025与正式2026卷年不可混。可核摘要/引言/章节摘录，未取得正式全文；其重点是基线的准确、简单、完整/防操纵、透明要求以及不可观测行为和数据缺口，并非宣称某深网通用获胜。

**对本项目的推断：** 参考预测排行榜不能代替本任务的下游有效性。平均小误差仍可能有持续正尾；逐点区间校准不保证整段任务可靠；正常EV充满停机、离站和调节都能产生下降，单看电表变化可能无法区分。需要先审数据中的正常会话机制和输入时点，再有限比较。

## 3. 核实的原始方法与适用判断

下表“本项目判断”均为适配推断，不是原文对本项目的实验结论。未核到全文细节处明确保留未知。

| 原始研究与已核来源 | 实际对象/方法 | 本项目判断 |
|---|---|---|
| Sobhy等，**When and where it counts: enhancing demand response in electric vehicle charging**，Applied Energy 401B,126739，2025，[出版页](https://www.sciencedirect.com/science/article/pii/S0306261925014692)、[作者实验室](https://cepslab.kaist.ac.kr/journal/)、[数据记录](https://zenodo.org/records/15312194) | 558个韩国充电站，CatBoost预测反事实消费并评价DR。公开数据记录可见，文件受限 | 最贴近EV的树模型依据，足以纳入强对照。站级有聚合平滑；不能搬成单桩/单车一分钟已验证。全文抓取受限，未独立核出用户隔离、所有输入时点和代码，不照搬其数值结论 |
| Weng/Yu/Rajagopal，**Probabilistic baseline estimation based on load patterns for better residential customer rewards**，IJEPES 100:508–516，2018，[出版页](https://www.sciencedirect.com/science/article/pii/S0142061517320719) | 住宅概率基线、Gaussian Process；页面明确PG&E小时级数据，个体基线区间可能很宽 | 支持将参考当分布而非确定真值；不能证明分钟单EV可窄带精确预测。建议小规模GP对照，特别评价开停与域外失败；本次未找到作者可直接复用的专用开源包 |
| Zhou/Gao/Yao/Yu，**A Robust Segmented Mixed Effect Regression Model for Baseline Electricity Consumption Forecasting**，JMPCE 10(1):71–80，2022，DOI10.35833/mpce.2020.000023，[作者稿](https://intra.ece.ucr.edu/~nyu/papers/2020-Robust-Mixed.pdf) | 混合效应＋分段回归＋稳健估计；南加州负荷 | 为用户差异、非线性和稳健回归提供可解释候选依据；并非单EV验证。新用户不能使用其测试结果拟合随机效应；正常离站也不能被当异常裁掉 |
| Brodersen等，**Inferring causal impact using Bayesian structural time-series models**，Annals of Applied Statistics 9(1):247–274，2015，[作者论文](https://kaybrodersen.github.io/publications/Brodersen_2015_AOAS.pdf)、[作者官方文档](https://google.github.io/CausalImpact/CausalImpact.html) | 扩散回归状态空间、趋势/季节/控制序列，输出反事实演化 | 可作动态参考思想和概率对照。官方要求控制序列不受干预影响且前后关系稳定；并非插入任意同站桩就能因果识别。没有合法控制组时，不能把CausalImpact名称当识别保证 |
| Sievers/Roozbehani，**A Generalized Synthetic Control Method for Baseline Estimation in Demand Response Services**，2026预印本，[全文](https://arxiv.org/html/2604.18469v1)、[作者库](https://github.com/JonasSievers/A-Generalized-Synthetic-Control-Method) | Ausgrid半小时住宅＋模拟储能，299个donor；加外生量/处理组历史/供体滞后 | 有合格同步未处理供体时可列备选；目前单EV不一定有。全文特别指出多步处理组滞后必须递归用预测值，不能用实际受处理功率。它仍把多步递归/不确定性列为后续，不能直接称现成解决 |
| Lei/Hong/Mathieu/Hiskens，**Baseline estimation of commercial building HVAC fan power using tensor completion**，Electric Power Systems Research，2020，DOI10.1016/j.epsr.2020.106624，[作者页](https://dahong.gitlab.io/)、[会议原文](https://pscc-central.epfl.ch/repo/papers/2020/579.pdf) | 多风机×日×时刻张量，利用重复结构补缺 | 证明矩阵/张量补全可用于基线，不是网络状态估计类无关“matrix completion”。单EV若会话高度稀疏且新用户无重复结构，低秩假设未证；若补全读取当前受调节格，则目标被污染 |
| Li等，**Load Profile Inpainting for Missing Load Data Restoration and Baseline Estimation**，IEEE TSG 15(2):2251–2260，2024，DOI10.1109/TSG.2023.3293188，[PNNL原始出版说明](https://www.pnnl.gov/publications/load-profile-inpainting-missing-load-data-restoration-and-baseline-estimation)、[作者预印本](https://arxiv.org/abs/2211.16332) | GAN＋自注意力/门卷积，明确使用补洞前后负荷和解释变量；包括CVR应用 | 不宜原样用于通知前预测；本任务后窗含回补，事后重建也需隔离污染。本文未核到可直接复用、许可明确的Load-PIN作者库；不把未找到说成不存在 |
| Hu/Ye/Kim/Lu，**BERT-PIN: A BERT-Based Framework for Recovering Missing Data Segments in Time-Series Load Profiles**，IEEE TII 20(10):12241–12251，2024，DOI10.1109/TII.2024.3417272，[作者预印本](https://arxiv.org/abs/2310.17742)、[作者公开库](https://github.com/hughwln/BERT-PIN_public)、[作者研讨材料](https://documents.pserc.wisc.edu/documents/general_information/presentations/pserc_seminars/webinars_2025/fall_2025/Webinar_Slides___Yi_Hu_11_19_25.pdf) | BERT双向profile补洞，公开日/周模型代码、训练数据因隐私未附 | 是匹配问题的Transformer候选，不必罗列通用预测模型榜单。若只留通知前信息，需要重新定义掩码/训练/评估，不能承继双向恢复成绩；公开库根未见许可证，不能当成熟许可清晰依赖直接复制 |
| Ansari等，**Chronos-2: From Univariate to Universal Forecasting**，2025-10-17预印本，[论文](https://arxiv.org/abs/2510.15821)、[Amazon作者库](https://github.com/amazon-science/chronos-forecasting)、[官方模型卡](https://huggingface.co/amazon/chronos-2) | 120M参数预训练encoder，zero-shot多步分位数；支持历史/已知未来协变量与跨序列group attention，CPU/GPU推理 | 是比双向补洞更匹配通知时预测的现代深度探索对照，值得限定预算纳入，不必先重训大型网络。通用/能源预测成绩不等于EV反事实与全过程时长验证；仍须非事件训练/查询口径、预训练来源与未来协变量合法性检查 |

补充检索：[IBi-GBM，An iterative bidirectional gradient boosting approach for CVR baseline estimation，Applied Energy，2024](https://www.sciencedirect.com/science/article/abs/pii/S0306261924008390)明确用CVR前窗正向、后窗反向，逐步补缺。这个案例说明**泄漏取决于可用信息，不取决于树还是神经网络**。[CBL-Imputer，IJEPES 178,111965，2026](https://www.sciencedirect.com/science/article/pii/S0142061526004072)摘要为自注意力补洞＋LightGBM残差提升；全文访问受限，未充分核其时点与许可，本次不据其摘要排名选型。

### 本次阅读深度与未核内容

- 2022综述：读到公开正文的分类与讨论；2024建筑综述：出版摘要/要点；2026 Li等综述：出版摘要、引言、章节摘录＋大学元数据，正式全文受限。
- EV CatBoost：出版摘要/要点、作者机构与Zenodo页面；全文403，未核模型特征全表/训练划分，未复现。Weng GP：出版摘要和方法/数据章节摘录；未取得并逐页阅读全文，未核专用代码。
- 分段混合效应：作者公开稿及搜索可读方程/方法段；未逐页核全推导/结果。BSTS：作者论文摘要与官方文档的假设/用法；未复现MCMC或验证EV适用性。
- 2026 SCM：可读arXiv HTML的方法、多步递归警告、附录实验设置和局限，并核作者库；未运行notebook。张量补全：会议原文可读内容及作者正式期刊元数据；未复现张量优化。
- Load-PIN：PNNL原始说明＋作者预印本摘要；已核前后窗输入，未逐层复现网络。BERT-PIN：作者预印本摘要、公开README/文件结构与作者研讨材料；未逐行审网络或运行训练。
- Chronos-2：原始预印本摘要、官方仓库与模型卡的输入能力/许可/本地推理说明；未下载权重、未跑CPU/GPU，未逐页审预训练数据表或证明测试数据无重叠。

因此本文给出的是有出处的适配判断和有限实验建议，不能将“论文可找到/代码公开”写成“已完整复现方法”或“该方法已在本项目验证”。

## 4. 时点与污染：必须先定这两种业务

**A. 通知时冻结参考预测。** 只用通知前目标用户资料，以及通知时已经发布的天气预报/日历等。所有任务及后窗一次预测完，禁止把任务后真实天气或目标车实际功率当事前输入。可使用该新用户自身更早合法历史，但训练/验证/测试用户分离、其历史只供查询，并不允许训练器读其未来标签。任务开始前但通知后的功率已经可能含预响应，同样不能悄悄回填。

**B. 事后反事实重建。** B1分析已完成任务时，允许怎样使用同时期未受影响供体、实际天气和充分恢复后的观测，理论上可以另立协议。但目标车任务窗/预响应/回补不能当“正常上下文”。需要先证明排除的处理影响窗足够长、供体无共享站控/共同干预/网络限额溢出，并明确这条路线不能通知时出结果。不能让B模型多用后窗，然后与A模型按同信息预测竞赛计分。

后窗数据并非任何情况下都不能用：经验证不受本次处理影响的事后外生信息可以服务B。但本项目有明确回补机制，直接双向补洞更容易把反弹误当自然高负荷，把自然离站/充满错误补成仍在充电。是否采用B须依据完整恢复资料与目标，而不是因为离线误差更小。以上为因果/时点适配判断；原Load-PIN的CVR成绩本身没有因此失效。

## 5. 成熟开源复用核查

| 实现 | 许可与本次核到的维护/资料 | 采用成本与判断 |
|---|---|---|
| [scikit-learn](https://github.com/scikit-learn/scikit-learn)、[许可证](https://github.com/scikit-learn/scikit-learn/blob/main/COPYING) | BSD3；有持续版本文档；官方提供[提升树分位数示例](https://scikit-learn.org/stable/auto_examples/ensemble/plot_gradient_boosting_quantile.html)与[GP](https://scikit-learn.org/stable/modules/gaussian_process.html) | 现环境已有，优先做最小可复核模型组；加性样条＋Ridge、树/分位数、GP均可在有限依赖内完成。分位数只是条件边际区间，不能自动推出整段联合覆盖 |
| [CatBoost](https://github.com/catboost/catboost)、[许可](https://github.com/catboost/catboost/blob/master/LICENSE)、[releases](https://github.com/catboost/catboost/releases) | Apache2；有发布页与完整官方文档；[Quantile/MultiQuantile](https://catboost.ai/docs/en/concepts/loss-functions-regression)可查 | 与EV领域论文最贴近，可作为一个强树对照；不同时引入多个树库无限调。用户ID不能当跨新用户泛化捷径；论文模型本身不等于官方库 |
| [LightGBM](https://github.com/lightgbm-org/LightGBM)、[releases](https://github.com/lightgbm-org/LightGBM/releases)、[参数](https://lightgbm.readthedocs.io/en/latest/Parameters.html) | MIT；仓库有CI、发布与量化回归文档 | 项目 `B1算法/requirements.txt` 已锁LightGBM4.6.0与scikit-learn1.7.2，初轮优先复用现有LightGBM轻量实现，不因EV论文用CatBoost就新增依赖；这属于同类树方法适配，并非原CatBoost论文同算法复现。CPU成本仍需实测 |
| [google/CausalImpact](https://github.com/google/CausalImpact)、[许可](https://github.com/google/CausalImpact/blob/master/LICENSE)、[维护元数据](https://github.com/cran/CausalImpact/blob/master/DESCRIPTION) | Apache2；维护元数据可见2025-09-24，依赖R/bsts等 | 适合作为有有效控制序列时的独立对照；引入另一运行栈且需MCMC，当前不为它扩大工程。若本地已有R仍先核兼容性，不在本轮安装 |
| [BERT-PIN作者库](https://github.com/hughwln/BERT-PIN_public) | 本次页面显示7 commits、无发布包、根目录未见许可证；训练数据未附 | 研究参考价值高，工程成熟度/复制许可待确认；不要将“公开可读”写成许可明确开源 |
| [Generalized SCM作者库](https://github.com/JonasSievers/A-Generalized-Synthetic-Control-Method) | 本次页面14 commits、notebooks/requirements；根未见许可证 | 可读方法和复现思路；同步供体可得性更是首要前提。未独立运行，不能承诺现成可复现 |
| [Chronos-2官方实现](https://github.com/amazon-science/chronos-forecasting)、[模型卡](https://huggingface.co/amazon/chronos-2) | 实现与模型卡均列Apache2；官方更新至2026、示例/测试与本地推理说明可查，支持CPU/GPU | 需新增chronos/PyTorch相关环境与下载预训练权重，zero-shot仅免任务训练，并非免安装/下载/推理成本；本轮均未做。云部署是可选项，无需上传项目数据。CPU延迟/内存本机未测，不把GPU宣传吞吐搬成本机性能 |

以上维护状态以本次网页显示为限，不把stars/commit数当算法质量，不断言所有项目的最后提交日期或最新固定版本。没有复制代码或安装库。

## 6. 单EV所需的数据与正常退出问题

[ACN-Data官方字段](https://ev.caltech.edu/dataset.html)区分实际`disconnectTime`、最后有电流的`doneChargingTime`、请求离开时间`requestedDeparture`，用户输入还有`modifiedAt`；含实测电流和pilot。这些字段可帮助建立合法会话条件，但**未来实际disconnect/doneCharging/最终kWhDelivered只能当标签/评价，不得输入通知时模型**。API需注册token。[2019作者论文](https://ev.caltech.edu/assets/pub/ACN_Data_Analysis_and_Applications.pdf)是工作场所数据；[作者acnportal](https://github.com/zach401/acnportal)BSD3，数据服务条款仍单独核。

同时ACN存在adaptive charging控制，实测pilot/current不等于未受任何控制的自然轨迹。即便将来使用，也须定义“无本次调节、保留正常站控”的参考，核用户缺失/采样/时区/电流转功率的原始证据；不能把它直接叫真实DR反事实标签。本轮不解冻或下载现项目真实数据，仅指出可用字段和限制。

对自然退出建议先作两个层次：在只知功率前缀的最低信息集上比较所有模型；在确有通知前会话字段时，再做同字段增益消融。若新方案需要SOC、预计离站等而基线没有收到同字段，不能把额外信息收益记作模型优势。正常自然下降、提前离开、缺失数据与真实指令减载分别计分；无法区分时保留状态不确定，不强行贴“响应”。

## 7. 最小方案与公平比较建议

第一轮只选A：通知时一次预测未知自然负荷，任务固定且带同一恢复观察期。建议有限同信息参考组：①相似历史日/会话平均＋合法事前level调整；②加性样条/正则回归；③标准提升树；④小规模GP或局部level/trend状态空间二选一；⑤一个Chronos-2零样本前缀预测探索对照。现有Ridge/GBDT可作为已有实现加入，但不要求它们必为主对照。Chronos-2可在明确下载和推理预算后参与，不因旧方案没有深网就排除；任务专门训练大型Transformer需长历史和足够异质会话数据再论证。双向补洞模型若削去后窗，需要重做训练任务与公平评估，不能沿用论文成绩。

候选机制先只加“会话条件化”和“非事件整段误差校准”中的一个，做可归因消融。会话条件化要解决的是自然退出/充满混淆；轨迹误差要解决的是持续偏差和相关残差。分位数可先做单点不确定性，但过程时长是非线性阈值泛函，不能把每分钟分位数独立拼成可信整条轨迹。若要输出特征不确定性，可在独立非事件任务上保留成块的完整误差轨迹，或用明确概率动态模型生成连贯路径，再验证覆盖/宽度和误检—漏检权衡；这部分需要新研究证据，不能先称已校准因果时长。

验证应同时给出：唯一用户/会话的功率RMSE和有符号偏差、持续正/负尾、任务电量偏差、自然退出分层；独立非事件整任务误报与响应弱幅/短时漏检；分钟与15分钟各按实际格宽重采样的特征误差。15分钟四格不能识别一分钟延迟/3分钟持续时间，输出应给分辨率限制，不用插值造物理时点。后段因素估计保留所有事件，并检查参考误差是否随激励/事前条件变化，不能只选测量准确者估曲线。

划分按原用户与时间：训练/校准/验证/测试分清，先冻结输入和预算；已见模拟只诊断，不作为独立新test。非事件留出只能验证预测与假事件误报，真实DR的个体反事实无法同时观测；受控模拟/注入用于有真值的特征评价并单独标注，真实记录用于可观察的输入/校准/外推检查，不能混为现场真值认证。

成功标准应预先声明下游可接受时长/电量误差与误报—弱漏、可用率、成本，而非所有模型按全局平均RMSE排序。若提升树只胜平均误差却持续尾更坏，应保留动态/校准路线；若概率模型带宽过大且无下游收益，应停止加复杂度。若缺会话可用字段导致单EV自然退出不可区分，应先界定可回答范围与缺失证据，不靠更大Transformer承诺补齐。

**当前明确推荐：** 先固定会话信息、前缀预测和整段误差这个问题结构，有限比较提升树/分位数与Chronos-2前缀预测，再用加性模型和GP/状态空间检验复杂度、非线性与动态不确定性的价值。SCM/矩阵补全以存在合法供体与稳定重复结构为准入条件；GAN/BERT补洞以真正需要事后重建、已隔离预响应/回补且许可明确为准入条件。现阶段文献不足以证明任何一条对单EV一分钟全过程必胜，适配方案须新验证；这里没有正式选定新主线或实现。
