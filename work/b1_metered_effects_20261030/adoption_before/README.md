# B1算法源码

后续B1算法在本目录内开发。这里保留运行源码和必要依赖配置；实验、核验、日志、来源说明及历史版本放在项目根目录的 `work/`。不打包，不设双击示例，报告后置。

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
