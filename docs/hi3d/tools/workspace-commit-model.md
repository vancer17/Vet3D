# `workspace_commit_model`

## 工具名称与注册来源

`workspace_commit_model` 是 Windows x64 版 Hi3D Agent 1.2.11 的 Runtime 动态工具。定义位于 `GL`，由 `Vg` 汇总，在 `thread/start` 通过 `dynamicTools` 交给随包 Codex 0.166.0。执行由 Runtime 的 `handleRuntimeDynamicTool` 分派给工作区注册表。

## 暴露给 LLM 的描述

以下代码块逐字保留安装包中 `description` 的解码值。

```text
Register a GLB just exported to exports/ as a version in a model family. An export identical to the latest version is returned as unchanged instead of creating a duplicate version. For a new model, include its classified tag4 in this call after inspecting its subject; edits can inherit the same model family classification. If a workflow graph already exists, include workflowNodeId to assign the registered model to its owner. Registration does not complete the node; report completion through workflow_report only after all work for that node is finished. image_classification remains available for earlier classification. If classificationRequired is returned, classify and retry this export without regenerating it. The exportPath file name must start with hi3d-, and Runtime also adds the hi3d- prefix to the committed version. Without this tool, the exported file remains only in exports/ and does not become a model version.
```

## 参数与结果

| 参数 | 必填性与默认值 | 校验或条件 |
| --- | --- | --- |
| `name` | 必填字符串，无默认值。 | 模型家族名。去除首尾空白后长度为 1 至 120。拒绝 `.`、`..`、末尾句点、控制字符和 Windows 文件名保留字符。Runtime 去除已有的 Hi3D 前缀后再次校验。 |
| `exportPath` | 必填非空字符串，无默认值。 | 参数说明采用工作区相对路径。Runtime 将路径解析到当前工作区的 `exports/` 内，实际文件也须位于该目录解析后的真实路径内。文件名须以 `hi3d-` 开头，路径须指向普通文件。Runtime 拒绝符号链接文件。新版本的导入要求 `.glb` 扩展名。 |
| `tag4` | 可选，无固定默认值。 | 接受 `humanoid`、`humanoid-base`、`statue`、`figurine`、`relief`、`sword`、`gun`、`general-prop` 或 JSON `null`。显式 `null` 是有效分类，会结束标签回退。省略时依次查当前线程和轮次的分类、同名家族最新版本的分类。家族分类按规范化后的名称精确匹配。 [image_classification](image-classification.md) |
| `workflowNodeId` | 可选字符串，用于显式指定工作流产物归属。 | 去除首尾空白后长度为 1 至 120。提供时须命中当前线程和轮次的工作流图中的节点 ID。 |

模型可见 schema 声明 `additionalProperties: false`。工作区、线程和轮次由宿主提供。成功时工具响应的 `success` 为 `true`，`contentItems` 中的 `inputText.text` 为 JSON 字符串，负载为 `{file}` 或 `{file, unchanged: true}`。`file` 包含 `name`、`index`、`fileName`、`path`、`size`、`updatedAt`。`path` 是工作区相对路径，`size` 为字节数，`updatedAt` 为文件修改时间的毫秒值。注册表的版本记录还可携带 `threadId`、`turnId`、`note`、`tags`、`source`。`tags` 包含 `tag4`，可信 `source` 包含 `provider`、`taskId`、`retryRootId`、`jobPath`、`kind`、`environment`、`ownerId`。

新版本写入工作区根目录的 `hi3d-<家族名>_<序号>.glb`，并保存版本元数据。已提供 `workflowNodeId` 时，Runtime 在取得版本后将对应 `fileName` 挂到当前图，再进入新版本的注册表刷新。刷新完成后发送 `workspace/modelUpdated`。复用分支同样可挂接归属，随后直接回包 `unchanged: true`。产物归属不会改变节点的完成状态。源文件保留在 `exports/`。 [图产物和节点状态](workflow-report.md#参数与结果) 显式 `tag4` 用于写入新版本标签，复用保留该版原有标签。原导出文件保留在 `exports/`。

登记成功确认 GLB 版本身份。新版本的文件校验覆盖 GLB 容器，原生多边形连接、资产属性和几何合格性由调用方检查。OBJ、`.blend` 和测量报告可作为独立工作区文件保存。已存在工作流时，可用 `workflow_report` 记录这些文件的归属。 [产物报告](workflow-report.md#参数与结果)

### 文件身份与复用

一次调用指定一个 `exportPath`。Runtime 以相对工作区的导出路径查找下载来源记录，再用该文件的 SHA-256 核对记录。路径和摘要匹配后，本次导出才具备可信任务来源。来源不匹配时仍可按本地导出处理。返回的 `file.source` 描述登记版本的作业来源。文件用途可从原下载清单核对到实际路径，几何和外观检查由调用方负责。 [生成工具的下载与登记结果](hi3d-api.md#已下载-3d-产物与登记)

生成下载登记器 `recordHi3dDownloads` 以原账本的 `backend: "hi3d-codex-v1"` 和 `state: "success"` 为入口条件，从账本的 `task_id` 建立 `source.taskId`。MDF 以 `status` 记录作业结果，从 `response.requestId` 取得用于服务侧核对的请求号。其导出文件可以走本地导出登记，MDF 回执本身无法建立生成来源或免费重试资格。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [MDF 作业记录实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:216>)

版本复用按忽略大小写的家族名匹配，分两种情况。带可信来源时，优先查找同任务 ID、同账号、同环境的已登记版本。此分支核对的是输入文件和它自己的下载记录，可以返回同任务下另一份字节不同的文件。其余情况比较家族最大序号版本的文件大小和 SHA-256，本次导出带可信来源时，还要求该版本的任务 ID 一致。需要确认返回版本对应确切导出内容时，可从返回路径读取文件并计算摘要。

**登记回包与验收文件的对账。** 调用方在验收时记录候选的工作区路径和 SHA-256，随后从返回的 `file.path` 读取实际登记文件并计算 SHA-256。新建和复用回包均可用此方法，组合生成返回 `registeredModel.path` 时也一样。摘要一致时，可把候选验收记录关联到确切的登记版本。摘要不一致或文件暂不可读时，保留原候选和登记回包，暂停交付并核查实际路径。若返回的是另一份文件，须按其实际内容重新验收，再决定是否交付。来源任务、`unchanged` 和文件名用于定位，字节身份以摘要对账为据。 [生成工具的登记结果](hi3d-api.md#已下载-3d-产物与登记)

新版本刷新后和已有版本复用时，Runtime 都会核对该工作区尚未终结的免费重试意图。登记版本的家族、来源和线程与意图匹配时，Runtime 将意图标为 `completed`，保存 `registeredFileName`。登记工具仍返回上述 `{file}` 或 `{file, unchanged: true}`。 [免费重试的结果复用](hi3d-api.md#免费重试与结果复用)

### 失败与重入

参数无效、当前线程没有工作区、归属 ID 不存在、路径或文件校验失败、注册表写入失败时，响应 `success: false`，负载含 `error`。缺分类时同时返回 `classificationRequired: true`，发生在导出文件检查之前。只需为本次新登记补录分类时，沿用原 `name` 和 `exportPath`，直接提供有效的显式 `tag4`。需要保存当前轮的通用分类时，可先调用 `image_classification` 再登记。该调用会同时覆盖当前工作区内同一线程、同一轮已登记版本的标签。 [分类写入范围](image-classification.md#补录范围与登记优先级)

新版本文件发布及可选的工作流归属发生在注册表刷新之前。写盘报错或回执丢失时，保留原导出和调用参数，先核对版本文件、登记元数据及其摘要。重交同一导出可命中复用分支。该分支直接返回 `unchanged: true`，因此回执仍须与已持久化的版本记录核对。这个调用执行本地登记，异步生成结果的续查由原作业入口负责。 [生成作业恢复](hi3d-api.md#作业持久化与恢复)

## 实现伪代码

**根据随包 Runtime 重建的实现伪代码。** 注册表在创建新版本时先复制到临时文件，检查 GLB 魔数、版本和声明长度，适用时再核对来源摘要，然后发布编号文件并准备元数据。工具分派器用调用前的版本文件名快照区分新登记与复用。

```python
# 实现伪代码，概括 Runtime 分派器和工作区注册表。
async def workspace_commit_model(args, call):
    try:
        params = parse_commit_arguments(args)
        workspace = registry.require_workspace_for_thread(call.thread_id)
        workflow_node = validate_optional_workflow_owner(params, call)
        tags = registry.resolve_model_tags(workspace, params, call)
        if tags is MISSING:
            return tool_error("Model classification is missing", classificationRequired=True)

        known_file_names = set(registry.list_version_file_names(workspace))
        export = require_safe_export_file(workspace, params.export_path)
        source = registry.find_download_source_by_path_and_hash(workspace, export)
        family = registry.find_family_for_commit(workspace, params.name)
        version = family.find_same_source_task(source) if source else None
        if version is None:
            version = family.find_identical_latest(export, source)
        if version is None:
            version = registry.import_glb(workspace, family, export, tags, source, call)

        if workflow_node is not None:
            record_artifact_owner(workflow_node, version)
        if version.file_name in known_file_names:
            reconcile_registered_retries(workspace)
            return tool_result({"file": version, "unchanged": True})

        await registry.flush()
        reconcile_registered_retries(workspace)
        record_skill_capture_artifact(call)
        notify_model_updated(workspace, version, call)
        return tool_result({"file": version})
    except Exception as error:
        return tool_error(str(error))
```

## 调用示例

**根据已核查的 schema 重建的工具参数。** 假定工作区已有 `exports/hi3d-example.glb`，显式使用 `null` 表示没有适用的命名类别。

```json
{
  "name": "example",
  "exportPath": "exports/hi3d-example.glb",
  "tag4": null
}
```

**根据已核查返回结构重建的复用负载。** 示例为解码 `inputText.text` 后得到的内容。

```json
{
  "file": {
    "name": "example",
    "index": 2,
    "fileName": "hi3d-example_2.glb",
    "path": "hi3d-example_2.glb",
    "size": 48000,
    "updatedAt": 1794368621000,
    "tags": {"tag4": null}
  },
  "unchanged": true
}
```

## 核查依据

- **安装包静态核查。** 安装包 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json` 标明 `runtimeVersion` 为 `1.2.11`。`resources/runtime/dist/runtime.mjs` 的 SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。工具描述与安装包中的字符串逐字核对。
- **原文件锚点。** 零基字节 `2151223` 为 `GL` 注册和相邻的 `ZL` 参数校验，`2692884` 为分类解析，`2693701` 为下载来源记录及生成账本门槛，`2695691` 为 `commitExport` 的文件检查及复用，`3197710` 附近为显式分派、文件名快照、归属和注册表刷新，`3200505` 为刷新后触发的重试对账。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)
- **实际运行观测。** 2026-11-11 留存会话第 145–148 行记录用显式 `tag4: null` 登记已下载的 GLB，回包含版本路径、分类和来源元数据。第 154–160 行核对登记文件存在及文件大小。另行复验留存文件时，该次导出与正式版本的 SHA-256 都为 `b217a0365f827657cabcda90aa427d5830e153cd4a7cf3271831ff1c568fb9f5`。同作业的另一份 GLB 摘要不同。第 941–944 行另记录同家族继承分类后的本地导出登记成功。 [下载文件登记](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:145>) · [本地导出登记](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:941>)
- **隔离分支复核。** 在 Node VM 中执行安装包的 `commitExport` 方法和字符串解码器，用替身提供路径、摘要、来源和已登记版本。同任务的不同字节返回原版本，不同任务的不同文件进入导入，来源摘要失效时作本地导出处理，与最新版本摘要和大小一致时返回已有版本。两个复用分支均直接返回已有版本，显式标签随新建导入分支写入。
- **待验证。** 登记故障后的文件与注册表状态、目录通知到桌面刷新的时序及自动展示分支仍需实际观测。
