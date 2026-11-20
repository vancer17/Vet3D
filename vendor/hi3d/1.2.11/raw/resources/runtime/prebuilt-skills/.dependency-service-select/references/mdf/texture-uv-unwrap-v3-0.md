# texture-uv-unwrap-v3-0

为网格建立二维 UV 布局，给后续贴图投影与烘焙使用；可按 need_repair 修复网格。

## 输入

`mesh_glb:B`, `texture_size:int`（当前 Geo 融合层默认 8192；其他调用方按自身配置）, `need_repair:bool`

## 输出

`uv_mesh_glb:B`, `num_faces`, `use_blender_wrap`, `timing`。公共控制/失败字段按 [MDF 契约](README.md)；检查本服务实际返回的 success 和必需业务产物。

## 效果、交接与限制

输出仍需检查 UV 是否存在、是否覆盖所有需贴图的 primitive、修复是否改变几何。texture_size 是 UV/贴图规划参数，不等价于 multiview 生成图分辨率；不要给已水密模型无条件重复修复。

## 来源与范围

[纹理调用方固定版本](http://172.31.0.3:8099/mathmagic/texture-workflow-service/-/blob/10ea6251d9fe3acbd76dc1f071867208f93040cd/workflow_texture.py)、[Geo 融合层](http://172.31.0.3:8099/zhaoshengchu/geo3.0_service/-/blob/63dbc6cb349eab768da4a5a5b1441d7f75a7f7fb/workflow_online_geo_texture.py)。本页覆盖可核对的调用方字段和明确的兼容分支，不声称是服务端所有隐藏参数。文件类型 B/Z、响应验收见 [共用格式](README.md)，调用命令见 [调用与恢复](../calling.md)。复杂几何与纹理交接分别见 [几何](../geometry.md)、[纹理](../texture.md)。

## 产物检查边界

查看 uv_area_ratio、repair_applied、num_vertices/num_faces 及实际 TEXCOORD_0。即使 need_repair=False，导入/展开过程也可能改变索引组织并按 UV 缝拆顶点；不能沿用旧逐顶点数据。UV 利用率很低时，提高 texture_size 也会浪费大量像素，应先检查碎片、重叠面与网格质量。
