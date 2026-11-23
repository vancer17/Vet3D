# workflow/read

## 接口名称与注册来源

`workflow/read` 是 Hi3D Agent 1.2.11（Windows x64）的宿主 RPC。桌面 renderer 通过 Electron 主进程的 Runtime RPC 通道调用。主进程将其列入可转发的方法，Runtime 的 `cg` 定义参数和返回结构，`Yg` 的工作区相关处理器负责分派。桌面另可接收 `workflow/graphUpdated` 通知以更新已读取的图。

## 模型可见定义

此方法注册在宿主 RPC 契约中，核查到的实现没有为它注册 LLM Tool 或模型可见 `description`。**接口概述。** 按已经登记的线程取得 Runtime 保存的工作流图。LLM 侧的工作流工具另见 [workflow_report](../../../tools/workflow-report.md)。

## 参数与结果

| 项目 | 已核查的契约 |
| --- | --- |
| `threadId` | 必填非空字符串，无默认值。Runtime 以其查找已登记的线程及其工作区。 |
| 返回值 | `{graphs: WorkflowGraph[]}`。已登记线程没有可读的图时，返回 `{graphs: []}`。 |
| 参数错误 | 缺少 `threadId` 或类型、长度校验失败，由 Runtime 返回 `INVALID_ARGUMENT`。 |
| 归属错误 | 线程没有关联到已登记工作区时返回 `METHOD_NOT_ALLOWED`。 |

底层 JSONL 传输用 `requestId` 关联单次请求和响应，查询所属线程由 `params.threadId` 决定。

每个 `WorkflowGraph` 的 `schema` 为 `runtime.workflow.v1`。图包含 `graphId`、`threadId`、可空 `turnId`、正整数 `revision`、`title`、`source`、可空 `skillName`、`layout`、`status`、`nodes`、`edges`、`artifacts`、`createdAt` 和 `updatedAt`，以及可选的 `continuedFromGraphId`、`locale`、`titleLocale`。`source` 为 `generic`、`explicit-skill` 或 `agent-plan`，`layout` 为 `linear` 或 `tree`，`status` 为 `planning`、`running`、`completed`、`failed` 或 `interrupted`。

| 数组 | 单项结构 |
| --- | --- |
| `nodes` | `id`、`label`、`role`、`status`、布尔值 `optional`、可空 `parentId` 和 `entry`，以及可选 `labelLocale`。`role` 为 `agent`、`subagent`、`local` 或 `step`，`status` 为 `pending`、`running`、`completed`、`failed`、`skipped` 或 `interrupted`。 |
| `edges` | `from`、`to`、`kind`。`kind` 为 `advance`、`contains`、`spawn` 或 `rollback`。 |
| `artifacts` | `id`、`kind`、`label`、`createdAt`，以及可空的 `nodeId`、`assetId`、`fileName`、`path`、`url`、`mimeType`。`kind` 为 `model`、`image`、`file` 或 `link`。 |

读取图时返回既有产物引用，文件内容和当前可访问性由相应的后续读取检查确认。

存储按线程位于 Runtime 数据目录的 `workflow-graphs/`，文件名由 `threadId` 的 SHA-256 派生。已缓存时读取当前进程的内存快照。缓存未命中时读取存储并按图契约校验。存储缺失时使用空数组，存储格式错误或不可读时记日志并使用空数组，单条图格式错误时跳过该条。冷读遇到持久化的 `planning` 或 `running` 图，会将图及其中仍为 `running` 的节点标记为 `interrupted`，更新图的 `revision` 和 `updatedAt`，并尝试写回。冷读结果通过 RPC 返回，该路径不发布 `workflow/graphUpdated`。写回失败记录日志，本次响应仍可返回已更新的内存快照。

## 实现伪代码

**根据安装包重建的伪代码。** Runtime 先检查参数和线程归属，再按原线程读缓存或磁盘。恢复标记发生在该线程首次载入缓存时。读取返回图数据的副本。

```python
def workflow_read(params, registry, store):
    thread_id = require_nonempty_string(params, "threadId")
    if registry.workspace_for_thread(thread_id) is None:
        raise RpcError("METHOD_NOT_ALLOWED")

    if thread_id not in store.cache:
        graphs = load_and_validate_stored_graphs(store, thread_id)
        store.cache[thread_id] = graphs
        changed = False
        for graph in graphs:
            if graph["status"] not in ("planning", "running"):
                continue
            graph["status"] = "interrupted"
            for node in graph["nodes"]:
                if node["status"] == "running":
                    node["status"] = "interrupted"
            graph["revision"] += 1
            graph["updatedAt"] = now_ms()
            changed = True
        if changed:
            store.save_with_warning_on_failure(thread_id)
    return {"graphs": deep_copy(store.cache[thread_id])}
```

`workflow/graphUpdated` 的参数是一份完整的图。renderer 将初次读取和后续通知送到同一合并函数，以 `graphId` 定位图，只接受严格更大的 `revision`。读取返回的列表按项合并，原缓存中未出现在回包里的图不会由这次合并删除。由于图变更尝试写盘后即可通知，桌面缓存可能领先于磁盘。若 Runtime 从较旧的磁盘图冷读，且 renderer 保留了较高或相同修订的快照，则读回结果可能被丢弃。重新读取继续使用原 `threadId`，读取方法本身不创建或续接工作流任务。

## 调用示例与核查依据

**根据安装包契约重建的宿主请求。** 假定 `thread_example` 已登记。

```json
{
  "type": "request",
  "requestId": "workflow-demo-1",
  "method": "workflow/read",
  "params": { "threadId": "thread_example" }
}
```

**根据宿主返回契约重建的示例。** 当前线程没有保存的图时，结果如下。

```json
{
  "type": "response",
  "requestId": "workflow-demo-1",
  "result": { "graphs": [] }
}
```

- Runtime 源于 Hi3D Agent 1.2.11 安装包 `resources/runtime/dist/runtime.mjs`，SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。契约见 `cg`、`lg`、`Qee`、`ete`、`tte`，分派见 `dispatchRuntimeMethod` 和 `Yg` 的 `workflow/read` 处理器，存储见 `nw.read`、`nw.save` 和 `fR`。
- 桌面包 `resources/app.asar` 的 SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。主进程 `out/main/index.js` 中的 `Ja` 负责允许转发。renderer `out/renderer/assets/index-CDPCug_K.js` 第 148 行包含初始读取和增量合并。核查时两个同哈希的安装产物位于 `D:/install/Hi3DAgent.__hi3d-transaction/`。
- 静态核对了接口契约、桌面转发和存储函数。用模拟注册表和存储执行提取的分派与读取函数，覆盖未登记线程、缺失或损坏存储、无效图记录过滤、冷读恢复标记、缓存复用及返回副本。真实磁盘写回、桌面进程间调用和通知到达时序仍需实测。
