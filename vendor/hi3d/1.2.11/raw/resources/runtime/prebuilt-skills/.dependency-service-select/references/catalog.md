# MDF 原子能力目录

按名称找到对应页；每页包含输入、输出、可实现效果与交接限制。B 为 BinaryFile，Z 为 data-io .zst 容器。除明确的源码默认外，数值是调用方配方；不能将清单当作当前在线证明。公开 API 另见 [API 能力](api.md)。

当前有契约的 12 项中，8 项在用户确认的露出名单内。`geometry-v4-geo2-pass1-cfg-distill-quant`、`multiview-service`、`texture-bake-v3-0`、`texture-render-v3-0` 因现有交接或调用保留契约，露出状态待确认，选择前须核实目标部署。`pcg-function-call-service` 已在用户确认的 9 项露出名单内，但尚无输入输出契约，未加入可调用目录；不能推测参数。

| 服务 | 功能与效果 |
| --- | --- |
| [auto-rig](mdf/auto-rig.md) | SkinTokens 自动生成骨骼与蒙皮，或利用已有骨骼条件预测蒙皮；输出 GLB，不生成动作。已确认 MDF3 SDK 队列/TCP 路径，默认 HTTP 网关未确认。 |
| [geometry-v4-geo2-pass1-cfg-distill-quant](mdf/geometry-v4-geo2-pass1-cfg-distill-quant.md) | 在已有网格与多视图 GrayColor/浮点 CCM 条件上继续生成 pass1-cfg-distill-quant 几何。 |
| [image-process-service-v2-0](mdf/image-process-service-v2-0.md) | 去除图像背景，返回带 alpha 的前景图。 |
| [mcolor-format-mesh](mdf/mcolor-format-mesh.md) | 转换网格格式，支持 GLB 规范化和 3MF 等格式导出。 |
| [mesh-lod](mdf/mesh-lod.md) | 按多个目标面数减面并重烘纹理/法线，生成多档 LOD。 |
| [mesh-watertight](mdf/mesh-watertight.md) | 对 GLB 补洞、水密重建及可选减面，返回单个 GLB；完整契约由 mdf-call 维护并随本包物化。 |
| [multiview-service](mdf/multiview-service.md) | 按参考图及法线/坐标条件生成多视图图像。 |
| [retopology-V2-0](mdf/retopology-V2-0.md) | 网格重拓扑，控制目标面数和面类型。 |
| [sapiens2](mdf/sapiens2.md) | 单图人体关键点、分割、相机法线、pointmap 与抠像，独立/组合调用和 CPU offload；部署待验证。 |
| [texture-bake-v3-0](mdf/texture-bake-v3-0.md) | 将多视图贴图烘焙到网格，或合成已有材质通道。 |
| [texture-render-v3-0](mdf/texture-render-v3-0.md) | 渲染法线/坐标/mask 条件，或选择纹理补绘视图。 |
| [texture-uv-unwrap-v3-0](mdf/texture-uv-unwrap-v3-0.md) | 网格 UV 展开，并按参数选择是否修复。 |

Geo 与 Video 两个 CenterControl 入口是组合工作流，不计作下游原子。它们使用的 workflow_name/request_type/image_list 或 URL 不等于单个 MDF 服务的业务输入。几何与纹理组合策略见 [几何交接](geometry.md)、[纹理交接](texture.md)，公开 API 的组合请求见 [API](api.md)。
