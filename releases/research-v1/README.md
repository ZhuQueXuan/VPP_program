# 正式第一版研究内容

版本：`research-v1.0.0`；日期：2026-11-05。

本版以课题一研究点一的当前五点框架组织，保存已执行研究及其代码、保留模型、结果说明与采用决定。保留未采用候选及负结果，避免将“已执行”误写成“效果通过”。其他项目模块沿用仓库原历史，本次不批量提交与研究点一无关的改动或本地删除。

## 内容入口

| 内容 | 入口 |
| --- | --- |
| 当前研究主线与五点框架 | [RESEARCH_FRAMEWORK.md](../../B1算法/RESEARCH_FRAMEWORK.md) |
| 现用算法、接口、参数和模型 | [B1算法](../../B1算法/README.md) |
| 第1点阶段验收 | [first_block_close](../../work/b1_first_block_close_20261103/README.md) |
| 第2点阶段裁定 | [factor_r3c](../../work/b1_factor_r3c_price_comparison_20261104/ROOT_REVIEW.md) |
| 第3点充电阶段收口 | [temporal_ev_demo](../../work/b1_temporal_ev_demo_20261104/STAGE_CLOSE.md) |
| 充电桩单资源模拟演示 | [ev_single_demo](../../work/b1_ev_single_demo_20261104/README.md) |
| 第4点真实数据准入 | [point4_ev_admission](../../work/b1_point4_ev_admission_20261105/ROOT_REVIEW.md) |
| 第4点共享辅助负结果 | [ROOT_DEVELOPMENT_REVIEW.md](../../work/b1_point4_stability_design_20261105/ROOT_DEVELOPMENT_REVIEW.md) |
| 第4点正则R负结果与后续 | [ROOT_RESULT.md](../../work/b1_point4_next_review_20261105/ROOT_RESULT.md) |
| 下一批真实记录要求 | [NEXT_DATA_REQUIREMENTS.md](../../work/b1_point4_next_review_20261105/NEXT_DATA_REQUIREMENTS.md) |

## 仓库与附件的分工

- **仓库直接保存：** B1程序源码和正式模型参数，全部`work/b1_*`研究代码、报告、协议、决策、主要复核记录、图和演示，以及小型结果表。仍使用原相对路径，发布时不重排或重写算法。
- **Release附件保存：** 体积较大的自有实验生成物、模拟输入、逐队列结果、数组与训练/核验中间证据，使用ZIP无损分卷。历史失败方案也保留；附件不是全部进入正式算法的声明。
- **不新增上传：** 原始数据、获取的原表/归档、许可未明确的外部论文文件、运行环境安装包、第三方库目录、本机缓存及敏感凭据。来源、版本、获取/准备脚本与缺口记录保留。详见`EXCLUDED_FILES.json`。

本清单覆盖本机当前`B1算法/`与全部`work/b1_*`研究目录；不将无关研究点、个人会话上下文或未整理的项目全目录直接上传。`.cmd`等历史启动入口不作为本版使用方式；通过程序接口使用算法。

## 恢复与回查

1. 获取本标签的源码快照，安装[环境依赖](ENVIRONMENT.md)。
2. 在[本版本Release](https://github.com/ZhuQueXuan/VPP_program/releases/tag/research-v1.0.0)下载`research-v1-evidence-*.zip`。
3. 使用`SHA256SUMS.txt`核对每个附件；将全部附件解压到仓库根目录，恢复原路径。现有文件与附件按清单互补，不需删除本机目录。
4. `FILE_MANIFEST.json`逐文件记录原始SHA256、大小、存放方式及附件名；`ASSETS.json`记录每卷大小与校验。发布整理脚本为`build_snapshot.py`。

数据获取、外部论文和本机运行依赖不随附件恢复；旧审计中指向这些本地原件的散列不能在没有原件时重新验证。取得对应原件后再按其原协议核查，不以缺文件冒称审计已复现。

发布过程不重新训练、不改研究参数，不将已消费测试数据重新用作独立验证。JSON与源码按原字节保留，避免Git换行转换破坏冻结散列。

## 来源与权限

仓库保持现有私有权限，不新设统一开源许可证。成熟算法、原RIDE数值实现和既有依赖的来源声明保留在各自代码及研究说明中；私有版本快照不改变原作者许可或数据使用条件。Python/R安装包和第三方库按原渠道准备，不镜像进本版。
