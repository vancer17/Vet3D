# 三角形提取与 STL 序列化

[blender_stl.py](../scripts/blender_stl.py) 将网格提取和纯字节序列化分开，写入路径、覆盖策略及摆盘仍由调用方承担。

- `evaluated_triangles(objects, scale=1000)`：求值后世界坐标，逐对象释放临时 mesh；不改变源对象。
- `raw_triangles(obj, world, scale=1000, triangulation="loop", precision="float64")`：原始网格；world 必填，显式 loop/BMesh 三角化，保留多边形对角线 profile；返回 N×3×3，无文件/修复/焊接。BMesh 成功与异常均释放。非法模式/单位失败。
- `stl_bytes(triangles_mm, header, padding=b" ", precision="float64", normal_floor=0)`：纯二进制 STL；80 字节头、uint32 三角数、float32 法线/顶点和零属性。拒绝非有限坐标、超长头、非法 padding/精度/下限；不删除退化三角形。默认零法线；可显式指定历史法线分母下限和 float32 中间计算。

灯具适配保留世界坐标、BMesh 对角线和所有原始顶点最低点 Z=0；护甲最终件保留局部坐标与 float32 计算，护甲拆分件保留世界坐标；两种护甲头使用零字节补齐、法线分母下限 1e-20。原始适配均不应用 modifiers；求值接口保持应用 modifiers 的独立契约。检查应回读坐标、三角形、头部与法线，不能用退出码证明可制造性。

[测试](../tests/test_blender_stl.py) 覆盖三角形回读、零面积、非法输入、raw/evaluated 差异和源几何保持。

来源保留布尔的 STL 适配传入毫米三角形，使用 float32、零字节头填充与 `1e-25` 法线分母下限；Manifold 取面、UV/面来源追踪和写入路径继续由调用方维护。灯具标准库试片写入器与面具 mathutils 流式写入器保持独立；不为统一记录格式增加运行依赖或更改归一化、排他创建和临时网格清理语义。

网格读取与临时资源统一复用物化的 [blender-tools 快照](../../.dependency-blender-tools/references/mesh-snapshot.md)。原坐标、精度、三角面前提与领域拒绝条件由此入口保留。
