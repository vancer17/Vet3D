---
name: ball-joint
description: "为明确的两个刚体生成配对球窝和间隙试片，保留局部来源表面；用于可打印活动连接的单点设计。"
---

# 球窝接口

为明确的两个刚体生成配对球窝和间隙试片，保留局部来源表面；用于可打印活动连接的单点设计。

## 输入与完成结果

- 输入：显式 BallSpec、关节坐标系、两个闭合 Manifold 实体和试片间隙列表。
- 输出：配对后的实体、坐标/间隙指标及试片；调用 scripts/joints.py 的 ball_tools、attach_ball_joint、pair_metrics，试片入口为 scripts/coupon.py。

## 调用与边界

NumPy、manifold3d；文件导出显式复用 print-export。必须核对完整实体与装入、保持范围；球窝几何不证明摩擦力、疲劳或实物可打印。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

试片裁切、间隙系列与配对来源记录复用 [fit-coupon](../.dependency-fit-coupon/REFERENCE.md)；本入口保留专用机构、支撑和实际公差定义。

<!-- managed-by: sparc3d-runtime -->
