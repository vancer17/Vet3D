---
name: nose-repair
description: "从已有高模与同源注册 Taro donor 切除错误鼻部、移植鼻子并构造 Poisson 接缝，验证局部几何和区域外来源。"
---

# 鼻部几何修复

从已有高模与同源注册 Taro donor 切除错误鼻部、移植鼻子并构造 Poisson 接缝，验证局部几何和区域外来源。

输入单几何高模 GLB、绑定源哈希的注册 donor NPZ 和全新输出目录。输出修复 GLB、来源映射、局部几何审计与耗时。已有 donor 可独立运行；缺少 donor 时先完成 [人头 workflow 的注册步骤](../.dependency-portrait-reconstruction/references/execution.md#注册步骤)。

按 [package-tools 打包约定](../.dependency-package-tools/references/usage.md) 物化本包，安装 requirements.txt 并提供 Blender 路径，再依 [准备、运行与验收](references/guide.md) 执行。自动 ROI 必须结合当前模型检查；局部通过不等于全头水密或可打印。

<!-- managed-by: sparc3d-runtime -->
