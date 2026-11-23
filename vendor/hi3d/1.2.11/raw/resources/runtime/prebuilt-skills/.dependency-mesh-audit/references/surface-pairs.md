# 表面对象对诊断

[surface_pairs.py](../scripts/surface_pairs.py) 提供 Blender mathutils BVH 后端；显式顶点/三角形可由 motion-check 的场景采样器提供，无反向依赖。

`surface_tree(points,triangles,epsilon=0)` 生成三角形 BVH；epsilon 使用当前几何单位。`pair_counts(trees,pairs)` 对显式名称对返回 `a / b` 到相交三角对数量，拒绝同名、缺失和重复对。`bounds_overlap(a,b)` 是严格 AABB 相交预筛选，相切 bounds 排除，调用者按既有 profile 选择使用。

BVH overlap 是表面候选诊断，不能替代 collision.py 的严格穿越过滤，也不检测完全包含。共面/相切要结合使用的 epsilon 和业务接触解释。允许接触对及理由由工作流保存，公共模块不自行忽略任何对象。

独立验收使用相交、分离、包含和相切几何，明确表面计数与实体体积判据的区别；采样器失败必须恢复时刻并释放求值网格。所有单位与对象名由调用方传入。

epsilon 必须非负且有限；points/triangles 可为显式列表或 NumPy 数组。只接收当前姿态数据，不维护按对象名或矩阵的跨帧缓存。每个采样姿态内对各对象建一次树，再对所有显式对象对复用；几何变化后必须重新提取。
