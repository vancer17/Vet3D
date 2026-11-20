# retopology-V2-0

重建面连接关系并控制网格复杂度，生成后续编辑/运行时可用的拓扑。

## 输入

`mesh_mdf:B(GLB)`, `face=50000`, `face_type="triangles"`, `topology_method="pamo"`

## 输出

`model_glb:B`, `face_topology`, `vertices_topology`。公共控制/失败字段按 [MDF 契约](README.md)；检查本服务实际返回的 success 和必需业务产物。

## 效果、交接与限制

已确认调用使用 face_type=triangles、topology_method=pamo；不能凭这些字段猜所有可用枚举。目标 face 不保证精确达到；检查实际面数、孔洞、薄片及纹理/UV 是否保留。

## 来源与范围

[Geo 调用方固定版本](http://172.31.0.3:8099/zhaoshengchu/geo3.0_service/-/blob/63dbc6cb349eab768da4a5a5b1441d7f75a7f7fb/workflow_online.py)。本页覆盖可核对的调用方字段和明确的兼容分支，不声称是服务端所有隐藏参数。文件类型 B/Z、响应验收见 [共用格式](README.md)，调用命令见 [调用与恢复](../calling.md)。复杂几何与纹理交接分别见 [几何](../geometry.md)、[纹理](../texture.md)。
