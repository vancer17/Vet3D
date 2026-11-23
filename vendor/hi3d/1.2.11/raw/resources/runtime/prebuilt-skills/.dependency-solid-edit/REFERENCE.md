---
name: solid-edit
description: "对带逐面来源与 UV 的闭合实体执行局部布尔并回写几何/材质来源，保留未改表面。"
---

# 来源保留布尔

对带逐面来源与 UV 的闭合实体执行局部布尔并回写几何/材质来源，保留未改表面。

## 输入与完成结果

- 输入：毫米制 NPZ 的 vertices/faces、逐角 UV、material_index；明确布尔工具与操作。
- 输出：scripts/solid_tools.py 的 Source 及 write 输出 NPZ；通过 Manifold face_id/run_original_id 追踪旧面并插值 UV，新切面另标材质。

## 调用与边界

NumPy、manifold3d；输入必须为适用实体，不能用全局重建冒充局部修复。检查源面映射与新面标记，布尔完成不代替拓扑和运动验收。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

<!-- managed-by: sparc3d-runtime -->
