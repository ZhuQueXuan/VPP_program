# 第二点因素关系分析与通用接口

第二点分别列出与报价有关、与实际响应有关，以及两边都有关的事前因素。以现有 PC/KCI 的无时间限制骨架为对照，本轮只限制用于判断关系的条件变量，避免用较晚的响应结果判断报价和事前因素是否相关。[时间顺序约束的论文](https://pmc.ncbi.nlm.nih.gov/articles/PMC11346914/)

## 同条件比较

充电桩、热泵各用六类模拟机制，每类配四个随机块。每组用 120 个模拟独立个体各一条事件。三项分别用自己的已知关系作为分母。

| 关系 | 无时间限制找回 | 加时间限制找回 | 加时间限制后的误报 |
| --- | ---: | ---: | ---: |
| 报价因素 | 30/72 | 41/72 | 2，与原来相同 |
| 响应因素 | 40/88 | 40/88 | 6，与原来相同 |
| 同时影响报价和响应的因素 | 9/64 | 12/64 | 0，与原来相同 |

额外加入报价筛查时，两边共同因素找回 10/64，低于仅加时间限制。共同因素的识别还弱，当前输出供复核，第三点仍需单独确认调整变量。这批数据是已知机制的模拟，现场表现待验证。完整计分见 [results.json](contract_replay/results.json)。

## 接入其他资源

从 `B1算法` 目录调用现有 `b1_api`。示例文件包含可直接传入的配置和事件。

```python
import json
from pathlib import Path

from b1_api import ResourceFactorStudy, analyze_resource_factors

example = Path('../work/b1_resource_factors_20261104/contract_replay/heat_pump_example.json')
data = json.loads(example.read_text(encoding='utf-8'))
result = analyze_resource_factors(ResourceFactorStudy(**data['study']), data['records'])
```

- 充电桩示例输入剩余时间和电量需求，以每千瓦时的补偿报价解释任务窗内的累计有效响应秒数。[示例数据](contract_replay/EV_example.json)
- 热泵示例输入室内温度余量和室外温度，以每次任务的补偿报价解释任务窗内的净减少用电量。[示例数据](contract_replay/heat_pump_example.json)
- 新资源自己定义事前因素、补偿单位、任务窗、响应指标及测量口径。每条事件提供报价形成前已可用的因素、事前报价和实际结果。接口核对时间、资源、结果名称和单位。各资源的原始信号由各自的提取方法处理。
- 每次分析使用同一种资源、同一个任务窗长度和同一种结果口径。调用方按独立用户或设备等填写分组标识，每组取最早一条任务。现版每次分析支持 1 至 8 个事前因素，要求至少 30 个独立分组。
