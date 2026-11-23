# Geometry V4 量化 Geo2 服务契约

[hitem_infer 服务源码](http://172.31.0.3:8099/yangzherui/hitem_infer/-/blob/f6e932ee0522121916e7f1a9994b46f01ceb9af7/scripts/geometry_v4/serve_mdf3/managed_service.py)；固定提交 `f6e932ee0522121916e7f1a9994b46f01ceb9af7`。本页仅记录 geometry-v4-geo2-pass1-cfg-distill-quant；契约按服务入口白名单、common.py、对应 serve/schema 与模型 profile 交叉核对；源码登记不保证当前目标环境已部署。

## MDF、内部 HTTP 与部署配置

MDF 业务请求只接受各页列出的文件及白名单参数。未转发字段通常被忽略，不代表生效；内部 HTTP schema 有该字段也不能绕过 MDF 白名单。服务端路径指服务进程可读路径，客户端本地文件必须先包装 BinaryFile。下面的内部 HTTP 字段仅用于理解或直接接入该内部接口，不能照搬到 mdf-call 的子服务请求。

- 文件别名按列出顺序取首个非 None/空字符串值。错误的高优先级字段会失败，不自动换下一别名。
- `seed:int=42` 只控制无 replay 时的 diffusion 初始噪声；不能承诺全流程确定性。replay 初始噪声优先。`deadline_seconds:float>0` 是内部任务截止元数据，不能当作网关超时或取消保证。
- `return_origin_mesh:bool=True` 由 MDF 入口消费。实现也接受数值按 bool 转换以及 true/false、yes/no、on/off 字符串；调用方应使用 JSON bool，避免将任意非零数误作标志。可透传布尔字段另由 schema 校验。
- `cache_schedule` 由 FlowCache parser 解析，不是任意标签；量化蒸馏 Geo2 锁定 profile，覆盖不了其 cache/步数/postprocess。

## 输出与失败

成功共有 success=True、status=success、fastapi_output、request_dir、output_dir、serve_log_path。末三项为服务器临时路径，成功后异步清理，不能当作可下载文件。获取 BinaryFile 产物；`fastapi_output` 的计数、路径、耗时是元数据。

失败返回 success=False、status=failed、error_message、error_info（同一错误）、可选 error_type 和日志尾；不向 MDF 抛出业务异常。文件缺失/不可读、无效槽和参数、推理失败、必需产物缺失均可导致失败。HTTP bridge 还包括提交、callback、poll 和 timeout 失败。失败日志可能含服务器信息，报告只保留必要诊断。

Geo2 返回 pass_name、num_verts、num_faces、grid_size、coord_resolution、latent_scale、elapsed_sec；model_glb 同样受 return_origin_mesh 控制；有 vxz_path 时附 vxz。本服务 save_vxz 默认 False；锁定 postprocess=False，不返回后处理的 simplified_mesh_glb/rendered_views_zip。

## Geo2 ZIP 与 mesh

prep_zip 必需，支持 B(zip) 或服务器 ZIP 路径（实现也兼容服务器目录）；每个 View{i} 有 GrayColor.jpg/jpeg/png 与 CCM.exr 或 BCCM.exr，GrayMask.png 可选。默认四视图；可用 `_face_view.json` 的 num_views/face_view_idx 增加人脸视图，必须提供全部索引对。camera_info.txt 可覆盖相机。ZIP 根目录即 bridge 输入，不能多套一层，也不嵌入 GLB。

mesh 别名优先级 stage1_mesh_glb / stage1_mesh_path / stage1_mesh / model_glb；MDF staging 允许省略，不等于每个推理配置都能无 mesh。通常明确传与图像、相机及坐标配套的当前网格。省略依赖 pipeline 坐标配置与 bridge 完整性，未实际验证时不能当作可用捷径。

## 外露表面坐标与缓存优先级

同一固定提交的 [prepare.py](http://172.31.0.3:8099/yangzherui/hitem_infer/-/blob/f6e932ee0522121916e7f1a9994b46f01ceb9af7/src/hitem_infer/methods/geometry_v4_stage2/pipeline/prepare.py) 中，`_resolve_coords` 优先读取显式 coords_npz；未设置且 coords_from_mesh=False 时，扫描 bridge 根目录 NPZ。`find_coords_npz_in_input_dir` 按文件名排序，优先选择包含 coords 且 latent_scale 匹配的文件，否则回退到其他含 coords 的 NPZ。因此仅换 stage1_mesh_glb 不保证重新体素化：旧 NPZ 可以继续生效。MDF 当前不透传强制重新体素化开关。

`load_coords_npz` 返回最终 latent 整数坐标；该路径不再执行 mesh 路径的 latent_scale 池化。loader 兼容多种 shape/packed 格式但不充分验证范围、来源或当前分辨率，调用者须自行检查。推荐唯一根目录文件 `geo2_coords.npz`，明确 `coords[N,3] int32`、`latent_scale=L`、`coord_resolution=G/L`，范围 `[0,G/L)`，去重；不要混入其他候选。G/L 取实际 pass 配置，不从服务名推断。

没有 NPZ 时，[coord_fitting.py](http://172.31.0.3:8099/yangzherui/hitem_infer/-/blob/f6e932ee0522121916e7f1a9994b46f01ceb9af7/src/hitem_infer/methods/geometry_v4_stage2/models/stage2/coord_fitting.py) 的 mesh_voxelizer 路径将 GLB 居中并按最长轴缩放到 0.99999，调用 [CUDA MeshVoxelizer](http://172.31.0.3:8099/yangzherui/hitem_infer/-/blob/f6e932ee0522121916e7f1a9994b46f01ceb9af7/extern/pytorch-voxelization/pytorch_voxelization/voxelize.py)（Stage2 pad=0；不能套用类默认 pad=3），再以 latent_scale floor-divide/unique。这个表面三角命中算子不剔除封闭内部结构。

口腔/眼球装配后需要排除封闭内部体素时，交接 [exterior-surface](../../.dependency-exterior-surface/REFERENCE.md)，在高分辨率筛选后再池化，并把唯一坐标 NPZ 添加至现有 prep.zip。这是固定源码支持的目录输入路径，不是 MDF 新增顶层字段，也未证明当前线上部署已采用该版本。保留相机、源模型和归一化绑定；不能用 save_vxz 替代输入坐标提取。

## 内部 HTTP 字段快照

以下逐项来自对应 Pydantic schema 的静态字段，列出类型、默认/约束表达式；`Field(...)` 中未设 default 的字段必填。Stage2 未额外设置 extra=forbid。公共 envelope 为 request_id、callback_url、deadline_seconds、log_file_path。服务封装会再修改默认，见各原子页。

### 公共 envelope

[字段来源](http://172.31.0.3:8099/yangzherui/hitem_infer/-/blob/f6e932ee0522121916e7f1a9994b46f01ceb9af7/src/hitem_infer/serve/schemas.py)

| 字段 | 类型 | 默认与约束 |
| --- | --- | --- |
| `request_id` | `str` | `Field(min_length=1)` |
| `callback_url` | `str` | `Field(min_length=1)` |
| `deadline_seconds` | `float \| None` | `Field(default=None, gt=0)` |
| `log_file_path` | `str \| None` | `None` |

### Geo2

[字段来源](http://172.31.0.3:8099/yangzherui/hitem_infer/-/blob/f6e932ee0522121916e7f1a9994b46f01ceb9af7/src/hitem_infer/methods/geometry_v4_stage2/serve/schemas.py)

| 字段 | 类型 | 默认与约束 |
| --- | --- | --- |
| `input_dir` | `str` | `Field(min_length=1)` |
| `output_dir` | `str` | `Field(min_length=1)` |
| `replay_dir` | `str \| None` | `None` |
| `bridge_input_dir` | `str \| None` | `None` |
| `stage1_mesh_path` | `str \| None` | `None` |
| `seed` | `int` | `42` |
| `num_inference_steps` | `int \| None` | `None` |
| `guidance_scale` | `float` | `3.0` |
| `true_cfg_scale` | `float \| None` | `None` |
| `mu` | `float \| None` | `None` |
| `preferred_views` | `list[int] \| None` | `None` |
| `coords_mesh_path` | `str \| None` | `None` |
| `coords_npz` | `str \| None` | `None` |
| `postprocess` | `bool` | `False` |
| `coords_from_mesh` | `bool` | `False` |
| `coord_fitting_mode` | `str \| None` | `None` |
| `negative_mode` | `str \| None` | `None` |
| `negative_blur_radius` | `float \| None` | `None` |
| `rgb_clean_erode_px` | `int \| None` | `None` |
| `rgb_clean_feather_px` | `int \| None` | `None` |
| `rgb_clean_bg` | `int \| None` | `None` |
| `save_vxz` | `bool \| None` | `None` |
| `camera_info_path` | `str \| None` | `None` |
| `step_shift_schedule` | `dict[str, object] \| None` | `None` |
| `rope_theta` | `float \| None` | `None` |
| `rope_coord_scale` | `float \| None` | `None` |
| `rope_coord_scale_xyz` | `list[float] \| None` | `Field(default=None, min_length=3, max_length=3)` |
| `dump_tensors` | `bool` | `False` |
| `cache_schedule` | `str \| None` | `None` |

## 部署参数

service_name/environment、设备/并行、checkpoint/profile、server_url/端口、work_dir、worker/puller 数以及超时是部署设置，不放进 input_data。HTTP bridge 默认内部等待 7200 秒、poll 2 秒、初始化 readyz 等待 600 秒；具体进程可覆盖。managed 模式在进程内运行，相同 MDF 文件契约不等于同一 HTTP 生命周期。需要部署时阅读源启动脚本，不将内部路径或 GPU 布局固定进本 skill。
