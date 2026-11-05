# CrowdCharge 计量口径有限复查

2026-11-04。发布方原计量字典及试验报告 §6.5.2 说明 `MaxAmpsUsed` 是车辆电流，量纲 A。`AmpsAllocated` 是桩端解释的限额，`CC_Amps_Allocated` 是后台计算限额。报告脚注列出取整以及电流值与百分比换算作为差异来源。控制器更新前按连接状态每分钟报送，更新后充电态每分钟、连接但未充电态每半小时。 [官方字典](https://commercial.nationalgrid.co.uk/downloads-view/81670) · [试验报告](https://eatechnology.com/media/girhcnsc/electric-nation-customer-trial-report.pdf)

按字段名、设备和试验名作一次定向搜索，未找到能同时连到本次 CrowdCharge 数据导出列和设备版本的统计区间、瞬时/汇总、相别及计量精度说明。GreenFlux 的三分钟文字定义不能借给 CrowdCharge。字段原小数位只描述存储格式。采用绝对记录电流及带符号记录变化，物理限流模型和误差门继续暂缓。两列分钟时间戳也未提供真实下发与收发回执。 [R1-A 原件核查](../b1_factor_round2_admission_20261104/README.md)
