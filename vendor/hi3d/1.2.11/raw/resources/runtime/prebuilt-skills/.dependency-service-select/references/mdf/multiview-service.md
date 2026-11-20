# multiview-service

根据几何控制图和参考图生成有序的新视图；几何分支生成 GrayColor，纹理分支生成 RGB/MR 参考。

## 输入

`reference_images:list[B/None]`, `normal_images:list[B]`, `ccm_images:list[B]`, `resolution`, `control_scale`, `steps`, `prompts:list[str]`, `seed?:int`；分支 MV

几何：resolution=2048、control_scale=0.8、steps=4；prompts 按 front/right/back/left。纹理：另传 cfg=1.0、negative_prompt=" "，control_scale=1.0、steps=4；分辨率由当前工作流决定，Geo fast 默认 1024。上述为调用方配方，不是服务全量默认。

## 输出

`generated_images:list[B]`，按输入视图顺序。公共控制/失败字段按 [MDF 契约](README.md)；检查本服务实际返回的 success 和必需业务产物。

## 效果、交接与限制

normal_images、ccm_images、prompts 及输出按视图索引对应。Geo 单图只送一张 reference，缺位 None 的多参考图不可压缩中间槽。控制图背景/CCM 通道见几何交接；新的视图是推断，需检查背面设计、武器数量和纹样一致性。

## 来源与范围

[纹理调用方固定版本](http://172.31.0.3:8099/mathmagic/texture-workflow-service/-/blob/10ea6251d9fe3acbd76dc1f071867208f93040cd/workflow_texture.py)、[Geo 融合层](http://172.31.0.3:8099/zhaoshengchu/geo3.0_service/-/blob/63dbc6cb349eab768da4a5a5b1441d7f75a7f7fb/workflow_online_geo_texture.py)。本页覆盖可核对的调用方字段和明确的兼容分支，不声称是服务端所有隐藏参数。文件类型 B/Z、响应验收见 [共用格式](README.md)，调用命令见 [调用与恢复](../calling.md)。复杂几何与纹理交接分别见 [几何](../geometry.md)、[纹理](../texture.md)。
