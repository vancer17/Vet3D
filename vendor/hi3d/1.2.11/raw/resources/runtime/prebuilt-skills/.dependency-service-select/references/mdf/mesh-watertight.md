# mesh-watertight

对 GLB 三角网格执行可选补洞、wt_finally 水密重建、可选减面与 sliver 清理，再验证并发布单个 GLB。当前仅一个生产后端；single/double_fix 是分析分类，不是可任意切换的服务路由。

来源：[服务仓库](http://172.31.0.3:8099/video-to-3d/service/mesh-watertight/-/blob/861eb6919bd4f715dae98b389589cfe49c185713/README.md)，固定提交 `861eb6919bd4f715dae98b389589cfe49c185713`；核对日期 2026-09-08。[MDF 入口](http://172.31.0.3:8099/video-to-3d/service/mesh-watertight/-/blob/861eb6919bd4f715dae98b389589cfe49c185713/mesh_watertight_service_mdf3.py)。完整传参以下列 **MDF process 实际读取字段**为范围；本地 API 与部署参数另列，未验证线上部署与该提交一致。

## 通过 mdf-call 调用

正文唯一维护在 `tools/mdf-call/references/mesh-watertight.md`；服务选择包通过 package.json 物化本文件。`SKILL_DIR` 指实际 mdf-call 工具包，`PYTHON` 为目标解释器，`RUN_DIR` 为包外任务目录。调用前按该工具入口检查运行时、目标部署及已有授权。

准备 `RUN_DIR/request.json`，与输入 `input.glb` 放在同一目录；也可从工具包 `assets/request.mesh-watertight.json` 复制模板：

```json
{"input_mesh_glb": {"$file": "input.glb"}, "target_face_num": null}
```

`$file` 由 CLI 读取为携带 `content:bytes`、`file_name="input.glb"` 和 `field_name="input_mesh_glb"` 的 MDF BinaryFile；不能仅向服务器传本机路径字符串。这个示例显式跳过减面，其余字段采用下表服务默认值；需要减面时填写单个正整数目标。

```bash
"$PYTHON" "$SKILL_DIR/scripts/mdf_call.py" \
  --service mesh-watertight --input "$RUN_DIR/request.json" \
  --run-dir "$RUN_DIR/watertight-call" --timeout 1800
```

输出目录须不存在。默认 HTTP 中控；显式 SDK 使用同一文件字段并额外满足完整 SDK、队列配置及 worker TCP 回连前提。示例客户端等待 1800 秒，不是服务默认或算法截止时间；按目标部署的排队、执行与传输预算调整。请求 `max_runtime_sec`、worker 外层超时与 CLI `--timeout` 是三个层级，客户端超时不保证后台任务取消，不自动重提。

从 `invocation.json.files` 中按 `field_path=["watertight_mesh_glb"]` 找文件，再读取 `artifacts/<file>`；文件名可能带 CLI 唯一序号，不硬编码 watertight.glb 路径。CLI 默认成功谓词为布尔 `success=True`，只记录 `SUCCEEDED`；检查 `watertight_succeeded`、`resolution_actual`、是否降级及下文产物边界后才可报告业务验收完成。`watertight_resolution<=0` 会跳过水密，不能以返回 GLB 宣称完成水密重建。BinaryFile 字节保存到客户端后再交接；服务器临时文件路径不是产物地址。

## MDF 输入

| 字段 | 类型 | 未提供时 | 行为/限制 |
| --- | --- | --- | --- |
| `input_mesh_glb` | BinaryFile | 必填 | 非空 GLB；文件 API 仅读第一个 mesh primitive，调用前应确认模型组织。 |
| `watertight_resolution` | int 可转换 | 4096 | >0 执行水密，<=0 跳过水密；实际分辨率由分类/容量策略决定并返回。 |
| `routing_mode` | str/null | wt_finally | 未传/None/空白使用默认；auto 是 wt_finally 兼容别名，其他值失败。 |
| `is_fillhole` | bool 可解析 | True | 补洞预处理；优先于 enable_holefill。 |
| `enable_holefill` | bool 可解析 | True | 仅 is_fillhole 缺失时读取的兼容别名。 |
| `target_face_num` | 单值/null | 5000000 | 单个正整数目标；None 或数值<=0 跳过减面；字符串空/none/null/-1/0 也转 None，其他字符串先 int；列表/tuple 拒绝。 |
| `k` | float 可转换 | 0.1 | 自适应减面初始 k。 |
| `enable_self_isect` | bool 可解析 | True | 减面自交保护；可关闭，与 mesh-lod 强制 True 不同。 |
| `strict_wt_enabled` | bool 可解析 | False | 已废弃兼容字段；无论值如何，水密最终失败都报错，返回 strict_wt_enabled=True。 |
| `preserve_original_boundary` | bool 可解析 | False | 锁定减面开始时的开边界顶点；保护约束可能令目标面数不可达。 |
| `enable_sliver_cleanup` | bool 可解析 | True | 减面后清理细长三角形。 |
| `sliver_cleanup_verify` | bool 可解析 | False | 清理后执行完整 CPU 指标验证。 |
| `allow_resolution_fallback` | bool 可解析 | True | 符合条件的水密容量/OOM 最多降分辨率重试一次；局部自交 guard OOM 直接失败。 |
| `max_gpu_memory_ratio` | float 可转换 | 服务启动比例（默认 0.95） | 实际实现要求有限、拒绝 bool，截断到 [0,1]；不得超过启动比例，实际显存预算还须满足算法最低 GiB。不是 README 所写的固定 (0,0.95] 校验。 |
| `max_runtime_sec` | float 可转换 | 部署值（默认 1200） | >0 用独立子进程执行并超时终止；<=0 直接执行。外层 worker 超时仍有效。 |

## MDF 输出

成功返回 `success=True`；失败返回 `success=False`、`error_type`、`error_message`，具体失败 status 见下表。本服务业务输出：

| 字段 | 类型/语义 |
| --- | --- |
| `watertight_mesh_glb` | BinaryFile(watertight.glb)，单模型输出；GLB 头和可加载网格校验后读取。 |
| `holefill_sec` / `watertight_sec` / `simplify_sec` / `sliver_sec` / `export_sec` / `total_algo_sec` | 秒，三位小数；无记录为 None，total 为已有阶段耗时和。 |
| `resolution_actual` / `resolution_fallback_applied` | 实际执行分辨率 / 是否发生容量降级。 |
| `backend` / `execution_backend` | single 或 double_fix 等分类 / wt_finally 实现；跳过阶段时可能缺少信息。 |
| `strict_wt_enabled` / `watertight_failure_ignored` | 固定 True / False。 |
| `watertight_succeeded` | 实际阶段结果，来自 run_stats。 |
| `watertight_error_type` / `watertight_error_message` | 成功响应固定 None。 |
| `status`（失败） | 子进程算法超时为 candidate_timeout，其他为 failed；伴随 success=False、error_type、error_message。 |


## 行为、依赖与版本差异

- 水密成功与否必须依据此版本实现；strict_wt_enabled 不能让失败转成功。allow_resolution_fallback=False 关闭容量重试，但不能覆盖双层分类触发的自适应分辨率选择。应检查 resolution_actual。
- 当前 MDF process 不读取 enable_adaptive_clamp_rollback；旧视频中控仍传该字段，不会覆盖自适应策略。本地文件 API 虽保留同名形参，也已无控制作用。
- visibility_shrink_depth_multiplier、intermediate_watertight_output_path、enable_log、result_stats 仅文件 API 提供；MDF 不会透传，完整 watertight_stats 不在 MDF 成功响应中。服务 README 的“其余字段与文件 API 一致”不能作为调用依据。
- 服务启动额外支持 --max-gpu-memory-ratio；MESH_WATERTIGHT_MAX_RUNTIME_SEC 默认 1200、MESH_WATERTIGHT_WORKER_TASK_TIMEOUT_SEC 默认 1400，业务 max_runtime_sec 和调用方 timeout_sec 是不同层级。
- 需要可见单张逻辑 GPU cuda:0、PyTorch、预构建 CUDA/C++ 扩展及 mesh-simplify；无运行时 JIT 兜底。临时输入/输出和 GPU 状态在 finally 清理。

## 可复用本地入口

下列为源码签名，路径参数指运行进程可访问的文件。返回值与副作用见对应函数；模型、设备、输出路径或高级调优参数不能直接塞入 MDF input_data。

- [`run_watertight`](http://172.31.0.3:8099/video-to-3d/service/mesh-watertight/-/blob/861eb6919bd4f715dae98b389589cfe49c185713/API.py#L118)：`(input_model_path: str, output_model_path: str, watertight_resolution: int=DEFAULT_WATERTIGHT_RESOLUTION, is_fillhole: bool=True, target_face_num: Optional[int]=DEFAULT_TARGET_FACE_NUM, k: float=DEFAULT_INITIAL_K, max_gpu_memory_ratio: float=DEFAULT_MAX_GPU_MEMORY_RATIO, visibility_shrink_depth_multiplier: int=DEFAULT_VISIBILITY_SHRINK_DEPTH_MULTIPLIER, intermediate_watertight_output_path: Optional[str]=None, enable_log: bool=False, enable_sliver_cleanup: bool=True, sliver_cleanup_verify: bool=False, allow_resolution_fallback: bool=True, enable_holefill: Optional[bool]=None, result_stats: Optional[dict[str, Any]]=None, routing_mode: str=DEFAULT_ROUTING_MODE, enable_self_isect: bool=True, enable_adaptive_clamp_rollback: bool=True, strict_wt_enabled: bool=False, preserve_original_boundary: bool=False)`。

本地 CLI：[`run.py`](http://172.31.0.3:8099/video-to-3d/service/mesh-watertight/-/blob/861eb6919bd4f715dae98b389589cfe49c185713/run.py)。启动 MDF 服务使用 `--env/-e`（默认 test，dev/test/prod）、`--service_name`（默认 mesh-watertight）、`--port/--tcp_port`（int，默认 None）、`--arbiter-host`（默认 127.0.0.1）、`--arbiter-port`（int，默认 19600）；这些是部署参数，不是业务字段。这里记录固定源码契约，具体线上版本需由当前调用核对。

依据：[API.py](http://172.31.0.3:8099/video-to-3d/service/mesh-watertight/-/blob/861eb6919bd4f715dae98b389589cfe49c185713/API.py)、[README.md](http://172.31.0.3:8099/video-to-3d/service/mesh-watertight/-/blob/861eb6919bd4f715dae98b389589cfe49c185713/README.md)、[mesh_watertight/Method/watertight_modes.py](http://172.31.0.3:8099/video-to-3d/service/mesh-watertight/-/blob/861eb6919bd4f715dae98b389589cfe49c185713/mesh_watertight/Method/watertight_modes.py)、[mesh_watertight/Method/gpu_capacity.py](http://172.31.0.3:8099/video-to-3d/service/mesh-watertight/-/blob/861eb6919bd4f715dae98b389589cfe49c185713/mesh_watertight/Method/gpu_capacity.py)。维护时同时核对 process 的 get/别名/helper、展开的 result_info、返回字典与被调用参数解析器；缺省值以实现为准，不因上游未传就省略服务支持项。

## 产物检查边界

原始索引网格按边计数封闭，仍可能含重叠或反向重复三角形；导入器删除重复面后可能露出边界。分别检查原始文件和目标软件导入结果的重复面、边界与法线，再检查细杆/薄片/负空间。服务 watertight_succeeded 不能代替打印准备验收。
