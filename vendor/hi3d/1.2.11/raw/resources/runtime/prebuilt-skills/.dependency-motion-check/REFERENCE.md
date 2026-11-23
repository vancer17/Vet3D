---
name: motion-check
description: "对明确刚体装配执行完整实体的静态相交、拆装路径及多部件姿态离散碰撞检查。"
---

# 实体运动检查

对明确刚体装配执行完整实体的静态相交、拆装路径及多部件姿态离散碰撞检查。

## 输入与完成结果

- 输入：Manifold 实体字典、毫米制路径/运动计划、显式步长或样本数和部件分组。
- 输出：scripts/motion_check.py 的 check_intersections、check_paths、check_motions 返回样本、最大交叠体积、首次碰撞和错误。

## 调用与边界

NumPy、manifold3d；原装配接口阈值沿用 0.01 mm³，显式姿态接口使用调用方公差，端点检查为保守 AABB 脱离判定。包括实体包含；不证明连续无碰撞、弹性扣合、强度或螺旋互锁保持，产品专属验收继续由调用方执行。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

Blender 求值采样与任意轴刚体姿态见 [姿态采样](references/scene-samples.md)。

多个零件同时运动或螺旋姿态时使用 [全实体姿态采样](references/solid-samples.md)，显式提供每个样本的全部刚体矩阵、对象对与公差策略。

<!-- managed-by: sparc3d-runtime -->
