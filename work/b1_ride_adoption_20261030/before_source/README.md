# B1算法源码

后续B1算法在本目录内开发。这里保留运行源码和必要依赖配置；实验、核验、日志、来源说明及历史版本放在项目根目录的 `work/`。不打包，不设双击示例，报告后置。

2026-10-30新增可选接口 `from b1_api import estimate_metered_effects`，实现位于 `b1_algorithm/metered_effects.py`。它直接接收完整原始电表记录，调用既有标准AIPW估计激励档位的相对用电作用，不要求参考功率预测或过程拟合。输入记录含 `task`、`starts_min`、`ends_min`、`power_kw`；另传事前条件 `X`、激励 `treatment` 和因果假设。首版限定30分钟、1.5kW共同任务及完整1分钟计量格；缺测、切格、重复物理窗口或单个坏事件整体拒绝，不隐删事件。正作用表示相对参考激励档减少了实际用电；各档绝对均值不是净交付比例、响应容量或过程特征。原 `analyze_events → estimate_event_effects` 路径与默认策略保持。

新增接口的协议、模拟比较和独立核验放在 `../work/b1_metered_effects_20261030/`。本轮未知参考过程比较与未准入的参考校正候选放在 `../work/b1_unknown_reference_20261030/`；预测参考下组合版未稳定优于CPOP，不能沿用给定参考试验的优势结论。通知前校正降低平均误差却增加误检，未纳入正式源码或默认流程。

```text
B1算法/
├── b1_api.py                  对外统一调用入口
├── requirements.txt           Python依赖
└── b1_algorithm/
    ├── api.py                 事件分析与效应计算衔接
    ├── contracts.py           输入输出与任务绑定
    ├── reference/             未调节参考功率
    ├── process/               响应过程识别与特征提取
    ├── effects/               激励效应估计
    └── runtime.json           本机R运行依赖配置
```

在本目录启动Python后，可直接 `from b1_api import analyze_event, analyze_events, estimate_event_effects`。其他目录调用时，把本目录加入Python搜索路径。统一入口是供研究程序调用的接口，不是双击运行程序。

当前Python环境：`../work/ride_b1_v02_reproduction_20261029/.venv/Scripts/python.exe`。依赖见 [requirements.txt](requirements.txt)。过程识别使用原生CPOP，因此 `b1_algorithm/process/cpop_batch.R` 和运行配置必须随源码保留；本机R安装仍由 `b1_algorithm/runtime.json` 指向既有位置。配置中的路径以项目根目录为起点，默认运行日志写入根目录 `work/b1_runtime/`。

算法说明与来源保留于 [开发资料](../work/b1_directory_migration_20261030/documentation/b1_algorithm/README.md)，实验与验收见 [研究证据](../work/b1_formal_v1_20261029/README.md)。迁移记录及检查见 [目录整理记录](../work/b1_directory_migration_20261030/README.md)。
