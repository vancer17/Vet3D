# 参数参考

核对日期：2026-09-07。价格和服务端参数可能变化；接口拒绝或需要报价时以当前 Hi3D 官方文档为准。

## 图生 3D / 贴纹理

| 参数 | 值 |
| --- | --- |
| `request_type` | 1 几何；2 贴纹理；3 几何+纹理 |
| `model/resolution` | `hi3dv3.0`: `2048quality/2048master`; `hitem3dv2.1`: `1536fast/1536pro`; `hitem3dv2.0`: `1536/1536pro`; `hitem3dv1.5`: `512/1024/1536/1536pro` |
| `pbr` | 0/1；v1.5 不支持 |
| `shading` | 0–1，步长 0.1 |
| `face` | 100,000–5,000,000 |
| `format` | `obj/glb/stl/fbx/usdz/3mf` 或对应 1–6 |

本地图片支持 PNG/JPG/JPEG/WebP，每张不超过 20MB。2–4 张多视图必须包含正面，并标注真实视角。

## 浮雕

`model_type=base/pro`；`height_relief=0.1..50`；`rmbg=0/1`；去背景时 `degree_rmbg=0..1` 步长 0.01；`width=20..600` 整数；`sculpmode=0` 凸雕、`1` 阴雕。格式：EXR/PNG/STL/GLB/3MF/BMP。

## 拆件与多色

拆件输入 GLB/STL/OBJ，不超过 200MB。`model=character` 时 `part=a..f`、`joint=none/ball/dovetail/pin`、`merge=yes/no`；`model=general` 时使用 `level=low/medium/high`。

多色输入带纹理 GLB，不超过 200MB；`number_color=1..8`，0 表示服务端最大颜色模式。输出颜色数不等于可打印部件数。

公开 Credits 参考：默认 v3 Quality 几何 90、纹理 10、PBR 5；浮雕 10、拆件 20、多色 20。余额接口只给 `totalBalance`，不能将前后差值直接归因为本批实际费用。
