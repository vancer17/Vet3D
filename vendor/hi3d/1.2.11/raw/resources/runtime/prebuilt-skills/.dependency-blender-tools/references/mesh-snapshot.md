# 脱离场景资源的网格快照

`mesh_snapshot.mesh_snapshot(obj, *, evaluated, space, scale=1, triangulation="loop", precision="float64", fields=(), depsgraph=None)` 必须显式选择原始/求值与 local/world。返回独立 NumPy vertices (N×3)、triangles (M×3 int32)、bounds（两组坐标，空顶点为 None）。scale 是输出单位/场景单位，不读取 scene.unit_settings。保持顶点编号；不焊接、修复或改变原数据。需要 Blender 和 NumPy，源文件无写入。

`triangulation="require_triangles"` 拒绝非三角面；`loop` 使用 Blender loop triangles；`bmesh` 保留旧 BMesh 对角线方式，只允许纯几何快照。precision 仅接受 float32/float64，单位必须正且有限。空/非有限数据留给领域调用方判断，工具不把它们认定为合格。

可选 fields：loops 返回 triangle_loops；uv 同时返回所有 UV 层的逐 loop 数组；materials 返回槽名称（空槽 None）和逐三角材质编号。不含字段时不复制这些属性，未知字段或 BMesh 属性请求失败，不能静默丢失。返回材质名称不携带节点或图片；需要完整材质导出时仍用场景 IO。

`mesh_data_snapshot(mesh, transform=None, ...)` 对已有 mesh 作同样复制，不取得资源所有权。`mesh_source(obj, evaluated, depsgraph=None)` 上下文管理临时转换：raw MESH 直接借用原 data；求值和曲线使用 to_mesh，成功、转换/回调异常均调用 to_mesh_clear。禁止从上下文返回借用 mesh；用 snapshot 返回独立数组。求值包括 shape keys、骨骼和 modifiers，调用方先设置帧并更新依赖图。

[测试](../tests/test_mesh_snapshot.py) 使用真实 Blender 验证 raw/evaluated、变换、属性和异常清理；快照不是全场景备份或动画缓存。
