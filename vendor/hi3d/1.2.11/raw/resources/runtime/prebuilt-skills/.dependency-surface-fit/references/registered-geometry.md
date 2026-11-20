# 注册几何修复

`registered_geometry.native_coordinates(vertices, linear, offset)` 将有限非空 Nx3 世界坐标按 `world = native @ linear.T + offset` 逆变换；要求可逆 3×3 linear 与长度 3 offset。输入保持，非法形状、非有限值或奇异矩阵抛 ValueError。

`repair_registered_geometry(rest, vertices, faces, linear, offset, *, budget_fraction=1e-4, max_trials=1000)` 接收同拓扑同坐标基线/当前顶点和整数三角形或四边形，返回 `(corrected_world, corrected_native, correction_report)`。复用 [mesh-audit](../../.dependency-mesh-audit/references/geometry-comparison.md) 的固定三角化与穿越定义，仅修复基线外新增穿越；返回原有 trials/history/budget/最大位移字段，不保证预算内必收敛。无文件/场景写入，原数组/面序不变；NPZ、OBJ、文件名与报告 scope 由调用方管理。

需要 NumPy 和 Blender mathutils；使用物化包的 `scripts` 路径导入。非负预算与整数试次先校验；修复前验证变换，避免无效输入先进行昂贵搜索。零预算/零试次保留顶点但仍返回实际未修复状态。只读比较直接用 mesh-audit，不需调用本修复函数。测试以合成拓扑、非平凡仿射变换和实际穿越检查验证输入保持、逆变换与失败边界。
