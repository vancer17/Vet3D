# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/solid_tools.py](../scripts/solid_tools.py) | `Source`, `write_solid`, `cube`, `cylinder`, `stl` |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

`stl(solid, path)` 保留 Manifold 三角形提取和显式文件写入；纯字节转换复用物化的 [print-export 序列化](../../.dependency-print-export/references/blender-stl.md)。使用毫米原坐标、float32 中间计算、法线分母下限 `1e-25`、既有 80 字节零填充头和零属性；不转换单位或修改实体，空实体仍输出零三角记录。它只导出几何，不携带 UV/面来源，也不代表制造通过。共享模块的 Blender 网格提取接口按需导入，本接口在 NumPy/manifold3d 环境即可使用。非有限或不能表示为有限 float32 的坐标现在明确失败，不能依赖历史写入无效 STL 的行为。

[STL 适配测试](../tests/test_stl.py) 通过真实实体和独立二进制记录读取验证坐标、头部、法线及源几何保持。
