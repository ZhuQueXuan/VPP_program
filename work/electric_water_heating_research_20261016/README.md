# 储热式电热水器研究过程入口

## 2026-10-17现用接续 D071 / DC-20261017-04

已有六类补强授权下，完成[24格矩阵](../process_notes/2026-10-17_六类资源四层证据矩阵.md)与[核验要求](../process_notes/2026-10-17_六类资源调研与数据核验要求.md)，盘点后只深查同原150L水箱的两个放水原件。[实查记录](../process_notes/2026-10-16_储热式电热水器研究.md)已更新，D067温度模型/失败保持。

- `draw_evidence_protocol_v1.json`：新统计前固定源审查，已见基本QA披露；无新模型/预测留出。
- `audit_draw_evidence.py`、`runs/DRAW_SOURCE_04/05/`：全部968数据行/100数值字段、原单位行、−127/状态/分组/正水段/恢复后窗；五科研产物与两快照共7份字节一致。01网络失败、02/03单位行记录不足的历史均保留，04/05修记录不改原数据/协议/数值。
- `verify_draw_evidence.py`、`runs/VERIFY_DRAW_SOURCE_01/receipt.json`：不导入审计函数，Decimal/独立datetime/原XLSX XML复核96800数值单元，111548精确及51822数值检查通过、最大差1e-10<1e-8；原六包104条目与旧温度协议不变。
- `draw_admission_v1.json`：仅发布每采样mL/Wh和有效温度逐文件描述准入。No/With水量151.04355/201.50534L、电能0/1966.279Wh；阀/目标流量/累计量全0而915正水，No累计原单位mL与字典L冲突，With无单位行，不能核累计实际单位/闭合。No后窗仅40s，With后窗0。名义5s等效W/Lmin仅条件量纲参照；控制、热平衡/效率/容量、完整恢复、因果/经济/授权不准入。
- `plot_draw_evidence.py`、`runs/DRAW_DESCRIPTION_01/draw_observations.png/svg`：全部两文件曲线，缺测保留空缺不插值，PNG已目检，SVG未另渲染；`visual_review.json`确认图源02的rows与现用04一致。绘图脚本固定该首次目录，目录已存在时停止。

可在项目根目录用Python执行`work/electric_water_heating_research_20261016/audit_draw_evidence.py --run-id DRAW_SOURCE_NEW`复跑本地审计（run-id须新，不覆盖原目录）；会读取已保存官方元数据，无需重新下载。独立核验器默认04/05并使用新的`--run-id`输出目录，参数详见其`--help`。当前审计读取XLSX需openpyxl；本轮使用Codex bundled Python已实际运行，无服务器或模型训练。

本单项源核查完成；下一能力研究先补真实控制/量测区间/单位校准、完整恢复及独立边界参照。最终v1.0与其16条发布身份保持，下面D067是原基础研究记录，不再把其“等待用户选专项”误作本轮未获授权。

## D067原温度基础包（结果保持）

2026-10-16，D067，卡DC-20261016-13。用户选择“储热式电热水器／电锅炉配水箱”为第六类。现以取得的150升卧式电阻水箱为实际研究对象，首轮基础包在发布温度特征及条件后续五分钟标签估计范围六项有限收口；没有将家用设备参数外推工业锅炉。

衔接103正式任务一资源影响因素/运行时序特征，为任务二后续能力研究提供温度状态参照；非因果解耦/真实容量/控制能力完成。两份现用核心文件与103口径保持。直接分析、保存过程，不新建outputs报告，不更新handoff/教师稿，不整合。

## 现用证据

| 入口 | 实际状态/含义 |
|---|---|
| `downloads/SOURCE_01/` | 官方Mendeley完整元数据65373字节、两配套论文Crossref登记 |
| `downloads/DICTIONARY_01/` | 原字段XLSX、测点与试验系统图、一个完整原CSV及DataBrief全文XML |
| `downloads/NATIVE_CLOCK_01/` | 首个配对JSON，证实时钟同CSV截至分钟 |
| `downloads/CLOCK_CANDIDATES_01/` | 一个完整秒时钟旧CSV、两小型放水JSON，仅核原件/字段/时钟，不纳入该预测实验 |
| `downloads/REGULATION_01/` | 按固定文件名规则其余六个加热保温JSON，未按成绩选择 |
| `runs/SOURCE_QA_01/` | 失败历史：解析器未接受源中单位行`YYYY-MM-DDTHH:mm:ss`；部分字典/论文提取保留 |
| `runs/SOURCE_QA_02/` | 现用全七JSON/130438条原条目QA，含3条单位/说明时间，未拟合；兼容源原有TraceCollection/字段大小写/时刻格式，未改源 |
| `temperature_protocol_v1.json`、`temperature_freeze_v1.json` | 误差前固定单一模型、样本、完整文件划分与成功标准 |
| `runs/PREP_TEMPERATURE_01/` | 16751分钟末锚点全候选/标志、16636样本和拟合前准入收据 |
| `runs/BL_TEMPERATURE_01/02/` | 六系数、全7331预测、96指标/分组/最差与代码身份；五科研产物逐字节一致 |
| `runs/VERIFY_TEMPERATURE_01/` | 向量时钟/锚点与逐行处理独立、显式SVD与lstsq独立；全部样本/预测/指标通过；JSON解码器共享 |
| `temperature_characteristic_protocol_v1.json` | 已见误差后的描述协议，不是新盲测 |
| `runs/CHAR_TEMPERATURE_01/02/` | 全七文件16751锚点分布、全部三个留出文件完整曲线；两科研描述产物字节一致 |
| `runs/VERIFY_CHAR_TEMPERATURE_01/` | 74462数值、全部图源和7331目标对齐通过；PNG目检，SVG同图导出未另渲染 |
| `runs/PACKAGE_TEMPERATURE_01/` | 最终标准库7331点回放、8非法/不完整输入、2边界、目录外两构造例；原五包88发布文件指纹不变 |

实际七原JSON共187682487字节，均与官方大小/SHA256一致。许可CC-BY-4.0。完整原件/逐点与运行目录已忽略Git；没有执行作者程序。原静态配置150L、3kW只作设备身份，不补造电能和控制。

## 主要结果与边界

训练四整文件9305点，评价三整文件7331点。原协议SHA256`5f75213a7d757989ee3f73e47194a4098827bc80bb5bf6aa5d240776e131bfa0`；准入SHA256`6ac8efa82f80c18e2106db02dcaf4ee8df9f5e4713fe16025aad4d6332ab9e06`。

三模型B_P/B_TREND/M_LAYER6的MAE为0.219086755/0.191718183/0.120594568℃，RMSE0.472491055/0.365369432/0.197517784℃。总体、三个留出文件各自、当前加热标记1的593点均较两基线双改善，事前门槛通过。标记0的6738点MAE/RMSE较B_P略退步；316域外特征点、最差2.295132845℃均保留，不事后路由、剪裁或调参。

源不同文件有分钟截断、无日期的时刻、跨午夜、单位说明行、−127缺测、元数据采样周期与源时钟不符。按原序最后分钟行而非最后有效行；无日期跨午夜/其他倒退与坏时刻重开块，不补日期秒数，不跨块。前后五分钟及中间11标签完整才有样本；100窗口失格、15温度条件失格，均留台账。当前完整分钟数据可得是假设，五分钟仅发布标签跨度，不证明真实精确300秒在线提前量。

三个明确日期互相重叠的文件全部放在留出；部分训练时间晚于留出，两个训练文件没有日期。只称整文件/工况留出，同一设备，不称新站点/三个独立物理事件或顺时间部署。跨两侧全信号连续三行完全相同的片段数0，也不证明物理独立。

三个留出电能字段全0而存在加热标记；PowerConsumed原为Wh/采样，不能叫kW或用3kW×标记补成实测。该用途暂不准入真实效率、热容或可调热容量。模型只用当前/历史局部温度、分层测温/两环境温度及发布加热标记；不读未来状态、电能、用水或设定。6系数是统计参数，不是物理R/C或效率。上/下测点温差不是整箱平均温度或能量。

六项审查已限定为原设备温度观察及条件标签估计；完整供水/舒适约束、真实控制、物理精确时延、实际储热量、工业锅炉配水箱和跨设备迁移均待专项。全体P1/103未通过。六类近期基础覆盖达到后，本轮停止新增实验，用户选择下一专项或明确授权整合后再推进。

## 复现入口

本机Python3.12.14、NumPy2.3.5、pandas3.0.1；源字段XLSX以bundled openpyxl只读，未编辑/导出工作簿；图表依赖使用已有work/python_packages/hvac_plots_20261016。CPU足够，无GPU或远程上传。各过程脚本按自身目录定位，新运行用新run-id，不覆盖旧结果。不要重跑`freeze_temperature.py`改原协议，不在已见留出改模型补成绩。

```text
python audit_sources.py --run-id SOURCE_QA_NEW
python prepare_temperature.py --run-id PREP_TEMPERATURE_NEW
python run_temperature.py --run-id BL_TEMPERATURE_NEW
python describe_temperature.py --run-id CHAR_TEMPERATURE_NEW
```

运行器绑定原PREP_TEMPERATURE_01，新准备不自动取代输入；模型核验器绑定01/02，描述核验绑定原CHAR01/02；首次归集器遇已有成果目录停止，不重复覆盖。机器核验收据与现场验证边界见最终README。

[最终使用](../../resource_research_results/electric_water_heating/README.md)；[过程记录](../process_notes/2026-10-16_储热式电热水器研究.md)；[决定](../../docs/DECISION_LOG.md)；[数据卡](../../docs/DATA_CARD.md)；[实验](../../docs/EXPERIMENT_LOG.md)。
