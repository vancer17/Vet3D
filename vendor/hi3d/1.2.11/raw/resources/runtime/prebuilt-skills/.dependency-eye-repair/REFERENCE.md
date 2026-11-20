---
name: eye-repair
description: "对已有头模定位并切除错误瞳孔或虹膜几何，以光滑球冠补全可见眼球，检查眼睑边界和多视角效果；按需交接 continuous remeshing。"
---

# 眼球几何修复

对已有头模定位并切除错误瞳孔或虹膜几何，以光滑球冠补全可见眼球，检查眼睑边界和多视角效果；按需交接 continuous remeshing。

输入已有 GLB/BLEND、真实相机或可核验的网格选择、要保留的眼睑与成品要求。输出另存模型、实际切除区域图、同相机前后对比、侧视近景及拓扑检查结论。适用于用户明确需要无瞳孔/虹膜结构的灰模眼睛。

通过 [blender-tools](../.dependency-blender-tools/REFERENCE.md) 操作当前模型并另存检查点；使用 [mesh-audit](../.dependency-mesh-audit/REFERENCE.md) 验证所声明的拓扑检查。按 [切除、球冠与验收](references/repair.md) 执行。

这是需要针对当前模型选择区域和检查结果的操作 skill，未提供通用自动定位或自动修复脚本。仅要求此局部操作时不启动上游图像生成、视觉服务或整头重建。

<!-- managed-by: sparc3d-runtime -->
