# 作者模型来源与许可

`thevenin_model.py`原样复制自Mark Blyth等作者仓库的`research/scripts/model.py`：

- 论文：How to parameterise an equivalent-circuit empirical battery model from time-domain data，DOI https://doi.org/10.1016/j.mex.2026.103865 。
- 仓库：https://github.com/MarkBlyth/parameterisation_methodsx 。
- 固定提交：`b60bf6ea91aa89bc2504be9589246c12d77c1fc3`。
- 作者仓库许可：GNU GPL version 3，全文保存在同目录`LICENSE`。不将作者代码署为本项目原创。
- 参数/OCV同源；本目录`../../parameters/voltage_25c_*.csv`为公开合并表中25℃行的原值抽取，不重新拟合。

本成果包中的电压适配入口`../voltage_model.py`调用该模型的参数插值和状态方程，显式检查求解成功与适用范围。该适配入口随上述GPLv3条款提供。后续分发或集成时保留这些许可和来源信息。

README与原论文构建引用的独立单温文件版本不同，本次不声明全文结果精确复现。其余本项目组件不借用这份许可声明替代各自来源记录。
