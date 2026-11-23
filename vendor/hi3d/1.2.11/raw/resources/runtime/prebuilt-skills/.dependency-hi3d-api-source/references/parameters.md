# 参数契约

本适配器依据分享包标记为 **2026-09-07** 的协议快照；迁移时官方文档访问未成功，因此未重新验证在线版本、价格或账户权限。实际服务契约变化时先核对公开文档再调整实现，不通过反复收费提交探测参数。以下是当前脚本允许的范围，默认值唯一来源为 [defaults.json](../defaults.json)。默认配置可被明确任务覆盖，不继承分享者个人偏好。网页带钻项与 Agent/网页差异见 [网页 option 门禁](../../hi3d/references/web-option-gates.md)；钻石表示会员，积分不能改这些字段。

## 建模与贴纹理

[公开创建接口说明](https://docs.hi3d.ai/zh/api/api-reference/list/create-task)

| 参数 | 本地校验范围 |
| --- | --- |
| model / resolution | 下表的兼容组合；切换版本须同时指定档位 |
| request_type | 1 几何；2 现有 GLB 贴纹理；3 几何与纹理 |
| 单图 / 多视图 | 1–4 张本地 PNG/JPG/JPEG/WebP，每张非空且 ≤20 MiB；只校验路径、扩展名、大小与哈希，图片内容由调用方检查 |
| views | 多视图需逐张标记 front/back/left/right，标签唯一且包含 front；脚本按此顺序上传并生成 multi_images_bit |
| mesh / mesh_url | 仅 request_type=2，需要 GLB 及参考图；文件或 URL 择一；v2.0/v2.1 不支持独立贴纹理 |
| pbr | 0/1；v1.5 不支持，纯几何不传 |
| shading | 0–1，步长 0.1；v1.5 不传 |
| face | 整数 100000–5000000；目标面数不等于实际面数 |
| format | obj=1 / glb=2 / stl=3 / fbx=4 / usdz=5 / 3mf=6 |

| model | resolution |
| --- | --- |
| hi3dv3.0 | 2048quality、2048master |
| hitem3dv2.1 | 1536fast、1536pro |
| hitem3dv2.0 | 1536、1536pro |
| hitem3dv1.5 | 512、1024、1536、1536pro |
| scene-portraitv2.1 | 1536profast、1536pro |
| scene-portraitv2.0 | 1536pro |
| scene-portraitv1.5 | 1536 |

resolution 是服务档位，不保证导出贴图尺寸；人像系列是可选契约项，不自动替代用户指定版本。独立贴纹理 mesh 没有来自快照的可靠大小上限，脚本仅要求非空 GLB；远程输入大小/内容需服务端校验。

## 浮雕

[公开浮雕说明](https://docs.hi3d.ai/zh/api/api-reference/list/depth-create-task)

单张本地图（同上限）或 HTTPS `image_url` 二选一，不接受 mesh/多视图。

| 参数 | 本地校验范围 |
| --- | --- |
| model_type | base / pro |
| height_relief | 0.1–50；高度单位未确认 |
| rmbg | 0 保留背景 / 1 去背景 |
| degree_rmbg | rmbg=1 时 0–1，步长 0.01；同时移除底座参数 |
| shape_base / thickness_base | rmbg=0 时：0 方形 / 1 圆形；0.1–20 mm，步长 0.1；未指定时为 0 / 1.0 |
| width | 整数 20–600 mm；导出 STL 仍需导入软件明确单位 |
| sculpmode / response_format | 0 凸雕 / 1 阴雕；仅 url |
| format | exr=1 / png=2 / stl=3 / glb=4 / 3mf=5 / bmp=6 |

## 拆件与多色

[公开拆件说明](https://docs.hi3d.ai/zh/api/api-reference/list/split-create-task)、[公开多色说明](https://docs.hi3d.ai/zh/api/api-reference/list/multicolor-create-task)。二者输入均为 mesh 或 HTTPS mesh_url，二选一；本地文件非空且 ≤200 MiB。

| 能力 | 参数及范围 |
| --- | --- |
| split 输入与格式 | GLB/STL/OBJ；输出格式编号同建模 |
| split model=character | part=a/b/c/d/e/f；joint=none/ball/dovetail/pin；有连接时 merge=yes/no，无连接时不传 merge |
| split model=general | level=low/medium/high，未指定时 medium；不传 part/joint/merge |
| multicolor 输入 | 带纹理 GLB；脚本只检查文件扩展名、大小、哈希，需调用方确认纹理 |
| multicolor 参数 | model=multicolor；number_color 整数 0–8，0 为服务最大颜色数模式，具体上限未确认 |
| multicolor 输出 | obj=1 / glb=2 / fbx=4 / 3mf=6 |

part 模板的具体部位组合应按服务示意选择，不能由数量推断任意角色解剖结构。球接不代表可装配，多色数量不代表对象数或可打印零件数。

所有创建接口可选 `callback_url`，必须 HTTPS；本工具不实现回调接收器，默认轮询。优先用格式名称，避免不同接口中数值含义不同。未列出的 `--set` 参数拒绝；不能把凭据作为参数传入。

不提供价格估算。需要费用时核对 [当前官方价格表](https://docs.hi3d.ai/zh/api/getting-started/pricing)；余额结果只记录 totalBalance 与查询时间，不能直接换算现金或据差值归因单任务费用。
