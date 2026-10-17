# 同事 VPP DML 成果检查入口

日期：2026-10-17。对应用户要求：读取根目录同事成果、尝试运行、判断与课题一的用途和出入。

主要结论和实际结果见 [检查说明](../../work/process_notes/2026-10-17_同事DML成果运行与适用性检查.md)。这是候选方法的独立检查，不是将其并入六类成果或宣布P1通过。

## 文件与证据

- 原交付：根目录 `vpp_dml_framework/` 下的修订稿和同名 ZIP，保持原样。
- `vpp_dml_framework/`：ZIP逐字节解压副本，23文件，原附带结果保持。
- `review_protocol.json`：运行前固定的检查范围、容差与比较规则。
- `environment.json`：实际运行版本。独立环境位于 `env/`，继承本机既有包，新增依赖只安装到本地env。
- `run_review.py`：在独立副本运行原脚本，保留指纹、日志、退出码和耗时。
- `quick.log` / `full.log`：未修复原程序的两次实际失败。
- `quick_repaired.log` / `full_repaired.log`：仅修复评价标准化除零后运行；不改拟合、数据、划分和参数。
- `*_run_receipt.json`：每次运行的命令、输入/输出SHA256与状态；`returncode=0` 才表示完整完成。
- `run_full_repaired/results/`：本次完整运行生成结果；两个coverage文件是复制保留的原附带内容，本次没有重训30轮。
- `comparison.json` / `comparison_key_metrics.csv`：完整复跑与原附带结果的逐列比较及主要指标。
- `audit_delivery.py` / `independent_audit.json`：独立检查ZIP、样本数、说明书字段、缺时钟行为、划分依赖与原覆盖率汇总算术。
- `coverage_independent.csv`：从原150行重复结果独立重算65个汇总数值；这不等于重新完成30轮训练。

## 查看与再次运行

直接打开检查说明即可了解结论。打开 `run_full_repaired/results/benchmark.csv` 可查看本次模型比较，打开 `comparison_key_metrics.csv` 可看主要指标。

已完成环境安装时，在项目根目录 PowerShell 运行：

```powershell
& '.\work\vpp_dml_review_20261017\env\Scripts\python.exe' -X utf8 '.\work\vpp_dml_review_20261017\run_full_repaired\experiments\run_benchmark.py'
```

上述命令会重写**运行副本**中的8个生成结果文件，不改原ZIP和原附带结果；若需保留每次运行，请先另建具名副本。两份coverage文件不会由benchmark生成，不据其存在声称已复跑覆盖率实验。

修改范围只有 `evaluate.py` 中 `_profiles` 的标准化分母：原 `prof.std()` 对常数画像可为0；当标准差绝对值不超过1e-12时改为1。修复只用于评价，常数画像仍无可区分的异质性；不改变任何训练模型、划分或模拟机制。

## 后续用户指定的本项目模拟数据试验

D069已另行完成，见[接入入口](../vpp_dml_project_trial_20261017/README.md)和[结果](../process_notes/2026-10-17_已有模拟数据接入DML.md)。与上面同事自带模拟的复跑分开记录，不改D068原成绩。

## 两方向接续（D070）

[代码功能与调研衔接](../process_notes/2026-10-17_DML代码功能与资源调研衔接说明.md)已完成；另建用户对话负责[40个体与候选](../process_notes/2026-10-17_同事DML资源清单与下一轮资源候选.md)，待用户选择再深调研。原实验结果和现用框架不变。
