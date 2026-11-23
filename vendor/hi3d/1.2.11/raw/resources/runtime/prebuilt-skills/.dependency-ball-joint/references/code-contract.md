# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/coupon.py](../scripts/coupon.py) | `coupon_geometry`, `export_coupons`, `main` |
| [scripts/joints.py](../scripts/joints.py) | `BallSpec`, `unit`, `joint_frame`, `require_solid`, `ball_tools`, `attach_ball_joint`, `pair_metrics`, `rotation_about` |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

## 按需资料

- [geometry.md](geometry.md)
- [runtime.md](runtime.md)
- [validation.md](validation.md)

试片公共实现见 [fit-coupon 契约](../../.dependency-fit-coupon/references/contract.md)，通过 package.json 物化。既有报告字段保留；新增配对记录中的 physical_test=not_run 仅表示尚无实际反馈。
