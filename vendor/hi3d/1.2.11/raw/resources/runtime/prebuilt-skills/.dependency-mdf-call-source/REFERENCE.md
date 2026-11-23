---
name: mdf-call
description: 按已确认契约单次调用 MDF 服务，默认使用 HTTP 中控，支持显式 SDK 队列/TCP 直连，提供文件与数组通信、运行时预检、脱敏审计和产物验收；异步状态查询与业务成功条件由调用方提供。
---

# MDF 服务调用

将已确认的服务契约、单次请求和业务验收组合成可追溯的调用。`SUCCEEDED` 表示业务响应成功；必需产物与副作用通过验收后才可报告 `VALIDATED`。

## 独立入口与传输选择

按 [打包约定](../.dependency-package-tools/references/usage.md) 提供完整分发目录并保留文档布局，通过 `$mdf-call` 或显式读取本文件使用；不要求业务工作流预先加载。`SKILL_DIR` 是实际工具包位置，`RUN_DIR` 是包外任务目录，`PYTHON` 是目标解释器。目录存在不等于宿主已发现工具入口。

**默认使用 HTTP 中控。** 调用端只需向网关发送 HTTP 请求，由服务器中控经 TaskQueue/TCP 联系 worker 并返回结果；worker 无需回连调用端。地址优先级为 `--endpoint` → `MDF_ENDPOINT` → `http://172.31.192.135:7789/generate_model`。文件型调用可使用随包 BinaryFile/protocol 4 通信子集与标准库 HTTP，无需完整 SDK、PyYAML 或本地回调端口。数组契约额外需要 NumPy。

仅在 worker 能回连当前主机临时 TCP 端口时，显式使用 `--transport sdk`，通过官方 `ServiceInvokeSession` 直连队列。此模式需要完整 MDF3 SDK 与 PyYAML，配置优先级为 `--config` → `MDF3_CONFIG_PATH` → 随包 test 配置。能访问队列不证明回连成立。HTTP 模式不读取 SDK 配置；SDK 模式不读取 HTTP 地址。两种模式不会在超时后自动切换或重提。

`--help` 查看 CLI。文件引用和产物交接两种模式相同。最小 Python 示例分别见 [HTTP 适配器](references/mdf3-generic-forward.md) 与 [SDK 适配器](references/mdf3-service-invoke.md)；运行时选择、来源与大文件边界见 [通信运行时](references/wire-runtime.md)。

## 调用前检查

运行 `scripts/check_runtime.py` 检查本地依赖，数组契约增加 `--require-numpy`；SDK 模式增加 `--transport sdk`。运行 `scripts/mdf_endpoint.py` 检查 HTTP 中控身份与健康；SDK 模式增加 `--transport sdk` 时只检查 YAML 和队列地址。这些检查均不提交业务，不能代替下游推理与产物验收。

服务名来自随包 [服务清单](assets/services.json)，auto-rig 与其他服务使用同一个 CLI。清单的 exposure_status 记录用户确认的露出范围；pending_confirmation 项须先核实部署。元数据不改变传输选择或 CLI 准入，也不保证当前在线。只有用户要求逐服务诊断时才使用 `mdf_probe.py --service <名称>` 或 `--all-services`，其默认同样为 HTTP；诊断会真实提交缺少业务输入的请求，必须保留 trace，不能作为每次业务调用的自动前置步骤。配置与诊断说明见 [部署与诊断](references/deployment-and-probes.md)。

## 直接调用业务服务

本地运行时与所选入口检查通过后，准备请求 JSON；以 auto-rig 为静止 T/A-pose 身体生成骨骼和蒙皮为例：

```json
{"mesh": {"$file": "body.glb"}, "options": {"use_skeleton": false, "use_transfer": true}}
```

`body.glb` 相对请求 JSON 所在目录解析；也可使用绝对路径。模板见 [自动绑定请求](assets/request.auto-rig.json)。

```bash
"$PYTHON" "$SKILL_DIR/scripts/mdf_call.py" \
  --service auto-rig --input "$RUN_DIR/request.json" \
  --run-dir "$RUN_DIR/call"
```

无需再写客户端。`--service` 选择当前清单中的服务，JSON 按该服务契约填写；`$file` 递归转为 MDF3 BinaryFile，支持列表和嵌套字典。输出目录必须不存在；保存 trace、运行时来源、审计、耗时、脱敏结果摘要及返回的二进制产物。默认要求业务 `success` 为布尔 True，其他已确认契约可用 `--success-field`/`--success-value` 覆盖。异常保留原 trace，不自动重试。完整参数与结果边界见 [部署与诊断](references/deployment-and-probes.md#业务调用与产物)。

auto-rig 复用同一入口：已确认契约下以 `mesh: {"$file":"body.glb"}`、`options: {"use_skeleton":false,"use_transfer":true}` 提交静止身体，从 `invocation.json.files` 的 `field_path=["rigged_mesh"]` 找返回文件。调用主机沿用用户指定位置；完整绑定修复由另行提供的 `rig-retarget` 接收原始 GLB 和源工程处理。服务参数详情可由独立 `service-select` 提供，文件保存成功不等于蒙皮动作通过。

网格水密处理读取 [mesh-watertight 契约与用法](references/mesh-watertight.md)，请求模板见 [水密请求](assets/request.mesh-watertight.json)；它返回 `watertight_mesh_glb`，需要核对实际水密阶段结果及网格边界。

## 调用流程

1. 优先使用上述传输选择与预检，再从当前官方客户端、服务入口或部署配置确认环境、服务名、输入输出、超时、ID 与成功条件。将其记录为 [RunSpec](assets/run_spec.template.json)。契约解析与运行时预检见 [契约与来源](references/contract-and-runspec.md)。
2. 本地校验输入，生成脱敏摘要与完整输入指纹。`inspect_runtime.py` 记录已确认导入安全的模块来源；实际 import 会执行模块初始化，不能把未知模块的导入称为无副作用预检。
3. 使用包内业务 CLI 或同一 Python 适配器；按所选 [HTTP 适配器](references/mdf3-generic-forward.md) 或 [SDK 适配器](references/mdf3-service-invoke.md) 解析入口、注入成功谓词，并调用一次。正式调用只走宿主全局 `waiting_choice`；Agent 不另做授权。本对话已选始终允许的 `mdf.invoke` 由宿主不再弹窗，「仅本次」只覆盖一次提交；按原 trace/request 恢复不新建请求，不再弹窗。
4. 异步任务由当前项目的查询客户端观测；超时、断连或无法解释的结果保留为 `AMBIGUOUS`，使用原 trace/request/task ID 恢复，不能换 ID 或重提。审计、状态分类与 [批清单](assets/batch_manifest.template.json) 见 [执行与恢复](references/execution-and-recovery.md)。
5. 用 `validate_artifact.py` 或注入的业务解析器检查必需产物，并核对 required 副作用；用 `verify_audit.py` 检查调用配对。完成条件见 [业务验证](references/validation-and-side-effects.md)。输出非空或审计通过不能替代业务验收。

## 必要边界

- 只发送任务所需数据；报告使用 endpoint 别名和配置文件名，不记录 TOS/Kafka/飞书密钥、签名 URL 或原始敏感响应。摘要器只识别已知敏感字段；其他私有字段需显式标记或使用白名单 hook。
- 适配器单次提交且不自动重试；只向当前确认可信的 MDF 部署发送请求。超时后中控侧任务可能仍在队列中，不能把超时当成未提交。
- `stable_digest` 是截断、脱敏摘要的指纹，只用于审计关联。checkpoint 的输入/契约/参数指纹必须来自完整、确定性的数据或文件 SHA-256；变更内容不能因摘要截断而被当作可复用。
- 成功谓词按真实服务契约注入；本包不实现所有 MDF 协议、通用异步轮询、业务 schema 或线上部署修改。

交付 RunSpec、JSONL 审计、产物/验证报告和必要 checkpoint；说明最终状态、原始 ID、脱敏输入摘要、重试次数与未验证项。运行记录和用户产物放在 `RUN_DIR`，不写回工具包。维护时以 `"$PYTHON" -m unittest discover -s "$SKILL_DIR/tests" -v` 做离线回归，不为测试调用线上服务。

## 公开 Runtime 模式

宿主提供 `mdf_api` 时读取 [mesh/invoke 调用](../mdf-api/SKILL.md) 和 [14 项能力完整参数/输出](../mdf-api/references/mesh-invoke-api.md)。`scripts/runtime/mdf_api.py` 由宿主调用；共享账号传输按 package.json 显式物化。公开模式与内部 HTTP/SDK 服务命名、成功码及恢复方式不同，不能互换。

<!-- managed-by: sparc3d-runtime -->
