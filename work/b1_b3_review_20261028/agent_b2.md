# B2及B1→B2→B3衔接独立审查

审查日期：2026-10-28。只读原包；未生成研究样本、未训练、未修改冻结代码或成绩、未删除。仅创建本目录审查材料，并以现有样例、现有模型进行6项输入查询。按A1术语一致、C3代码对应、B6证据强度检查。以下P1是已复现代码错误；P2衔接项是正式完整链条的必要补充，并非据此否定已明确限定的局部实验收口。

## 先给结论

1. B2有真正可调用的研究预测函数，不是仅文档概念。物理层确实调用现用EV-CAP-v1，选择/条件执行/总体交付及回补确实分层计算。
2. B1→B2没有实际数据/模型消费链；B2→B3也没有实际学习模型消费链。当前是三个边界不同、分别验证的研究包。B3中引用B2目录的源码只用于冻结保护，不是运行依赖。
3. B2已有许可门存在输入类型错误：字符串`"0"`被当作有许可。应列P1，后续独立修复入口并保留原冻结评分，不能用既有核验通过数掩盖。
4. B2→B3缺口的最小补充是明确一个受限连接合同及逐例验证，不需要统一平台重构、扩大资源或继续追模型分数。

## 已复现问题

### [P1] B2许可数值校验后又读取原始字符串，`"0"`绕过已有许可硬门

- 位置：`D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:18`将全部字段转float；`D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/common.py:47`据此允许permission为0/1。但`D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:21`、`:26`、`:38`使用`bool(case['permission'])`，读取未经统一的原始值。
- 触发：现有`example_output.json`完全相同输入，仅把permission从合法数值0改成JSON字符串`"0"`或`"0.0"`。前者转float后通过0/1校验，之后非空字符串又转成True。
- 实测：0/False均`blocked`、eligible=false、0情景、预计0kW；`"0"`/`"0.0"`均`ok`、existing_permission=true、eligible=true、5情景、预计0.6456820699203722kW。1/True与有许可基准一致。
- 后果：从JSON/表单/将来连接程序传来字符串时，“未许可”可被错标为“已许可候选”。当前无实际控制下发，且仍要求实际接受、committed_kw=null；不能据此声称已发生真实误控制。但它确实违背研究API的硬门语义，后续连接不得原样复用。
- 最小修正方向：先严格拒绝字符串许可，或把合法0/1统一成一个布尔值，后续所有准入/返回只读该值；无论采用哪种，都增加0/1、False/True、字符串0/1、缺失和非法值边界证据。原科学模型和原评分不需要重训重算。
- 本次证据：`D:/myDocu/project_postg/VPP_program/work/b1_b3_review_20261028/b2_api_probe.py`及`D:/myDocu/project_postg/VPP_program/work/b1_b3_review_20261028/b2_api_probe_results.json`。写出使用独占创建；api/common/模型/选择文件查询前后SHA相同。既有8项API核验只测数值permission=0，见`D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/audit_results.py:82`。

## 输入输出和实际连接状态

| 连接 | 代码事实 | 本轮判断 |
| --- | --- | --- |
| 现用EV物理核→B2 | `D:/myDocu/project_postg/VPP_program/work/b2_single_ev_baseline_20261026/physical.py:5`动态载入现用capability_model；`:13`构造单EV声明场景、`:16`执行；`D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/common.py:8`再只读复用该physical模块 | **已接通**，但只覆盖7.2kW单车、E=bT/60、30min任务，不代表任意EV全部输入已支持 |
| B2选择轮→动态轮 | `D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/experiment.py:57`保存验证多数规格，`:64`读取；`:76`在新训练数据重新拟合 | **已接通规格选择依赖**，并非直接继承原轮拟合系数、用户或测试 |
| B2物理→选择→条件执行→期望/情景 | `D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:19`物理与余量，`:25`载模型，`:26`选择，`:27`执行分布/标量，`:30`期望，`:33`回补 | **已接通局部预测链**；五种情景是候选/条件结果，期望不是可执行承诺，已有许可门需修 |
| B1特征/因果结果→B2输入/拟合 | `D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/common.py:29`—`:37`独立抽样偏好/参考/期限/风险/物理余量；`:8`只接旧B2物理。`D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/experiment.py:16`条件执行特征只有risk、margin | **没有接通**；不是消费B1图/因素估计/时序表示后得到B2 |
| B2模型→B3首包 | `D:/myDocu/project_postg/VPP_program/work/b3_coordination_20261028/experiment.py:43`—`:56`自行抽样EV、许可、接受；`D:/myDocu/project_postg/VPP_program/work/b3_coordination_20261028/physics.py:44`—`:59`自行构造四类本地约束 | **没有接通学习结果**；相容物理思想已适配，B3数学约束实际可算 |
| B2动态→B3反馈 | `D:/myDocu/project_postg/VPP_program/work/b3_feedback_20261028/experiment.py:25`—`:35`自行抽样许可/接受、未来限幅；`D:/myDocu/project_postg/VPP_program/work/b3_feedback_20261028/model.py:5`固定下界，`:33`按下界/上一格限幅规划，`:98`执行 | **没有接通**；外部限幅模型不能替代B2所学延迟/退出/接受过程 |

B2 API输入是b(kW)、T(min)、q(kW)、E(kWh)、low/high/reference(假设元)、prob(金融高收益概率)、green_preference(0—1)、green_attribute(0/1)、risk(0—1事前技术执行条件)、permission(已有许可)。这里**金融prob与技术risk不是同一概率**，也不是绿色价值实测。b/T/E重复声明必须满足E=bT/60。单车上限7.2kW、30min事件长度等没有从输入读取，是该版本任务族常量。

B2输出qmax_kw是条件物理上界，task_kw是给定任务量，acceptance_probability是预计接受，conditional_service_probability是已接受条件下任务成功，service30_v1_probability是含拒绝/不发送的总体任务概率。expected_delivery_kw/kwh及expected_event/post轨迹是总体平均；dynamic_scenarios的概率条件于接受。返回control_requires_actual_acceptance=true、committed_kw=null，语义本身正确。实际接受不是B2概率查询的输入，后续须由外部另提供；不能把候选情景当实际动作命令。

## [P2] 正式链条需要补齐的具体合同

### 1. B1输出不能原名映射为B2时序/成功标签

- `D:/myDocu/project_postg/VPP_program/work/b1_ev_factor_chain_20261026/features.py:6`只接固定360点10s曲线；`:8`取第10—30min的20min事件、用固定0.15kW阈值；`:13`S为累计至少600s。`D:/myDocu/project_postg/VPP_program/work/b1_ev_factor_chain_20261026/estimators.py:15`按二元X/W分层预测两个干预状态的结果，不是B2单事件接受/执行概率模型。
- B2为30min事件、90%任务幅度、2min内达到、连续至少28min、末格仍达标且离站前补够。其动态标签直接由已抽取模板state生成，`D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/generate.py:38`—`:41`；没有调用B1提取器。
- 所需最小补充：分别声明“事后标签提取合同”和“事前预测字段合同”。B1当前事件的事后时长、功率、接受A不得回填当前B2事前输入；如只共享物理事前条件，可明示“不要求B1所有结果成为B2特征”。若需要历史特征，必须携带事件结束时点、截止可得时点和用户命名空间，另审时间隔离；不需要为了图表上有箭头而强行加入无增量特征。

### 2. B2→B3必须先限定同一任务、时间轴及可行动作族

- `D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:22`训练域只有T=60/90/120min、q=1.5/3kW；`:28`—`:35`输出固定30个1min点及恒定回补。
- 首个B3为24个5min点、T=120min，但EV事件期可以逐格任意减载，`D:/myDocu/project_postg/VPP_program/work/b3_coordination_20261028/physics.py:42`—`:48`。B3第二包H=36、3h期限，实际欠账持续递推，`D:/myDocu/project_postg/VPP_program/work/b3_feedback_20261028/model.py:5`、`:46`—`:54`、`:106`。因此不能把B2的T=120模型直接套到180min连续调用，也不能把固定q任务概率解释成任意优化后EV轨迹的成功概率。
- 精度例：B2延迟2min模板是service30_v1成功状态，但5min平均后的首格只有0.6q。B3逐5min格至少q的严格服务会判该单车首格不足。守恒重采样保住kWh，也不能保住2min延迟和连续28min判定。依据模板`D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/generate.py:15`及B3判定`D:/myDocu/project_postg/VPP_program/work/b3_feedback_20261028/simulation.py:76`。
- 最小连接可先选T=120、单30min、q∈{1.5,3}的交集；原1min服务标签保留、5min协调只计算均值与能量。若坚持B3现有严格每格任务，就必须重新定义成功标签并由现有五模板逐例映射，不得搬用B2服务概率。当前B3双调用及180min能力保持独立适用域。

### 3. B3物理可行域与B2行为情景需分别交付

- B3不是消费B2五情景后求联合计划：首包允许EV在[0,b]任意控制，反馈包的最差因子固定[.65,.65,.75,.65]；`D:/myDocu/project_postg/VPP_program/work/b3_feedback_20261028/model.py:39`—`:41`、`:104`—`:111`是幅度限幅，不表示晚2/5min、15min退出。B2五情景中存在晚到/退出为零的片段，不能从B2推出每格至少65%可用。
- 最小合同分为两份：可行域给参考/上限/剩余AC需求/期限/许可/实际接受与恢复约束；行为预测给带model_id与任务id的接受概率、条件五情景概率及原时间网格，明确只供情景评价/计划候选，不作为保证边界。若B3要利用行为预测改准入，应另声明风险准则与共同扰动关系，不能直接相加概率或把期望路径作为保证。
- 许可/接受须绑定主体、任务和有效时窗，包含已观察/未知/未给出的状态。当前B3要求显式布尔，缺失不可用是正确的；但只有固定agents顺序及静态布尔，尚没有B2任务id或第二次任务重新接受的来源。边界内可以保持原场景声明；正式连接才需要补合同。

### 4. B2模型索引尚不能当真实用户类型推断

- `D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:8`默认replicate=0、population=1；`:25`直接索引20×3组模拟模型，每个population分别拟合，见`D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/experiment.py:65`—`:84`。这些不是从用户特征识别的模型路由结果。
- 现文档明确披露此限制，`D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/README.md:33`、`:53`，不是“当前API暗用未来真值”或“已发生泄漏”。但正式单体能力应用仍缺固定可追踪模型版本、合法适用人群/任务域及未知机制回退。最小合同将replicate/population留作显式研究配置，不能在未知用户请求上默默用默认值代表已验证泛化；不在此次审查扩训练。

## [P2] 复核命令会写回冻结目录，不能当只读核验入口

`D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/README.md:61`—`:66`建议运行verify和audit_results复核；但`D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/verify.py:116`会dump原independent_verification.json，audit_results.py`:76`、`:89`、`:97`会dump原example_output/api_checks/supplementary_audit。`D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/common.py:13`使用write_text可覆盖，不是独占创建。再次执行不等于重训，但可能覆写已有证据；本次没有运行这些命令。最低补充是在新审查目录提供只读结果重算/新输出目标的审计适配，不修改原科学代码。

## 最小补充的验收例，不需要新增研究样本

1. 权限类型6—10例：合法0/1和布尔稳定一致；字符串按合同统一拒绝或正确转义，绝不能将0解释成真。
2. 单个T=120声明的已知EV：现用物理核、B2物理层、B3本地约束在同一固定矩形任务下qmax/能量一致；共享约束仅在组合层收紧。
3. 原5个1min模板逐一审计：原网格任务成功标签、5min功率均值、kWh守恒、回补截止和重采样后任务标签分别列出；不拿重采样成功替代原2min服务定义。
4. 未许可、未知实际接受、已拒绝分别阻断；改变预测接受概率不得改变许可/接受字段。
5. 非本任务域（180min、第二次调用带未偿欠账、任意逐格优化任务）明确unavailable/只供物理层，不悄悄用默认B2概率。
6. B1当前结果不可供当前B2事前预测的时间门；若仅传历史已结束特征，核对availability_time≤decision_time。无益特征可以不传，但应取消“已经接通B1学习链”的表述。

这些是让未来连接可验证的补充建议，不是已实施连接，也不自动授权重开原B1/B2或生成主实验。当前可保留B2单EV模拟原型及B3限定物理组合/反馈原型局部收口；正式完整B1—B3链条、真实可靠性、绿色价值和103验收均不能由这些局部成绩合并推出。
