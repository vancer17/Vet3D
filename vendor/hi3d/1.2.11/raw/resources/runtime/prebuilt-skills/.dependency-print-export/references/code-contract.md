# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/mesh_io.py](../scripts/mesh_io.py) | `to_trimesh`, `read_stl_solid`, `write_3mf` |
| [scripts/stl_to_3mf.py](../scripts/stl_to_3mf.py) | `decode_stl`, `model_xml`, `package_3mf`, `convert`, `main` |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

## 按职责维护的公共模块

- [product_print](../scripts/product_print.py)：`stl`、`export_parts(output, parts)`；后者以安全文件名→对象字典写毫米 STL，返回每件原始拓扑摘要，物化审查模块。创建输出目录并沿用显式覆盖，不生成预览或保证完整事务；调用方使用新修订目录并回读验收。
- [planar_print](../scripts/planar_print.py)：`export_stl_legacy`。
- [frame_print](../scripts/frame_print.py)：`prepare_stl_triangles`、`export_stl`。
- [studio_print](../scripts/studio_print.py)：`stl`。

共享模块先按 package.json 物化。纯几何复用选择 `*_core`；各职责显式导入，路径与 profile 见 [组合契约](../../.dependency-shape-build/references/composition.md)。不同 profile 保留毫米/米、渲染策略和导出清理差异。

- [blender_stl](../scripts/blender_stl.py)：`evaluated_triangles(objects, scale=1000)` 复制世界坐标求值三角形并释放临时 mesh；`stl_bytes(triangles_mm, header, padding=b" ")` 纯序列化，拒绝非有限输入，不修复或焊点。

完整 raw/evaluated、三角化、精度和法线策略见 [STL 原子契约](blender-stl.md)。

`product_print.export_parts` 接收明确对象白名单和输出路径，返回文件与拓扑摘要；STL 数值为毫米。制造件输出与展示半切/GLB 分开，实际 STL 须回读验收。
