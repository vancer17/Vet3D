# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/motion_check.py](../scripts/motion_check.py) | `translation`, `rotation`, `transform`, `is_rigid`, `overlap`, `require`, `check_intersections`, `check_paths`, `check_motions` |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

[场景样本与姿态数学](scene-samples.md)：scene_samples.sample_frames/world_mesh、pose_math.axis_pose；普通 Python 的实体检查不加载 bpy。

[solid_samples](solid-samples.md) 提供 `intersection_volume`、`sample_solids`；刚体矩阵校验 `is_rigid` 唯一源为 pose_math，motion_check 保留公开导入名。
