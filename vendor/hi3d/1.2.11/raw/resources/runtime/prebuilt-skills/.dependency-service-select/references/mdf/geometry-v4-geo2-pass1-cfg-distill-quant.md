# geometry-v4-geo2-pass1-cfg-distill-quant

在已有网格与多视图 GrayColor/浮点 CCM 条件上继续生成 pass1-cfg-distill-quant 几何。

## 输入

必填 prep_zip:B(ZIP)，通常明确传 stage1_mesh_glb:B（staging 可省略，推理是否可省略取决于坐标配置）。pass 固定在服务，不接收 stage 路由。可选 seed:int=42、deadline_seconds:正 float/None、save_vxz:bool=False、postprocess:bool=False、return_origin_mesh:bool=True。managed 入口另透传 cache_schedule:str/None。

## 输出

model_glb（return_origin_mesh=True）；pass_name、num_verts、num_faces、grid_size、coord_resolution、latent_scale、elapsed_sec；启用 VXZ 且生成成功时返回 vxz。蒸馏服务锁定 postprocess=False，不应期待 simplified_mesh_glb 或 rendered_views_zip。

## 效果、交接与限制

MDF 不透传 guidance_scale、num_inference_steps、true_cfg_scale、mu、preferred_views、coords/negative/RGB cleanup/RoPE/replay 等内部 HTTP 字段。蒸馏服务强制 guidance_scale=1、25 步、postprocess=False、cache_schedule=bud:uniform:12；覆盖值无效，量化与否不改变这个模型约束。 prep.zip 必须和当前前阶段网格及相机配套；新背面/细节是生成推断，不保证逐次保留。

## 来源与范围

装配眼球/口腔后的封闭内部面可能进入默认三角面体素化。需要外露表面坐标时使用 [exterior-surface](../../../.dependency-exterior-surface/REFERENCE.md)；唯一 coords NPZ 随 prep.zip 根目录交接的版本约束、池化尺度和旧缓存优先级见 [共有契约](../geometry-v4-contract.md#外露表面坐标与缓存优先级)。MDF 不新增 coords_npz 请求字段。

[hitem_infer 服务源码](http://172.31.0.3:8099/yangzherui/hitem_infer/-/blob/f6e932ee0522121916e7f1a9994b46f01ceb9af7/scripts/geometry_v4/serve_mdf3/managed_service.py)；固定提交 `f6e932ee0522121916e7f1a9994b46f01ceb9af7`。契约按服务入口白名单、common.py、对应 serve/schema 与模型 profile 交叉核对；源码登记不保证当前目标环境已部署。

文件别名、失败语义、内部 HTTP 全字段和部署边界见 [Geometry V4 共有契约](../geometry-v4-contract.md)。图像准备、视角顺序及 ZIP 连接见[几何交接](../geometry.md)，执行入口见[调用与恢复](../calling.md)。
