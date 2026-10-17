# 储能组件数据与baseline入口

2026-10-17 D071证据补强：[六类矩阵](../process_notes/2026-10-17_六类资源四层证据矩阵.md)、[调研要求](../process_notes/2026-10-17_六类资源调研与数据核验要求.md)、[储能分项核对](../process_notes/2026-10-17_储能光伏风电四层证据核对_分项.md)。现用15条发布身份一致，三原组件/容量失败保持。下一控制证据候选为同站BESS请求/执行—LMO1设定的字段/时钟核查；需另准入成员、模式/插值与送达生效，当前未启动。经济层另核真实合同传导/报价，选择层区分运营决策/EMS策略/设备闭锁，不为自动系统机械问卷。本轮唯一深入对象为原水箱，未并行开启储能新实验。

**D047成果代码入口：**[根目录资源研究成果](../../resource_research_results/README.md)／[锂离子储能最终组件](../../resource_research_results/lithium_ion_storage/README.md)。本目录继续保存研究过程、旧实验和复现依据；最终目录仅保留计算代码、必要参数、使用样例和结果摘要。后续先逐类研究，跨资源整合待用户确认。`package_storage_results.py`及`verify_packaged_storage.py`仅负责本次工程组装/回放，留在本过程目录，不纳入成果。

D045现用配图：[模块关系PPT](../../outputs/课题一_储能模块关系图_可编辑版_v1_20261015.pptx)，源代码及核验位于`../teacher_storage_brief_20261015/ppt_relationship_build/`。图中实际输入和并行解释证据分开，无反向校正；D043线性版为历史。

D043配图入口：[单色可编辑研究框架PPT](../../outputs/课题一_储能研究框架_可编辑版_v1_20261015.pptx)。现用PNG由PPT导出；单色图生成及核验入口为`../teacher_storage_brief_20261015/ppt_build/`，D042彩色绘图脚本仅追溯。

D042仅更新汇报图文：现用图1为全文研究框架，原方法图保留为历史；已同步重写[简要讲解稿](../../outputs/课题一_锂离子储能成果汇报_简要讲解稿_v1_20261015.md)。研究与实验状态不变，见现用成果汇报。

本目录保存P1组件baseline过程。最新D046（2026-10-15）已恢复研发，按单类基础包有限验收；固定公开2RC参数的电压对照、同版本复跑及独立参照/指标复算完成，储能首轮基础包按限定范围收口，可接下一类型准入，见EXPERIMENT_LOG。系统01容量失败与D039诊断保持，不再无限推进端点排查。现用汇报/handoff不改，多类型P1/90%未完成。以下旧“停止实验/下一端点组件”只记录当时安排。


## 公开参数2RC电压模型受限复现（D046）

- [验收边界/执行过程](../process_notes/2026-10-15_单类资源验收边界与储能论文复现.md)、[论文代码核查](../process_notes/2026-10-15_储能论文代码复现路线候选核查.md)、[冻结协议](blyth_voltage_protocol_v1.json)。
- 运行：`run_blyth_voltage.py --run-id <新的唯一ID>`，使用固定下载目录内作者model.py与原始WLTP导出行；主代码从自身位置找项目根，不依赖cwd。需要现有plot_dependencies的NumPy/pandas及`work/python_packages/storage_ecm_20261015`的SciPy1.16.2。源文件不齐时不自动替换版本。
- `inspect_blyth_source.py` / `download_blyth_minimal.py` / `download_blyth_validation.py`是本次有上限的固定来源取得记录，目标存在时停止，不能当作自动重复抓取所有网络材料的入口。下载后逐份Git blob/长度/SHA256核对；GPLv3声明随作者文件保留。
- `audit_blyth_wltp.py`正确读取原工作簿错误维度并导出395302源行；`prepare_blyth_validation.py`抽25℃并在误差前保存协议，现有协议不覆盖。作者demo输入不同，不混用评分。
- `verify_blyth_voltage.py`独立stdlib复建源行导出表的整数秒参照及误差、检查复跑指纹与旧材料保持；不是独立模型重解。全部原始/预测/收据在已忽略`downloads/blyth_ecm_20261015/`。
- 首次ID `BL_BLYTH_VOLTAGE_20261015_01`：79058点，MAE7.733327→4.597734mV，RMSE13.432776→8.378924mV；最差2RC265.958311mV在末秒。只支持已知电流/初值、25℃等温放电下的参考比较，不认定SOC/容量/未来功率或现场部署精度。复现ID02及最终核验见台账。

## 8端点上下文诊断及有限阶段收口（D039）

沿[冻结协议](home_endpoint_context_diagnostic_protocol_v1.json)实际执行四事件原选8点，不改端点/窗口/阈值/容量成绩。以下ID已使用，重跑须换唯一ID；产物在已忽略的downloads/rwth_home_endpoint_context_20261015/。

```powershell
python audit_home_endpoint_contexts.py --run-id QA_HOME_CONTEXT_20261015_01
python verify_home_endpoint_contexts.py --audit-run QA_HOME_CONTEXT_20261015_01 --verification-id VERIFY_HOME_CONTEXT_20261015_01
```

独立stdlib从原CSV核对70497上下文/守卫行、6个原始月成员指纹和8点全部诊断量/方向/活动与静置最大性，最大差8.673617379884035e-19<1e-9。紧邻段不代表整个前序充放周期，观测起点不代表物理控制起点；2019低端静置右删失，其他完整阈值静置也不证明平衡OCV。没有容量标签读取、新预测/指标/参数拟合或SOC筛选。

冻结协议中的not executed仅是冻结时快照，实际执行以本节/收据为准，不回改。阶段收口限于跨期比较和适用边界诊断；整体P1/90%未通过。按用户要求停在节点，汇报v2新增图6但沿用旧成绩；下一物理端点组件准入/验证未启动，handoff不改。

## 结束依据来源核查（D038，2026-10-15）

acquire_home_endpoint_sources.py仅补取两份此前超5MB上限的出版方工作簿，单份上限25MB；下载、失败、源/代码指纹记录在downloads/rwth_home_endpoint_evidence_20261015/，该目录已忽略Git。源表02/04放新日期目录，旧失败/已有源文件不覆盖。下列ID已使用，重跑须换唯一ID，下载器还拒绝覆盖已有工作簿。

```powershell
python audit_home_endpoint_sources.py --run-id QA_HOME_ENDPOINT_20261015_01
python verify_home_endpoint_sources.py --audit-run QA_HOME_ENDPOINT_20261015_01 --verification-id VERIFY_HOME_ENDPOINT_20261015_02
```

8工作簿40页签/391表头、两表各60测试键及Fig3示例时间独立核验通过；01日期表示转换失败已保留，02只修正读者返回datetime的处理，数据/预期不改。相关PDF11/12页已渲染核对。没有找到2019该次精确结束/SOC/EMS停止日志，仅限定已核查来源；不否定出版方容量标签或全数据集用途。对现有来源查找收口，旧成绩/handoff/老师稿不改。

下一项[8端点上下文诊断协议](home_endpoint_context_diagnostic_protocol_v1.json)已冻结、未执行：原端点/窗口保持，检查前序方向/吞吐量/静置及质量/删失，不设SOC阈值重选/重评或拟合OCV。不要把冻结协议写成实际结果。

## 2019受控附近记录诊断（D037，无新容量积分或成绩）

[诊断协议](home_test_record_diagnostic_protocol_v1.json)复用v3原24h窗口，针对性通道分析前冻结；旧质量/参照已见，回顾诊断。产物在已忽略的downloads/rwth_home_test_record_diagnostic_20261014/。下列ID已使用，复跑换新唯一ID；诊断/核验/绘图均拒绝覆盖。

```powershell
python audit_home_test_records.py --run-id QA_HOME_TESTREC_20261014_01
python verify_home_test_records.py --audit-run QA_HOME_TESTREC_20261014_01 --verification-id VERIFY_HOME_TESTREC_20261014_02
python plot_home_test_records.py --audit-run QA_HOME_TESTREC_20261014_01
```

原始48118行/193阈值状态段、3时段×2质量口径和起点上下文独立核验通过，最大差1.776356839e-15；02在已通过01上补充起点汇总/上下文核验，01保留，不称新模型复跑。图逐秒/断档断线/插值标记且已目视检查。数值变化间隔不等于采样率；不能统一乘倍数、移位或据电流回零造SOC/测试结束。作者加载器只读检查，未执行；BMS耗能计量文字边界见过程记录D037澄清，未补偿容量。

## 2019失败片段量测与端点诊断（D036，无新模型成绩）

产物在已忽略Git的downloads/rwth_home_local_span_20261014/failure_diagnostics/。下列ID已使用，复跑须换新唯一ID；图脚本固定绘制01且拒绝覆盖收据，重绘需显式另设输出。诊断全块而非据曲线挑窗；P积分仅检查口径差，不改原UI预测。来源页码/方法边界与下一项见过程记录D036节。

```powershell
python audit_home_2019_failed_span.py --run-id QA_HOME_FAILURE_20261014_01
python verify_home_2019_failed_span.py --audit-run QA_HOME_FAILURE_20261014_01 --verification-id VERIFY_HOME_FAILURE_20261014_01
python plot_home_2019_failure.py
```

VERIFY_HOME_FAILURE_20261014_01逐原始字段/积分/静置/极值复算12188行通过，最大汇总差2.220446049e-16；failed_span_curves.png已目视检查。6秒变化间隔不等于采样率/时钟倍数，I=0而P非0也未判定固定滞后或故障。作者方法还有吞吐量/松弛模型/系统偏置条件；不能移植其他系统参数调本次成绩。

## 同块完整区间候选（D034/D035，回顾探索/失败保留）

[候选协议](home_capacity_local_span_protocol_v1.json)在新积分/评分前冻结。`freeze_home_local_span_protocol.py`已执行，拒绝覆盖。四事件原窗口/阈值/净I/UI保持，缺口重置、块首左删失端点不配对、只用同块完整区间；时龄只报告不调阈值。设计已见参照和2019端点，不称盲测。

以下ID已使用，复跑须改新唯一ID。产物位于已忽略的downloads/rwth_home_local_span_20261014/samples/及baselines/，与原方法分开。8份样本/5份比较产物分别复跑一致，VERIFY_HOME_LOCAL_20261014_01原始独立重建四历史及原XLSX/32行结果通过1e-9，失败保留，不作为物理能力验证通过。

```powershell
python prepare_home_local_span_samples.py --run-id PREP_HOME_LOCAL_20261014_01
python prepare_home_local_span_samples.py --run-id PREP_HOME_LOCAL_20261014_02
python run_home_local_span_baselines.py --run-id BL_HOME_LOCAL_20261014_01 --sample-run PREP_HOME_LOCAL_20261014_01
python run_home_local_span_baselines.py --run-id BL_HOME_LOCAL_20261014_02 --sample-run PREP_HOME_LOCAL_20261014_01
python verify_home_local_span_baselines.py --first-sample PREP_HOME_LOCAL_20261014_01 --repeat-sample PREP_HOME_LOCAL_20261014_02 --first-run BL_HOME_LOCAL_20261014_01 --repeat-run BL_HOME_LOCAL_20261014_02 --verification-id VERIFY_HOME_LOCAL_20261014_01
```

模型B_LOCAL_SPAN四次给数，但2019大幅低估，旧B_HIST_SPAN的2019两量仍缺预测，4个B_DS Ah仍不支持；全部32行及6项不可用保留。不要把覆盖4/4当精度或方法改进，也不要把失败原因先归咎于时龄/SOC/老化/量测错误。以下各节为旧版本研究证据，旧失败/协议/成绩不回改。

## 2019固定窗口缺口诊断（D033，现用过程）

`audit_home_third_history_gaps.py`只读取v3固定历史，切分原秒连续块，各块独立确认静置/锚点及高低端点，不跨缺口、不积分、不读出版方标签或评分。块首静置真实起点未知者标左删失，不能冒称完整静置起点。结果/收据在已忽略Git的downloads/rwth_home_third_test_20261014/gap_diagnostics/，不写入旧样本目录。

以下ID已使用，复核换新唯一ID。两次9份产物一致，独立stdlib原始重建七表/统计通过（锚点电压差0），没有新容量成绩；下一步是先冻结片段候选新协议，不能给2019直接补分。

```powershell
python audit_home_third_history_gaps.py --run-id QA_HOME_GAPS_20261014_01
python audit_home_third_history_gaps.py --run-id QA_HOME_GAPS_20261014_02
python verify_home_third_history_gaps.py --first-run QA_HOME_GAPS_20261014_01 --repeat-run QA_HOME_GAPS_20261014_02 --verification-id VERIFY_HOME_GAPS_20261014_01
```

## 第四次事件v4（现用，D031/D032）

[冻结协议v4](home_capacity_crossperiod_protocol_v4.json)，历史2022-10-17 00:38:48至10-28 15:02:27前，1002219秒/48h；原静置阈值/配对/净I/UI和三对照保持。`freeze_home_fourth_test_protocol.py`及`acquire_audit_home_fourth_test.py --attempt ACQ_HOME_FOURTH_20261014_01`已完成线上索引/目录重核和10月单成员CRC/SHA/质量核验；目录downloads/rwth_home_fourth_test_20261014已忽略Git，拒绝覆盖，不直接重跑获取/冻结。

125锚点、2个配对中1因26插值失败/1合格，按最近合格选择10-27 13:48:13—18:15:21；73缺高端保留。样本8份/结果5份复跑一致，原始全历史重建和区间/XLSX独立复算通过1e-9。以下命令已实际运行，ID已用；复跑使用新唯一ID并同步各参数，原始数据及冻结协议不覆盖。Python环境同前，脚本按自身位置定位。

```powershell
python prepare_home_fourth_test_samples.py --run-id PREP_HOME_FOURTH_20261014_01
python prepare_home_fourth_test_samples.py --run-id PREP_HOME_FOURTH_20261014_02
python verify_home_fourth_test_samples.py --first-run PREP_HOME_FOURTH_20261014_01 --repeat-run PREP_HOME_FOURTH_20261014_02 --verification-id VERIFY_HOME_FOURTH_20261014_01
python run_home_fourth_test_baselines.py --run-id BL_HOME_FOURTH_20261014_01 --sample-run PREP_HOME_FOURTH_20261014_01
python run_home_fourth_test_baselines.py --run-id BL_HOME_FOURTH_20261014_02 --sample-run PREP_HOME_FOURTH_20261014_01
python verify_home_fourth_test_baselines.py --first-run BL_HOME_FOURTH_20261014_01 --repeat-run BL_HOME_FOURTH_20261014_02 --sample-run PREP_HOME_FOURTH_20261014_01 --sample-verification VERIFY_HOME_FOURTH_20261014_01 --verification-id VERIFY_BL_HOME_FOURTH_20261014_01
```

`summarize_home_four_test_checks.py`已从现用4个事件逐模型产物生成本地four_event_summary_01.json，保留缺预测、不新增平均/准确率；旧事件成绩不变。下一单项为2019缺口与连续子段质量诊断，先不改方法或补预测；有方法变化另冻结协议。以下各节为旧版本运行入口，其“先交接/未取得”等描述按D030/D032更新理解，保留历史追溯。

## 第三次事件v3（冻结保留，D028/D029）

[冻结协议v3](home_capacity_crossperiod_protocol_v3.json)及[核查与handoff第三次节](../process_notes/2026-10-14_系统01容量代理跨期复核.md)。历史2019-06-17 23:31:27至06-29 13:55:06前，1002219秒/48h，原算法保持；实际92113条/9处非秒接点，不补插值或延窗。B_HIST_SPAN两量raw_history_not_admitted，B_DS Ah不支持，3项不可用均保留。候选/锚点0是未执行该步骤，不当作原始子段没有锚点。

`freeze_home_third_test_protocol.py`与`acquire_audit_home_third_test.py --attempt ACQ_HOME_THIRD_20261014_01`已真实完成线上索引/目录、两个成员CRC/SHA及质量核验，拒绝覆盖。原始与收据位于已忽略Git的downloads/rwth_home_third_test_20261014。准备/比较使用同一事件，以下ID已使用；复跑换唯一ID并同步参数，不重取或覆盖原始文件。

```powershell
python prepare_home_third_test_samples.py --run-id PREP_HOME_THIRD_20261014_01
python prepare_home_third_test_samples.py --run-id PREP_HOME_THIRD_20261014_02
python verify_home_third_test_samples.py --first-run PREP_HOME_THIRD_20261014_01 --repeat-run PREP_HOME_THIRD_20261014_02 --verification-id VERIFY_HOME_THIRD_20261014_01
python run_home_third_test_baselines.py --run-id BL_HOME_THIRD_20261014_01 --sample-run PREP_HOME_THIRD_20261014_01
python run_home_third_test_baselines.py --run-id BL_HOME_THIRD_20261014_02 --sample-run PREP_HOME_THIRD_20261014_01
python verify_home_third_test_baselines.py --first-run BL_HOME_THIRD_20261014_01 --repeat-run BL_HOME_THIRD_20261014_02 --sample-run PREP_HOME_THIRD_20261014_01 --sample-verification VERIFY_HOME_THIRD_20261014_01 --verification-id VERIFY_BL_HOME_THIRD_20261014_01
```

独立样本验证从原始CSV重建缺口/空代理，baseline验证从出版方XLSX重算支持量与缺预测；无历史选中区间，积分为null。目录仍为home_capacity_sample_runs/和home_capacity_baseline_runs/，原秒算法未改、无拟合/GPU。下一候选最后一次2022-10-30的原始月尚未取得，本轮先总结交接。

## 第二次事件v2（冻结保留，D026/D027）

- [核查与handoff](../process_notes/2026-10-14_系统01容量代理跨期复核.md)、[冻结协议](home_capacity_crossperiod_protocol_v2.json)、[措辞附注](home_capacity_crossperiod_protocol_v2_clarification.json)。2018-03-06事件；历史02-21 02:00:56至03-04 16:24:35半开、1002219秒，原阈值/48h隔离/静置配对/净I/UI不变。公布值已见，非盲测。
- `freeze_home_crossperiod_protocol.py`已在线重核元数据/目录并冻结；`acquire_audit_home_crossperiod.py --attempt ACQ_HOME_CROSS_20261014_02`已取得2月/3月成员和用途准入收据。下载目录`downloads/rwth_home_crossperiod_20261014/`已忽略Git。以上获取/冻结入口不能直接重跑覆盖，应复用指纹一致的本地文件；失败记录也保留。
- 准备与独立验证各自沿用v1算法，新增跨月读取/时窗筛选。下列命令已真实运行，ID均已使用；复跑改新唯一ID并同步参数，不覆盖旧目录。使用捆绑Python3.12（pandas3.0.1、numpy2.3.5），脚本按自身路径定位，命令示例从本目录运行。

```powershell
python prepare_home_crossperiod_samples.py --run-id PREP_HOME_CROSS_20261014_01
python prepare_home_crossperiod_samples.py --run-id PREP_HOME_CROSS_20261014_02
python verify_home_crossperiod_samples.py --first-run PREP_HOME_CROSS_20261014_01 --repeat-run PREP_HOME_CROSS_20261014_02 --verification-id VERIFY_HOME_CROSS_20261014_01
python run_home_crossperiod_baselines.py --run-id BL_HOME_CROSS_20261014_01 --sample-run PREP_HOME_CROSS_20261014_01
python run_home_crossperiod_baselines.py --run-id BL_HOME_CROSS_20261014_02 --sample-run PREP_HOME_CROSS_20261014_01
python verify_home_crossperiod_baselines.py --first-run BL_HOME_CROSS_20261014_01 --repeat-run BL_HOME_CROSS_20261014_02 --sample-run PREP_HOME_CROSS_20261014_01 --sample-verification VERIFY_HOME_CROSS_20261014_01 --verification-id VERIFY_BL_HOME_CROSS_20261014_01
```

样本8份/实验5份产物分别一致，完整历史锚点/配对及原始区间/XLSX复算通过1e-9。产物沿用`home_capacity_sample_runs/`和`home_capacity_baseline_runs/`，新ID与v1分开；代码与源指纹见收据。下一单项候选2019-07-01的原始月尚未取得/准入，本轮止于总结交接，不调阈值或启动复杂方法。

以下为首轮与其他组件的可追溯入口，其中“当前/未取得”等表述对应当时版本；跨期现用状态以上节为准。

- 老师交付入口：[研究样板](../../outputs/课题一_锂离子储能单体特性研究样板_v1_20261014.md)及同目录5图。图像/文档编制与核查代码在work/teacher_storage_brief_20261014，不改变本目录的模型/协议；需要发送时保持Markdown与图1—图5同目录，不发送原始数据和逐秒预测。

- 当前交接：[首轮储能样板总结与handoff](../process_notes/2026-10-14_首轮储能样板阶段总结与handoff.md)。容量现用PREP_HOME_CAP_20261014_01（重复02），BL_HOME_CAP_20261014_01（重复02）；独立收据VERIFY_HOME_CAP_20261014_01、VERIFY_BL_HOME_CAP_20261014_01。
- [容量样本v1](home_capacity_sample_protocol_v1.json)与[baseline v1](home_capacity_baseline_protocol_v1.json)已冻结。prepare/verify_home_capacity_samples.py负责历史候选和独立原始重建；run/verify_home_capacity_baselines.py负责比较及独立原始I/UI/XLSX复算。样本/实验目录已忽略Git；既有ID拒绝覆盖。

- 当前容量核查：[过程记录](../process_notes/2026-10-14_RWTH单系统容量参照与原始窗口准入核查.md)。`prepare_home_capacity_evidence.py`获取方法/图源及远程ZIP目录；`acquire_home_system01_month.py`只下载系统01首测所在月成员并核对CRC/SHA；`audit_home_system01_month.py`核验全月和固定诊断窗，不拟合模型。三入口已运行、拒绝覆盖现有收据；直接重跑会报已有文件，需另设运行版本。
- `downloads/rwth_home_capacity_20261014/`保存所选CSV、出版方参照/补充说明、诊断窗及核查收据，已忽略Git；没有全ZIP/全库校验、其他三测试月份或独立容量模型结果。

- 新源核查：[过程记录](../process_notes/2026-10-13_独立储能数据候选与容量测试线索核查.md)。`inspect_external_bess_candidates.py --receipt-id <唯一ID>`下载小文件并记录失败/指纹；`audit_external_bess_candidates.py`核验2017全CSV、固定LFS与2025有限前缀。当前audit固定field_audit_01、禁止覆盖，不直接重跑已有ID。
- `downloads/independent_candidates_20261013/`包含已忽略的原始文件和收据：PPL2017全CSV、2025前缀、RWTH元数据包与LFP README；不代表全部来源已准入，不执行发布者MATLAB或GP代码。

- `sample_protocol_v1.json`：冻结来源指纹、60秒窗口规则、字段角色和完整试验划分。改变规则须新版本，不沿用旧实验口径。
- `prepare_bess_samples.py`：读取ZIP，不覆盖原始文件；生成样本、全部候选/排除记录、划分和收据。
- `verify_bess_samples.py`：直接从原始CSV独立复算，并检查两次运行文件指纹一致。
- `baseline_protocol_v1.json`：运行前冻结比较、评价和复现容差；输入样本卡版本05。
- `run_bess_baselines.py`：B0理想转换、B1仅Test1估计每单元充/放固定效率，Test2评价。
- `verify_bess_baselines.py`：独立复算参数、预测、误差与指标，并核验两次运行一致。
- `audit_bess_soc.py`：直接核查SOC跳变及同期功率，条件容量换算明确非真值。
- `downloads/`、`sample_runs/`、`baseline_runs/`、`state_audit_runs/`：本地保存，已忽略Git；脚本和协议可版本管理。

已在捆绑Python环境真实运行，依赖Python 3.11及以上、pandas、numpy。程序按自身位置定位项目，不依赖当前工作目录。下列`python`须使用已配置环境；从其他目录运行时传入完整脚本路径。

```powershell
python prepare_bess_samples.py --run-id PREP_M5BAT_20261013_01
python prepare_bess_samples.py --run-id PREP_M5BAT_20261013_02
python verify_bess_samples.py --first-run PREP_M5BAT_20261013_01 --repeat-run PREP_M5BAT_20261013_02 --verification-id VERIFY_M5BAT_20261013_02
```

以上ID已使用，复跑须换新ID；程序拒绝覆盖旧结果。现用产物在`sample_runs/PREP_M5BAT_20261013_01/`：

| 文件 | 内容 |
|---|---|
| samples.csv | 2911合格单元窗，Test1的1133个用于fit，Test2的1778个用于evaluation |
| candidate_windows.csv | 34560个候选单元窗、资格、主要排除原因及诊断标记 |
| split_manifest.csv | 样本ID、来源、单元、窗口和划分；不随机切秒 |
| protocol_snapshot.json | 本次运行协议快照 |
| validation_receipt.json | 代码/来源/协议指纹、环境、数量、边界检查和产物指纹 |

独立收据为`sample_runs/VERIFY_M5BAT_20261013_02.json`；两次运行四份数据/配置文件指纹一致，全部候选资格及原始窗口均值复算通过。

模型输入只取协议白名单：单元、方向、AC均值。DC是参照，损耗和异常标记仅作诊断，不作为输入或按结果删样本。窗口结束时点是可得性的保守协议界限，缺真实接收时间。限单站稳定窗口，不能称事前容量预测、跨站或完整能力验证。

## baseline实际运行

```powershell
python run_bess_baselines.py --run-id BL_M5BAT_20261013_01
python run_bess_baselines.py --run-id BL_M5BAT_20261013_02
python verify_bess_baselines.py --first-run BL_M5BAT_20261013_01 --repeat-run BL_M5BAT_20261013_02 --verification-id VERIFY_BL_M5BAT_20261013_01
```

这些ID亦已使用，复跑换新ID。现用结果在`baseline_runs/BL_M5BAT_20261013_01/`，含参数、逐窗预测、单元/方向指标、主指标、失败表、最差窗口、协议快照及运行收据；独立复核见`baseline_runs/VERIFY_BL_M5BAT_20261013_01.json`。

Test2四单元等权DC均值MAE：B0为8.397877kW，B1为1.422310kW，相对误差降低83.063%；8个单元/方向均改善。8份数据/配置产物复跑指纹相同，全部参数/预测/指标独立复算通过。

AC稳定不保证DC也稳定，最大残差窗DC有大跳变；所有异常保留，未按结果重筛。Test2现已用于正式评价与残差诊断，后续不称未见测试，也不据其结果修改当前协议。

本节仅记录转换组件的G1证据；后续日志预测闭环另见下节。最新接续状态以[数据卡](../../docs/DATA_CARD.md)、[实验台账](../../docs/EXPERIMENT_LOG.md)为准。完整SOC/容量/真实时延仍未验证，继续P1；83.063%不是准确率或90%验收证明。

## SOC/容量诊断与下一数据准入

```powershell
python audit_bess_soc.py --run-id SOC_AUDIT_20261013_01
```

该ID已使用，复跑须新ID。现用`state_audit_runs/SOC_AUDIT_20261013_01/`保存247条跳变、文献参数计算和收据。SOC仅作BMS观测，额定/SOH参数不等于独立容量真值；未校正原数据或改baseline。详见[SOC与容量核查](../process_notes/2026-10-13_储能SOC与容量依据核查.md)。

## APR2023 LMO1字段核验（已完成）

[公开源](https://publications.rwth-aachen.de/record/985923)原始ZIP已取得，位于`downloads/rwth_m5bat_apr2023/M5BAT_04-2023_RAW_downloaded.zip`。成员Batt5.csv对应LMO1，提取为同目录`Batt5_LMO1_original.csv`，仅所选成员CRC核验通过，其他成员未提取。压缩方式Deflate64，标准Python解压不支持；实际通过.NET读取，原始文件保留。

- `extract_apr2023_lmo1.ps1`：复用同一.NET提取方法，固定源指纹，只选Batt5，拒绝覆盖已有输出；本次实际提取采用等价的一次性.NET调用，尚未单独运行该封装入口。
- `apr2023_lmo1_field_protocol_v1.json`：源指纹、字段、倍率、时区声明及用途限制；SOC/I/U分别乘0.1。
- `audit_apr2023_lmo1.py`：原始完整性、倍率/模式、I/U/P、SOC、原AC稳态窗口统计；无拟合/时移。
- `audit_apr2023_lmo1_followup.py`：分块独立计数及SOC/停机模式上下文；固定证据运行ID，重复执行须先显式改为新ID。
- `apr2023_audit_runs/`：实际QA_APR_LMO1_20261013_01/02，收据和原始上下文；已忽略Git。

从本目录复核字段可运行：

```powershell
python audit_apr2023_lmo1.py --run-id QA_APR_LMO1_RECHECK_01
```

请选择未使用的ID，拒绝覆盖结果。CSV为2592000行连续秒记录，插值标记全0，但4555行活动AC下电流为零、1338行AC与重建DC异号，SOC有765条>1百分点跳变。全0插值标记不保证真实信号每秒刷新/同步；I×U是端口重建量，不是独立功率真值。

原稳态规则仅59窗（充55/放4），未拟合新效率或替换既有baseline。分块独立计数与主核验一致；详细[过程核查](../process_notes/2026-10-13_APR2023_LMO1数据准入核查.md)。卡08/D011当时仅准入质量及回顾端口诊断，之后D012/D013新增以下受限日志预测；完整能量/容量和真实接收时延仍缺参照。

## 日志下一秒AC预测（受限闭环完成）

- `apr2023_response_sample_protocol_v1.json` / `apr2023_response_baseline_protocol_v1.json`：拟合前冻结样本、时间划分、输入白名单、三对照和评价容差；实际输入卡09，结果登记卡10，不改协议。
- `prepare_apr2023_response_samples.py` / `verify_apr2023_response_samples.py`：生成分开的输入/未来标签、完整候选和日支持，再从原始CSV逐条独立复核。
- `run_apr2023_response_baselines.py` / `verify_apr2023_response_baselines.py`：B0保持功率、B_SET当前设定、B1训练期单参数修正；独立从原始CSV复算参数、全预测及每日/主指标。
- `apr2023_response_sample_runs/` / `apr2023_response_baseline_runs/`：本地派生数据及模型结果，已忽略Git；准备/模型/验证代码及协议快照已保存。

从本目录运行（下列ID已使用，复跑换新ID）：

```powershell
python prepare_apr2023_response_samples.py --run-id PREP_APR_RESPONSE_20261013_01
python prepare_apr2023_response_samples.py --run-id PREP_APR_RESPONSE_20261013_02
python verify_apr2023_response_samples.py --first-run PREP_APR_RESPONSE_20261013_01 --repeat-run PREP_APR_RESPONSE_20261013_02 --verification-id VERIFY_APR_RESPONSE_20261013_01
python run_apr2023_response_baselines.py --run-id BL_APR_RESPONSE_20261013_01 --sample-run PREP_APR_RESPONSE_20261013_01
python run_apr2023_response_baselines.py --run-id BL_APR_RESPONSE_20261013_02 --sample-run PREP_APR_RESPONSE_20261013_01
python verify_apr2023_response_baselines.py --first-run BL_APR_RESPONSE_20261013_01 --repeat-run BL_APR_RESPONSE_20261013_02 --verification-id VERIFY_BL_APR_RESPONSE_20261013_01
```

每个入口拒绝覆盖旧结果。全部2591994样本输入/历史/目标逐条匹配原始记录；18/6/6天分区无跨块原始支持，首尾及接缝6个原点排除，停机/静默/未知及未来变化均保留。未来诊断只在标签文件，模型输入限白名单，真实数据送达时点仍未知。

三对照共2591994条有效预测，失败0。评价当前PQ 114647条、6日期，日MAE等权平均B0 11.481660、B_SET 4.431353、B1 6.650428kW；六天均B_SET更优。beta=0.6219249796583536仅fit当前PQ估计，无评价调参。十份模型产物复跑指纹一致，原始独立复算参数/全预测/每日和主指标在冻结容差内；分层表只作字节复现核验。

模型结果见`apr2023_response_baseline_runs/BL_APR_RESPONSE_20261013_01/`，独立收据为`VERIFY_BL_APR_RESPONSE_20261013_01.json`，阶段记录为`G1_LOGGED_RESPONSE_20261013.json`；详细[样本与实验核查](../process_notes/2026-10-13_LMO1日志功率预测样本与baseline核查.md)。G1仅日志行可得假设下回顾预测组件通过，真实时延/在线部署、容量、因果与90%未验证；后续残差阶段核查见下节。

## B_SET残差与日志阶段诊断（已完成，D014）

- `apr2023_response_residual_protocol_v1.json`：事后描述协议，明确选例、连续PQ日志时龄及>50kW诊断阈值，不作物理时延/失败标签。
- `audit_apr2023_response_residuals.py`：从原始记录生成最大20条前后10秒上下文及全体当前PQ分组统计；逐条核对冻结B_SET预测，原十份模型产物和源指纹检查前后不变。
- `verify_apr2023_response_residuals.py`：用相邻模式判据独立核验三个时段九组计数/残差总和/大残差数量，以及最大例差分、导出AC/设定/电流/PQ原始值。
- `apr2023_response_residual_runs/`：本地诊断产物、收据与代码/协议快照，已忽略Git。

实际运行（ID已使用，复核须新ID，拒绝覆盖）：

```powershell
python audit_apr2023_response_residuals.py --run-id RESID_APR_RESPONSE_20261013_01
python verify_apr2023_response_residuals.py --audit-run RESID_APR_RESPONSE_20261013_01 --verification-id VERIFY_RESID_APR_RESPONSE_20261013_01
```

evaluation前两条PQ仅1.5543%样本，占绝对残差总和40.6931%；最大20条目标AC均0、19条前两条。不是已识别原因解释了40.7%误差，模式/功率先后不作真实时延。原主日MAE4.431353kW不变，不剔除切入阶段。三分区分布相似，属于受评价启发的事后描述；详见[过程核查](../process_notes/2026-10-13_B_SET大残差与模式切入核查.md)。

本节为D014诊断当轮结果；D015的接续规格和实际附表如下。April evaluation已参与阶段设计，只可回顾探索，独立确认需未参与设计时段，不追加复杂方法。

## 历史阶段附表与冻结规格v2（准备完成，模型结果另见下节）

- `apr2023_response_phase_sample_protocol_v2.json`：保持v1样本/目标/划分，明确追加本块历史模式前缀及phase_state白名单；块首/未知记录后的起点不制造0，连续观测≥3条可判断持续，但精确起点仍左删失。
- `apr2023_response_phase_baseline_protocol_v2.json`：冻结复用原B0/B_SET/B1、B_PHASE三个训练组系数及其他/不可识别退回B_SET的规格；保留拟合前状态，实际结果另见下节。
- `prepare_apr2023_phase_features.py`：只读当前分区历史模式/质量，生成原样本键一致的阶段附表与支持统计。支持表`null_exact_age`包括非PQ不适用及未知，须结合phase_state/删失标志解释。
- `verify_apr2023_phase_features.py`：不导入准备函数，以原始连续观察段独立重建全体阶段/时龄/删失/前缀/ID/划分，并核对父样本指纹。
- `apr2023_response_phase_sample_runs/`：本地时序附表和核验/代码/配置快照，已忽略Git。

现用PREP_PHASE_APR_20261013_02；01仅支持列名订正为02的null_exact_age，阶段特征字节相同，其他产物不称全部相同。操作示例（下列ID已使用，复跑换新ID，拒绝覆盖）：

```powershell
python prepare_apr2023_phase_features.py --run-id PREP_PHASE_APR_20261013_02
python verify_apr2023_phase_features.py --feature-run PREP_PHASE_APR_20261013_02 --verification-id VERIFY_PHASE_APR_20261013_02
```

现用`phase_features.csv.gz`逐ID/顺序关联原`inputs.csv.gz`，没有未来列，模型只读v2白名单。2591994条全部原始独立重建一致，原七份样本/协议产物不变，6条未知模式保留。实际PQ起点左删失0；未知/块首等边界通过构造逻辑检查，不当真实场景验证。

详见[阶段规格与核验](../process_notes/2026-10-13_历史模式阶段特征与分阶段baseline协议.md)。D015阶段规格/准备证据保留，D017实际比较如下；April评价仍为已见回顾探索，不作新方法独立确认。

## 分阶段baseline回顾比较（现用03/04，数值/复现闭环完成）

- `run_apr2023_phase_baselines.py`：只拟合3个阶段系数，复用原对照预测；所有样本、未知模式和回退原因保留。
- `verify_apr2023_phase_baselines.py`：不导入拟合代码，原始块内最多3条模式前缀重建分类，复算三参数、全部预测/回退和每日/主/阶段指标。
- `apr2023_response_phase_baseline_runs/`：本地结果、失败、代码/配置快照，已忽略Git。

现用03、复跑04，以下ID已使用，复跑换新ID、拒绝覆盖：

```powershell
python run_apr2023_phase_baselines.py --run-id BL_PHASE_APR_20261013_03 --feature-run PREP_PHASE_APR_20261013_02
python run_apr2023_phase_baselines.py --run-id BL_PHASE_APR_20261013_04 --feature-run PREP_PHASE_APR_20261013_02
python verify_apr2023_phase_baselines.py --first-run BL_PHASE_APR_20261013_03 --repeat-run BL_PHASE_APR_20261013_04 --verification-id VERIFY_BL_PHASE_APR_20261013_03
```

01/02复制了CSV整数对照数组，小数预测被截断，独立核验失败，原3.821705kW不采纳。改为浮点并补小数检查后，协议/公式/容差未变，以03/04重跑；失败和旧快照保留，不默认读取初次结果。

三个fit系数0/0.6559257561/0.8801352038；首条raw−0.0001377573触预定[0,1]边界。主日MAE B_SET4.431353→B_PHASE3.813732kW，六日均改善，但首条改善、次条/后续退化。保留探索候选和原B_SET，不按April继续调参；逐条回退在predictions.csv.gz记录，实际未知模式6条保留、预测失败0。

03/04十二份产物指纹相同，原始独立复算全部2591994条四模型预测/阶段/回退、参数及每日/主/阶段指标通过容差；其他分层仅字节复现，原10份对照不变。详见[实际核查](../process_notes/2026-10-13_分阶段baseline回顾比较与复现核查.md)。新方法独立确认/真实时延/容量未验证，下一项适配新时段用途准入；Pb1铅酸不替代本LMO对象。

本机CPU有效运行系数估计0.145—0.186秒、含IO/统计32—35秒，没有连接服务器。用户已明确有高性能GPU服务器，后续重训练按[AGENTS](../../AGENTS.md)准备具体实验后申请用户连接；不得以本机不足限制有依据的方法，也不因算力充足提前复杂化。

## 单系统容量代理baseline实际命令与范围

以下为已成功运行的现用ID，复跑时更换新run-id和verification-id，并对应改引用。脚本拒绝覆盖，Python环境同前文。

```powershell
python prepare_home_capacity_samples.py --run-id PREP_HOME_CAP_20261014_01
python prepare_home_capacity_samples.py --run-id PREP_HOME_CAP_20261014_02
python verify_home_capacity_samples.py --first-run PREP_HOME_CAP_20261014_01 --repeat-run PREP_HOME_CAP_20261014_02 --verification-id VERIFY_HOME_CAP_20261014_01
python run_home_capacity_baselines.py --run-id BL_HOME_CAP_20261014_01 --sample-run PREP_HOME_CAP_20261014_01
python run_home_capacity_baselines.py --run-id BL_HOME_CAP_20261014_02 --sample-run PREP_HOME_CAP_20261014_01
python verify_home_capacity_baselines.py --first-run BL_HOME_CAP_20261014_01 --repeat-run BL_HOME_CAP_20261014_02 --sample-run PREP_HOME_CAP_20261014_01 --sample-verification VERIFY_HOME_CAP_20261014_01 --verification-id VERIFY_BL_HOME_CAP_20261014_01
```

样本目录home_capacity_sample_runs/包含features与references分文件、历史静置/配对/缺锚点/替代锚点、划分和收据。实验目录home_capacity_baseline_runs/包含全部6行预测/指标（含B_DS Ah不可用）、失败记录、输入/协议快照和运行收据。

样本8份/实验5份产物分别复跑一致，原始历史流式锚点/积分重建及原始区间/XLSX预测/指标重算通过1e-9容差。单个受控测试、无拟合，1个明确不可用输出、运行失败0。代理不是厂家SOC端点、真实满循环或VPP容量，不以百分比误差推90%验收；当前交接后才决定跨期复核。
