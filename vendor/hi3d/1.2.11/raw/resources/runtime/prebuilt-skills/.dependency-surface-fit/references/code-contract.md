# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/brush.py](../scripts/brush.py) | `similarity`, `adjacency`, `vertex_normals`, `smooth_target`, `target_surface`, `gaussian_brush`, `closest_compatible`, `signed_areas`, `landmark_weights`, `fit_brush` |
| [scripts/contact_repair.py](../scripts/contact_repair.py) | `repair` |
| [scripts/fit_metrics.py](../scripts/fit_metrics.py) | `distance_stats`, `metrics` |
| [scripts/mesh_io.py](../scripts/mesh_io.py) | `write_obj` |
| [scripts/surface.py](../scripts/surface.py) | `sample_surface`, `smooth_samples` |
| [scripts/ear_fit.py](../scripts/ear_fit.py) | `validate_inputs`, `initialize`, `deform`, `grid_matrix`, `grid_lap`；[耳部契约](ear-fitting.md) |
| [scripts/ear_guard.py](../scripts/ear_guard.py) | `guard_ears`；[耳部验收](ear-fitting.md) |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

注册修复独立接口见 [registered_geometry.py](../scripts/registered_geometry.py) 的 `native_coordinates`、`repair_registered_geometry`，契约见 [注册几何](registered-geometry.md)。
