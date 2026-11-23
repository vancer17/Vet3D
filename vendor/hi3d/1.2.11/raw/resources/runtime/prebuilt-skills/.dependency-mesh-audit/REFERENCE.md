---
name: mesh-audit
description: "对已有网格执行明确类型的拓扑、STL、表面相交或通道距离检查，输出诊断而不修改源模型。"
---

# 网格检查

对已有网格执行明确类型的拓扑、STL、表面相交或通道距离检查，输出诊断而不修改源模型。

## 输入与完成结果

- 输入：二进制 STL、GLB/BLEND 或 vertices/faces；必须指明单位、对象集合与检查类型。
- 输出：validate_stl.py 提供 STL 闭合/绕序/连通/有限值检查；collision.py 提供严格表面穿越；[geometry_compare.py](references/geometry-comparison.md) 比较同拓扑基线之外的新增穿越；blender_validation.py 提供 Blender 网格与通道采样指标；glb_bounds.py 提供变换后包围盒。

## 调用与边界

Python、NumPy、SciPy、manifold3d；Blender 模式另需 bpy/mathutils。STL 默认单闭合正体积体，表面穿越不含共面/相切或完整包含；通道表面距离不证明内腔连通或流体。实体路径检查交给 motion-check。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

显式对象对 BVH 诊断见 [表面对象对](references/surface-pairs.md)。

拓扑测量与各单位/阈值 profile 使用 [只读测量核心](references/mesh-measure.md)，不在工作流重复计算连通分量与边指标。

纯 NumPy 三角索引面积、边使用次数及精确位置虚拟焊接也见该测量契约；按输入 profile 选择，不能替换原多边形边或实体检查。

需要聚合已加载资产的对象计数、世界包围盒及显式对象的局部拓扑/体积时，读取 [场景测量](references/scene-measure.md)；它保留原始网格、精度与空对象策略，文件载入和报告适配分别组合。

<!-- managed-by: sparc3d-runtime -->
