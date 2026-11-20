# 只读网格测量

`mesh_measure.measure_mesh(mesh, *, transform=None, unit_mm=1.0, weld=None, area_epsilon=0.0, area_inclusive=False)` 只在临时 BMesh 上读取/计算，成功和失败都释放。对象是否先求值由调用方显式决定；不编辑原网格、合并场景或自动修复输出。需要 Blender bmesh，无 NumPy 依赖。

返回 vertices/faces/triangles、components、boundary_edges/nonmanifold_edges/inconsistent_winding_edges、degenerate_faces、finite、signed_volume/bounds（变换后的原坐标单位）及 signed_volume_mm3/bounds_mm。空网格 bounds 为 None，体积为 0。components 包含孤立顶点。有限性是诊断字段，不把非有限网格认定为通过。

`transform` 在测量前作用于临时几何；可选 `weld` 只焊接诊断副本。面积阈值和焊接距离均使用该坐标系原单位，`unit_mm` 仅换算返回长度/体积。area_inclusive 显式选择 `<=` 或 `<`；长度、体积或面数不证明自交/包含/可制造性。非法单位/阈值先失败。

兼容适配：screw-bottle 用原始毫米、退化面积 `<=1e-12`；keychain 原始米转换 mm³，保留 non_manifold_edges/finite_coordinates 旧字段；mask-design 用毫米、面积 `<1e-9`，仅满足旧闭合/非退化前提才给体积；lamp-design 先世界变换、保留体积先按米³四舍五入再换算和对象 dimensions。blender_validation 的可选 weld 与 `<1e-16`、product_audit 的 mesh 原始/curve 求值及 ml 口径保持。阈值校验、对象筛选和业务通过条件仍在各适配器。

通过物化清单导入；[测试](../tests/test_mesh_measure.py) 在真实 Blender 中检查封闭/反绕序/空/多分量/变换/只读保持。迁移调用方须逐字段比较其原 profile，不能用统一字段名称覆盖旧契约。

## 三角索引数组

[triangle_arrays.py](../scripts/triangle_arrays.py) 只依赖 NumPy，不访问文件或 Blender，不修改输入；坐标与阈值均由调用方明确，不推断毫米。

- `triangle_double_areas(vertices,triangles)`：N×3 坐标、M×3 索引 → M 个叉积模长（两倍面积）。保留输入的 float32/float64 运算精度；不自动换算、焊点或丢面。
- `edge_incidence(triangles,discard_collapsed=...)`：整数 M×3 → 无向唯一边数组、使用次数、塌缩边使用次数。discard_collapsed 必填；仅按索引排序/计数，不做几何焊接。空 M×3 返回空边/次数。
- `edge_counts(triangles)`：排除塌缩边后给 unique_edges/boundary_edges/edges_over_two_faces/collapsed_edge_uses；该口径保留三角化内部边，不等同 BMesh 原多边形边。
- `measure_indexed(coords,triangles,area_threshold=1e-12,exact_weld=False)`：局部坐标 → 顶点/三角数、finite_coordinates、local_bounds_min/max、degenerate_triangles、area_threshold_local_squared、indexed_topology。面积采用 `<=`；无三角或坐标非有限时退化数为 None，空/非有限 bounds 为 None。有限非负阈值必须显式符合来源单位。exact_weld 对有限坐标增加 exact_position_weld_diagnostic，按完全相同位置重新映射索引，既不跨对象合并也不做容差焊接。

二进制 STL 保留塌缩边参与非流形和连通图统计，面积先转换 float64，严格零面积与近零非零分别记录；表面 triangle_stats 保留两倍面积与尺度相关阈值。不能把这两种 profile 改成同一退化判据。Trimesh 的 watertight/winding/面连通与 BMesh 的原始边/孤立顶点统计也不同，调用方仅使用库指标的薄适配不另造重复算法。

数组边界测试见 [test_triangle_arrays.py](../tests/test_triangle_arrays.py)；真实 Blender 对象/材质/UV 元数据由调用工具负责，数组核心不包含来源哈希、显示副本或产品放行条件。
