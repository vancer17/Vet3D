---
name: motion-retarget
description: "依据源/目标休止姿态、骨骼层级与映射，将已有动作样本转换为目标骨架的旋转和根位置。"
---

# 动作重定向

依据源/目标休止姿态、骨骼层级与映射，将已有动作样本转换为目标骨架的旋转和根位置。

## 输入与完成结果

- 输入：source/target 骨架和休止矩阵、动作 samples、明确链映射与尺度配置。
- 输出：scripts/retarget_math.py 的 retarget_samples 返回目标动作采样；two_bone_ik 和层级/刚体检查可独立调用。

## 调用与边界

Blender mathutils、NumPy；不创建源动作、不写用户场景。骨架休止轴校准和 Blender 烘焙由 rig-retarget 工作流衔接，需保留全段形变验收。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

<!-- managed-by: sparc3d-runtime -->
