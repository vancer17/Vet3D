# MDF 服务功能与传参

收录 12 个有输入输出契约的下游服务；另保留 2 个外部中控入口作为调用方参数来源。下表数值采用已有工作流用法或明确标注的服务默认值，契约覆盖范围见各页。通过 [mdf-call](../mdf-api/SKILL.md) 默认经 HTTP 中控调用，显式 SDK 使用 TaskQueue/TCP；清单不等于当前在线、路由可达或业务验收保证。

当前有契约的 12 项中，8 项在用户确认的露出名单内。`geometry-v4-geo2-pass1-cfg-distill-quant`、`multiview-service`、`texture-bake-v3-0`、`texture-render-v3-0` 因现有交接或调用保留契约，露出状态待确认，选择前须核实目标部署。`pcg-function-call-service` 已在用户确认的 9 项露出名单内，但尚无输入输出契约，未加入可调用目录；不能推测参数。

`B` = MDF BinaryFile；`Z` = B 包装的 data-io `.zst` 数组；`?` = 条件性字段；`a/b` = 按顺序兼容取值。二进制字段的类型与文件格式须一致；`list[B/None]` 中 None 表示参考图空槽。共用数组格式和调用接口见[服务契约](mdf/README.md)。

公共控制/错误字段如 `success`、`status`、`error_type`、`error_info`、`error_message`、`error` 按各服务契约取用，不在每行重复。

## 下游服务

| 服务名 | 可实现的功能 | 输入参数 | 输出参数 |
| --- | --- | --- | --- |
| [auto-rig](../.dependency-service-select/references/mdf/auto-rig.md) | SkinTokens 自动生成骨骼与蒙皮；可利用已有骨骼条件预测蒙皮，不生成动作。 | `mesh:B(OBJ/FBX/GLB)` 必填，`field_name="mesh"`，安全文件名，默认 ≤256 MiB；`options:dict={}`，默认 `use_skeleton=False/use_transfer=True/use_postprocess=False`、`top_k=5/top_p=0.95/temperature=1.0/repetition_penalty=2.0/num_beams=10/seed=42`；范围与分支见专页 | `rigged_mesh:B(GLB)`，`metadata` 含骨骼/蒙皮/顶点统计、worker/模型初始化标识及耗时；`trace_id` |
| [geometry-v4-geo2-pass1-cfg-distill-quant](../.dependency-service-select/references/mdf/geometry-v4-geo2-pass1-cfg-distill-quant.md) | 在已有网格与多视图 GrayColor/浮点 CCM 条件上继续生成 pass1-cfg-distill-quant 几何。 | 必填 prep_zip:B(ZIP)，通常明确传 stage1_mesh_glb:B（staging 可省略，推理是否可省略取决于坐标配置）。pass 固定在服务，不接收 stage 路由。固定源码支持 prep_zip 根目录的唯一 latent coords NPZ（非 MDF 顶层字段）；范围、来源与缓存优先级见详情。可选 seed:int=42、deadline_seconds:正 float/None、save_vxz:bool=False、postprocess:bool=False、return_origin_mesh:bool=True。managed 入口另透传 cache_schedule:str/None。 | model_glb（return_origin_mesh=True）；pass_name、num_verts、num_faces、grid_size、coord_resolution、latent_scale、elapsed_sec；启用 VXZ 且生成成功时返回 vxz。蒸馏服务锁定 postprocess=False，不应期待 simplified_mesh_glb 或 rendered_views_zip。 |
| [image-process-service-v2-0](../.dependency-service-select/references/mdf/image-process-service-v2-0.md) | 去除图像背景，返回带 alpha 的前景图。 | `image:B`, `only_remove=True` | `image:B(RGBA PNG)`，alpha 表示前景 mask |
| [mcolor-format-mesh](../.dependency-service-select/references/mdf/mcolor-format-mesh.md) | 转换网格格式，支持 GLB 规范化和 3MF 等格式导出。 | 格式输入见 M 两个分支 | 导出：`output_model:B`, `mode`；转 GLB：`output_model/glb:B`, `mode`, `vertex_count`, `face_count` |
| [mesh-lod](../.dependency-service-select/references/mdf/mesh-lod.md) | 按多个目标面数减面并重烘纹理/法线，生成多档 LOD。 | `input_mesh_glb:B`, `target_face_num_list=[500000,200000]`, `normal_map_resolution_ratio=2.0`, `normal_map_max_long_edge=8192`, `simplify_self_intersection=True` | `mesh_lod_glbs:dict`（键为面数 int 或 str，值 B(GLB)）, `mesh_lod_metadata` |
| [mesh-watertight](../.dependency-mdf-call-source/references/mesh-watertight.md) | GLB 补洞、水密重建与可选减面。 | `input_mesh_glb:B(GLB)` 必填；`watertight_resolution=4096`、`is_fillhole=True`、`target_face_num=5000000`（null 跳过减面）；完整参数、超时与约束见专页 | `watertight_mesh_glb:B(GLB)`、`watertight_succeeded`、实际分辨率/降级标记及分阶段耗时；失败字段见专页 |
| [multiview-service](../.dependency-service-select/references/mdf/multiview-service.md) | 按参考图及法线/坐标条件生成多视图图像。 | `reference_images:list[B/None]`, `normal_images:list[B]`, `ccm_images:list[B]`, `resolution`, `control_scale`, `steps`, `prompts:list[str]`, `seed?:int`；分支 MV | `generated_images:list[B]`，按输入视图顺序 |
| [retopology-V2-0](../.dependency-service-select/references/mdf/retopology-V2-0.md) | 网格重拓扑，控制目标面数和面类型。 | `mesh_mdf:B(GLB)`, `face=50000`, `face_type="triangles"`, `topology_method="pamo"` | `model_glb:B`, `face_topology`, `vertices_topology` |
| [sapiens2](../.dependency-service-select/references/mdf/sapiens2.md) | pose、分割、法线、pointmap、抠像的独立/组合推理；源码契约，部署待验证。 | `image:B`，`task="all"` 或 `tasks:list`；`offload_cpu=True`、`visualize=True`；pose 可传 `bboxes` 或 `detect_persons=False`；完整控制见服务页。 | `results.<task>.data:B(NPZ)`、可选 `visualization:B(PNG)`、metadata；原图关键点/labels/normals/pointmap/depth/alpha/预乘 RGB，以及计时与内存指标。 |
| [texture-bake-v3-0](../.dependency-service-select/references/mdf/texture-bake-v3-0.md) | 将多视图贴图烘焙到网格，或合成已有材质通道。 | 烘焙/合成输入见 BK | 按分支读取 `baked_glb:B`, `texture_image:B`, `texture_mr_image?:B`, `preview_image?:B`, `visible_texture?:B`, `coverage_mask?:B`, `coverage`, `consistency_mode`, `timing`（读取 bake_sec/export_sec） |
| [texture-render-v3-0](../.dependency-service-select/references/mdf/texture-render-v3-0.md) | 渲染法线/坐标/mask 条件，或选择纹理补绘视图。 | 条件渲染/补绘选相机输入见 R | 条件渲染：`normal_images:list[B]`, `ccm_images:list[B]`, `mask_images:list[B]`, `camera_azims`, `camera_elevs`, `view_weights`, `selection_source`；补绘：另读 `masked_target_images`, `missing_mask_images`（list[B]） |
| [texture-uv-unwrap-v3-0](../.dependency-service-select/references/mdf/texture-uv-unwrap-v3-0.md) | 网格 UV 展开，并按参数选择是否修复。 | `mesh_glb:B`, `texture_size:int`（当前 Geo 融合层默认 8192；其他调用方按自身配置）, `need_repair:bool` | `uv_mesh_glb:B`, `num_faces`, `use_blender_wrap`, `timing` |

视频中控内 Geometry V4 / 几何 multiview 的 `seed` 来自中控 `seed`，缺省每请求随机。

## 多种功能的传参

| 服务 / 功能 | 输入参数 |
| --- | --- |
| M：mcolor-format-mesh 导出 | `func="glb2format"`, `glb:B`, `transfer_format:int`, `output_file_name="model"`；3mf 可加 `threemf_mode`（auto/orca/standard）。格式码 1=obj、2=glb、3=stl、4=fbx、5=usdz、6=3mf。 |
| M：mcolor-format-mesh 转 GLB | `func="format2glb"`, `input_model:B`, `input_format`（obj/glb/stl）, `output_file_name="model.glb"`。 |
| MV：multiview-service 几何图 | 主表字段，`resolution=2048`, `control_scale=0.8`, `steps=4`；单参考图，prompts 按 front/right/back/left 顺序。 |
| MV：multiview-service 纹理图 | 主表字段，另传 `cfg=1.0`, `negative_prompt=" "`；`resolution=2048`, `steps=4`, `control_scale=1.0`, `seed=0`。参考槽按 front/right/back/left 排列，可含 None。 |
| R：texture-render-v3-0 条件渲染 | `mesh_glb:B`, `resolution:int`；显式相机传 `camera_azims`, `camera_elevs`，可加 `view_weights`；否则传 `num_views`（纹理工作流默认 8）。 |
| R：texture-render-v3-0 补绘选视图 | `op="inpaint_select"`, `mesh_glb:B`, `visible_texture:B`, `coverage_mask:B`, `existing_camera_azims:list`, `existing_camera_elevs:list`, `num_views:int`, `resolution:int`, `texture_size:int`。 |
| BK：texture-bake-v3-0 烘焙 | `mesh_glb:B`, `view_images:list[B]`, `camera_elevs:list`, `camera_azims:list`, `view_weights:list`, `consistency_mode="off"`, `texture_size=8192`, `enable_mesh_inpaint:bool`, `return_visible_artifacts:bool`, `export_preview:bool`；可加 `bake_channels`（rgb/mr/rgb+mr）、`mr_view_images:list[B/None]`，MR 图与视图逐位对齐。 |
| BK：texture-bake-v3-0 材质合成 | `mesh_glb:B`, `texture_image:B`, `bake_channels="compose"`, `export_preview:bool`；可加 `texture_mr_image:B`, `texture_normal_image:B`。 |

- UV 的 `need_repair` 优先由 `uv_need_repair` 指定，否则取 `not watertight_applied`；上传无 UV 网格默认 True。UV/bake 尺寸依次取 `texture_size`、`uv_texture_size`、工作流默认。

## 中控入口

以下为外部组合调用方的固定来源记录，不在用户确认的 9 项 MDF 露出名单或本工具可调用目录内，也不表示仓库提供这些完整生成链。中控注册名与 `workflow_name` 分别使用，下游服务名用于 `target_service`。

| 中控注册名 | 可实现的功能 | 输入参数 | 输出参数 |
| --- | --- | --- | --- |
| `CenterControlService-V3-0` | 单图/多视图几何生成、已有网格贴纹理或两者串联。 | `workflow_name` 为 `v30-generate-standard`（默认）/`v30-generate`（full）/`v30-generate-fast`；`request_type=1/2/3` 对应几何/纹理/串联，默认 1。几何用 `image_list`（front/left/back/right，最多 4 张）或 `image_url`；纹理用 `image_url`+`mesh_url`。可选 `needRemesh=False`, `transfer_format`, `js_transfer=0`, `threemf_mode`；格式码见 M 分支。 | 组合阶段输出及 `request_type`，可附几何、重拓扑和格式导出结果。 |
| `CenterControlService-VideoTo3D` | 从视频生成 3D 模型、纹理、封面和展示视频。 | `workflow_name="video-to-3d-pipeline"`；`video_url`，可选 `sidecar_url` 与纹理参数；内部阶段覆盖包括 `cpe_target_frame_num=64/cpe_min_spread_deg=45.0/cpe_max_gpu_memory_ratio=0.95`、`gs_fit_steps=12000/max_image_size=1920`、`iqm_min_mask_ratio=0.5/iqm_target_frame_num=200`、`fad_max_deform_ratio=0.05/fad_lambda_smooth=10.0/fad_lambda_magnitude=0.3/fad_max_disp_ratio=0.08/fad_deform_query_chunk_size=16`、`s1_seed=0/s1_num_steps=25/s1_guidance=4.0/s1_geo_max_tokens=24576/s1_max_pc_points=16384/s1_target_view_num=8`，仅作为该外部中控的输入。 | 模型/封面/视频 object_key、质量指标与分支元数据。 |

服务及工作流参数来源：[视频入口][V]、[Geo 入口][G]、[纹理模块][T]、[公共参数][D]；各服务的契约覆盖范围、输入、输出和限制见主表名称链接。

[V]: http://172.31.0.3:8099/video-to-3d/service/video-to-3d-center/-/blob/c567a59c4c9c5102353088fc03cceec8241e1ead/center_control_service_video_pipeline_mdf3.py#L56

[G]: http://172.31.0.3:8099/zhaoshengchu/geo3.0_service/-/blob/63dbc6cb349eab768da4a5a5b1441d7f75a7f7fb/workflow_online_geo_texture.py#L36

[T]: http://172.31.0.3:8099/mathmagic/texture-workflow-service/-/blob/10ea6251d9fe3acbd76dc1f071867208f93040cd/workflow_texture.py#L974

[D]: http://172.31.0.3:8099/video-to-3d/service/video-to-3d-center/-/blob/c567a59c4c9c5102353088fc03cceec8241e1ead/pipeline_defaults.py#L63

## 账号公开入口

公开 POST /v1/mesh/invoke 的 14 项能力与内部服务名称不是一一映射；[完整参数及输出](../mdf-api/references/mesh-invoke-api.md) 由调用工具维护。图片能力为 remove-background、pose、seg、normal、pointmap、matting；网格能力为 unwrap-uv、convert-3mf、watertight、retopology、mesh-lod、auto-rig；结构分析为 extract-centerline、check-printability。公开参数使用 capability + params + file，成功判定为 HTTP 200、整数 code=0、status=SUCCEEDED；不存在公开查询端点。部署可用性由实际宿主确认。
