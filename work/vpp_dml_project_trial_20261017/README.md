# 现有模拟数据接入同事DML

用户2026-10-17明确授权，用本项目已有模拟数据运行同事程序。结果见[本次说明](../process_notes/2026-10-17_已有模拟数据接入DML.md)；[16类测试平均效应图](heldout_type_effects.png)。

**已完成实际接入与两次运行。** 使用解耦专用模拟数据内部2.4的3456个独立任务；训练1728、验证576、测试1152。只接任务补贴到任务完成率的效应，不虚构小时历史、绿色/调频激励、调查或参考价。

原同事代码保持，在 `run_experiment.py` 中用适配类复用其交叉拟合、LightGBM、线性基函数与因果森林。替换的是时间面板的数据协议：按训练聚合体3折，事前识别闸门，测试只调用已拟合的effect。此处不调用原baseline新数据接口，也不使用原evaluate真值体系。

## 查看

- `protocol.json`：拟合前冻结的输入白名单、划分、五模型、指标和边界。
- `runs/RUN01/summary.csv`：全部模型、验证/测试、三档补贴的主要结果。
- `runs/RUN01/metrics_by_group.csv`：总体、16类、聚合体与零效应对象的615组结果。
- `runs/RUN01/predictions.csv`：25920条留出效应估计，先于真值评价保存。
- `runs/RUN01/receipt.json`：来源/代码指纹、环境、耗时及状态；必须为completed。
- `runs/RUN02/`：固定配置复跑，数值容差内一致，不称逐字节完全一致。
- `verification.json`：独立原表/真值、3690指标数值、5184线性DML预测SVD核验和复跑比较。
- `run01.log` / `run02.log`：实际运行记录。

所有runs派生文件本地保留并忽略Git。未修改或重新生成原模拟数据、六类实测成果、原ZIP或同事代码。

## 再次运行

本机已完成上一轮独立环境安装，可双击本目录 `run.cmd`。会在runs下创建新的时间命名目录，不覆盖RUN01/02。命令行等价入口已实际运行两次；本轮未通过UI双击实测。

项目根目录PowerShell：

```powershell
& '.\work\vpp_dml_review_20261017\env\Scripts\python.exe' -X utf8 '.\work\vpp_dml_project_trial_20261017\run_experiment.py'
```

这次结果用于判断DML核心对既有模拟任务的适用性。任务完成比例的0.1表示10个百分点；它不等于0.1MW，也不是心理损失规避、真实价格弹性或容量准确率。总体均值接近时仍须查看类型差异和零效应对象。
