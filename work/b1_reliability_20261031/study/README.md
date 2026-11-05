# EV参考与整任务证据：研究实施入口

中央协议：`../protocol.json`，SHA `d095a56114f34f6d827e708a8f063b4dd758c5b113abc222f73f259e72cf3749`。本目录只实施预定研究；正式算法源码由主代理维护。未改旧模拟器、原数据、默认路由、报告或B2/B3。

## 阶段一

- `prepare_receipt.json`：192用户384个明确未发任务的non-event训练记录；另96用户192个独立non-event校准记录。金额字段仅为配对随机抽样，未宣布信号。
- `models/reliable_reference.json`：冻结模型 `evref-350d5ae0d77d060531bc`；训练截止254585，校准全部标签截止2253305。
- `calibration/receipt.json`：old/new参考×原CPOP/RIDE revised四路分别标定，同96个原始用户、各2事件；不筛选已发生不响应者。
- `validation/assessment.json`、`test/assessment.json`：一次预定验证、八块新测试，测试1024基础任务×三配对变体×四路径=12288输出，全部ok。
- `audit_receipt.json`：164175项只读身份、配对、合法时点、积分、直接窗口扫描与rank核验。核验次数不是性能样本量。
- `stratified_metrics.json`：阈上正响应/物理无动作分层误差及唯一基础任务的参考误差，避免用零轨迹或重复变体混淆结论。
- **计时修正**：原冻结assessment的`process_timing_seconds_sum`字段因标签匹配错误全为0，已废弃。只使用`timing_corrected.json`；这是四worker共享机器下的批耗时和，不是独占单事件延迟。原件不回写、不重跑。
- `phase1_scientific_files_sha256.json`：830个文件封存，后续第二阶段核验其全部逐字未变。

证据结论与实测时长/原η分别保存。`inconclusive`不表示没有响应；所有事件保留参与总作用估计，不能按证据筛选或把时长改零。

## 阶段二共享输入

`continuous/validation/receipt.json`包含7520200的512条positive事件；`continuous/test/receipt.json`包含8块4096条positive/zero配对事件。每条均用同一新冻结参考和原CPOP计算，未按证据筛选，全部ok。

输入路径为`continuous/{validation|test}/events/{seed}_{scenario}.json`与`factor_inputs/{seed}_{scenario}.json`；后者为原始L/U及身份、可得时点记录列表。`evaluator/`为生成器封存真值，作用模型完成拟合前不得用于选择。这里的zero严格来自原模拟器`scenario='zero'`：激励无作用，但允许实际响应，不能解释为阶段一的物理null。

`continuous/input_audit_receipt.json`包含55664项不读真值的输入核验；`continuous/scientific_files_sha256.json`封存共享输入、来源和过程。作用选择、拟合和评价位于父目录`../effects/`，本输入程序不选择或重训作用模型。

所有事实保存在版本化`data/B1_reliability_v1_20261031/`。脚本使用独占新建；重复执行会拒绝覆盖，失败件保留。模拟结果不是现场可靠性或完整不确定性覆盖保证。
