# texture-bake-v3-0

将多相机生成图融合到 UV 贴图并输出材质模型；compose 分支只装配现有材质通道。

## 输入

烘焙：`mesh_glb:B`, `view_images:list[B]`, `camera_elevs:list`, `camera_azims:list`, `view_weights:list`, `consistency_mode="off"`, `texture_size:int`, `enable_mesh_inpaint:bool`, `return_visible_artifacts:bool`, `export_preview:bool`；可加 `bake_channels="rgb"/"mr"/"rgb+mr"`, `mr_view_images:list[B/None]`，逐位对齐。

合成：`mesh_glb:B`, `texture_image:B`, `bake_channels="compose"`, `export_preview:bool`；可加 `texture_mr_image:B`, `texture_normal_image:B`。

## 输出

按分支读取 `baked_glb:B`, `texture_image:B`, `texture_mr_image?:B`, `preview_image?:B`, `visible_texture?:B`, `coverage_mask?:B`, `coverage`, `consistency_mode`, `timing`（读取 bake_sec/export_sec）。公共控制/失败字段按 [MDF 契约](README.md)；检查本服务实际返回的 success 和必需业务产物。

## 效果、交接与限制

网格、UV、相机、view_images 和 MR 列表必须同源同序。compose 不执行多视图投影；coverage 不是接缝或颜色一致性保证。先验收第一轮结果再决定是否补绘，实际材料连接、透明度和通道内容需在模型查看器检查。

## 来源与范围

[纹理调用方固定版本](http://172.31.0.3:8099/mathmagic/texture-workflow-service/-/blob/10ea6251d9fe3acbd76dc1f071867208f93040cd/workflow_texture.py)、[Geo 融合层](http://172.31.0.3:8099/zhaoshengchu/geo3.0_service/-/blob/63dbc6cb349eab768da4a5a5b1441d7f75a7f7fb/workflow_online_geo_texture.py)。本页覆盖可核对的调用方字段和明确的兼容分支，不声称是服务端所有隐藏参数。文件类型 B/Z、响应验收见 [共用格式](README.md)，调用命令见 [调用与恢复](../calling.md)。复杂几何与纹理交接分别见 [几何](../geometry.md)、[纹理](../texture.md)。
