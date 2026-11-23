# studio_capture_view

## 工具名称与注册来源

`studio_capture_view` 是 Hi3D Agent 1.2.11（Windows x64）的桌面动态工具。Electron renderer 的 `mS` 在 `thread/start` 提交 `S0e` 中的工具定义，Runtime 合并后交给随包 Codex 0.166.0。该工具依赖当前活动会话中的 `StudioHost`。`thread/start` 是线程 RPC，工具定义中的输入只包含截图尺寸上限。

## 暴露给 LLM 的描述

以下内容为安装包 renderer 的 `S0e` 中实际随 `thread/start` 注册的 `description` 原文。该字符串也与两份留存会话中 `exec.description` 内的 `studio_capture_view` 声明一致。

```text
截取当前 Studio 视口为 PNG 并登记为截图产物。
```

同一 ASAR 的 `node_modules/@sparc3d/contracts/schema/dynamic-tools.json` 另有英文静态声明，其中也写 PNG，并提到以 `artifactId` 作为图片输入。实际调用以 `S0e` 注册定义和 `StudioHost.capture` 的实现为准。1.2.11 调用 `canvas.toBlob(…, "image/jpeg", 0.85)`，登记 MIME 为 `image/jpeg`，文件扩展名为 `.jpg`。

## 参数与结果

参数为对象，无必填属性。模型可见 schema 声明 `additionalProperties: false`。线程、轮次和工作区来自宿主调用上下文。

| 字段 | 类型与默认行为 |
| --- | --- |
| `width` | 可选整数。模型可见范围为 64–4096。指定时用作目标编码宽度上限，省略时不增加宽度限制。 |
| `height` | 可选整数。模型可见范围为 64–4096。指定时用作目标编码高度上限，省略时不增加高度限制。 |

renderer 的 `VN` 解析器校验可选整数，64–4096 是工具 schema 的约束。目标尺寸计算将正整数用作各轴上限，保持原画布宽高比，不放大，且最长边最多 1024 像素。两项均省略时使用原画布尺寸和最长边上限。目标尺寸四舍五入至整数，每边至少 1 像素。

成功时返回 `{success: true, contentItems: [{type: "inputText", text: ...}]}`。`text` 中的 JSON 对象仅含 `artifactId`、`width`、`height`。返回的宽高是目标编码尺寸。缩放画布无法取得 2D 上下文时，编码回退到原画布，实际文件可能超过目标上限。需要确切尺寸时，读取已登记文件核对。

工具读取 Studio 内的第一个 canvas，沿用当前模型及相机。写入位置为工作区 `exports/`，保存名基于 `hi3d-view-<时间戳>.jpg`。主进程清理文件名、追加唯一后缀并以 `wx` 模式新建文件，然后调用 `artifact/register` 登记 `screenshot` 角色。主进程的 IPC 应答 `{artifact: ...}` 和 Runtime 的 `artifact/registered` 通知中的产物对象含相对路径 `artifact.path`。模型可见应答只提供截图 ID 和计划尺寸，缺少文件路径、MIME、图像字节、相机状态和模型文件名。已核查的工具注册中未发现通用 `artifact/get` 或 `artifact/list` 定义。调用方如果另有可信的工作区截图路径，可以将该路径交给本地图像读取工具。 [view_image](view-image.md)

参数解析失败时返回 `Invalid parameters`。Studio 未挂载、没有已加载模型身份、模型属于其他工作区、缺少 canvas、编码无结果或调用上下文变化时，返回对应工具错误。写入或登记异常由桌面工具桥转为 `STUDIO_NOT_READY` 错误。

### 版本与观察方向核对

1. 截图前用 `studio_get_state({})` 确认 `ready: true`，并将实际已加载的 `assetId` 和 `fileName` 与目标版本核对。需要切换时，用 `studio_load_revision` 指定确切文件名，再确认实际加载状态。 [读取视窗状态](studio-get-state.md#使用视窗快照) · [加载版本](studio-load-revision.md#版本身份与就绪确认)
2. 截图读取当时画面。按用途记录已确认的观察方向或镜头，只有自由视角依据时记录为自由视角。取得回包后再检查版本和就绪状态，保留两次状态、观察方向依据及 `artifactId`。两次状态一致只表明两个采样点匹配。安装包检查会话及工作区范围，捕获期间同一工作区内的模型文件、加载代次和镜头仍可能变化。
3. 将 `artifactId` 对应的可信文件引用、已核对版本和方向共同用于取证。有切换或归属不明时，截图先保留为待核对证据，重新取证时可在已确认的视窗状态重拍。需要指定方向、可重复的对照或无法追溯截图归属时，可用确切版本文件和固定相机渲染。查看已有证据图时读取对应文件。 [读取实际图像](view-image.md)

## 执行与治理

1. Codex 用 `item/tool/call` 发起请求。Runtime 的 `forwardServerRequest` 先经 `skillCredits.confirm(threadId, turnId, [])`，可以等待或阻断该轮已有的额度确认。该工具未追加待确认的付费 Skill，桌面截图链也未经过 shell 授权。`forwardConfirmedServerRequest` 为桌面 `serverRequest` 分配 `requestId`，与原 app-server RPC 请求关联。
2. renderer 的 `vi` 检查活动线程、轮次和工作区，并在会话、轮次或账号切换等条件下中止调用。`M0e` 要求 Studio 句柄已挂载、已有加载身份且归属当前工作区。此分支核对 `assetId`，没有额外等待 `ready` 或锁定相机及模型文件。`StudioHost.capture` 在异步编码前后核对活动工作区和 `sessionRevision`，`Ce` 在转换图像字节期间还核对 `activeThreadId`。
3. `Ce` 通过 preload 调用 `file:writeArtifact`。IPC 请求字段为 `assetId`、`fileName`、`bytes`、`role`、`mimeType`、`threadId`，其中 `role` 为 `screenshot`，`mimeType` 为 `image/jpeg`。主进程校验可信 renderer 和 IPC 参数，要求 `bytes` 是至多 1 GiB 的 `ArrayBuffer`，并按 `assetId` 解析工作区后写入和登记。此载荷未传 `turnId`。Runtime 的 `artifact/registered` 工作流自动关联分支要求同时存在 `threadId` 和 `turnId`，因此这条截图路径只登记产物。
4. renderer 在取得结果后重新校验调用和视窗归属，经 preload 和 `runtime:respond` IPC 回交主进程。主进程以 `serverResponse` 写回 Runtime，`handleServerResponse` 用 `requestId` 找回原请求，最终完成对应的工具调用。

这条链等待本次编码和登记后返回，工具没有作业查询或续跑参数。切换期间的晚到结果可能被拒绝。若文件已写入而登记失败，文件可能保留。若登记完成后调用失效，已登记的截图也可能保留。重查时可在有效会话中重新调用；每次成功写入都生成新文件，取的是重调时的画面。

## 实现伪代码

**根据安装包分支重建的伪代码。** `scope` 记录桌面活动线程、轮次、工作区和挂载的 Studio 句柄。读取画面与保存文件分别核对会话代次，桌面另在返回前核对工具调用的作用域。会话代次是宿主状态。

```python
async def studio_capture_view(call, desktop):
    scope = desktop.require_current_thread_turn_and_workspace(call)
    studio = desktop.require_mounted_studio()
    scope.require_loaded_asset(studio)

    width, height = parse_optional_integers(call.arguments)
    capture_scope = studio.capture_session_scope()
    canvas = studio.first_canvas()
    if canvas is None:
        return tool_error("Capture failed or Studio is not ready")

    size = fit_within(canvas.size, width, height, longest_edge=1024, upscale=False)
    blob = await encode_canvas_jpeg(canvas, size, quality=0.85)
    capture_scope.require_same_asset_and_session_revision()
    if blob is None:
        return tool_error("Capture failed or Studio is not ready")

    save_scope = studio.capture_session_scope(include_thread=True)
    data = await blob.array_buffer()
    save_scope.require_same_asset_session_revision_and_thread()
    reply = await desktop.file_write_artifact({
        "assetId": scope.asset_id,
        "fileName": timestamped_name("hi3d-view", ".jpg"),
        "bytes": data,
        "role": "screenshot",
        "mimeType": "image/jpeg",
        "threadId": scope.thread_id,
    })
    scope.require_active_call()
    scope.require_current_studio_scope(studio)
    return text_tool_result({
        "artifactId": reply["artifact"]["artifactId"],
        "width": size.width,
        "height": size.height,
    })
```

## 调用示例

**根据已核查的 schema 重建的工具参数。** 将当前视口截图限制在 800 × 600 像素的范围内，按原比例缩放。

```json
{
  "width": 800,
  "height": 600
}
```

**根据安装包行为重建的成功应答。** 原画布为 2560 × 1440 且能取得缩放画布的 2D 上下文时，计划编码尺寸为 800 × 450。`artifactId` 使用示例值。

```json
{
  "success": true,
  "contentItems": [
    {
      "type": "inputText",
      "text": "{\"artifactId\":\"artifact-example\",\"width\":800,\"height\":450}"
    }
  ]
}
```

## 核查依据

- **安装包静态实现。** 1.2.11 的 `D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。`out/renderer/assets/index-CDPCug_K.js:146–148` 的 `S0e`、`mS`、`M0e` 和 `vi` 覆盖注册、作用域校验和分派，参数解析器 `VN` 的定义位于 `:58`。成员内 UTF-8 零基字节偏移可从 `1090971` 定位 `S0e`，从 `1095958` 定位截图分派，从 `4717572`、`4724056`、`4712488` 分别定位 `capture`、`ht` 与紧随其后的 `Ue`、以及 `Ce`。
- **安装包静态实现。** `out/preload/index.js:1` 的 `writeArtifact` 对应 `out/main/index.js:29` 的 `O.handle(R.fileWriteArtifact, …)`，后者的成员内字节偏移为 `178352`。安装目录中的 `resources/runtime/dist/runtime.mjs:2` 包含 `forwardServerRequest`、`forwardConfirmedServerRequest`、`handleServerResponse`、`artifact/register` 和 `artifact/registered` 分支，可复核调用治理、应答映射和产物登记。该 Runtime 文件的 SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。
- **模型可见声明。** ASAR renderer 成员内零基 UTF-8 字节偏移 `1092418` 是该工具的定义。本机 rollout 第 2 行 `additional_tools` 事件中的 `exec.description` 包含同一描述。该样本的工具调用轨迹未覆盖截图。 [声明记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:2>)
- **离线复现。** 在隔离 JavaScript 环境中用替身 canvas 运行原始 `ht` 和 `Ue`。2560 × 1440 的画布按默认上限得到 1024 × 576，指定上限 800 × 600 得到 800 × 450，小画布保持原尺寸。编码调用使用 `image/jpeg` 和质量 `0.85`。缩放画布无法取得 2D 上下文时，复用原画布编码，计划尺寸仍沿用缩放结果。替身验证的是编码调用参数与分支。
- **桌面待实测。** 两份留存记录用于核对工具声明。实际桌面截图文件的像素尺寸和编码字节、捕获期间在同一工作区切换版本或镜头时写入的画面，以及写入后切换会话时登记事件、工具回执与落盘文件的关系，仍需用实际 `studio_capture_view` 调用核对。
