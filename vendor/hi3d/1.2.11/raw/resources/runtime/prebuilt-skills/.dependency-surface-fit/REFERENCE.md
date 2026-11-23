---
name: surface-fit
description: "将固定拓扑模板以相似变换、局部 Gaussian brush 和可选耳部共享体积形变拟合到目标表面，并有界修正新穿越。"
---

# 表面拟合

将固定拓扑模板以相似变换、局部 Gaussian brush 和可选耳部共享体积形变拟合到目标表面，并有界修正新穿越。

## 输入与完成结果

- 输入：模板 vertices/quads、目标点/网格/法线、landmarks 和显式迭代/位移预算。
- 输出：scripts/brush.py 的 fit_brush 返回顶点、变换、基准与历史；surface.py 提供采样；contact_repair.py 仅处理基线之外的新穿越；fit_metrics.py 提供距离指标。

## 调用与边界

NumPy、SciPy，穿越修正另需 Blender mathutils。保持模板拓扑；需区分基线/新增穿越、预算耗尽及未收敛，不把最邻近距离作为外观或闭合证明。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

需要将已注册顶点有界修复并还原 native 坐标时，调用 [注册几何核心](references/registered-geometry.md)；归档与 OBJ 写出仍由调用方明确执行。

已有耳部三维对应点且需要调整耳形时，读取 [耳部注册](references/ear-fitting.md)；可独立调用初始化、体积求解与验收。

<!-- managed-by: sparc3d-runtime -->
