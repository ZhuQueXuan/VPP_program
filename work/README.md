# 项目过程文件

2026-10-17 D072：[执行进展综合review](project_progress_review_20261017/执行进展综合review.md)及[三项审查入口](project_progress_review_20261017/README.md)。当前研究快照1a88be0已GitHub保存，范围/字节核验见[git_delivery_20261017](git_delivery_20261017/snapshot_manifest.json)。审查提出按正式方法输出收敛与明确阶段判据，未自动启动下一实验或升级P1。

2026-10-17 D071已有六类证据补强：[四层矩阵](process_notes/2026-10-17_六类资源四层证据矩阵.md)、[数据核验要求](process_notes/2026-10-17_六类资源调研与数据核验要求.md)。唯一深入问题及实际运行留在[electric_water_heating_research_20261016](electric_water_heating_research_20261016/README.md)，继续维护原[水箱过程记录](process_notes/2026-10-16_储热式电热水器研究.md)，未新建正式outputs报告。原六类成果代码/参数/失败保持，现用卡DC-20261017-04。

按2026-10-08决定，所有当前过程材料集中放在此目录。01—04资料目录和三个算法顶层目录保留；正式成果、算法核心代码、配置、样例、数据和可复现结果仍在原位置。

| 目录 | 保存内容 |
| --- | --- |
| `resource_market_adaptation_scoring/` | 评分路线的文档编制、专利处理、截图、临时PDF、试跑明细、检查及备份 |
| `resource_regulation_behavior_causal_decomposition/` | 驱动因素路线的文档编制、Excel预览、临时PDF、试跑明细、检查及备份 |
| `resource_static_classification_baseline/` | 静态基线的逐条派生记录、数据质量核查和运行元数据 |
| `tmp/pdfs/` | 从正式任务书渲染出的临时页面截图 |
| `python_caches/` | Python运行缓存，保留原有缓存迁入记录 |
| `old/` | 原根目录历史归档整体搬入，保留内部结构，默认不读取 |
| `folder_organization_20261008/` | 此次整理说明、逐文件搬迁记录、核对结果及修改前路径文件副本 |
| 其他现有具名目录 | 课题一共用或跨路线的文档处理、核验、依赖和过程脚本 |

三套算法目录内不再建立独立的 `work/`。新增过程文件按所属路线放在对应子目录，避免同名任务混在一起。报告源稿生成的PDF副本在各路线 `report_exports/`；正式来源PDF、正式成果图表继续保存在资料或成果目录。

根目录 `outputs/` 的共用正式成果已展开为单层文件；原 `reports/` 和其中 `figures/` 的9个文件均直接放在 `outputs/`。

Python可通过此目录的 `run_python.ps1` 运行，自动将缓存集中在这里；例如在项目根目录运行：

```powershell
./work/run_python.ps1 resource_static_classification_baseline/run_baseline.py
```

历史备份和发布收据保留当时的内容与哈希。如其中记录了原来的 `<方法目录>/work/`，对应现行位置为本目录的 `<方法目录>/`，可查阅[整理说明](folder_organization_20261008/整理说明.md)。整理只移动文件，不删除或覆盖同名文件。
