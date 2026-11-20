# `workflow_report`

## 工具名称与注册来源

模型可见名称为 `workflow_report`。核查版本为 Windows x64 版 Hi3D Agent 1.2.11，随包 Codex 0.166.0。Hi3D Runtime 通过 `Vg` 将 `BL` 中的定义合入 `thread/start` 的 `dynamicTools`，按工具调用关联的对话和轮次查找工作流图。调用方需要已关联的工作区。

## 暴露给 LLM 的描述

下文是 `description` 原文，解码字符串转义后保留原文措辞。

```text
Report a workflow only for a turn using a skill. Do not call for ordinary chat. For a selected or implicitly chosen installed skill, call operation=inspect with its exact skillName before substantive work. This is the Runtime-confirmed invocation boundary; do not call merely to browse, recommend, or describe a skill. Always do this even when its instructions were read earlier in the conversation. It loads its architecture. Immediately report operation=plan with the same canonical node IDs and topology, translating title and every node label into the language of this turn’s user message, independently of the app UI language. If no architecture is installed, call operation=plan with skillName and stable nodes before substantive skill work. If continuing the same skill task after an interrupted turn, call operation=resume first; include skillName when known, then translate its labels with plan without resetting completed progress. Use operation=node for progress; its nodeId belongs at the top level. For operation=artifact, put the responsible nodeId inside every artifacts[] item, together with the exact committed model fileName or workspace-relative image/file path. Before finishing a skill turn, call operation=inspect and assign any unclassified outputs. This updates UI only, not the skill output contract. Never include credentials or signed URLs.
```

此描述与 1.2.11 原包定义解码后逐字一致。按正文 UTF-8 字节计算，描述长 1367 个字符，SHA-256 为 `20860d40a15222e11edfd4689129a4268889d450b383a9d30a203c936c3e378b`。该摘要只覆盖代码块中的描述正文，排除围栏及两端换行。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)

## 参数与结果

`operation` 是模型可见 schema 中唯一全局必填的字段。Runtime 依操作继续校验必填项和当前图状态。注册约定将报告限定在实际选用已安装 Skill 的轮次。只浏览 Skill 目录或说明用法时无需上报。

| `operation` | 参数和条件 | 成功返回的 JSON 负载 |
| --- | --- | --- |
| `inspect` | 读取当前轮的图。没有当前图时，需给出准确的 `skillName`，Runtime 尝试从该工作区可用的已安装 Skill 加载架构。 | `graphId`、`revision`、`nodes`、`unassignedArtifacts`。节点摘要含 `id`、`label`、`status`、`parentId`、`role`、`entry`、`optional`。未分配产物摘要含 `kind`、`label`、`fileName`、`path`、`url`。 |
| `plan` | 必须提供 `nodes`。创建新图时还需提供 `skillName`。可提供 `title`、`layout` 和 `edges`。已有规范架构时保留原节点与拓扑，已结束的图拒绝改写。 | `graphId`、`revision`。 |
| `resume` | `skillName` 可选，用于匹配同一对话内上一轮的中断图。保留先前完成项和产物。 | `graphId`、`revision`、`continuedFromGraphId`、`nodes` 和 `artifacts`。节点摘要含 `id`、`label`、`status`，产物摘要含 `kind`、`label`、`nodeId`、`fileName`、`path`。 |
| `node` | 必须提供顶层 `nodeId` 和 `status`。当前图必须正在运行，且已包含该 ID。 | `graphId`、`revision`。 |
| `artifact` | 必须提供 `artifacts`。每项提供 `nodeId` 和 `kind`，再依类别提供产物引用。 | `graphId`、`revision`、`count`。`count` 为处理的输入项数。 |

| 字段 | 校验与默认值 |
| --- | --- |
| `title`、`skillName`、`layout` | 分别允许长度 1–160、1–120，以及 `linear` 或 `tree`。新计划省略标题时使用 `<skillName> · 工作流程`。省略布局时沿用已有图的布局，新图默认为 `linear`。 |
| `nodes` | 1–80 项。每项必填 `id`、`label`。`id` 以字母开头，随后最多 63 个字母、数字、下划线或连字符，计划内须唯一。`label` 长 1–160。可选 `parentId`、`entry` 支持 `null`，新项默认 `null`。`role` 可为 `agent`、`subagent`、`local` 或 `step`，新项默认 `step`。`optional` 默认 `false`。 |
| `status`、`nodes[].status` | 允许 `pending`、`running`、`completed`、`failed`、`skipped`、`interrupted`。新计划省略某项状态时，沿用已有同 ID 状态或初始化为 `pending`。全部为 `pending` 时，Runtime 启动一个初始节点。 |
| `edges` | 最多 160 条。每条必填 `from`、`to`、`kind`，两端均须对应节点。`kind` 可为 `advance`、`contains`、`spawn` 或 `rollback`。省略边或传空列表时，线形图连接相邻节点，树形图根据父子关系生成 `contains` 或 `spawn`。父级必须存在且不能形成环。 |
| `artifacts` | 1–30 项。每项 `kind` 可为 `model`、`image`、`file` 或 `link`。`model` 提供工作区内已登记版本的准确 `fileName`，`image` 和 `file` 提供工作区内常规文件的 `path`，`link` 提供通过凭据校验的 HTTPS `url`。`image` 允许 `png`、`jpg`、`jpeg`、`webp`、`gif`、`avif` 扩展名。`label` 可选，长 1–160，省略时按类型取模型名称、文件名或 URL。`mimeType` 可选，模型产物固定为 `model/gltf-binary`。 |

模型可见 schema 对顶层及子对象都声明 `additionalProperties: false`。Runtime 拒绝额外的顶层字段。`artifact` 分支还有一项向后兼容处理，如果已提供顶层 `nodeId`，会在运行时将它补给缺少 `nodeId` 的产物项。当前调用契约仍要求在每个产物项内明确其归属。

工具成功时把上述 JSON 负载包装在 `success: true` 和 `contentItems` 的文本项中。无工作区、参数错误、图不存在、Skill 不可用或没有可恢复的中断图时返回工具错误。当前轮没有图时，`inspect` 在有效 Skill 根目录查找 `pcg/architecture.yaml`。只有可用的规范架构会在该分支建立图。缺少架构时，错误提示要求改用 `plan`，提供 `skillName` 与稳定的 `nodes`。`plan` 不能替换已有规范架构，父级关系无效、节点 ID 重复或边端点未知也会使其失败。`node` 对未知节点或非运行中的图返回错误。`artifact` 在写入前校验所有产物的引用和节点归属。

`plan`、`resume`、`node` 和 `artifact` 可以更新工作流记录。`inspect` 从已安装架构初始化时也会写图。当前轮没有图且 `inspect` 成功匹配有效 Skill 时，Runtime 在尝试加载架构前先记录 Skill 调用，因此架构缺失的错误返回也可能伴随用量状态更新。产物按类型和目标引用识别，重复上报可更新归属。归属到一个待处理节点时，该节点可转为 `running`。业务动作由各自的执行工具完成。

`node` 在状态改变时先更新缓存与修订号，尝试保存整线程的图，然后向桌面发送 `workflow/graphUpdated`。处理器在此之后执行调用记录和 `completed` 的 Skill 用量核验，最后回传 `graphId` 和 `revision`。核验针对符合条件的已完成叶节点和有效 Skill，其用量记录独立持久化。该分支以当前图处于 `running` 且包含所报节点为状态更新条件，未检查前置节点、输出内容或质量。整图终态在轮次结束时另行计算。

图写盘失败时 Runtime 记录告警，缓存更新、通知与成功回包仍可继续。相同节点状态重复上报返回原修订，无新增图保存或通知。重复 `completed` 仍可进入用量核验，后续图确实变化时才会再次保存整线程缓存。

回执丢失但当前图仍可读取时，先用 `inspect` 核对实际节点状态和修订，再补报尚缺的变化。若需要检查持久化，以图文件及 Runtime 保存告警对账。保存失败时，`inspect` 的内存快照及桌面收到的修订可能与磁盘记录不同。中断任务使用 `resume` 取得的既有进度和产物续接，实际跨进程恢复见待实测项。 [续接与存储实现](#实现伪代码)

`artifact` 按引用维护图内产物索引。本地图片可用 `kind: "image"` 和 `path`，工作区中已落盘的工程、JSON 报告或 HTML 可分别以 `kind: "file"` 和各自的相对 `path` 上报。工程与报告的引用分别解析，内容和配对关系由调用方核对。对 `kind: "model"`，Runtime 在当前工作区的版本目录中对 `fileName` 做精确匹配，从命中的版本取得 `assetId`、`fileName` 和 `path`。查不到该版本会返回 `Model version is not registered in this workspace`。家族名和候选导出路径无法代替版本文件名。Runtime 在增加图内产物前先解析全部输入项。图内同一引用由 `kind`、`assetId`、`fileName`、`path`、`url` 识别，重复上报可改变归属，`count` 仍为本次成功解析的输入项数。 [版本登记工具](workspace-commit-model.md)

NPZ 缓存和对应 JSON 也使用 `kind: "file"`，分别给出工作区相对路径；文件类别没有 NPZ 内容解码、数组有限性、摘要配对或动作质量门禁。图中保存的是引用，工具不会冻结文件字节。脚本后来覆盖同一路径时，重复上报仍可命中同一引用，不能据此证明图中保留了旧版文件内容。需要固定版本时由调用方使用独立文件名并保存摘要。上报失败不回滚已经生成的文件；图状态为 `completed` 也不替代实际文件验收。

模型工具也可在登记时直接写入图内归属。`inspect` 返回的 `unassignedArtifacts` 只列出已进入当前图且缺少归属的记录。空列表表示图中没有待分配记录。图内归属、`node` 的状态回执以及轮次结束后计算的整图终态各有自己的写入时点。

### 已安装架构的加载范围

Runtime 从当前工作区可用的已安装 Skill 中解析 `pcg/architecture.yaml`，读取节点标识、标签、父级、角色、可选标记和 `entry`，建立待处理节点及关系。父子关系可投影为 `contains` 或 `spawn`，线形布局也可投影有效的 `rollback_to` 关系。该转换把这些字段保存为图数据。`function`、`outputs` 和 `irreversible` 这样的声明不参与此转换的动作派发。看到 `spawn` 边只表示架构关系，实际子 Agent 调用需有独立的调用记录。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)

随包的 `pcg-view` Python 帮助程序另可在生成决策视图时读取 `pcg/routes.yaml`。`routes.yaml` 属于该视图的输入，`workflow_report` 的 `inspect` 加载的是架构。工具更新的节点状态也不触发几何脚本执行或质量验收。 [PCG 视图参考](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-pcg-view/REFERENCE.md>) · [决策视图实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-pcg-view/scripts/view_ir.py:28>)

## 调用示例

**根据工具 schema 构造的示例。** `example-skill` 是占位名，调用时填写当前工作区中实际可用的 Skill 名称。

```json
{
  "operation": "inspect",
  "skillName": "example-skill"
}
```

**根据缺少已安装架构时的回退契约构造的示例。** 当前轮已选用该 Skill，`inspect` 返回缺少架构的提示，调用方为初始计划提供稳定节点。

```json
{
  "operation": "plan",
  "skillName": "example-skill",
  "nodes": [{"id": "prepare_report", "label": "准备报告"}]
}
```

下面的请求假定当前图已有 `prepare_report`，且所引用的报告文件已存在。

```json
{
  "operation": "artifact",
  "artifacts": [
    {
      "nodeId": "prepare_report",
      "kind": "file",
      "label": "处理报告",
      "path": "exports/hi3d-report.md"
    }
  ]
}
```

**根据文件产物 schema 重建的示例。** 假定当前图已有 `process_files`，下列两个独立文件已写入工作区。返回成功只表示引用解析及归属更新成功，缓存和报告的内容配对由调用方另验。

```json
{
  "operation": "artifact",
  "artifacts": [
    {"nodeId": "process_files", "kind": "file", "path": "exports/example-cache.npz"},
    {"nodeId": "process_files", "kind": "file", "path": "exports/example-cache-report.json"}
  ]
}
```

**根据图片产物 schema 重建的示例。** 假定当前图已有 `prepare_preview`，且预览文件已存在。

```json
{
  "operation": "artifact",
  "artifacts": [
    {
      "nodeId": "prepare_preview",
      "kind": "image",
      "path": "exports/sample-preview.png",
      "label": "预览图片"
    }
  ]
}
```

**根据模型产物 schema 重建的示例。** 假定当前图已有 `review_asset`，工作区版本目录中有 `hi3d-example_2.glb`。请求使用已登记的确切文件名。

```json
{
  "operation": "artifact",
  "artifacts": [
    {
      "nodeId": "review_asset",
      "kind": "model",
      "fileName": "hi3d-example_2.glb",
      "label": "示例模型"
    }
  ]
}
```

**根据工具 schema 构造的通用工程与报告示例。** 假定当前图已包含 `prepare_report`，两份常规文件均已落盘。工程与 JSON 分别解析为 file 引用；工具不读取 Action／NLA、不验证报告内容或配对关系，也不冻结字节。文件可引用与模型版本已登记是不同状态。

```json
{
  "operation": "artifact",
  "artifacts": [
    {
      "nodeId": "prepare_report",
      "kind": "file",
      "path": "exports/sample-scene.blend",
      "label": "示例工程"
    },
    {
      "nodeId": "prepare_report",
      "kind": "file",
      "path": "exports/sample-scene-report.json",
      "label": "示例报告"
    }
  ]
}
```

## 实现伪代码

**根据 Runtime 控制流重建的伪代码。** 分派前校验参数并关联当前工作区与轮次。图的查询和更新以当前调用上下文为准，`graphId` 与 `revision` 由 Runtime 返回。续接时定位同一对话最后一份已绑定其他轮次的图，核对中断状态和 Skill，再把进度与产物关联到当前轮。已为本轮续接的图可复用。`continuedFromGraphId` 保存来源关系，调用 `resume` 时无需传旧图或旧轮次 ID。`plan` 可在宿主根据短继续指令标记的轮次中自动尝试续接，压缩续跑只是该标记的一种来源。

```python
def workflow_report(call):
    args = validate_schema(normalize_legacy_artifact_node_id(call.arguments))
    workspace = require_workspace(call.thread_id)
    graph = graph_for_turn(call.thread_id, call.turn_id)

    if args.operation == "resume":
        graph = resume_interrupted_graph(call, args.skillName, workspace)
        return summarize_resumed_graph(require_graph(graph))

    if args.operation == "inspect":
        if graph is None and args.skillName:
            skill = require_enabled_skill(workspace, args.skillName)
            record_skill_invocation(call, skill)
            architecture = load_workflow_template_for_skill(call, skill)
            if not has_installed_canonical_architecture(architecture):
                return tool_error("No installed architecture for this skill; call operation=plan with skillName and nodes")
            graph = begin_and_bind_to_turn(call, architecture)
        return summarize_nodes_and_unassigned_artifacts(require_graph(graph))

    if args.operation == "plan":
        graph = save_plan(call, args, allow_auto_resume=is_marked_continuation(call))
        return graph_id_and_revision(require_graph(graph))

    require_graph(graph)
    if args.operation == "node":
        require_running_graph(graph)
        # 状态变化时先更新缓存、尝试保存并发出图更新通知
        graph = report_known_node(graph, args.nodeId, args.status)
        if args.status in ("running", "completed", "failed", "interrupted"):
            record_skill_invocation_if_eligible(call, graph)
        if args.status == "completed":
            verify_skill_usage_if_eligible(graph, args.nodeId)
        return graph_id_and_revision(graph)

    artifacts = [resolve_artifact(workspace, graph, item) for item in args.artifacts]
    for artifact in artifacts:
        graph = attach_to_node(graph, artifact)
    return {**graph_id_and_revision(graph), "count": len(artifacts)}


def resolve_artifact(workspace, graph, item):
    require_known_node(graph, item.nodeId)
    if item.kind == "model":
        return require_registered_model(workspace, item.fileName, item.nodeId)
    if item.kind == "link":
        return validate_credential_free_https_link(item.url, item.nodeId)
    artifact = require_regular_file_in_workspace(workspace, item.path, item.nodeId)
    if item.kind == "image":
        validate_image_extension(artifact)
    return artifact
```

如果从旧图恢复，已完成节点及既有产物继续保留。首个 `interrupted` 节点重新进入 `running`，其余中断节点置为 `pending`。无中断节点时，Runtime 尝试启动首个待处理节点。保存工作流图失败时，当前实现记录告警，工具成功返回的修订号本身无法证明本地文件写入成功。

## 核查依据

- 核查使用 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/` 下的原安装事务备份。`manifest.json` 标记版本 `1.2.11`，`dist/runtime.mjs` 的 SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。
- `BL=[` 位于 UTF-8 零基字节偏移 `2146219`，包含模型描述和 schema。`FL` 是 Runtime 参数校验。分派分支 `===Px` 位于偏移 `3176802`，兼容处理见 `Yge`。`T8`（`3048756`）查找可用 Skill 的架构，`Uge`（`3044474`）读取架构，`Mge`（`3045196`）投影节点和边。`inspect` 在 `3180767` 附近校验模板来源和节点并决定建图或提示提交计划。图状态与存储行为见 `nw.reportPlan`、`reportNode`（方法名从偏移 `3072320` 开始，参数正文从 `3072331` 开始）、`resume`、`addArtifact`、`mutate`（`3076125`）和 `save`（`3076703`）。完成用量核验见 `Xv.verify`（`3038892`）。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)
- **会话声明与实际调用。** 原始描述与安装包定义及两份本机 rollout 第 2 行 `exec.description` 的嵌套声明逐字一致。活跃样本第 19、24 行记录 `inspect` 因缺少架构返回工具错误，第 28、31 行记录 `plan` 成功返回 `graphId`。第 154–160、171–175 行记录 `node` 更新同一图的修订号，随后 `inspect` 读取已完成的节点和空的 `unassignedArtifacts`。这些调用确证图状态操作。 [模型可见声明](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:2>) · [状态更新实录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:154>) · [复查图实录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:171>) `resume`、压缩后自动续接和持久化错误分支依据安装包静态核查。
- 模型产物查找、参数解析及逐项写入在 Runtime 偏移 `3183890` 至 `3187500` 的分派片段内。图内引用键及更新逻辑见 `addArtifact`，其参数锚点为 `3072936`。留存样本中，`node` 及随后 `inspect` 均返回修订 8，线程图文件随后记录修订 9 的整图终态。图内模型归属由登记工具写入。`artifact` 示例的独立调用依据静态 schema 和分派实现。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [节点状态回执](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:173>) · [留存图文件](<D:/download/.sparc3d-runtime/environments/prod/workflow-graphs/39c03c1881feb41ce45e56a40380876211e366e02a24e8cfca31dd7a3e5f69c5.json>)
- 用替身工作流图隔离运行随包的 `addArtifact`。同一模型引用改派给另一节点时，图中仍有一条产物记录，归属随之更新，待处理节点进入 `running`。该实验覆盖图内更新，完整工具分派及桌面刷新仍以各自证据为准。
- **待实测。** 已安装架构加载后的桌面完整更新、实际跨轮和重启后的恢复，以及图缓存更新、磁盘修订和桌面显示在保存失败时的对应关系。留存会话只证明样本轮次的工具声明及对应操作。
