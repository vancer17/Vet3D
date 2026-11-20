# mesh-lod

对 GLB 网格按目标面数渐进减面并重烘纹理/法线，生成多个 LOD；自交保护强制启用，每次 MDF 请求在独立子进程执行，完成后返回 GLB 字节及每档元数据。无神经网络推理模型。

来源：[服务仓库](http://172.31.0.3:8099/video-to-3d/service/mesh-lod/-/blob/8be59f2c8bb0499396d233091206efe690d55230/README.md)，固定提交 `8be59f2c8bb0499396d233091206efe690d55230`；核对日期 2026-09-08。[MDF 入口](http://172.31.0.3:8099/video-to-3d/service/mesh-lod/-/blob/8be59f2c8bb0499396d233091206efe690d55230/mesh_lod_service_mdf3.py)；[共用调用/数组约定](README.md)、[工作流调用方速查](../catalog.md)。完整传参以下列 **MDF process 实际读取字段**为范围；本地 API 与部署参数另列，未验证线上部署与该提交一致。

## MDF 输入

| 字段 | 类型 | 未提供时 | 行为/限制 |
| --- | --- | --- | --- |
| `input_mesh_glb` | BinaryFile | 必填 | 非空 GLB；临时存为 input.glb，经下层 GLB 检查。 |
| `target_face_num_list` | list/tuple 或单值 | [2000000,500000,200000] | 优先读取，单值包装成列表后交目标规范器；请求多个正整数目标。 |
| `target_face_num` | 同上 | 同上 | 仅 target_face_num_list 缺失时读取的兼容别名。 |
| `normal_map_resolution_ratio` | float 可转换 | 2.0 | 必须有限且 >0，拒绝 bool；法线贴图相对纹理分辨率比例。 |
| `normal_map_max_long_edge` | int 可转换 | 8192 | 正整数，拒绝 bool/非整浮点；法线最长边上限。 |
| `simplify_self_intersection` | bool 可解析 | True | 虽可解析 False，但业务层明确拒绝关闭严格自交保护。 |
| `bake_workers` | int 可转换/null | None | 透传烘焙并发；None 由下层决定，入口未做正数范围校验。 |
| `uv_batch_count` | int 可转换 | 8 | UV 批次数，透传下层；不把入口没有实现的范围检查写成保证。 |

## MDF 输出

公共成功/失败字段见[共用契约](README.md)。本服务业务输出：

| 字段 | 类型/语义 |
| --- | --- |
| `success` | True；此服务成功/失败都不返回 status 字段。 |
| `mesh_lod_glbs` | dict[int, BinaryFile]，键为请求面数；文件名 input_<面数标签>.glb（如 input_50w.glb）。 |
| `mesh_lod_metadata` | dict[str, dict]；键为面数字符串。每档含 requested_faces、actual_faces、size_bytes、skipped、lod、bake_result，剔除服务内部 output_path。 |
| `lod` / `bake_result` | 下层产物 metadata 经递归 JSON 化后透传，动态扩展字段；不是固定可用于发请求的 schema。 |


## 行为、依赖与版本差异

- 视频中控只请求 [500000,200000]，服务默认另含 2000000；目标面数不是最终实际面数保证，应验收 actual_faces。
- 依赖 mesh-normal-bake/mesh-simplify、CUDA/Blender 等由下层提供。稳定 API/Module 层分别负责入口与编排，Method/artifacts 负责 GLB 校验、命名和原子发布。
- MDF 固定 overwrite=True、独立临时目录；子进程异常/退出/超时保留 error_type 和 error_message，整次服务失败，不返回部分成功结果。
- 部署默认 MESH_LOD_WORKER_TASK_TIMEOUT_SEC=7200、MESH_LOD_CHILD_TASK_TIMEOUT_SEC=7170、MESH_LOD_CHILD_TERMINATE_GRACE_SEC=5；要求 child<worker，父进程死亡/超时会终止请求进程树。这些不是业务字段。
- 本地 API 的 max_ray_distance、simplify_initial_k、output_dir、overwrite 没有暴露为 MDF 字段，发送同名键不会生效。

## 可复用本地入口

下列为源码签名，路径参数指运行进程可访问的文件。返回值与副作用见对应函数；模型、设备、输出路径或高级调优参数不能直接塞入 MDF input_data。

- [`bake_mesh_lods`](http://172.31.0.3:8099/video-to-3d/service/mesh-lod/-/blob/8be59f2c8bb0499396d233091206efe690d55230/mesh_lod/API/lod.py#L18)：`(input_model_path: str, target_face_num_list: List[int]=DEFAULT_TARGET_FACE_NUM_LIST, normal_map_resolution_ratio: float=DEFAULT_NORMAL_MAP_RESOLUTION_RATIO, normal_map_max_long_edge: int=DEFAULT_NORMAL_MAP_MAX_LONG_EDGE, max_ray_distance: Optional[float]=None, simplify_initial_k: Optional[float]=0.1, simplify_self_intersection: bool=True, bake_workers: Optional[int]=None, uv_batch_count: int=8)`。
- [`run_mesh_lod`](http://172.31.0.3:8099/video-to-3d/service/mesh-lod/-/blob/8be59f2c8bb0499396d233091206efe690d55230/mesh_lod/API/lod.py#L43)：`(input_model_path: str, output_dir: str, target_face_num_list: List[int]=DEFAULT_TARGET_FACE_NUM_LIST, normal_map_resolution_ratio: float=DEFAULT_NORMAL_MAP_RESOLUTION_RATIO, normal_map_max_long_edge: int=DEFAULT_NORMAL_MAP_MAX_LONG_EDGE, max_ray_distance: Optional[float]=None, simplify_initial_k: Optional[float]=0.1, simplify_self_intersection: bool=True, bake_workers: Optional[int]=None, uv_batch_count: int=8, overwrite: bool=False)`。

本地 CLI：[`run.py`](http://172.31.0.3:8099/video-to-3d/service/mesh-lod/-/blob/8be59f2c8bb0499396d233091206efe690d55230/run.py)。启动 MDF 服务的公共 CLI 参数见共用契约；这里记录固定源码契约，具体线上版本需由当前调用核对。

依据：[API.py](http://172.31.0.3:8099/video-to-3d/service/mesh-lod/-/blob/8be59f2c8bb0499396d233091206efe690d55230/API.py)、[README.md](http://172.31.0.3:8099/video-to-3d/service/mesh-lod/-/blob/8be59f2c8bb0499396d233091206efe690d55230/README.md)、[mesh_lod/API/lod.py](http://172.31.0.3:8099/video-to-3d/service/mesh-lod/-/blob/8be59f2c8bb0499396d233091206efe690d55230/mesh_lod/API/lod.py)、[mesh_lod/Module/lod.py](http://172.31.0.3:8099/video-to-3d/service/mesh-lod/-/blob/8be59f2c8bb0499396d233091206efe690d55230/mesh_lod/Module/lod.py)、[mesh_lod/Method/artifacts.py](http://172.31.0.3:8099/video-to-3d/service/mesh-lod/-/blob/8be59f2c8bb0499396d233091206efe690d55230/mesh_lod/Method/artifacts.py)。维护时同时核对 process 的 get/别名/helper、展开的 result_info、返回字典与被调用参数解析器；缺省值以实现为准，不因上游未传就省略服务支持项。
