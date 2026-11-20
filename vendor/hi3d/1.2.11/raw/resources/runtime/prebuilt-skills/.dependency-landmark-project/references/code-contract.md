# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/project_sapiens2_landmarks.py](../scripts/project_sapiens2_landmarks.py) | `digest`, `run` |
| [scripts/sapiens2_landmarks.py](../scripts/sapiens2_landmarks.py) | `build_landmarks` |
| [scripts/camera_ray.py](../scripts/camera_ray.py) | `pixel_ray`；眼唇/耳部共用正交光线计算 |
| [scripts/ear_projection.py](../scripts/ear_projection.py) | `validate_mapping`, `orthographic_ray`, `fuse_observations`；[耳部契约](ear-projection.md) |
| [scripts/project_ear_landmarks.py](../scripts/project_ear_landmarks.py) | `project`、Blender CLI；[多视角输入输出](ear-projection.md) |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

`project_sapiens2_landmarks.main(argv=None)` 接收一个 JSON 配置文件位置参数，兼容 Blender 的 `--` 分隔并支持 `--help`；run(config) 的相机、来源哈希及映射检查保持不变。
