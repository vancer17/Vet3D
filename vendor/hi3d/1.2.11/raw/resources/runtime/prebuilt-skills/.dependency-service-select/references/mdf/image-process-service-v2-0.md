# image-process-service-v2-0

将背景透明化，得到后续几何前景 mask；不改变模型几何，因为输出仍是二维图。

## 输入

`image:B`, `only_remove=True`

## 输出

`image:B(RGBA PNG)`，alpha 表示前景 mask。公共控制/失败字段按 [MDF 契约](README.md)；检查本服务实际返回的 success 和必需业务产物。

## 效果、交接与限制

检查 RGBA 的 alpha 同时含背景和非空前景，检查武器、毛发、孔洞、底座是否保留。白色 RGB 背景不等于 alpha mask。Geo 的空 mask 原图回退属于调用方逻辑，原子调用失败时不要伪造合格 mask。

## 来源与范围

[Geo 调用方固定版本](http://172.31.0.3:8099/zhaoshengchu/geo3.0_service/-/blob/63dbc6cb349eab768da4a5a5b1441d7f75a7f7fb/workflow_online.py)。本页覆盖可核对的调用方字段和明确的兼容分支，不声称是服务端所有隐藏参数。文件类型 B/Z、响应验收见 [共用格式](README.md)，调用命令见 [调用与恢复](../calling.md)。复杂几何与纹理交接分别见 [几何](../geometry.md)、[纹理](../texture.md)。
