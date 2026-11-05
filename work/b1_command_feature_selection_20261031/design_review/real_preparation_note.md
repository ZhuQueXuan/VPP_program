# 本轮真实辅助数据准备结果

2026-10-31。主审授权后，已仅在新work目录实现并运行`real_prepare.py`；没有运行估计器、训练模型或修改旧文件。

从原PREP的admitted命令按每recording每方向4个等距原序索引固定选择，单命令优先L1，得到18recording×8=144事件（72up/72down，均L1）。精确协议与144个ID在读取原Parquet前写入。全部通过原gap及100ms分箱检查，未替换失败事件；每bin4—6个原观测，最大原相邻gap35ms。保存了每事件原微秒时间、相电流、命令与原文件行号NPZ，以及200个100ms观测均值和指令归一progress。

已有DuckDB是CPython3.12二进制，主算法旧环境为3.10。未安装依赖，而是使用已有uv CPython3.12.15、`work/python_packages/pv_metadata_20261015`的DuckDB1.4.3及`work/python_packages/pyreadr`的NumPy2.5.3完成只读解码；下游估计器仍可用原3.10环境读取JSON/NPZ。准备收据明确记录了解码环境，不把它说成主算法环境变更。

`verify_real_preparation.py`随后在原算法3.10环境独立从NPZ以bincount重算全部分箱均值、progress、事前噪声和36个均匀选择组；三类数值最大差均0。原5个来源含422MB Parquet前后SHA同、144个原样本NPZ SHA核同。初始审查有一条多余的dict_values对象直接比较断言失败，移除该审查自身错误后通过；未改变准备数据或选样。

产物为新根下`real_cases.json`、`real_selection.json`、`real_preparation_protocol.json`、`real_preparation_receipt.json`及`real_raw_traces/`；独立核验为本目录`real_preparation_independent_check.json`。

这只是固定记录子样本的准备与核验。不存在潜在干净电流真值或未调控反事实参考；原50Hz记录特征仍只作描述参照。RIDE生产接口在此标N/A，不能把秒级电流数据伪装成分钟级kW减载。TF/CP/LABS尚需由主审按相同真实秒坐标、固定参数及同样扰动独立运行，后续结果限于记录差异和扰动稳定性。
