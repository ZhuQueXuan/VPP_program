# Optimise Prime｜Royal Mail 车库试验准入

**0 个补偿比较事件准入。** WS2 的原表把一个车库日计划里的事前计划价、实际下发的调度和实测车库 EV 负荷接到了同一时窗。六个连续半小时都来自这一份计划。缺成交费率、同类任务的可比分配和全体分母，尚不能估计提高补偿带来的增量。[原试验附录第2节](https://d1oyzg0jo3ox9g.cloudfront.net/app/uploads/2023/10/PR_OP_Deliverables_D7_Appendix-1-Use-of-EV-flexibility-by-DNOs_Ver1.1.pdf) · [字段审计](source_audit.json)

Product A 提前签订选项后按需调用。报告记录 8 个车库 305 次减载事件，通常持续 2–3 小时。Product B 是日前竞价及计划，报告记录 7 个车库 404 场事件、涉及 303 辆车，每日计划分成 48 个半小时。调度片段属于同一计划，不计为独立分配。两产品的预告、出清、时窗、结算参照和支付结构都不同，不能将其作为同一任务的两个价格组。报告表4中 £326.33 和 £120.70/MWh 是按历史市场费率计算潜在收入的基准。报告另列试验价口径，尚无逐事件合同费率或支付台账可核。[原试验附录第2.2、2.3节](https://d1oyzg0jo3ox9g.cloudfront.net/app/uploads/2023/10/PR_OP_Deliverables_D7_Appendix-1-Use-of-EV-flexibility-by-DNOs_Ver1.1.pdf)

发布方目录转到登录页，发布方同步的目录说明给出了公开只读 Azure 发布通道。通过该通道实读 WS2 的 23 个目录。表25/26为计划和调度，表27为车库 EV 实测负荷，表30/31为执行摘要。目录没有独立的合同价或所有分配对象表。车库负荷汇总也无法替代桩级响应或车辆分配名单。[发布方指南](https://ukpowernetworks.opendatasoft.com/api/datasets/1.0/ukpn-optimise-prime/attachments/202302_op_deliverables_d6_dataset_guidance_v4_pdf/) · [发布目录回执](release_directory.json) · [CC BY 4.0 目录记录](https://open-data.org.uk/dataset/ukpowernetworks/ukpn-optimise-prime)

原表25的 Product B 计划包含指南示例未列出的 `utilisationPrice`。车库 8 在 2021-11-04 11:25:40 UTC 录入 83.1，13:17:27 更新为 144。2021-11-07 15:34 前后下发次日 00:00–03:00 UTC 的六个半小时片段，每段找到 5–6 个原始计量时点。83.1 和 144 是同一批窗口的一次计划修订，不形成两个报价组。D2 报告以 £/MW/h 表述产品费率，表25字段自身未声明单位，也未核到计划价就是清算价或最终结算。D2 表16说明试验调度需求为人工拟定，表26保留了试验中的实际指令。三个 A 摘要窗也能连计划、调度和实测，小样中的 A 计划没有价格字段。[三表追踪及源行](trace_checks.json) · [D2第3.1.2.2节及表16](https://d1oyzg0jo3ox9g.cloudfront.net/app/uploads/2023/10/OP_Deliverables_D2_Ver_1.1.pdf)

原表30/31分别有 655 和 21,490 行。A、B 完全重复的额外行分别为 151、6,646。B 有 6,452 行起止相同、202 行结束早于开始。CSV 行数不能替代报告的执行事件数。表27的七个定长字节片段共 9,688 条完整行，其中 901 条无可核时间，含 287 条零读数。另有 2,575 条零读数带时间戳，仍需用状态判断实际零。按同车库及明确时间偏移联接出 A 3 窗、B 48 个计划片段的计量交集，其中上述 6 个片段具备正值计划价和同起点调度。此处只核联接和覆盖，没有积分或比较用电。[计量检查](sample_checks.json) · [联接明细](technical_matches.csv) · [原表散列](source_bytes.json) · [切片散列](meter_window_bytes.json) · [计划与调度散列](trace_bytes.json)

表27字典写无时区，已核有时间的原表样本实际带 UTC 偏移。六个半小时片段的最大间隔约 6–10 分钟，仍需核全窗口数据。若后续审查单桩执行，可沿调度和车库负荷连接桩、插座、RFID 和生效时点的资产版本。桩端功率以 kW 计，限流以 A 计。桩端变化报文会去重，缺行、通信中断、无效读数与有状态证明的零须分别处理。竞标计划或近五个合格日同窗均值可用于复算结算。单车未控功率、报价前需求和计划离站还需补证。[发布方指南第3节](https://ukpowernetworks.opendatasoft.com/api/datasets/1.0/ukpn-optimise-prime/attachments/202302_op_deliverables_d6_dataset_guidance_v4_pdf/)
