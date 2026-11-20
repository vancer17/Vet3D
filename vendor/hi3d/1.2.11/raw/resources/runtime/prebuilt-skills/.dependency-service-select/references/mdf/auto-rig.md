# auto-rig

基于 SkinTokens，为模型生成骨骼与蒙皮权重，返回可继续检查、摆姿或制作动画的 GLB；本服务不生成动作，不保证自动绑定达到最终动画质量。

## 来源与调用范围

服务仓库：[hi3dreamer/auto-rig](http://172.31.0.3:8099/hi3dreamer/auto-rig)。本文依据已部署适配器 `auto_rig_algo.py`、`auto_rig_service_mdf3.py`、`API.py` 和 `runtime.py`；这些适配文件尚未发布为固定提交，不能用仓库初始提交重现本契约。底层固定版本为 [SkinTokens 273b691d](https://github.com/VAST-AI-Research/SkinTokens/tree/273b691d35989d71cd17ff2895fdc735097b92d1) 和 [MDF3 3.2.1 / 8af6e48a](http://172.31.0.3:8099/TangPei/mdf3/-/tree/8af6e48ab048219ab61ecca9f87272624e15f674)。更换适配器或部署前须重新核对接口，不能将底层版本当作适配器已发布的证据。

注册默认名为 `auto-rig`，部署默认环境 `test`、Nacos group `v3.0`。默认调用路径是 HTTP `generic-forward` 中控 → 同环境 TaskQueue → worker → 中控回传；GLB 输入与绑定输出已完成跨主机真实调用验证。也支持显式完整 SDK `ServiceInvokeSession` 直连，其同机 GLB 路径已有真实验证；SDK 异机回调、OBJ/FBX、Draco 压缩输入及可选骨骼/后处理分支仍需单独验证。通过统一 mdf-call 入口按服务名调用；清单收录不保证当前在线，实际队列与回调网络仍须可达。

## MDF 输入

`input_data` 必须为 dict，只消费 `mesh` 与 `options`；其他顶层字段忽略。文件类型遵循[共用 BinaryFile 约定](README.md#二进制与数组)。

| 字段 | 类型 / 默认 | 约束与语义 |
| --- | --- | --- |
| `mesh` | 必填 BinaryFile | `field_name` 必须为 `mesh`；`file_name` 必须为无目录、无反斜杠的安全 basename，后缀不区分大小写，仅 `.obj`、`.fbx`、`.glb`。`content` 为非空 bytes，默认最多 256 MiB；部署可用 `AR_MAX_INPUT_BYTES` 调整。不能传服务器路径、URL、ZIP 或 JSON 中的普通文件描述对象。 |
| `options` | dict，默认 `{}` | 只允许下表字段；未知字段或显式 null 拒绝。布尔值不接受字符串或 0/1；整数参数不接受 bool/浮点；数值参数拒绝 NaN、无穷及 bool。 |

只传一个文件，OBJ 的 MTL 或 OBJ/FBX 的外部纹理不会随请求自动传输；需材质时优先使用自包含 GLB。扩展名校验通过不表示内部数据一定可导入。

人形工作流推荐只提交静止身体网格，服装、护甲、头发和道具另行装配；这是输入准备建议，不是服务强制的单 Mesh 限制。用于调用的简化代理与最终交付高模分开保留，回迁前检查坐标、尺度和轮廓。已有合格绑定或需要精确保留面部/DNA 骨架时优先沿用原方案。

| options 字段 | 类型 / MDF 默认 | 范围与作用 |
| --- | --- | --- |
| `top_k` | int / `5` | 0–4096；生成采样候选数。 |
| `top_p` | int 或 float / `0.95` | (0, 1]；核采样概率阈值。 |
| `temperature` | int 或 float / `1.0` | (0, 10]；采样温度。 |
| `repetition_penalty` | int 或 float / `2.0` | (0, 10]；重复 token 惩罚。 |
| `num_beams` | int / `10` | 1–20；beam 数，增大会提高资源消耗。 |
| `use_skeleton` | bool / `False` | False 时生成骨骼和蒙皮；True 时在输入可提取骨骼 token 的情况下用已有骨骼条件预测蒙皮。没有骨骼 token 时仍可退回生成，不能据此保证原骨骼名称、层级精确保留。 |
| `use_transfer` | bool / `True` | 将预测绑定转移回原模型以保留材质与原始尺度；False 使用上游直接导出路径，可能改变尺度、网格组织与材质。两者均需检查输出，不承诺逐顶点/拓扑完全一致。 |
| `use_postprocess` | bool / `False` | 启用体素蒙皮后处理，再归一化权重。 |
| `seed` | int / `42` | 0–4294967295；控制随机种子，不承诺跨设备或版本逐字节可复现。 |

## 输出与失败

成功返回 `success: bool=True`、`status: str="success"`、`trace_id: str`，以及：

| 字段 | 类型与含义 |
| --- | --- |
| `rigged_mesh` | BinaryFile，`field_name="rigged_mesh"`、`file_name="rigged.glb"`，内容为 GLB 2.0；含骨骼 skin、绑定节点和具有 `POSITION` / `JOINTS_0` / `WEIGHTS_0` 的 primitive。不是服务器文件路径。 |
| `metadata` | dict，包含以下全部统计；不含服务器输出路径。 |
| `metadata.bytes` | int，GLB 文件字节数。 |
| `metadata.joints` / `skins` | int，各 skin 的 joints 数之和 / skin 数；共享关节可能重复计数。 |
| `metadata.skinned_primitives` / `vertices` | int，带蒙皮属性的 primitive 数 / 这些 primitive 的 POSITION accessor 顶点数之和；不是去重顶点数。 |
| `metadata.worker_id` / `worker_pid` | worker 标识 / 进程 ID，用于区分处理实例。 |
| `metadata.model_initialized_at` | float，常驻模型初始化的 Unix 时间戳，秒。 |
| `metadata.requests_completed` | int，该模型会话已完成请求数。 |
| `metadata.elapsed_seconds` | float，worker 请求处理耗时，秒，保留 3 位小数；不含完整排队/网络耗时。 |

算法异常返回 `success=False`、`status="failed"`、`trace_id`、`error_type: str`、`error_message: str`，不返回 `rigged_mesh`。进程被超时或致命 CUDA 错误终止时可能只有框架失败或调用超时，不能要求一定有上述算法错误字段。错误正文可能带内部信息，不直接复制到公共报告。

请求临时输入/输出在处理结束后清理；调用方应保存 BinaryFile 字节再交给下游。超时不代表请求未执行，保留原任务标识，不自动换 ID 重提。

## 调用依赖与最小交接

与其他 MDF 下游服务共用独立 `mdf-call`，无需 auto-rig 专用客户端。先按 [统一调用说明](../calling.md) 提供 `MDF_DIR`（mdf-call 的实际目录）、`PYTHON`（HTTP 文件型调用支持标准库运行时，SDK 模式才要求完整 SDK 与 PyYAML）和包外 `RUN_DIR`。SDK 3.2.1 是上文服务部署的来源基线；客户端依赖与配置解析沿用 mdf-call 的统一运行时要求。

默认 HTTP 模式要求 worker 与中控使用同一队列并能双向通信，worker 不必回连本机。显式 `--transport sdk` 才要求 worker 连接调用方临时 TCP 服务，以 fetch 输入和回传结果；此模式的 test 配置可用随包值，其他队列通过 `--config` 指定。两种模式均不因服务名为 auto-rig 而要求专用客户端或额外凭据，不自动在不明结果后切换传输。

在 `RUN_DIR/request.json` 中填写：

```json
{
  "mesh": {"$file": "input.glb"},
  "options": {"use_transfer": true}
}
```

`input.glb` 相对请求 JSON 所在目录解析；也可指定已授权输入的绝对路径。`$file` 会由统一入口构造成 `field_name="mesh"` 的 SDK BinaryFile。已获业务调用授权且运行时预检通过后执行：

```bash
"$PYTHON" "$MDF_DIR/scripts/mdf_call.py" \
  --service auto-rig --input "$RUN_DIR/request.json" \
  --run-dir "$RUN_DIR/call" --timeout 1800
```

默认 `success=True` 判定与本服务一致，无需额外成功谓词。返回的 `rigged_mesh` 由统一入口保存到 `call/artifacts/`，在 `call/invocation.json` 的 `files` 中按 `field_path=["rigged_mesh"]` 定位实际文件；不要假定第一个文件就是绑定模型。CLI 的产物保存成功仍需后续业务验收。

验收时解析 GLB，核对骨骼/skin/顶点属性索引、权重有限且非负并归一化，再在 Blender 等工具中检查材质、尺度与关节弯曲。服务的 GLB 结构检查不能替代蒙皮变形质量验收。超时沿用统一入口保留的 trace 与审计恢复，不重提。

重点检查弯臂、屈腕和屈指时的尖刺：归一化权重仍可能含对侧骨骼影响。对照原始服务结果与高模回迁结果，按实际骨头位置、层级和异常面顶点定位；不能从编号猜语义，也不先全身平滑或重新调用。完整回迁、局部修复与动作验收显式交给另行提供的 `rig-retarget`，读取其 `references/service-rig.md`；交接原始 GLB、源工程、目标对象和保留项。本工具继续只负责原子调用与结果检查，不复制该工作流脚本。

## 部署参数与本地 API 区别

本适配器使用 standalone `ServiceBase`，1 worker、1 puller，模型在 worker 初始化时加载并复用，不要求 arbiter。其 CLI 不使用共用托管入口的下划线参数名：

| CLI | 环境变量 / 默认 |
| --- | --- |
| `--env` | `MDF3_ENV` / `test` |
| `--service-name` | `MDF3_SERVICE_NAME` / `auto-rig` |
| `--config` | `AR_MDF3_CONFIG` / `/etc/mdf3/config/config.test.yaml` |
| `--tcp-port` | `MDF3_TCP_PORT` / `19780`；MDF TCP，不是 HTTP |
| `--task-timeout` | `AR_TASK_TIMEOUT` / `1800` 秒；worker 超时终止策略 |

`AR_MODEL_DIR` 指向部署侧本地模型目录，不接受请求覆盖；启动等待 worker 就绪上限为 600 秒。Blender RPC 固定为宿主本地端口 `59876`，当前 host-network 封装在同一宿主只支持一个实例，不据此横向复制容器。

本地 `API.run_auto_rig` / CLI 接收本地路径，`use_transfer` 默认 False，而 MDF 业务默认 True；本地 `model_dir`、`session`、`timeout`、输出路径等不是 `options` 字段。不要将本地 API 参数、部署参数或其他 UE/MetaHuman auto-rig 接口混入本服务请求。
