# 正式第一版研究内容

这是研究点一当前保留的代码版。只包含算法源码、推理所需模型参数、配置和依赖，不包含实验过程、历史候选、训练数据、评测输出或大附件。

## 目录

```text
B1算法/
  b1_api.py                 程序接口
  b1_algorithm/             当前算法实现和内部模型参数
    observed/               真实充电观测适配的推理代码与保留参数
    runtime.json            本机R/CPOP路径配置
config/study.example.json   任务和因素配置示例
models/ev_demo.json         已拟合的充电模拟演示模型
requirements.txt           Python依赖
```

## 使用

Python 3.10及以上，安装依赖：

```powershell
python -m pip install -r requirements.txt
```

直接加载已保存模型，查询补偿变化，不重新训练：

```python
from pathlib import Path
import sys

sys.path.insert(0, str(Path("B1算法")))
from b1_api import load_research_point_one, query_research_point_one

model = load_research_point_one("models/ev_demo.json")
result = query_research_point_one(model, [0.4, 1.2])
print(result["mean_curve"]["curve"])
```

演示模型使用模拟数据拟合，面向其固定人群查询；不能直接当作新用户或现场充电的效果保证。使用自己的数据时，调用下列训练/分析接口。

| 接口 | 功能 |
| --- | --- |
| `analyze_event` / `analyze_events` | 从任务、参考及实测功率提取响应特征 |
| `analyze_resource_factors` | 整理报价前因素及其作用关系 |
| `run_research_point_one` | 从原始任务及因素记录完成研究点一分析 |
| `fit_response_research` | 对已取得的结果与事前因素进行分析 |
| `query_research_point_one` | 查询保存模型的补偿增量、分组及相关结果 |
| `save_research_point_one` / `load_research_point_one` | 保存和加载模型 |

真实充电观测适配可独立调用：

```python
from b1_algorithm.observed import analyze_observed_event

# record["model_input"]包含同轴的relative_seconds、power_kw、current_a、pilot_a。
# fitted_power_kw为调用方提供的、与原观测逐点对应的CPOP拟合功率。
result = analyze_observed_event(record, fitted_power_kw)
```

该接口报告可见变化及恢复，不能将观测跨度当成物理有效减载时长。

## 配置

- 任务参数见`config/study.example.json`，按实际数据填写；因果条件未确认时不能将结果称为因果作用。
- 原生CPOP路径需安装R及`cpop`，原环境使用R 4.6.1和cpop 1.0.10。编辑`B1算法/b1_algorithm/runtime.json`中的Rscript、R库和输出位置，可使用本机绝对路径。
- R安装包、原始数据和运行输出不存入仓库。`runtime.json`的`sha256`可填写本机依赖校验；为空时不执行额外文件散列校验。

默认保留当前连续DR方法及已保留的过程模型。阈值等接口已存在，真实补偿作用和全部现场精度仍需对应数据验证。

仓库保持私有；代码内原方法来源和第三方声明保持原样，不新增统一开源许可。
