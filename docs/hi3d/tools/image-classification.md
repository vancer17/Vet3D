# `image_classification`

## 工具名称与注册来源

注册名为 `image_classification`。本页核查版本为 Windows x64 版 Hi3D Agent 1.2.11。Hi3D Runtime 将定义加入动态工具集合，并通过 `thread/start` 的 `dynamicTools` 交给随包 Codex。模型根据已获得的信息判断类别，工具负责保存给定的标签。

## 暴露给 LLM 的描述

以下是 Runtime 工具定义中的 `description` 原文。字符串转义已解码，五行措辞和换行保留。

```text
为当前模型任务的主体保存分类标签，供模型登记使用；不用于对所有聊天图片进行分类。报错截图、界面截图、普通图片问答以及不涉及模型生成或登记的图片编辑任务，无需调用。若用户明确把截图中的对象作为建模目标，则按该模型主体分类。
图生 3D 根据用于建模的参考图分类；文生 3D 在生成并查看参考图后分类。无参考图的建模任务，根据模型描述或预览在登记前分类。多张参考图描述同一主体时只分类一次，同一模型家族且主体不变的修改可继承已有分类。
也可在 workspace_commit_model 中直接提供已判断的 tag4；若登记返回 classificationRequired，补充分类后使用相同 name 和 exportPath 重试登记，不要重新生成图片或模型。
tag4 仅允许 humanoid、humanoid-base、statue、figurine、relief、sword、gun、general-prop 或 null；没有适用类别时使用 null，不得编造类别。
参数只能是 {"tag4":"类别"} 或 {"tag4":null}，不附加其他字段。通过工具保存标签，不在面向用户的回复中输出内部分类 JSON。
```

## 参数与结果

| 参数 | 必填与默认值 | 校验 |
| --- | --- | --- |
| `tag4` | 必填，无默认值。 | 接受 `humanoid`、`humanoid-base`、`statue`、`figurine`、`relief`、`sword`、`gun`、`general-prop` 或 JSON `null`。显式 `null` 会保存为一条有效记录，表示没有适用类别。 |

参数使用严格对象，拒绝额外字段。`threadId` 和 `turnId` 来自宿主的工具调用信封，工作区由 Runtime 按 `threadId` 查找。图片内容、文件路径和工作区 ID 均无需由模型传入。

| 结果 | Runtime 响应与副作用 |
| --- | --- |
| 保存成功 | 响应 `success: true`，`contentItems` 含一个 `inputText` 项，`text` 是原标签对象的 JSON 字符串。保存给定的分类，覆盖同一轮的已有分类记录及命中的模型版本标签。写盘后发送 `runtime/imageClassification`，并对每个受影响的版本发送 `workspace/modelUpdated`。 |
| 参数无效 | 缺字段、枚举错误或存在额外字段时，响应 `success: false`，文本项为含 `error` 的 JSON 字符串。错误提示为 `Invalid parameters: tag4 must be selected from the supported classification list; use null for other types`。 |
| 工作区或保存异常 | 当前对话未绑定工作区、目录校验失败或注册表写入失败时，响应 `success: false`，`error` 以 `Failed to save model classification: ` 开头并附具体原因。持久化错误应以该次返回结果判断。 |

工具在本次调用内等待本地注册表写盘，响应无需后续查询。更新已有版本仅涉及分类元数据。`runtime/imageClassification` 的负载为 `{tag4}`。该分支的 `workspace/modelUpdated` 顶层字段为 `assetId`、`name`、`file` 和 `workspace`，版本本身的 `threadId`、`turnId` 位于 `file` 内。

### 补录范围与登记优先级

Runtime 遍历当前工作区内所有家族的已登记版本，匹配每个版本原有的 `threadId` 和 `turnId`。两项都匹配时，整份 `tags` 被本次 `{tag4}` 覆盖，适用于不同家族，也适用于原来带显式分类的版本。其他轮次或线程的版本保留原标签。工具参数未提供家族或单版本过滤字段。此路径更新版本元数据，不改写 GLB 字节。

模型登记解析分类时，优先使用登记请求的显式标签，其次使用当前工作区对应的轮次标签，最后使用同模型家族最新版本的标签，按规范化后的家族名精确匹配。`{"tag4": null}` 是有效标签对象，按同样的优先级处理。如果只需给本次新登记补类，可在 `workspace_commit_model` 重试中沿用相同的 `name`、`exportPath` 并传入显式 `tag4`。该参数用于新建版本的标签，复用分支仍返回已有版本的原标签。 [显式登记参数](workspace-commit-model.md#参数与结果) · [文件身份与复用](workspace-commit-model.md#文件身份与复用)

## 实现伪代码

下例概括安装包的 `handleRuntimeDynamicTool`、`recordImageClassification` 和结果包装函数 `ge`。参数校验先于工作区读取。更新类别与版本标签后，Runtime 等待 `flush`，成功时才发送事件并回复。

```python
async def handle_image_classification(call):
    parsed = parse_strict_tag4(call.arguments)
    if not parsed.success:
        return tool_error("Invalid parameters: tag4 must be selected from the supported classification list; use null for other types")

    try:
        workspace = registry.require_workspace_for_thread(call.thread_id)
        registry.assert_workspace_cwd(workspace)
        tags = parsed.value
        versions = registry.record_image_classification(call.thread_id, call.turn_id, tags)
        await registry.flush()
    except Exception as error:
        message = f"Failed to save model classification: {error}"
        log_warning(message)
        return tool_error(message)

    notify("runtime/imageClassification", tags)
    for version in versions:
        notify("workspace/modelUpdated", {
            "assetId": workspace.asset_id,
            "name": version.name,
            "file": version,
            "workspace": workspace,
        })
    return text_tool_result(success=True, value=tags)
```

`record_image_classification` 更新 `registry.json` 对应的内存记录并安排写入。`save` 同步抛错时会恢复本次改动的类别和版本元数据。随后 `flush` 报错时，处理器返回失败并保留注册表的待写入状态，代码中没有看到在此分支恢复内存旧值。`tool_error` 和 `text_tool_result` 都通过 `inputText` 包装 JSON 字符串。

## 调用示例

以下请求示例显式保存「无适用类别」。

```json
{
  "tag4": null
}
```

以下响应示例根据 Runtime 的结果包装重建。

```json
{
  "success": true,
  "contentItems": [{ "type": "inputText", "text": "{\"tag4\":null}" }]
}
```

## 核查依据

- **安装包静态核查。** Hi3D Agent Windows x64 留存包清单的 `runtimeVersion` 为 `1.2.11`。`resources/runtime/dist/runtime.mjs` 的 SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [安装版本清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>)
- 原始 `runtime.mjs` 的零基 UTF-8 字节位置中，`Yee=`（工具描述）为 `2150458`，`VL=[`（工具定义）为 `2150874`，`Vg=`（动态工具集合）为 `2671153`，`===Lx`（工具分派）为 `3187576`，该分支的 `workspace/modelUpdated` 为 `3188337`。分类保存和同轮版本元数据更新见 `recordImageClassification`（`2678199`），登记时的分类解析见 `resolveModelTags`（`2692884`），结果包装见 `ge`。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)
- **离线核查。** 工具描述逐字对照了安装包中的字符串，响应示例经隔离运行 `ge` 核对。参数、按线程和轮次覆盖版本标签的范围、持久化和通知顺序来自静态核查。
- **会话声明与实际调用。** 本机活跃记录第 2 行的 `exec.description` 包含嵌套工具声明，第 35–39 行出现显式 `{tag4: null}` 调用并成功回传 `{tag4: null}`。后续模型登记也显式传入该值。省略标签时的读取顺序和已登记版本的标签更新以静态实现为依据。 [模型可见声明](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:2>) · [分类工具调用及回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:35>) 多家族版本补录后的实际落盘和桌面通知仍待实测。
