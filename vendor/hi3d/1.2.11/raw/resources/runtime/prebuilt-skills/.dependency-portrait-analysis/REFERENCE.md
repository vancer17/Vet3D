---
name: portrait-analysis
description: "对已有头模渲染调用 Sapiens2，获得关键点、人体分割和预测法线，保留源模型、图像与真实相机绑定；不生成或修补几何。"
---

# 人像视觉分析

对已有头模渲染调用 Sapiens2，获得关键点、人体分割和预测法线，保留源模型、图像与真实相机绑定；不生成或修补几何。

输入已有 GLB 或带来源/相机绑定的渲染图、所需任务和全新输出目录；输出原始 NPZ、叠图、相机/图像绑定及质量判断。已有检测产物可直接检查。

在线推理调用独立 [mdf-call](../mdf-api/SKILL.md)，传入已确认的 sapiens2 endpoint 和所需 tasks，复用已有任务状态。

渲染脚本按 [package-tools 打包约定](../.dependency-package-tools/references/usage.md) 物化后运行。读取 [输入选择、请求与结果契约](references/guide.md)；三维投射交接 [landmark-project](../.dependency-landmark-project/REFERENCE.md)，本 skill 不执行 fitting 或几何修复。

<!-- managed-by: sparc3d-runtime -->
