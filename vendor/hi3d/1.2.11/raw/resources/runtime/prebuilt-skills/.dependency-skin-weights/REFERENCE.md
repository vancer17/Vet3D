---
name: skin-weights
description: "对已有网格与骨骼权重执行局部约束修复或图正则求解，保留范围外权重并输出质量指标。"
---

# 蒙皮权重处理

对已有网格与骨骼权重执行局部约束修复或图正则求解，保留范围外权重并输出质量指标。

## 输入与完成结果

- 输入：vertices/faces、骨骼名和初始权重、明确修复分区/阈值或求解设置。
- 输出：scripts/rigging/skin_weights.py 提供归一性检查、repair_regions 与 stretch_metrics；weight_graph.py 提供 solve_weights/solve_archive 及网格和校准指纹。

## 调用与边界

NumPy、SciPy；图求解器按实际依赖加载。无需网络/Blender；不创建骨架或动作。需验证范围外保持、非负归一、跨侧泄漏及实际动作形变。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

<!-- managed-by: sparc3d-runtime -->
