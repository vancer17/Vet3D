# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/audit_models.py](../scripts/audit_models.py) | `audit`, `main` |
| [scripts/blender_validation.py](../scripts/blender_validation.py) | `mesh_metrics`, `check_stl`, `passage_clearance`, `require_print_topology` |
| [scripts/collision.py](../scripts/collision.py) | `segment_hits_triangle`, `crossing_pairs`, `triangle_stats` |
| [scripts/fresh_review.py](../scripts/fresh_review.py) | `execute`, `main` |
| [scripts/scene_measure.py](../scripts/scene_measure.py) | `object_bounds`, `measure_objects`；完整字段与回读适配见 [场景测量](scene-measure.md) |
| [scripts/geometry_compare.py](../scripts/geometry_compare.py) | `triangulate_faces`, `compare_geometry` |
| [scripts/glb_bounds.py](../scripts/glb_bounds.py) | `inspect` |
| [scripts/validate_stl.py](../scripts/frame_stl.py) | `inspect_binary_stl`, `main` |
| [scripts/verify_stl.py](../scripts/verify_stl.py) | `validate`, `main` |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

## 按职责维护的公共模块

- [product_audit](../scripts/product_audit.py)：`topo`。
- [planar_audit](../scripts/planar_audit.py)：`bounds`。
- [brush_audit](../scripts/brush_audit.py)：`bounds`。
- [studio_audit](../scripts/studio_audit.py)：`bounds`、`metric`。

共享模块先按 package.json 物化。纯几何复用选择 `*_core`；各职责显式导入，路径与 profile 见 [组合契约](../../.dependency-shape-build/references/composition.md)。不同 profile 保留毫米/米、渲染策略和导出清理差异。

product_audit.topo 对曲线使用临时求值网格，释放后保持源对象类型；指标不保证闭合或可制造性。

[surface_pairs](surface-pairs.md)：surface_tree、pair_counts、bounds_overlap；不改源模型。

[mesh_measure.py](../scripts/mesh_measure.py) 的 `measure_mesh` 统一临时 BMesh 计量；参数、单位、返回字段和兼容 profile 见 [只读测量](mesh-measure.md)。

## product 接口契约

下表 validation 是产品包对本能力 blender_validation.py 的物化别名；源码仍由上表链接的文件维护。

| 模块/函数 | 输入 → 输出与副作用 | 失败及限制 |
|---|---|---|
| `validation.mesh_metrics / check_stl` | 对象或实际STL → 焊接诊断副本的连通/边界/非流形/退化/体积 | check_stl按毫米读为米，移除临时导入；GLB材质拆顶点不直接等同打印缺陷；数字指标不是实物批准。 |
| `validation.passage_clearance` | 真实对象、毫米采样点、要求半径 → 最近距离与采样误差界 | 距离本身不能证明点在空腔，须另查起终点和连通；有限采样不冒称全域绝对最小。 |

## 打印拓扑门槛

`validation.require_print_topology(results)` 对实际STL回读结果要求单连通、无边界/非流形/退化和正体积；构建器先保存测量再调用此门槛，失败保留候选并非退出0。此门槛不覆盖尺寸净空、流体、材料或实物性能。

GLB 容器读取直接复用 [glb-clips 的 read_glb](../../.dependency-glb-clips/references/contract.md)，只检查版本、总长、完整对齐 chunk 和唯一首个 JSON，不执行动画合并。audit_models 在清场和导入前验证容器；glb_bounds 保留原世界变换、尺寸/实例数/动画/外部资源报告，仅从单个嵌入 BIN 的非 sparse float VEC3 读取位置，检查有限值、步长与 accessor/view/buffer 字节范围，拒绝外部位置 buffer 或多 BIN 的歧义。它不是完整 glTF 验证器，不处理压缩位置、蒙皮/形态键求值或动画姿态；动画范围检查仍由 Blender audit_models 完成。
