# `model_retry_prepare`

## 工具名称与注册来源

`model_retry_prepare` 是 Windows x64 版 Hi3D Agent 1.2.11 的 Runtime 动态工具。定义位于 `dz[1]`，由 `Vg` 汇总，在 `thread/start` 通过 `dynamicTools` 交给随包 Codex 0.166.0。Runtime 的 `handleRuntimeDynamicTool` 将调用分派给免费重试记录管理器 `Cg`。

## 暴露给 LLM 的描述

以下代码块逐字保留安装包中 `description` 的解码值。

```text
Prepare an explicitly requested free retry of an exact registered model file. Returns retryRequestId. If a model-card retry message only names a file, call this to retrieve its existing request. Then call hi3d_api(action="retry", retryRequestId). Never substitute paid generation.
```

## 参数与结果

| 参数 | 必填性与默认值 | 校验或条件 |
| --- | --- | --- |
| `fileName` | 必填字符串，无默认值。 | 精确匹配当前工作区注册表中的版本文件名，包含 `.glb` 后缀。新建请求时，版本须有可验证的 Hi3D `source`，来源类型为 `model`，且调用位于原会话。原会话的 `threadRuntimeToolVersion` 须至少为 `2`。 |

模型可见 schema 声明 `additionalProperties: false`。工作区、会话、轮次和内部调用标识由宿主提供。用户明确请求免费重试是模型可见说明中的调用条件。工具处理器校验文件名、来源、会话和额度，使用宿主传入的上下文。

可验证的 `source` 来自 Runtime 识别的 Hi3D 生成记录。其他服务的响应 ID 或本地导出路径不能建立生成来源。即使 GLB 已登记，仍需按版本元数据与原生成记录核对来源和重试资格。 [版本来源记录](workspace-commit-model.md#文件身份与复用)

| 结果 | 负载与副作用 |
| --- | --- |
| 成功 | `{retryRequestId, fileName, next_action}`，`retryRequestId` 为免费重试意图的 UUID，`next_action` 说明 `hi3d_api` 的 `retry` 动作如何消费该 ID。新意图写入 `dataDir/model-retries.json`，保存固定的工作区 `jobPath`、`outputDir`、原版本家族名和 `tag4`。原版缺分类时保存 `null`。记录状态变化时发送 `model/retryChanged`。准备阶段可读取额度，远端任务在 `retry` 动作中提交。 |
| 失败 | 负载为 `{error}`。缺少工作区或字符串参数、模型来源或会话无效、内部请求标识已绑定其他文件、同一重试链已有冲突请求、额度无法确认可用或持久化失败时返回错误。 |

Runtime 通过 `ge` 将负载编码为 `contentItems` 中的 `inputText.text` JSON 字符串，并设置外层 `success`。成功响应中的 ID 标识本地重试意图。远端 `task_id` 在服务受理后由后续执行写入作业记录。

## 实现伪代码

模型发起该工具时，Runtime 为传给 `Cg` 的 `clientRequestId` 生成随机 UUID。工具的 `callId` 和 App Server RPC ID 仍用于调用与应答关联。管理器按工作区和 `clientRequestId` 检查重复请求，再用来源的环境、账号和根任务 ID 对同一重试链串行处理。重复的模型调用可以生成不同的 `clientRequestId`；同一会话中已有未终结的意图时，仍可按重试链复用原 `retryRequestId`。其他会话的冲突会报错。新建前通过缓存或桌面代理核查额度，只有 `can_retry` 为真时才创建记录。额度查询的 `jobId` 由同链的重试记录或当前版本的来源决定。 [Runtime 工具分派，原始字节偏移 3189679](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [额度读取与重试结果](hi3d-api.md#免费重试与结果复用)

```python
# 实现伪代码，概括 Runtime 分派器和重试记录管理器。
async def model_retry_prepare(args, call):
    try:
        workspace = require_workspace_for_thread(call.thread_id)
        file_name = require_string(args, "fileName")
        client_request_id = generate_uuid()
        record = find_by_client_request(workspace, client_request_id)
        if record is not None:
            require_exact_file_match(record, file_name)
        else:
            model = require_supported_model(workspace, file_name, call.thread_id)
            async with serialize_retry_chain(model.source):
                record = find_open_retry(model.source)
                if record is not None:
                    record = accept_or_reject_existing_request(record, call)
                else:
                    quota = await read_retry_quota(workspace, model)
                    require(quota.can_retry)
                    record = persist_new_retry_intent(workspace, model, call, client_request_id)

        bind_turn_if_active(record, call.turn_id)
        if app_server_was_replaced(call) or turn_is_terminal(call):
            interrupt_pending_retry_execution(call)
        return tool_result({
            "retryRequestId": record.request_id,
            "fileName": record.file_name,
            "next_action": retry_tool_instruction(),
        })
    except Exception as error:
        return tool_error(str(error))
```

同一 `retryRequestId` 在原会话中解析为同一意图、`.hi3d/retries/<ID>.json` 和 `exports/hi3d-retry-<ID>`。`hi3d_api(action="retry")` 从记录取得父任务来源并校验原作业。首次执行时，脚本独占创建子作业，向桌面代理发送 `POST /v1/model3d/retry`。请求体只包含原任务根 ID `parentGenerateId`。响应中的 `jobId` 校验后写为子作业的 `task_id`，后续按该 ID 查询和下载。 [hi3d_api](hi3d-api.md#免费重试与结果复用)

等待返回 `pending` 或执行中断后，继续使用原 `retryRequestId`，按子作业里已记录的 `task_id` 续查。已有作业与原计划一致时复用作业，已完成登记时复用版本。提交结果不明确且缺少子作业 `task_id` 时，Runtime 返回 `attention` 和 `submission_uncertain_without_task_id`，保留原意图及作业记录供核对。

## 调用示例

**根据已核查的 schema 重建的工具参数。** 假定当前会话拥有符合重试条件的注册版本 `hi3d-example_2.glb`。

```json
{
  "fileName": "hi3d-example_2.glb"
}
```

**根据 Runtime 成功负载重建的示例。** UUID 仅为示例值。实际负载位于 `contentItems[0].text`。

```json
{
  "retryRequestId": "66dd624b-f618-4da0-b991-dda7a2d1a7bb",
  "fileName": "hi3d-example_2.glb",
  "next_action": "Call hi3d_api with action=retry and this retryRequestId. Runtime handles paths, free submission, download and registration."
}
```

## 核查依据

- 1.2.11 Windows x64 留存包 `runtime/dist/runtime.mjs` 的 SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。`dz[1]`、`Vg` 和 `handleRuntimeDynamicTool` 对应注册与分派。`Cg` 的 `model`、`quota`、`create`、`plan`、`observe` 和 `completedResult` 对应来源、额度、意图和恢复处理。 [安装清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)
- `retry_job` 与 `generate_retry_task` 对应子作业持久化、提交和下载。 [作业脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:108>) · [组合重试脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:62>) · [随包免费重试参考](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-free-retry.md)
- 工具描述与安装包中的字符串逐字核对。Runtime 意图与登记行为来自静态核查。随包 `hi3d/tests/runtime/test_account.py` 的五项相关离线测试通过，覆盖额度只读查询、提交使用原根任务、服务受理后的记录顺序及父任务冲突校验。本机已核查的 rollout 未观察到该工具的实际调用。真实账号的额度、云端受理和产出仍需实测。 [随包测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/tests/runtime/test_account.py>)
