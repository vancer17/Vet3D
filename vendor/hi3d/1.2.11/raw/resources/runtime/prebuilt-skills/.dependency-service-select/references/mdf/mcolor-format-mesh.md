# mcolor-format-mesh

转换模型容器/表示，或把 OBJ/STL/GLB 规范成 GLB 以接入后续服务。

## 输入

`func="glb2format"`, `glb:B`, `transfer_format:int`, `output_file_name="model"`；3MF 可加 `threemf_mode="auto"/"orca"/"standard"`。格式码：1 OBJ、2 GLB、3 STL、4 FBX、5 USDZ、6 3MF。

规范成 GLB：`func="format2glb"`, `input_model:B`, `input_format="obj"/"glb"/"stl"`, `output_file_name="model.glb"`。

## 输出

导出：`output_model:B`, `mode`；转 GLB：`output_model/glb:B`, `mode`, `vertex_count`, `face_count`。公共控制/失败字段按 [MDF 契约](README.md)；检查本服务实际返回的 success 和必需业务产物。

## 效果、交接与限制

文件名后缀必须匹配真实内容。OBJ/FBX 输出可能是含依赖文件的 ZIP，不能只提取其中一个 mesh 丢掉贴图。STL 不保存纹理；3MF 的 auto/orca/standard 是导出组织模式，不证明模型可打印。

## 来源与范围

[Geo 调用方固定版本](http://172.31.0.3:8099/zhaoshengchu/geo3.0_service/-/blob/63dbc6cb349eab768da4a5a5b1441d7f75a7f7fb/workflow_online.py)。本页覆盖可核对的调用方字段和明确的兼容分支，不声称是服务端所有隐藏参数。文件类型 B/Z、响应验收见 [共用格式](README.md)，调用命令见 [调用与恢复](../calling.md)。复杂几何与纹理交接分别见 [几何](../geometry.md)、[纹理](../texture.md)。
