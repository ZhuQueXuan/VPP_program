# 新第3点 T1 热泵来源定向准入

2026-11-04。**本轮5个来源中没有达到既定T1同条件门的新增资料。** 实际读到两个热泵热水器站点共2,853行原表，可从控制字段读到状态转换，但表中间隔约1小时，无法验证停止后6小时的5分钟级形态。原9户4对、0三元组及[冻结规则](../b1_temporal_t1_comparability_20261104/T1_RULES.md)沿用，总管裁定暂不放行T2。[总管审查](ROOT_REVIEW.md)

## 准入口径

- 每户事件键须同时连接控制与原功率。区分计划结束、控制端已发解除、设备记录恢复许可、后续功率回升。聚合图、费率结束或仅有控制状态采样分别提供图示、计划或时刻区间。禁止用功率形态定对齐点。
- 核设备计量、时钟、实际持续时间、结束原因、前1小时状态、后6小时覆盖及是否有其他控制。T1要求相邻原点间隔≤450秒、边缘最近点≤300秒。沿用匹配所需的通知、控制构型、试验季、温度、时长和能量。对其他试验中语义未明的字段标缺口。
- 结构门仍为至少8个可比对覆盖6户，至少两个互不重叠的三户评价组和至少12个合格三元组。满足结构后才建立隔离原点参照。户、设备、电表、试验日期及逐户可用事件分开计数。

## 五个来源

| 来源与现场规模 | 控制、测量及公开入口 | T1结果 |
| --- | --- | --- |
| **LATENT，英国，Turner等，Applied Energy 2025**。期末干预30栋、对照30栋，论文报告22场结果。 | Modbus 分钟级热泵电输入，另有供暖及生活热水热输出、10分钟室温和小时外温。论文图12中2023-02-07和02-20两场均约17:00–18:00，处理组分别20和21。两场热水控制不同，图中的公共事件时段无法判断逐户恢复许可。试验存在温度排除与用户覆盖。 | 字段和重复控制最接近。机构材料说明产业伙伴提供数据并导入研究数据库。未找到逐户控制日志和原功率的公开下载，论文许可仅针对公开文稿。合格户和逐户事件未知。[作者论文及图12](https://eprints.soton.ac.uk/499747/1/APEN_final_ASHP_flexibility.pdf) · [机构目录](https://eprints.soton.ac.uk/499747/) · [数据说明](https://eprints.soton.ac.uk/502081/1/SRSG_Annual_Report_2024.pdf) |
| **HeatFlex UK，Nesta 与 Centre for Net Zero，2024**。43户入组，主报告30场，约半数受控。 | 远控恒温器，前2小时预热、后2小时降低供热。报告区分整户与热泵用电，公开结果以半小时电量呈现，原生设备时钟及粒度待核。有事前退出，计划结束不足以判明设备执行。 | 在公开项目、报告下载页和数据目录未找到可直接读取的逐户执行日志与原始子表。主报告和活动回顾分别写30与27场，沿用主报告出版口径。合格分母及原表许可未知。[Nesta主报告](https://www.nesta.org.uk/report/heatflex-the-untapped-potential-of-automated-heat-pump-flexibility/) · [CNZ项目](https://www.centrefornetzero.org/research/heatflex) · [数据目录](https://www.centrefornetzero.org/data) · [活动回顾](https://www.nesta.org.uk/event/heatflex-the-untapped-potential-of-automated-heat-pump-flexibility/) |
| **FREEDOM，英国威尔士，National Grid/PassivSystems**。75户混合供暖。 | 发布方分析附录7.1确认曾取得设备分钟级热泵电功率、时间、部分机型的已发送开关事件及半小时故障记录。原分析剔除后留64份半小时文件，分钟数据也有空段。 | 项目与报告公开，原控制和功率表未获，数据门户检索遇 robots 限制，原表许可未知。机型缺控制字段、发送与接收差异以及燃气备用切换均需先核。64份文件不能换算为合格家庭或事件。[项目目录](https://commercial.nationalgrid.co.uk/innovation/projects/freedom) · [项目报告](https://commercial.nationalgrid.co.uk/downloads/12221/freedom-project-final-report.pdf) · [字段与清理附录](https://commercial.nationalgrid.co.uk/downloads-view-reciteme/457837) |
| **OrtsNetz，瑞士 ETH/EKZ，2026**。2,447电表安装，606关联试验，64户装新控制器，66块电表关联热水器或热泵试验控制。 | 作者表2–4给出UTC区间起点、15分钟电量、部分热泵独立表、参与及控制类型标签。公开ZIP含电表CSV、元信息、资费，未列逐事件开始或解除。两个官方元数据端确认数据 CC BY 4.0，作者分析代码 MIT。 | 具有热泵独立表且受控的户数待核，15分钟间隔已超过450秒。目录证据足以判断，未取904,206,916字节压缩包。[作者字段字典](https://arxiv.org/html/2607.19294v1) · [Zenodo目录](https://zenodo.org/records/21398769) · [作者代码](https://github.com/ka-kai/smart-meter-data) · [存档元数据](raw/OrtsNetz_zenodo.json) |
| **PNNL Central Florida HPWH Load Shifting，DOE**。目录25个移峰站点条目，原论文整体试验约45户。 | CTA-2045控制，站点公开设备表。实读2个住宅站点、2个设备别名。功率与控制状态共在一表，字段支持状态转换区间。未找到同站点独立的发令/解除表和发布方时钟字典。 | 实核最短间隔3,554和3,570秒，均超过450秒。供生活热水的设备亦缺T1所需前态。新增合格0户、0事件、0对、0三元组。站点可匿名读取，原表专用许可未确认。[DOE目录](https://heatpumpdata.energy.gov/data/sites) · [ORLa438](https://heatpumpdata.energy.gov/data/sites/pnnl-hpwh-2021-orla438-load-shifting) · [ORLa461](https://heatpumpdata.energy.gov/data/sites/pnnl-hpwh-2021-orla461-load-shifting) · [原研究](https://www.pnnl.gov/publications/field-study-grid-connected-heat-pump-water-heaters-southeast-us-next-right-thing) |

## 实读样本与时钟核对

DOE 两表分别1,426和1,427行。设备功率 curr_watts 以 W 记录，分别有772和728个原始0值，无空功率单元。两表分别有13和12处超过3,660秒的断档，最长约16.1天。原始0值保留，空单元与整段无记录分开核算。

local_time 不含偏移。数值 timestamp 与本地字段的相对经过时间最多差1秒，两表首个 unique_hour 标签为03:00，而本地字段为00:30。未确认数值时钟起算点、时区和行的聚合方式，未转成绝对UTC。采用同名EcoPort字段的另一研究将状态8解释为恢复常态，本次未取得Florida官方完整码表。按当前表把代码1/11且正控制值转到8、状态ID改变记为候选区间，再按时间先后抽第一组。[字段语义旁证，第III节](https://sparklab.engr.uky.edu/sites/spark/files/2021%20IEEE%20ACCESS%20UK%20SPARK%20AOS%20Generic%20Aggregated%20EWH-compressed.pdf) · [原点核验](doe_sample_audit.json)

首个共同例在2020-11-16当地记录05:30→06:30，由代码1和ID48338转到代码8和ID48339。两个站点相应功率0→349.6 W及0→343.4667 W。06:30是第一条常态状态行，转换只能定位在一小时区间。自该行向后查6小时，两台设备各只有7个点（含起始点），12:30又有不同控制状态。两表共239个常规小时候选区间，117个首条常态ID在两表共有，另有1个跨长断档候选。状态ID与真实解除事件分开统计。[固定首例的原点和源行](doe_first_control_transition_points.csv) · [状态转换台账](doe_status_transition_ledger.csv)

两份DOE原CSV合计447,032字节，保存两份发布页及两个瑞士官方元数据响应。对英国三项仅核公开论文、机构目录与发布方资料。未获取大数据包、注册、登录或联系外部。audit_doe.py 可复算本地源行、时距和候选转换。[DOE下载收据](raw/doe_fetch.json) · [瑞士目录收据](raw/ortsnetz_fetch.json) · [独立复算](verification.json)

## 交总管判断

现有可读资料尚未同时具备逐户可追溯停控、细粒度设备原功率和可核事前状态。三个英国项目的可用分母未知，DOE实读样本符合原T1的分母为零。没有新增可比组可送隔离盲审。保留[T2草案](../b1_temporal_t1_comparability_20261104/T2_DRAFT.md)，本轮停在准入，0训练，旧确认未开。

记录用户长线方向。新9.1最终需要跨多类资源通用，先完成一个资源示例，再迁移验证。此次未修改通用算法或接口。
