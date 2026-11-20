# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

## 按职责维护的公共模块

- [product_core](../scripts/product_core.py)：`active`、`mat`、`mesh`、`cyl`、`cube`、`lathe`、`tube`、`boolean`、`bisect_half`、`copy_obj`、`clean`、`pipe`、`hollow_pipe`、`make_stem`、`remove_numerical_islands`。
- [planar_core](../scripts/planar_core.py)：`material`、`mesh`、`bevel`、`bore`、`repair_boolean_flaps`、`cube`、`loop`、`loft`、`ring3`、`tube`、`plate`、`sample`、`height_mesh`、`ring_relief`、`clean_solid_mesh`。
- [frame_core](../scripts/frame_core.py)：`applymods`、`boolean`、`cylinder`、`hole`、`smoothmesh`。
- [box_core](../scripts/box_core.py)：`union_solids`、`apply`、`boolean`、`cyl`、`hole`。
- [studio_core](../scripts/studio_core.py)：`reset`、`mat`、`tag`、`apply`、`smooth`、`cube`、`cyl`、`uv`、`tube`、`bar`、`empty`、`parent`、`boolop`、`cutbox`、`hole`。

共享模块先按 package.json 物化。纯几何复用选择 `*_core`；领域调用路径见 [组合契约](composition.md)。不同 profile 保留毫米/米、渲染策略和导出清理差异。

[primitive_core / blender_primitives](primitives.md) 定义独立坐标构造和显式 Blender primitive profile；既有 product_core.tube 与工作流适配调用该唯一实现。

## product 接口契约

| 模块/函数 | 输入 → 输出与副作用 | 失败及限制 |
|---|---|---|
| `product_core.lathe / pipe / hollow_pipe` | 显式米制剖面/点与半径、材质 → Blender对象；pipe另回采样路径 | 创建场景几何；hollow_pipe是真实布尔内腔。对象连接/内孔是否符合本任务仍需验证。 |
| `product_core.boolean / clean / copy_obj` | 明确对象及操作 → 修改对象或派生对象 | boolean会消费切刀，clean清理指定对象；先留原件，失败不要继续展示残片。 |
