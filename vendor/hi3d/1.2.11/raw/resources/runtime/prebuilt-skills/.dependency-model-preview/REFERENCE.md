---
name: model-preview
description: "从已有模型与明确展示姿态产生多视角图片、可视 GLB 和姿态构图检查，复用当前几何。"
---

# 模型预览

从已有模型与明确展示姿态产生多视角图片、可视 GLB 和姿态构图检查，复用当前几何。

## 输入与完成结果

- 输入：已有 Blender 对象或 NPZ/source.blend、显式输出位置及展示/装配姿态。
- 输出：头部正交检查场景与图片；scripts/product/media.py 提供图像/剖面/GLB/姿态构图；scripts/product_scene.py 提供保留材质的加载和网页动作导出。

## 调用与边界

Blender、NumPy；product/product_core.py 按米，product_scene 的来源按毫米并转换。输出仅是预览，不能代替打印或实体运动验收。视频帧只在明确请求时生成。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

同步片段合并复用 [glb-clips](../.dependency-glb-clips/REFERENCE.md)，具体时间/通道限制见其契约；本流程仅为已明确同时播放的动作选择全部 clips。

需要独立构图、灯光或显式对象 GLB 导出时读取 [展示原子](references/preview-atoms.md)，选择 raw/evaluated bounds 和完整导出选项；导出和逐帧检查恢复临时状态。

对已规范化来源生成正背侧顶与 hero 检查图时，使用 [来源视图](references/source-views.md)，显式传入原流程的取景和灯光参数。

头部检查保留原几何与场景单位，读取 [头部预览](references/head-preview.md) 后调用 `head_preview.studio/render_view`。

<!-- managed-by: sparc3d-runtime -->
