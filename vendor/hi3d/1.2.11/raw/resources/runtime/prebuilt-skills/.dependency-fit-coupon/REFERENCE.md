---
name: fit-coupon
description: 从真实配合零件裁切试片或为既有机构生成器组织间隙系列，输出配对文件、来源与打印朝向记录，不推断实物配合成功。
---

# 配对试片

单一目标：为真实接口生成可追溯的成对局部试片。输入为配合双方的毫米 STL、各自打印到装配的刚体矩阵、共同 ROI 和公差定义；也可为调用方已有机构生成器提供显式间隙系列与配对记录。输出为两侧 STL、coupon-to-assembly 变换和来源/待测报告。

按 [打包约定](../.dependency-package-tools/references/usage.md) 与 [清单](package.json) 物化后，可显式 `$fit-coupon`。先读取 [契约和 spec 格式](references/contract.md)，裁切模式运行：

```sh
python scripts/coupon_crop.py --spec pair.json --output new-coupons
```

裁切需要 NumPy、trimesh、manifold3d；Blender 原生对象模式使用 blender_coupon.crop_object 和调用者指定的布尔/清理 profile。series/record 仅需标准库。输入源保持；新输出目录不得存在。公差由真实接口或生成器参数决定，裁切不加额外间隙。

保留配合双方、打印轴向、扣根/释放空间和真实接口来源。局部裁切改变热历史、支撑和足迹，完整最长接口仍需实测。透光厚度片、球窝支撑、燕尾斜面定义留在专用能力；不能用通用圆孔试片代替复杂锁止。完成时回读每个 STL 和双方来源，报告数字检查与实际试配的不同状态。

<!-- managed-by: sparc3d-runtime -->
