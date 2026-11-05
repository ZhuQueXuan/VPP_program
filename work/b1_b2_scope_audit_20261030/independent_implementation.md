# B1与B2当前实现的独立技术审查

日期：2026-10-30。范围：只读源码、接口、既有说明及模型注册；未导入业务模块、训练或加载模型运行预测，未启动新实验，未修改正式源码、模型、既有实验与报告。本文件为本次分析的工作记录。

## 1. 可直接支持的结论

**B1与B2具有相交的测量、物理和统计工具，但当前主目标、训练标签及交付结果不同，未发现把同一拟合模型换名重复计为两项算法的证据。真正需要澄清的是：新B1与旧b123兼容接口并行，B1当前连续作用没有接入现用B2；B2仍依赖已声明的理想参考和五种执行模板。**

B1职责不能收缩为事后算量，也不能用“凡是预测都归B2”划线。现有B1确实包含事前无任务功率预测、总体连续金额—平均结果查询、旧版按条件查询结果均值。B2的区别在于：面向某个待发方案，在设备、期限、财务、许可等当前条件下预测参加、条件执行和交付，并区分物理上界与承诺。[B1公开入口](D:/myDocu/project_postg/VPP_program/B1算法/b1_api.py:2)、[B1连续目标](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/effects/continuous.py:165)、[B2固定查询入口](D:/myDocu/project_postg/VPP_program/work/b1_b3_stability_20261028/b2_adapter.py:14)。

本审查不采用“B1禁止个体条件因果分析”的规则。总体、分组和条件作用都可属于因素研究；当前具体连续接口标准化到所供事件总体，代码尚未提供新任务个体化的独立冻结因果曲线查询对象。这个实现边界与理论上禁止个体条件分析是两回事。

## 2. 实际调用链与现用版本

```text
正式新B1：B1算法/b1_api.py
  ├─ reference/core.py：fit_reference / predict_reference / save / load
  ├─ reference/ev_selection.py：仅过去非任务历史选择GBDT或历史均值
  ├─ api.analyze_events → process.batch → process.api
  │    └─ RIDE / CPOP / 显式ride_revised → F0与累计/连续特征、原始η
  └─ factors.fit_ev_factor_curve → effects.continuous.fit_continuous_effects
       → 同一任务定义下连续金额的平均结果和对比

根统一兼容入口：b123_api.py → work/b1_b3_stability_20261028/api.py
  ├─ b1_adapter.extract_event → work/b1_research_20261021/features.py（旧F0）
  ├─ b1_adapter.fit_factor/predict_factor → 20261026二元分层均值表
  └─ b2_adapter.predict_single → isolated('bridge') → D122 api/guards
       → legacy_loader.legacy('b2') → work/b2_completion_20261027/api.evaluate
       → dynamic/models.joblib[0][1] + dynamic/selection.json

可选历史研究：work/b1_b2_history_20261028/api.predict_with_history
  ├─ legacy.b1_event → 20261021旧F0，完成的同资源前三次事件
  └─ 当前条件 + 历史统计/PCA/AE → 新六结果预测头，验证选法
```

根加载位置及导出见[b123_api.py:10](D:/myDocu/project_postg/VPP_program/b123_api.py:10)、[D124导出:2](D:/myDocu/project_postg/VPP_program/work/b1_b3_stability_20261028/api.py:2)；旧B1源路径见[b1_adapter.py:22](D:/myDocu/project_postg/VPP_program/work/b1_b3_stability_20261028/b1_adapter.py:22)及[41](D:/myDocu/project_postg/VPP_program/work/b1_b3_stability_20261028/b1_adapter.py:41)；B2隔离加载见[b2_adapter.py:11](D:/myDocu/project_postg/VPP_program/work/b1_b3_stability_20261028/b2_adapter.py:11)、[loaders.py:7](D:/myDocu/project_postg/VPP_program/work/b1_b3_stability_20261028/loaders.py:7)、[D122 guards.py:23](D:/myDocu/project_postg/VPP_program/work/b2_b3_integration_20261028/guards.py:23)、[legacy_loader.py:8](D:/myDocu/project_postg/VPP_program/work/b2_b3_integration_20261028/legacy_loader.py:8)、[D118 api.py:25](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:25)。

正式B1入口首行已说明b123为冻结兼容接口。D124注册明确固定`b2_ev_d118_dynamic_r0p1`，历史分支未采用，非对新查询选一个最好的重复。[registry.json:2](D:/myDocu/project_postg/VPP_program/work/b1_b3_stability_20261028/registry.json:2)。当前显式`ride_revised`已加入正式B1，可选调用；默认仍由旧分辨率配置决定，不能把修复版当默认或当B2新预测器。[process/api.py:16](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/process/api.py:16)、[_policy.json:4](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/process/_policy.json:4)、[最新修复说明:5](D:/myDocu/project_postg/VPP_program/work/b1_template_repair_20261030/README.md:5)。

## 3. 输入、输出与拟合对象

|部分|真正输入/拟合标签|真正输出与适用解释|
|---|---|---|
|B1无任务参考|事前前缀、已完非任务历史均值、日历温度、严格可得时点；训练目标是历史非任务功率|未来各格无任务功率预测，`counterfactual_identified=False`；不是本次参加概率。见[reference/core.py:23](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/reference/core.py:23)、[220](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/reference/core.py:220)、[249](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/reference/core.py:249)。|
|B1单事件过程|已发生的任务、完整实际功率、同身份同格参考、名义噪声、测量配置|原始η、拟合/原始观测过程特征和曲线；输出的`prediction`是对已观测事件的曲线拟合，不是提前预测新EV会执行哪条曲线。见[api.py:28](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/api.py:28)、[process/api.py:93](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/process/api.py:93)。|
|B1当前因素与连续作用|多个已完同定义事件、同身份因素、因素状态及可得时点、实际发出金额、声明DAG/调整假设、连续设计与支持域|按所供总体等事件权重的金额→平均结果和相对参考金额差；条件不确认只报标准化关联。默认因素结果是累计有效响应秒数，也支持最长连续秒数与原η。见[factors.py:18](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/factors.py:18)、[102](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/factors.py:102)、[173](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/factors.py:173)、[continuous.py:217](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/effects/continuous.py:217)。|
|B1可选无功率参考作用|多个已完任务的实际电量、请求功率和时窗、因素与金额|负归一化实际用电的作用；绝对值不等于净交付或容量；对比与净交付对比等价另需参考不随处理变化。见[metered_effects.py:1](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/metered_effects.py:1)、[49](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/metered_effects.py:49)。|
|B2物理层|当前平坦充电参考`b`、声明离站剩余时长`T`、请求`q`，限定需求`E=bT/60`|单EV物理任务上界和可行性；既有资源约束核给出物理结果。见[physical.py:8](D:/myDocu/project_postg/VPP_program/work/b2_single_ev_baseline_20261026/physical.py:8)。|
|B2选择+条件执行|当前`b,T,q,E`、风险方案`low/high/prob`、收益参考点`reference`、绿色偏好/属性、risk、已有许可；训练标签为已发方案的实际选择`A`和接受后的动态状态|参加概率、条件状态/服务概率、期望kW/kWh与轨迹、五条条件情景和回补。可承诺量为null，真实接受另为硬门。见[D118 api.py:9](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:9)、[25](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:25)、[36](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:36)。|

当前B1连续函数每次`fit_continuous_effects(X,treatment,outcome,users,...grid...)`重新作用户交叉拟合和曲线计算，返回数值结果与诊断；其公开入口没有独立的连续作用模型保存/加载/对新查询对象预测协议。B1参考模型另有独立save/load/predict，旧b123也有`predict_factor`查询条件均值表，因此应只说“当前连续因素函数尚缺独立冻结模型查询”，避免泛称“B1不能预测”。[continuous.py:85](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/effects/continuous.py:85)、[165](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/effects/continuous.py:165)、[207](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/effects/continuous.py:207)、[B1导出:16](D:/myDocu/project_postg/VPP_program/B1算法/b1_api.py:16)、[旧条件查询:45](D:/myDocu/project_postg/VPP_program/work/b1_b3_stability_20261028/b1_adapter.py:45)。

## 4. 相似或重复部分应怎样判定

1. **F0是实际复用。**新B1的`process/_frozen_f0.py`与20261021原F0字节SHA相同：`c722dc3d03510e847be48d50f4a5dbce62f8f8cc11ae1d8ef1de05a126c8f0b7`。根兼容B1和可选历史分支调用旧路径，正式新B1调用包内副本。这是共享测量算子；它们没有各自训练一套预测模型。
2. **设备物理核心共享，用法不同。**B2调用既有EV-CAP-v1的`evaluate`校核方案可行性。新B1恢复核仅调用同一核心的`prepare`作声明校验，并对实测功率积分；代码明确不调用优化轨迹代替已发生响应。两者不应重复声称发明EV物理模型。[B2 physical.py:5](D:/myDocu/project_postg/VPP_program/work/b2_single_ev_baseline_20261026/physical.py:5)、[16](D:/myDocu/project_postg/VPP_program/work/b2_single_ev_baseline_20261026/physical.py:16)、[B1 ev.py:66](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/resources/ev.py:66)、[100](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/resources/ev.py:100)。
3. **同为回归/logit不等于研究重复。**新B1连续结果辅助模型是样条/Ridge拟合结果，剂量模型拟合金额的条件密度，形成DR伪结果；它没有拟合本次愿不愿参加。B2选择模型拟合已发方案的`A`，执行多项logit拟合接受后的五状态。B1的参与节点目前是DAG中的处理后中介；父集筛选只筛金额分配子图，不是B2意愿模型。[continuous.py:98](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/effects/continuous.py:98)、[107](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/effects/continuous.py:107)、[factors.py:97](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/factors.py:97)、[206](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/factors.py:206)、[B2 experiment.py:68](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/experiment.py:68)。
4. **两个“模板”拟合对象不同。**RIDE在已提供的`reference-actual`曲线上优化时间/幅度、比较BIC；B2先规定五条30分钟执行模板，只学习新方案属于哪条模板的条件概率，并给出混合预测。前者不提供新任务五状态预测，后者不对未知参考下的任意实测事件重新识别形状。[RIDE修复:104](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/process/_ride_revised.py:104)、[B2模板:14](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/generate.py:14)、[B2预测:27](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:27)。
5. **B2内部多模型有合法对照用途。**普通效用、前景、固定非线性比较选择机制；标量与动态比较执行表述。动态轮对相同新训练分区重新拟合是独立研究轮的设计，不是B1重做。是否具有增量须看各自目标和负结果，不能按模型数认定原创项数。[experiment.py:35](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/experiment.py:35)、[61](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/experiment.py:61)、[README:15](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/README.md:15)。
6. **历史研究确实新增六结果头，但未替换默认。**D123使用相同当前输入，比较不加历史/6统计/PCA6/AE6；前三次完整事件由旧F0提取，当前事件事后曲线不入预测。六结果把拒绝和五种接受状态统一概率化，是预测增量研究，不是再估连续因果曲线。其rep0验证选C0，PCA/AE未采用；默认D124仍D118权重。[history/features.py:21](D:/myDocu/project_postg/VPP_program/work/b1_b2_history_20261028/features.py:21)、[history/models.py:16](D:/myDocu/project_postg/VPP_program/work/b1_b2_history_20261028/models.py:16)、[history/api.py:53](D:/myDocu/project_postg/VPP_program/work/b1_b2_history_20261028/api.py:53)、[README:13](D:/myDocu/project_postg/VPP_program/work/b1_b2_history_20261028/README.md:13)。

## 5. 容易误接的同名字段与合同差异

|字段/表述|当前具体含义与误读风险|
|---|---|
|B1 `reference`、`reference_kw`|同任务同格的无任务功率参考，单位kW；B1参考预测不等于已识别真实反事实。|
|B2 `reference`|收益评价的心理参考点；`low-reference`、`high-reference`和不参加的`-reference`进入风险价值函数。不是功率曲线。见[choice_model.py:10](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/choice_model.py:10)。|
|B2 `low/high/prob`|同一个待发风险方案的两种收益结果和高结果概率；期望是`low*(1-prob)+high*prob`，不是B1高/低金额两处理档，也不是估计倾向概率。见[choice_model.py:19](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/choice_model.py:19)。|
|B1 `reference_dose` / `reference_incentive`|作用曲线的对比金额；属于处理剂量基准。与上述两种reference都不同。见[continuous.py:192](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/effects/continuous.py:192)、[218](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/effects/continuous.py:218)。|
|`q`、`T`、时窗|q均为请求kW，但新B1显式任务时长自由配置，B2当前固定30分钟服务、q1.5/3、T60/90/120，T是剩余连接期限；B3站级180分钟不等于B2行为支持180分钟。见[D118 api.py:22](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:22)、[D124 controller.py:11](D:/myDocu/project_postg/VPP_program/work/b1_b3_stability_20261028/controller.py:11)。|
|`cumulative_response_seconds`|新B1默认阈值为`onset_fraction=.1`乘q，累计满足阈值的格；最长连续另算，驻留仅作用于最长连续。见[ev.py:19](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/resources/ev.py:19)、[process/api.py:79](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/process/api.py:79)。|
|`cumulative90_s`、`cumulative90_min`、`continuous90`|旧根B1新增字段与B2桥接指标是90%q判据。B2桥接确实另写`fine_features`公式，并以“2分钟内到90%、连续28分钟、末格活跃”判service30。不是新B1默认10%q累计时长。见[b1_adapter.py:25](D:/myDocu/project_postg/VPP_program/work/b1_b3_stability_20261028/b1_adapter.py:25)、[bridge.py:99](D:/myDocu/project_postg/VPP_program/work/b2_b3_integration_20261028/bridge.py:99)。|
|累计/连续、速度|B2五模板无退出重入，所以当前两类90%持续数值相同；新B1允许间断，二者可不同。B1F0起点是观测格区间，B2首次达到是模板混合下条件期望；不能当同一物理延迟。见[D118 api.py:43](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:43)、[F0 features.py:83](D:/myDocu/project_postg/VPP_program/work/b1_research_20261021/features.py:83)。|
|参加/许可/因果零作用|B1DAG参与是金额后的中介，阈值检测不推断实际参加；B2许可是发送硬门，A是实际选择，接受概率不授权；零作用允许有动作。不可用一个0/1统一代替。见[factors.py:97](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/factors.py:97)、[D118 api.py:47](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:47)、[最新比较说明:23](D:/myDocu/project_postg/VPP_program/work/b1_template_repair_20261030/README.md:23)。|

桥接`fine_features`确有90%阈值、累计/最长连续和能量的再次编码。它在B2/B3评价里生成同定义标签和核对结果，属于可统一的共享判据；重复几行阈值公式本身不能支持“重复建同一算法”的结论。现阶段应保留口径差异，未来抽公共测量函数时需要显式阈值、驻留、单位、任务成功标准，不能直接拿一个同名字段替换。

## 6. 已存在的接口边界与尚未发生的设计风险

**事实A：新B1连续作用目前没有被现用B2消费。**在D118、D122、D123、D124的Python源码中检索`b1_api/b1_algorithm/fit_continuous/estimate_event_curve/fit_ev_factor_curve/causal_curve`均未发现新B1连续调用；逐段动态加载也指向旧F0与旧B2。D123接通的是合法历史测量，不是新B1因果曲线。不能据“B1→B2历史已接通”写成“研究点一新连续因素链已进入容量预测”。

**事实B：B2当前理想参考与新B1未知参考研究尚有差距。**B2以已给定平坦b为基准，模拟器直接生成`event_power=b-q*template`及完全回补，预测也使用b；标签由生成状态直接得到。它没有消费新B1的预测参考误差、RIDE/CPOP测量及其不确定性。B2在这个域的成绩不能证明未知参考下整链可靠。[generate.py:38](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/generate.py:38)、[api.py:30](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/api.py:30)。

**事实C：B2剩余需求门保持实际状态，支持域会拒答。**D124输入`E=b*remaining_T/60+actual_debt`；正欠账超出冻结行为族明确不可用，T30/180不外推。B3对原回补另有授权时可以重排实际控制，原预测只保留为预测/见证。这是既有范围边界，不能靠把时间归零或抹欠账伪造接通。[b2_adapter.py:27](D:/myDocu/project_postg/VPP_program/work/b1_b3_stability_20261028/b2_adapter.py:27)、[controller.py:1](D:/myDocu/project_postg/VPP_program/work/b1_b3_stability_20261028/controller.py:1)、[125](D:/myDocu/project_postg/VPP_program/work/b1_b3_stability_20261028/controller.py:125)。

**未来设计风险D：重复乘参加概率。**B1默认总体为`all_supplied_invited_EV_events`，流程不按参与筛样本，金额作用可经参与中介进入结果；因此所得总体平均结果已经包含拒绝/无动作等事件贡献。若未来直接把这条无条件曲线当作“接受后的交付”再乘B2参加概率，会重复计入参与。只有先明确定义条件于参加的结果、目标人群、因果目标和可识别条件，或把曲线仅作可评估的辅助信息，才可设计融合。当前源码未接该曲线，故本项是设计风险，不是已发生bug。[factors.py:25](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/factors.py:25)、[102](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/factors.py:102)、[197](D:/myDocu/project_postg/VPP_program/B1算法/b1_algorithm/factors.py:197)。

“B2必须消费B1每一个输出”也缺乏支持。共享测量与物理约束可以复用；历史/表示/因素曲线是否作为预测增量，应有目标和数据支持。D123负结果支持当前不默认采用该历史分支，不能外推为所有历史或因果信息都无价值。[history/README.md:62](D:/myDocu/project_postg/VPP_program/work/b1_b2_history_20261028/README.md:62)。

## 7. 已有B2/B3与当前B1主线的关系

根据用户所给AGENTS协作记录，B2启动、两项主要功能补强、B3有限组合、反馈、B2/B3联调、历史增量及前三算法稳定性均有当时用户授权；D118说明也明确按用户“继续”实施。它们是已授权的并行研究资产，不能仅因当前重新聚焦B1就倒推为全部越界。代码审查只能核实现了什么，无法独立认证历史对话授权，授权判断依据本轮用户提供的记录。[D118 README:3](D:/myDocu/project_postg/VPP_program/work/b2_completion_20261027/README.md:3)。

当前研究点一的六步B1主线仍应独立判断完成度。已有B2/B3只能证明各自有限域的预测、联调或控制功能，无法替代B1连续敏感性/候选阈值/独立冻结查询/目标匹配时序用途/新独立EV全链比较。本审查不启动任何一项缺口，也不建议为串联形式把未获稳定收益的历史/PCA/AE强制设为默认。

## 8. 仅供决策的建议

1. 文档用“测量结果/因素作用”“待发任务预测/物理能力”“共同约束协调”分别写清B1/B2/B3的交付；允许共享输入和工具，不以事前/事后一刀切。
2. 对外保留明确版本：正式新B1入口、旧b123兼容B1、固定B2模型、可选D123历史。不能把它们的成果合并成一条已完成的新算法链。
3. 将`power_reference_kw`、`payoff_reference`、`contrast_incentive`和10%/90%阈值口径显式区分。若未来实施共享测量模块，先冻结共同结果定义再复用。
4. 下一步是否共享新B1因素曲线到B2，应先选用途：校验已有预测的金额敏感性、作辅助特征/约束，或另定义条件作用。当前不具备把总体曲线直接当单体可承诺容量的依据。

以上为建议，不视为新开发或实验授权。

## 9. 只读核查记录与主张强度

- 确认源码调用链、字段定义、默认路由、模型注册、历史分支选择；这些是直接实现事实。
- 读取D124注册时，B2模型SHA为`67401e56c9aeb0a40af38366d95fcb6b4436f99f3f66c58f22f6268e7a863e2e`、选择SHA为`ca37e8d583be64ba43fbcb3e3983d2696150fd85b95f8ff18d5990208bf9420b`，本轮实际文件散列与注册相同。
- F0两路径SHA相同，支持代码字节复用；不据此推出新旧全部测量配置或全部算法输出等价。
- 未运行训练/预测/实验，也未复算既有性能数字；本审查不提供新的数值正确性或真实场景有效性证明。
- “未发现重复训练同一模型作为B1/B2两项贡献”限于上述实际当前实现与指定研究分支；“融合可能重复计参加概率”为未来设计推论，当前未复现该bug。

