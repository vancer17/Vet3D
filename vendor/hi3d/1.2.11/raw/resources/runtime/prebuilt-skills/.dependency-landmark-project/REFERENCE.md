---
name: landmark-project
description: "将带相机与来源证据的 Sapiens2 眼唇或多视角耳部关键点投影为目标网格三维配准点。"
---

# 关键点投影

将带相机与来源证据的 Sapiens2 眼唇或多视角耳部关键点投影为目标网格三维配准点。

## 输入与完成结果

- 输入：目标网格、正交方形渲染相机/图像、1×308×2 pose、1×308 scores，以及同版模板映射和来源哈希。
- 输出：scripts/project_sapiens2_landmarks.py 输出三维 landmarks 与来源记录；scripts/sapiens2_landmarks.py 提供映射与置信过滤。

## 调用与边界

Blender、NumPy；显式依赖 head-template 与 Blender IO。只支持实现中验证的正交方形相机，不将透视图硬套；默认置信阈值与眼唇点预算见代码。至少四个非共线有效点，旧图/模型哈希不符即停止。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

需要左右耳多视角观测时，读取 [耳部反投影](references/ear-projection.md)；只检测目标，复用固定模板映射。

<!-- managed-by: sparc3d-runtime -->
