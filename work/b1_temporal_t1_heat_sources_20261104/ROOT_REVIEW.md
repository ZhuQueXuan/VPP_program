# 第3点新增热泵数据总管审查

2026-11-04。**本轮五个来源均未补齐现有比较所需的样本。T2 暂不放行。** 回升曲线比较沿用[原 T1 冻结规则](../b1_temporal_t1_comparability_20261104/T1_RULES.md)。此前比利时采暖热泵资料有4个可比对、涉及5户，合格三元组为0。本轮可计入的新增户和事件均为0。未取得原表的项目，可用户数和事件数记为未知。[来源核查](README.md) · [上一轮总管审查](../b1_temporal_t1_comparability_20261104/ROOT_REVIEW.md)

- **美国 DOE 热泵热水器。** 主审核对六份原件和发布元数据的收据散列，另用两个原始 CSV 复算时间和功率。两站分别1,426和1,427行，无重复时点和空功率单元，原始零值分别772和728个，且存在成段无记录。最短间隔分别3,554和3,570秒，均超过 T1 的450秒上限。控制状态变化只把解除时点约束在两条记录之间。热水器可作为未来另一类资源的线索，本轮不并入户用采暖热泵。 [实读核验](doe_sample_audit.json) · [DOE 站点原表](https://heatpumpdata.energy.gov/data/sites/pnnl-hpwh-2021-orla461-load-shifting)
- **瑞士 OrtsNetz。** 对照作者字段表和公开目录，数据记录的是每15分钟的电表电量，可识别部分独立热泵表和参与试验的标记。目录未列逐户逐次控制指令与解除时点。档案元数据已经足以判断采样不合格，未取大包。 [作者字段与文件目录](https://arxiv.org/html/2607.19294v1)
- **英国 LATENT、HeatFlex 和 FREEDOM。** LATENT 的分钟级设备功率和反复控制最接近目标。HeatFlex 的公开结果按半小时呈现，原生采样待核。FREEDOM 报告确认部分混合供暖机型有分钟级功率和开关发令记录。三项均未取得可按同户同事件关联的公开原表，计划结束、控制端发令和设备实际获准恢复须分别核对。 [LATENT](https://eprints.soton.ac.uk/499747/) · [HeatFlex](https://www.nesta.org.uk/report/heatflex-the-untapped-potential-of-automated-heat-pump-flexibility/) · [FREEDOM 数据说明](https://commercial.nationalgrid.co.uk/downloads-view-reciteme/457837)

下一次有符合条件的实际资料时，先核逐户停控锚点、开始前1小时的状态、解除后6小时的连续设备功率，以及同类控制和覆盖条件下的独立家庭数。用冻结规则确认可比组，盲审形态参照通过后再用同一批样本和简单统计比较。本轮没有训练或新增效果分数，保留[比较草案](../b1_temporal_t1_comparability_20261104/T2_DRAFT.md)。
