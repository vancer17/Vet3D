# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/extract_stl.py](../scripts/extract_stl.py) | `extract`, `main` |
| [scripts/metric_relief.py](../scripts/metric_relief.py) | `load_metric_heightfield`, `apply_metric_relief`, `ellipse_arc_coordinates` |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

[heightfield_io.py](../scripts/heightfield_io.py)：`load_heightfield(path,key)` 禁用 pickle，只读有限的至少 8×8 数字数组且范围 [0,1]，返回独立副本；key 必须存在。

[height_sampling.py](../scripts/height_sampling.py)：`sample_mesh`；[height_ops.py](../scripts/height_ops.py)：`subtract_baseline`、`normalize_height`、`median_filter`、`repair_pits`。见 [参数契约](heightfield-core.md)。

`extract` 的面积和边使用次数复用物化的 [mesh-audit 三角数组](../../.dependency-mesh-audit/references/mesh-measure.md)：`triangle_double_areas(v,f) * 0.5` 与 `edge_incidence(f, discard_collapsed=False)`。本入口继续负责 STL 解码、精确焊点、轴重排/正面方向、高度采样与修补；报告仍按 `area == 0`、`counts == 1`、`counts > 2` 计数，塌缩边参与统计，不能套用别的非流形或容差 profile。共享计算不修改采样坐标和索引。

本入口在写出统计前构建 Blender 显示网格；重复角点等塌缩面可能使既有 BMesh 法线重算无法完成。数组函数能统计退化项不代表这种 STL 能完整通过显示/提取流程；异常输入先做独立网格诊断，不以未写出报告视为零退化。
