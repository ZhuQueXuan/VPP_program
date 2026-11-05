# B1源码目录整理

2026-10-30，按用户要求，将当前B1正式运行源码移入根目录 `B1算法/`，后续在该目录开发。过程材料仍留在 `work/`。

- 当前入口：`../../B1算法/b1_api.py`。
- 当前实现：`../../B1算法/b1_algorithm/`，保留三模块结构及原有导入名称。
- 17个Python文件、1个必要的R计算文件、2份运行配置及Python依赖清单随源码迁移。
- 4份详细说明及2份来源记录放在本目录 `documentation/`，不混入运行源码目录。旧缓存完整保存在 `legacy_cache_tree/`，没有删除文件。
- 原根目录 `b1_api.py` 和 `b1_algorithm/` 已迁走，避免同时维护两份当前源码。原 `b123_api.py` 属于旧B1/B2/B3兼容入口，保持不变。

两处代码改动只适配目录：统一入口定位项目根目录的层级，以及直接调用过程模块时默认日志目录定位。算法参数、公式和数值流程不变。R安装、参考模型、Python虚拟环境仍复用已有位置，源码不从历史 `work/` 原型导入实现。

逐文件原路径、现路径、整理前SHA见 [before_manifest.json](before_manifest.json)；迁移后检查见 `organization_receipt.json`。

[算法详细说明](documentation/b1_algorithm/README.md)、[参考说明](documentation/b1_algorithm/reference/README.md)、[过程说明](documentation/b1_algorithm/process/README.md)、[效应说明](documentation/b1_algorithm/effects/README.md)保留迁移前内容。里面的源码相对路径按 `before_manifest.json` 对应到新目录；历史文件路径不代表新的开发入口。

`verify_migration.py`使用同一输入比较迁移前后实际原生CPOP结果、原始电量及参考模型预测；另复用既有31项事件到效应核验，输出到本目录 `after/`，不覆盖历史结果。原研究脚本与科学文件保持，后续从历史脚本启动时，须把根目录 `B1算法/` 加入Python搜索路径。
