---
name: relief-map
description: "从已有浮雕提取线性高度数据，或将度量高度场映射到明确目标曲面，保留尺度与来源记录。"
---

# 浮雕高度映射

从已有浮雕提取线性高度数据，或将度量高度场映射到明确目标曲面，保留尺度与来源记录。

## 输入与完成结果

- 输入：二进制 STL 与轴/正面方向/目标网格密度，或 height、mask、bounds_xy_mm 的度量高度场与旋转曲面。
- 输出：extract_stl.py 提供统一采样、修补与输出字段；metric_relief.py 提供曲面弧长映射。

## 调用与边界

NumPy、SciPy，曲面模式另需 Blender。高度场投影丢失倒扣；各模式字段与线性单位不同，不混用。读取前后/repair_mask 等诊断，保持 XY 比例与显式深度。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

首击采样与归一化/修补可分别直接调用，参数、精度和三类 profile 见 [高度场核心](references/heightfield-core.md)。

<!-- managed-by: sparc3d-runtime -->
