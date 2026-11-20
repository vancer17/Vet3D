# 工作流图的状态发布与续接

适用于 Hi3D Agent 1.2.11（Windows x64）中通过 Skill 工作流图记录的进度。LLM 通过 [workflow_report](../../tools/workflow-report.md) 上报或查询，桌面通过 [workflow/read](interfaces/workflow-read-rpc.md) 读取并接收通知。本页说明这两条通道怎样观察同一份 Runtime 状态，以及进程内状态和磁盘记录何时会分离。

## 节点完成如何生效

1. **校验调用。** Runtime 校验工具入参和线程所属工作区。它用工具调用的 `threadId`、`turnId` 取当前图。图必须处于 `running`，且包含所报 `nodeId`。缺少当前图和节点更新失败有各自的工具错误。节点更新失败的 `Unknown workflow node` 也可能由图已结束引起。安装包的 `reportNode` 不检查前置节点是否完成、产物是否已经登记或验收，也没有只许向前的状态转换约束。
2. **修改内存，再尝试写盘。** 节点状态变化时，`nw.mutate` 修改缓存中的图，将 `revision` 加一并更新 `updatedAt`。随后 `nw.save` 将该线程的全部缓存图序列化为临时文件，写入后用 `renameSync` 替换 `workflow-graphs/<sha256(threadId)>.json`。异常由 `save` 捕获，记录告警并尝试清理临时文件。缓存仍保留新版，写入结果不进入工具回包。
3. **发送桌面通知，再处理 Skill 用量。** `save` 返回后，`nw.mutate` 发送完整图的 `workflow/graphUpdated`。控制流随后回到工具分派，执行 `skillUsage.invoked`，收到 `completed` 时再执行 `Xv.verify`，最后向模型返回 `graphId` 和 `revision`。这里的顺序指 Runtime 发出通知与回包的顺序，桌面实际渲染和模型实际收到回包的时间需分别观测。

`Xv.verify` 核对图仍在运行、该节点已完成且是叶节点，并比对已有效启用的 Skill 名称、实例、版本和路径。符合条件时，它按线程、轮次、Skill 实例及版本去重记录 `skills/usageCompleted`，另按实例及版本写入首次使用记录并发送 `skills/usageVerified`。这是发布图之后的用量记录流程。用量记录写入失败时可跳过对应事件，图状态及回包不回滚。源自 `plan` 的节点状态更新也不经过这条 `operation=node` 的核验分支。

**根据安装包控制流重建的伪代码。** 省略工具应答包装和其他操作。

```python
def report_node(call, args, store, skill_usage):
    graph = require_running_graph_for_turn(call.thread_id, call.turn_id)
    node = require_known_node(graph, args.node_id)
    if node.status != args.status:
        node.status = args.status
        graph.revision += 1
        graph.updated_at = now_ms()
        store.try_save_thread_cache(call.thread_id)  # 捕获写入或替换错误并记录告警
        notify("workflow/graphUpdated", copy_graph(graph))

    if args.status in ("running", "completed", "failed", "interrupted"):
        skill_usage.record_invocation_if_eligible(call, graph)
    if args.status == "completed":
        skill_usage.verify_eligible_leaf(call, graph, node)
    return {"graphId": graph.graph_id, "revision": graph.revision}
```

节点 `completed` 与整图终态分别计算。对非 `generic` 图，若 Codex 轮次成功结束，`nw.finish` 先看是否有 `failed` 节点，再看是否有 `running`、`pending` 或 `interrupted` 节点，依次得到整图 `failed`、`interrupted`、`completed`。可选节点仍为 `pending` 时也会阻止整图完成。原本为 `running` 的节点随该整图终态更新，已完成节点保留。通用 `generic` 图有独立规则，成功轮次可把全部节点标为完成。`workflow/graphUpdated` 还可由计划变更、产物归属或终态更新触发，看到事件后要检查具体节点与整图状态。

## 模型、桌面和磁盘的可见结果

| 情况 | 模型与 Runtime 查询 | 桌面 | 磁盘 |
| --- | --- | --- | --- |
| 节点状态改变且写入成功 | 工具返回新修订，`inspect` 可读取新节点状态。 | 接收完整图，按 `graphId` 更新到更高修订。 | 线程图文件已替换。 |
| 图写入或替换失败 | 告警留在 Runtime 日志。工具仍可返回新修订，同进程 `inspect` 仍读到新状态。 | 仍可接收并展示新修订。 | 已有文件仍是上一份快照。首次保存失败时可能没有图文件。 |
| 同图同节点重复上报同一状态 | 图仍运行时返回原修订。重复 `completed` 仍进入用量核验，可重试符合条件但此前未写入的用量记录。 | 不产生新的 `workflow/graphUpdated`。 | 不重试保存工作流图。后续确有变化的操作如果保存成功，会将当时的整线程缓存写入磁盘。 |
| 缓存未命中后冷读 | 以磁盘为起点，恢复前只有成功写盘的进度可用。 | `workflow/read` 返回恢复后的快照，冷读本身不推送更新事件。 | 磁盘图若仍在 `planning` 或 `running`，冷读会把图和其中运行中的节点标为 `interrupted`，加一修订并尝试写回。 |

renderer 的 `QR` 对事件与 `workflow/read` 回包使用同一合并规则。同一 `graphId` 只接纳严格更大的 `revision`。例如磁盘停在修订 7，写失败后内存和桌面已看到修订 8 的节点完成，冷读可能从修订 7 重新生成内容不同的修订 8。**若桌面仍保留旧缓存，等号会使这次冷读回包被忽略。** 缓存清空或新建桌面读者时则可接受磁盘派生的快照。这个冲突由控制流和隔离复现确认，生产环境是否在 Runtime 重启时保留 renderer 缓存未实测。 [桌面读取与缓存契约](interfaces/workflow-read-rpc.md)

## 中断与续接

1. **确定中断来源。** 正常的轮次终结通过 `finish` 更新该轮图。Codex 退出或重启时，仍存活的 Runtime 用 `interruptActive` 更新缓存中的活动图，走尝试保存后通知的路径。Runtime 自身重启后，首次读取线程时走上述冷读分支，按磁盘状态恢复。
2. **在同线程新轮显式续接。** `workflow_report(operation="resume")` 检查同线程最后一份属于其他已绑定轮次的图。该图须是 `interrupted` 并匹配请求的 Skill；上一图为 `explicit-skill` 时，工具先核对其中声明的 Skill 仍可用。它不会跳过最近一份不匹配的图去寻找更早的中断图。
3. **保留进度并关联新轮。** 保留原图的已完成、失败、跳过等节点状态和产物引用，将第一个 `interrupted` 改为 `running`，其余中断节点改为 `pending`。没有中断节点时，尝试启动第一个 `pending`。若当前轮有可复用的运行图，则写入该图；若没有，则创建新 `graphId`，修订从 1 开始。两种情况都写 `continuedFromGraphId`。模型得到当前图 ID、修订、节点摘要和产物引用，桌面接收完整图。已关联来源的当前图可直接返回，重复续接本身不重写图。首次续接仍服从相同的尝试写盘和发布规则。
4. **区分自动续接和实际任务恢复。** `plan` 还能在 Runtime 按短继续指令标记的轮次中尝试续接匹配的中断图。识别条件使用 `turn/start` 中拼接后的文本，长度至多 180，允许「继续」「接着」「续做」或 `resume`、`continue` 等开头，排除含「新任务」「重新开始」「从头开始」或 `start over` 的文本。压缩后生成的继续指令也可满足这些条件。重启时，如果旧图从未写盘且运行时找不到匹配的中断图，图续接可以失败。图中沿用的产物只是引用。重新使用前，调用方按需要核对实际文件、已登记模型版本、视窗状态，以及远端作业的原 `jobPath` 和任务 ID。模型上下文所需的 Skill 正文和阶段依赖仍从有效历史或工作区文件取得。 [本轮材料与续跑](llm-context.md) · [文件与模型版本查询](query-assets-and-model-versions.md)

## 核查依据

- 固定 Runtime 1.2.11 的 SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。模型上报分派见 `handleRuntimeDynamicTool` 的 `===Px` 分支，图读写及终态见 `nw` 的 `reportNode`、`mutate`、`save`、`read`、`finish`、`interruptActive`、`resume`，用量见 `Xv.verify`，继续指令识别见 `Xge`。 [Runtime 安装备份](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>)
- 固定桌面包 SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。renderer 的 `out/renderer/assets/index-CDPCug_K.js:148` 中 `QR` 实现读回和事件合并。 [桌面安装备份](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
- 隔离执行从安装包提取的分派、图存储和 renderer 合并逻辑，注入重命名失败并检验告警、图事件、重复上报、冷读和续接。生产样本的末个节点完成及同轮 `inspect` 回包均为修订 8，同一图的落盘记录为修订 9，状态为 `completed`。真实桌面的故障通知、跨进程恢复和显示时序仍待实测。 [节点回包与查询](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:173>) · [生产图快照](<D:/download/.sparc3d-runtime/environments/prod/workflow-graphs/39c03c1881feb41ce45e56a40380876211e366e02a24e8cfca31dd7a3e5f69c5.json>)
