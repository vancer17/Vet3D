---
name: texture-bake
description: 使用本地 Blender Cycles 将已有高模材质或几何细节烘焙到带 UV 的目标网格，输出颜色或切线法线 PNG 并恢复临时场景状态。
---

# 高模到 UV 烘焙

输入为同场景且对齐的源 mesh、已有 UV 和独立节点材质的目标 mesh、通道及显式 cage/ray/清空/设备/输出参数；输出为 packed image 和 PNG、设备/参数/耗时报告。源几何、目标拓扑和 UV 保持。只处理本地 DIFFUSE 颜色、EMIT 和 OpenGL +Y 切线 NORMAL，不调用同名远端服务。

按 [打包约定](../.dependency-package-tools/references/usage.md) 与 [package.json](package.json) 提供完整包，可显式 `$texture-bake`。先读取 [契约](references/contract.md)，在后台 Blender 的 Object 模式，通过已安装 scripts 路径导入：

```python
from texture_bake import bake_image
image, report = bake_image([high], low, path=output_png, name='Albedo', size=1024,
    kind='DIFFUSE', colorspace='sRGB', cage=0.01, ray=0.05, margin=8, use_clear=True)
```

示例 cage/ray 是当前场景单位，需按模型尺度确定；不自动注册、重拓扑或生成 UV。EMIT 源着色、保护区域/初始颜色和最终贴图绑定由调用方明确提供。默认 CPU、失败传播和禁止覆盖；Metal 等设备及 CPU 回退必须显式选定。

完成后检查源/目标保持、贴图颜色空间、实际覆盖、接缝和眼口/边缘；成功烘焙不等于颜色融合或视觉质量通过。临时图像节点、选择、可见性、bake/设备/颜色设置在失败和成功后恢复，返回图像保留。工作流负责计时汇总和最终材质/工程保存。

<!-- managed-by: sparc3d-runtime -->
