# texture-render-v3-0

从网格和相机渲染 normal/CCM/mask 条件；补绘模式针对已有覆盖情况选择相机。

## 输入

`mesh_glb:B`, `resolution:int`；显式 camera_azims/camera_elevs，可选 view_weights；或使用 num_views。

补绘：`op="inpaint_select"`, `mesh_glb:B`, `visible_texture:B`, `coverage_mask:B`, `existing_camera_azims:list`, `existing_camera_elevs:list`, `num_views:int`, `resolution:int`, `texture_size:int`。

## 输出

条件渲染：`normal_images:list[B]`, `ccm_images:list[B]`, `mask_images:list[B]`, `camera_azims`, `camera_elevs`, `view_weights`, `selection_source`；补绘：另读 `masked_target_images`, `missing_mask_images`（list[B]）。公共控制/失败字段按 [MDF 契约](README.md)；检查本服务实际返回的 success 和必需业务产物。

## 效果、交接与限制

条件图是三维几何在相机下的投影，不是已经生成的纹理。所有相机、权重、图像逐位保存；补绘所需 visible_texture/coverage_mask 来自同一网格与 UV。相机角单位与坐标按目标服务定义，不把视频相机矩阵直接换成 azim/elev。

## 来源与范围

[纹理调用方固定版本](http://172.31.0.3:8099/mathmagic/texture-workflow-service/-/blob/10ea6251d9fe3acbd76dc1f071867208f93040cd/workflow_texture.py)、[Geo 融合层](http://172.31.0.3:8099/zhaoshengchu/geo3.0_service/-/blob/63dbc6cb349eab768da4a5a5b1441d7f75a7f7fb/workflow_online_geo_texture.py)。本页覆盖可核对的调用方字段和明确的兼容分支，不声称是服务端所有隐藏参数。文件类型 B/Z、响应验收见 [共用格式](README.md)，调用命令见 [调用与恢复](../calling.md)。复杂几何与纹理交接分别见 [几何](../geometry.md)、[纹理](../texture.md)。
