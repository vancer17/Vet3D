---
name: exterior-surface
description: "从装配模型的高分辨率表面体素中剔除封闭内部结构，保留与外界空气相邻的表面，生成 Geo2 稀疏坐标；用于口腔、眼球装配后的几何条件准备。"
---

# 外露表面体素

输入装配完成的静态 GLB，或绑定源模型与格网的高分辨率表面 NPZ；输出外露/剔除体素、Geo2 latent coords 和检查报告。当前实现生成体素条件，不删除原 mesh、不重建水密网格、不保留骨架/UV 到新几何。

本 skill 解决封闭内部壳层混入条件的问题。张嘴后与外界连通的口腔仍是表面，不能自动删掉可见牙齿、舌头或眼球正面。先读 [定义、运行与验收](references/extraction.md)。

按 [package-tools](../.dependency-package-tools/references/usage.md) 物化后运行 `scripts/exterior_surface.py`。CPU 过滤依赖 NumPy/SciPy；从 GLB 体素化另需与目标部署相符的 hitem_infer、PyTorch/CUDA 和 pytorch_voxelization，复用上游算子，不复制其实现。

用于 geometry-v4-geo2-pass1-cfg-distill-quant 时读取 [服务对照](references/geo2.md)。已有图像条件包由 [geometry-input](../.dependency-geometry-input/REFERENCE.md) 组装，本 skill 仅添加经过过滤的唯一坐标 NPZ。

交付前检查穿过眼球、口腔和颈底的切片，并与原模对照。服务调用交接独立 [mdf-call](../mdf-api/SKILL.md)，提交同源 GLB 与配套 prep.zip，复用已有任务；维护本 skill 不启动在线推理。

<!-- managed-by: sparc3d-runtime -->
