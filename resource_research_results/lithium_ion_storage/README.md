# 锂离子储能研究成果 v1.0.0

日期：2026-10-15。现用成果代码入口；保存已保留组件及参数，不含下载、清洗、调参、诊断或实验核验脚本。

## 文件与使用范围

| 组件 | 代码 | 输入 → 输出 | 适用范围 |
|---|---|---|---|
| 稳态功率转换 | [conversion.py](code/conversion.py) | 单元、方向、稳态交流功率 → 直流功率、适用状态 | M5BAT已核验4单元/8方向；正功率放电，负功率充电。需先确认符合原研究稳态条件，代码不会从单个功率值自动判断稳态 |
| 下一秒日志功率预测 | [log_power_forecast.py](code/log_power_forecast.py) | 当前功率、设定值、模式 → 持续/设定值/混合三种预测 | M5BAT LMO1日志同时可得假设；设定值baseline是此次评价最优方法，混合模型未胜过它。未知模式保持当前功率并标记 |
| 条件电压轨迹 | [voltage_model.py](code/voltage_model.py) | 已知电流轨迹、给定初SOC → 电压、递推SOC | 作者MLP001电芯公开25℃参数、2.132Ah、放电/静置；不估计未知SOC或容量，不预测未知未来功率 |

三个组件来自不同研究对象，不组成同一设备完整模型。参数不能直接迁移至其他电芯或场站。完整SOC、可用容量、实际指令时延、VPP可承诺能力仍未通过或未完成；容量失败候选不作为可用算法放入此目录。

## 运行样例

Python3.12为已核验环境。前两个组件仅使用Python标准库；电压组件另需NumPy、pandas和SciPy。`requirements.txt`记录本次核验版本，代码不依赖原`work/`目录、原始数据或绝对电脑路径。

如环境尚未安装依赖，在本目录执行：

```powershell
python -m pip install -r requirements.txt
```

在本目录执行以下命令，一次运行三个小样例，输出保存在新建的`outputs/example_时间/`：

```powershell
python run_examples.py
```

`examples/`全部是人工构造的输入格式样例，用来展示调用方式，不是新增真实试验或效果证据。已有同名输出不会覆盖。也可分别运行：

```powershell
python code/conversion.py --input examples/conversion_input.csv --output outputs/my_conversion.csv
python code/log_power_forecast.py --input examples/log_power_input.csv --output outputs/my_log_power.csv
python code/voltage_model.py --input examples/voltage_current.csv --output outputs/my_voltage.csv --initial-soc 1
```

转换输入必须包含`steady_state_confirmed`。不确认稳态、单元未知、方向冲突或无有效参数时保留该行并返回不可用原因。超出拟合功率范围的转换结果保留数值并明确标记，不当作范围内验证通过。稳态筛选仍由使用者依据数据和原研究条件完成。

电压输入只接受`time_s,current_discharge_A`两列，时间从0开始非递减，重复时间保留原顺序。电流按作者np.interp处理，输出在唯一观测时刻；原始亚秒时间未知时不能补造。负电流不在本次发布范围。参数域外或求解失败直接报错，不裁尾/裁剪/外推。`soc_from_given_initial`仅为给定初值递推状态，未验证为真实SOC。

## 已有验证结果

完整摘要在[validation_summary.json](results/validation_summary.json)，本次成果代码与原冻结结果的核对状态在[release_validation.json](results/release_validation.json)。

| 组件 | 已有证据 | 结论边界 |
|---|---|---|
| 转换 | Test1拟合1133窗、Test2评价1778窗；等单元MAE从8.397877降到1.422310kW | 同站稳态转换；1778窗中394窗超出拟合功率支持范围，整体成绩包含这些窗 |
| 日志预测 | 18/6/6天划分；评价期PQ日等权MAE持续11.481660、设定4.431353、混合6.650428kW | 设定值优于混合；不证明真实通信时延、跨站迁移或可用容量 |
| 电压 | 原整窗79058点评价及复跑；2RC MAE4.597734mV，R0为7.733327mV | 最差2RC误差265.958311mV在末秒，未裁掉；公开参数参考再现，非独立SOC/容量精度或全文精确复现 |

原始完整输入、逐条实验预测和独立核验仍在原研究目录保存，不复制大体量过程产物到成果目录。旧成果和教师材料没有移动或覆盖。原始研究入口为[原储能README](../../work/resource_sample_selection_20261013/README.md)，本目录的模型运行不依赖它。

## 参数与来源

- `parameters/conversion_m5bat.json`：冻结Test1得到的8组效率及功率支持范围，原值保存。
- `parameters/log_power_lmo1.json`：原冻结混合系数；保留作为对照，不宣称最优。
- `parameters/voltage_25c_params.csv`与`voltage_25c_ocv.csv`：Blyth作者公开合并表中25℃行，原值抽取。论文 https://doi.org/10.1016/j.mex.2026.103865 ，固定提交与GPLv3全文见[第三方来源说明](code/third_party/NOTICE.md)。

仅发布确定的计算部分及其必要文件。探索性阶段特征预测、容量代理候选、数据获取和核验程序继续留在`work/`。后续资源分别研究，跨资源整合待用户另行决定。
