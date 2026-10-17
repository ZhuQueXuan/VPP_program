# 电动汽车充电设施研究过程入口

2026-10-17 D071证据补强：[六类矩阵](../process_notes/2026-10-17_六类资源四层证据矩阵.md)、[数据要求](../process_notes/2026-10-17_六类资源调研与数据核验要求.md)、[EV分项核对](../process_notes/2026-10-17_EV空调热水箱四层证据核对_分项.md)。现用18发布条目/两冻结协议身份保持，665未越限和Honda AC退步不改。ACN官方字典/作者论文补需求版本与收费规则核查依据，未取会话或开启另一对话候选C；modifiedAt后提交内容不能倒作事前，paymentRequired非报价，收费/服务规则共变不自动识别因果。真实需求、共享容量、控制时点和调节授权分别核，Dortmund/KIT/ACN不拼同车；本轮唯一深入为水箱，无EV新实验。

日期：2026-10-16；现用D058、数据卡DC-20261016-04。EV首轮基础包限定收口；完整现场控制及容量仍待准入。储能、光伏成果保持。

## 当前D058：首轮基础包有限收口

- [最终EV v1.1](../../resource_research_results/ev_charging/README.md)包含独立Dortmund静态映射和KIT记录级分相阶跃特征；[六项范围](../../resource_research_results/ev_charging/results/basic_research_acceptance_v1_1.json)。二者不同对象、不拼接。真实控制时延/容量/需求授权及全体P1未验，下一类型与整合等待用户决定。
- 新源[Zenodo17866847](https://zenodo.org/records/17866847)/[KIT目录](https://publikationen.bibliothek.kit.edu/1000190660)，CC-BY-4.0；422470722字节LF原件MD5通过，24474687行/18记录/16品牌车型组合，9,547变化。名为ns的字段实际TIMESTAMP_MICROS/非UTC调整，按实际20/21ms间隔计算；一处966ms间隙、两目录行数差异保留。
- [冻结协议](kit_step_protocol_v1.json)SHA256 `ad7b9f2dc4a99f7808c61e124394d3766ff6e0cb0b07bb782934d51f5862f9e8`，准入在特征计算前冻结。PREP_KIT_STEPS_01保留28,641候选和全部排除，1,875变化/4,928分相观察，不按速度或误差删点。完整前5后15秒、恒定指令、事前负荷等条件仅允许回顾记录级特征，不是全工况或在线可用性。
- `run_kit_steps.py --run-id <新的唯一ID>`实际完成CHAR_KIT_STEPS_01/02四产物一致；所需原LF在downloads/KIT_LF_SOURCE_01，DuckDB依赖位于work/python_packages/pv_metadata_20261015，路径由kit_common.py管理。4263条观测到90%幅度、665未观测返回空值；仅已观测者上调中位1.113s/下调0.420s，末窗全样本偏差最差10.89A保留。0新增拟合，非预测留出实验或103精度。
- `verify_kit_steps.py`独立准入/布尔连续段及汇总复算113866值或空值通过，共享Parquet解码器。`verify_packaged_steps.py`最终全部4928回放差0、4类非法输入拒绝、无越限空值及两个目录外构造例通过。原D057代码/参数/结果与PV v1.2指纹保持。现用成果results/release_validation_v1_1.json，release_validation.json为v1.0历史（旧README指纹不对应现用版）；核验脚本均拒覆盖原收据。
- 过程记录见work/process_notes/2026-10-16_电动汽车充电设施研究.md文末D058；卡DC-20261016-04。原Dortmund字典/接口/许可缺口并未补齐；KIT作者全文PDF403未取得，不称精确论文复现。EPFL仅字段/开头记录候选审查，分钟级来源不入本轮秒级结果。无GPU/高级模型/整合，新正式报告及handoff不自动更新。



## 前序D057（历史时点）：共同指令同期映射已完成（整体EV研究仍进行中）

- [成果v1.0](../../resource_research_results/ev_charging/README.md)已保留静态公式/15组参数/构造例/聚合结果。不是完整响应或容量模型，官方状态/接口/物理时点与许可仍待核，不猜活动接口或STATE含义。
- [协议](common_command_mapping_protocol_v1.json)误差前冻结，SHA256 `8b3fb1bd4f4aa6fa2ca6cc2e53ec53d77c020d46bc07f07eb5b09aecf56e4c0b`。三接口同一行指令严格相等，原时间高水位/2s连续/5s历史；PREP_EV_MAPPING_01全263283原行/262154合格，1129排除保留。
- `run_mapping.py --run-id <新ID>`已完成BL_EV_MAPPING_01/02六产物同。按15组原时间前半整实验训练/后半评价，20训练103151点/28评价159003点，训练实验等权拟合截顶统计点。MAE1.518949→0.789190/RMSE3.016654→1.687642kW，总体及AC/DC双改善，仅8/15组、14/28实验双改善，Honda AC更差及最差11.524kW保留。不在留出上重调或称新盲测。
- `verify_mapping.py`已独立原CSV/向量时钟、拟合、159003预测及768指标；01/verification.json现用，重复拒覆盖。`verify_packaged_mapping.py`最终全159003点差0、非法/不等输入拒绝、目录外构造例通过，当时发布收据在成果results/release_validation.json（v1.0历史）。
- 04字典/API超时，05系统HTTPS连接超时，失败收据保留。当前静态问题不依赖未确认状态；真实动态、最大/可承诺量、离站/需求/授权及V2G仍未验，若继续须先各自准入。卡DC-20261016-03，过程文末D057；无整合/handoff/高级分支或GPU。



## D056原始来源研究问题与范围（历史时点）

先研究实验室单向充电的“功率指令—电网侧实际功率”关系及其条件，服务正式任务一设备/状态影响和任务二响应能力基础。不把桩额定功率当车辆可承诺功率。缺少事前离站、需求、授权与共享容量证据，暂不研究可移时电量/意愿/站级聚合；V2G另需设备、状态、授权及放电用途的准入，不和单向数据混用。

- 主候选：[TU Dortmund发布记录v2.0.0](https://zenodo.org/records/14065331)，论文[Esser等，Scientific Data 2025](https://doi.org/10.1038/s41597-025-05524-5)，已从[作者大学库](https://eldorado.tu-dortmund.de/server/api/core/bitstreams/62811138-8df5-49fd-8da9-a065cd4e2f98/content)取得12页全文。论文描述实验室静态/动态V1G/V2G及同步G/C记录；作者[配套代码](https://github.com/esserm/charging-postprocessing)用于异步文件后处理，不把它当现成的能力模型。
- 备选：[Caltech ACN官方数据](https://ev.caltech.edu/dataset)更适合后续连接/离站/需求行为；官方API要求注册令牌，未注册或代用户登录，未下载其时序。两来源不同车辆/对象，不拼成同一控制事件。
- 原始merged包以前用于历史研究。本轮重新核对当前发布者MD5 `8459a973f9c196a4f7daa3faf1ee148e`、207735184字节与本地包一致，SHA256 `99e9d10555b01d72b89d60099af57add3d80fd28d75f6a17b945d52eb54cb155`。不声称新盲测、独立新来源或沿用旧模型/成绩。原包未复制/修改/再分发。

## D056原始来源实核结果与重要缺口（持续保留）

官方新取得measurements.csv的MD5 `332378d8e25b2edf808f3f05a610fdc1`一致，实读142条实验目录；merged包含128个CSV、全部完整读到文件末尾/CRC通过。casefold后精确匹配127条，1个Nissan文件未匹配，目录15条无精确merged文件；保留双向差异表，不模糊改名关联。

按文件名可识别65个单向动态文件；其中48个与官方目录精确对应且为EVTEC（25AC/23DC、8车型），共263283原行。48文件指令和电网侧P_kocos_200均为kW，核心功率/epoch无非有限；其他Wirelane为不同字段/电流指令，不混合。全65文件诊断表88353项“P_kocos_200不可用”大部分来自整列不存在，不能表述为88353条传感器丢数。

48个候选中的4组共15处epoch倒序、27处相邻间隙超过2秒；最长间隙400881ms。倒序和间隙留原始，不先排序插值。epoch数量级/间隔符合毫秒解释及论文0.5—1秒轮询说明，但设备更新时间、物理同步和上传可得时刻未独立确认，不能仅由轮询间隔宣称响应时延。

parameters.csv/Zenodo API下载遇SSL握手、超时，网页预览遇429；已有限重试并停止，不绕过限流/关闭证书校验。官方状态码、接口码与数据集单独许可尚待核验，STATE等数值只保留不解释。文章CC-BY4.0不自动代表数据集同许可；原始不再分发。

## D056来源核验程序及复现

- `fetch_sources.py --attempt <新唯一ID>`只读取source_plan_v1.json列出的公开小文件，默认网络01失败、获公开URL网络权限后02取得论文/ACN说明。`retry_zenodo.py`仅一次证书正常验证的兼容重试，03取得measurements.csv，另两项失败保留；遇429停止。不要为重跑覆盖旧attempt或频繁重试。
- `audit_ev_sources.py --run-id <新唯一ID>`逐成员原CSV/单位/时间/字段诊断；现用runs/EV_SOURCE_QA_02。01因遇1个精确目录缺失而失败，failure保留，02将未对应文件明确列出并排除于元数据对应候选，不自动改名或放松匹配。
- `verify_ev_source_qa.py`已用独立pandas读取48候选全部原数据对照stdlib审计，768数值核验、单位/目录/15次倒序/27个间隙一致。核验结果在02/verification.json，重复拒覆盖；仅证实来源/质量，不证实模型、控制或物理校准。
- downloads/runs已忽略Git。过程记录见[充电设施研究记录](../process_notes/2026-10-16_电动汽车充电设施研究.md)，三台账沿现用入口。

## D056当时的下一项与验收方向（历史安排，现用见上）

当前单项是补核官方接口/状态字典及时间异常处理口径，随后才固定样本、实验级训练/留出和透明baseline。不得用全会话事后最大输出识别事前未知接口、把充电器输出DC与电网侧AC混比、把相邻记录随机分到训练/测试，或沿用旧EPFL分位折扣为通用能力。

首轮候选对照为直接把设定当实际功率的透明基线，与仅在训练实验确定参数的简单受限响应模型；具体形式/窗口/阈值须在误差前由数据准入与依据确定，不把候选写成已实现。评价需同样本/信息、MAE与RMSE、逐实验/车种/ACDC、覆盖/失败/最差及复跑；通过后才把最终代码归集resource_research_results/。当前不预建空成果目录、不整合其他类型、不进入高级模型，不更新handoff/教师稿。
