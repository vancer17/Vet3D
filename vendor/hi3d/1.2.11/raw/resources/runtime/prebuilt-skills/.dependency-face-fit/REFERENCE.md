---
name: face-fit
description: 将已有带发或光头高模的同源面部观测注册到 Taro 模板，输出保持拓扑的局部面部 donor、五官与鼻部贴合指标。用于鼻部修复前的注册，不生成光头图、不改原高模，不要求全头拟合。
---

# 面部局部注册

输入已有高模及同源分析目录：带纹理正面图、真实正交相机、表面采样/可见性、Sapiens2 pose+seg 与来源绑定。只有 GLB 时先调用 [portrait-analysis](../.dependency-portrait-analysis/REFERENCE.md)，接收这些产物；已有合格分析直接继续，不做图生图或重新建模。

按 [打包约定](../.dependency-package-tools/references/usage.md) 在仓库外物化本入口。Python 依赖见 requirements.txt；另需 Blender。读取 [执行契约](references/guide.md)，显式提供 source、analysis output 和 Blender。`scripts/face_fit.py CONFIG --blender BLENDER` 组合语义选区、反投影、拟合、检查与 donor 导出。

复用 [head-template](../.dependency-head-template/REFERENCE.md) 的固定模板/映射、[landmark-project](../.dependency-landmark-project/REFERENCE.md) 的真实相机反投影和 [surface-fit](../.dependency-surface-fit/REFERENCE.md) 的 brush 内核；本入口只维护面部可见性适配、来源绑定和局部验收。头发、后脑与颈部不作为当前拟合目标，不重建被遮挡的头皮。

输出 `registered_glb_coordinates.npz`、`registered.glb`、`landmarks.png`、`face_fit_report.json` 及几何/计时记录；donor 保留完整模板拓扑，但只声明观测面部的拟合范围。需修鼻时交接 [nose-repair](../.dependency-nose-repair/REFERENCE.md)，不会在本步骤删面或移植。

验收分别看眼唇残差、鼻部表面距离、接缝邻域与同相机视觉对比；距离低不等于解剖准确。全模板几何失败保留失败指标，不能自动标为鼻部可用；局部 donor 仍需确认鼻部及接缝范围无相关缺陷。来源/关键点错误时停止，不降低置信阈值凑数。

本地子阶段使用 [run-tools 预算与心跳](../.dependency-run-tools/references/budget-run.md)，首版低档每阶段 180 秒；CLI 可显式指定预算，超时停止，不自动重试加时。沿用总任务授权，长任务档位升级按预算契约处理。已有 fit/导出拒绝覆盖，新尝试用新目录；本版不提供自动缓存复用，不把旧结果当作新源码结果。

<!-- managed-by: sparc3d-runtime -->
