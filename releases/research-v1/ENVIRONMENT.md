# 运行与复核环境

本次是原研究版本归档，不是重新训练或跨电脑重新验收。不会因为源码可导入就声称真实效果已验证。

## Python

依赖清单为[`B1算法/requirements.txt`](../../B1算法/requirements.txt)。本次发布机器的Python为3.10系列；最新训练环境记录见[`development/environment.json`](../../work/b1_point4_next_design_20261105/development/environment.json)，该大实验记录随Release附件恢复。

建议在独立Python环境中按清单安装，将`B1算法`加入模块搜索路径后通过`b1_api`调用。源码接口见[`B1算法/README.md`](../../B1算法/README.md)，完整原型说明见[`RESEARCH_POINT_ONE.md`](../../B1算法/RESEARCH_POINT_ONE.md)。不需要双击启动器。

## R/CPOP

原生CPOP过程分析需要R和`cpop`。原研究使用R 4.6.1、cpop 1.0.10；具体历史路径与散列保留在[`runtime.json`](../../B1算法/b1_algorithm/runtime.json)。本版不打包数百MB的R安装环境。迁移到其他机器时须安装对应版本，并按该文件配置实际Rscript和R库位置；原有路径记录不会自动变成新机器上的有效路径。

仅加载已保存的连续曲线、查看HTML演示或部分连续估计接口，不等于已安装或测试了原生CPOP依赖。不同入口按其说明使用。

## 数据与模型

正式模型参数随源码保存；部分研究分支模型及大数组在Release附件。原始ACN、iFlex、London等数据按对应研究目录的来源与准备协议自行取得，不随本版本重复分发。

模拟生成器、固定种子、开发/确认分工及负结果完整保留。审计脚本若需要缺省未发布的原始数据或外部依赖，会明确缺失；不能把只验证文件结构、导入或模拟的结果写成现场验证成功。
