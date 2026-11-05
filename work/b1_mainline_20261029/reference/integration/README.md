# 未知参考与平均过程模型的有限联调

日期：2026-10-29。本次实际串联参考估计A和过程拟合B，目的是检查参考误差进入过程后的影响。它不是另一次主方法排名，也没有增加新的拟合或调参。

## 协议与范围

[protocol.json](protocol.json)在运行前冻结，SHA为`63ce97fb19c5aca36668541a58c9ea1b2552d8402e4d236bc0df1cdbb1b0e23c`。使用新seed 940000—940009，共10个独立块，每块两种配对温度条件、200用户各4事件。训练用户沿用固定四角色划分中的50%，SafeGBDT超参数和输入特征保持参考主实验设置。

测试用户内，仅按事前任务条件筛选W=30分钟、q=1.5kW，再按事件ID取每资源前两条。没有使用是否响应、真实幅度或估计效果来选择事件。40个“种子×温度×资源”格中20格不足两条，最终共52个事件记录；不足格原样保留，没有替换种子。不同资源实际覆盖6—9个种子块，不能把每格都写成10次完整重复。两温度条件是配对变体。

1分钟计量，截取[-15,45]分钟，共60格；任务窗[0,30]分钟。共同噪声标准差0.15kW。对每事件分别使用评价器的真实未调节参考和实际拟合的共同SafeGBDT参考；每种参考均输入相同Grid_point和Grid_average算法。算法直接导入process/models.py，不修改其候选网格、最多4结点、复杂度惩罚、求解器和停止规则。两个模型的输出均经过平均算子后评价。

真目标为模拟真实未调节功率B减去无计量噪声的事实功率P，而非强行按理想模板解释发生的动作。评价只看任务窗平均减载曲线误差与原始积分净交付比例误差，不输出物理时点或置信区间。

## 结果

下面为52条选择记录的描述性汇总；主分资源、按种子先汇总的结果见[summary.csv](summary.csv)。

| 参考来源 | 方法 | 任务窗曲线RMSE kW | 原始积分η RMSE |
| --- | --- | ---: | ---: |
| 给定真参考 | Grid_point | 0.081258 | 0.012653 |
| 给定真参考 | Grid_average | 0.082016 | 0.012653 |
| 共同SafeGBDT | Grid_point | 0.231644 | 0.142004 |
| 共同SafeGBDT | Grid_average | 0.231536 | 0.142004 |

本次1分钟有限子域里，区间平均与点观测的过程差异很小，没有展示稳定的新优势。参考由真值换成预测值后，曲线误差和积分交付误差明显增大，说明参考误差会主导这一链路，不能凭过程模型在给定参考实验中的收益预期完整链路同样改善。

原始积分η对两个过程模型完全相同，共104组配对均核验一致。因为完整窗η由共同观测残差直接积分，本轮没有通过改换拟合电量制造算法优势。未将参考模块的窗口级校准半宽当作逐格σ或sB；仍使用共同计量σ=.15，只把参考偏差另列。因此本结果也不构成参考误差已完整传播的全链时点置信带。

## 文件与核验

- [run_integration.py](run_integration.py)：实际运行入口；已有完整收据时拒绝覆盖主实验。
- [before.json](before.json)、[receipt.json](receipt.json)：运行前协议/过程模型/参考实现SHA与运行后核验，耗时17.3秒。process/models.py及reference_api.py未变，原RIDE46个文件SHA未变。
- [availability.csv](availability.csv)、[selected_events.csv](selected_events.csv)：任务域可用数量及实际选择记录。
- [raw.csv](raw.csv)、[interval_records.csv](interval_records.csv)：208方法记录及12480格明细，可核查共同输入和误差。
- [seed_metrics.csv](seed_metrics.csv)、[summary.csv](summary.csv)：先按独立种子汇总的分格结果；[descriptive_overview.csv](descriptive_overview.csv)仅为上述描述性概览。
- [audit_integration.py](audit_integration.py)、[audit_receipt.json](audit_receipt.json)：独立从逐格文件重算208组误差，核对104对共同η，全部通过。

初次独立重算发现，原模拟float32求均值及float32逐格CSV序列化，与重读后float64累加产生约1.02×10⁻⁷的η差及2.29×10⁻⁸kW的RMSE差。核验器改用绝对容差10⁻⁶，原始科学输出和主实验不变；保留[initial_audit_float32.json](initial_audit_float32.json)。

这些是原RIDE模拟器下少量任务域记录的联调结果，没有真实数据、正式CPOP新排名、时点识别或总体因果结论。参考模块的伪事件可迁移性、未来声明来源及真实噪声仍需真实证据；本轮没有据联调负结果扩样或追分。
