# studio_load_revision

## 工具名称与注册来源

`studio_load_revision` 是 Hi3D Agent 1.2.11（Windows x64）的桌面动态工具。Electron renderer 的 `mS` 在 `thread/start` 提交 `S0e` 中的工具定义，Runtime 合并后交给随包 Codex 0.166.0。实际加载由 renderer 的 `M0e` 操作当前 `StudioHost`。

工具按线程注册，执行时要求该线程、轮次和工作区仍与活动视图匹配。本机运行记录通过 Code Mode 的 `tools.studio_load_revision` 调用，模型可见声明位于 `exec.description` 内。 [exec](exec.md)

## 暴露给 LLM 的描述

以下内容为安装包中的 `description` 原文。

```text
在右侧 Studio 加载会话中的 GLB。fileName 精确选择版本，modelName 选择最新版；都不传则加载最近更新的模型。
```

## 参数与结果

| 参数 | 必填性 | 选择规则 |
| --- | --- | --- |
| `assetId` | 必填字符串。 | 工作区 ID，须与当前线程绑定的工作区匹配。 |
| `fileName` | 可选字符串。桌面校验要求非空。 | 精确匹配列表中的版本文件名或相对路径。与 `modelName` 同时提供时，校验通过后优先用 `fileName` 选版本。 |
| `modelName` | 可选字符串。 | 省略 `fileName` 时，精确匹配模型家族，取该家族中数字序号最大的版本。桌面解析器去除首尾空白，限制为 1–120 个字符，拒绝文件名保留字符、控制字符、`.`、`..` 和末尾的点。 |

两个选择参数都省略时，renderer 将各家族的所有版本按 `updatedAt` 排序，选取最近修改的文件。所有选择均在当前工作区的模型版本目录内完成。传入相对路径时，它必须精确命中目录记录的 `path`，仅在磁盘存在的文件无法通过该工具打开。指定项匹配失败时返回错误。模型可见 schema 声明 `additionalProperties: false`。宿主解析器 `TN` 还接受非空 `revisionId`，选择器仅在 `fileName` 缺省时将其当作文件名或路径匹配。该兼容字段没有列入模型可见 schema。

成功响应为 `{success: true, contentItems: [{type: "inputText", text: ...}]}`。解析 `text` 得到 `{loaded: true, assetId, modelName, fileName, state}`。顶层身份来自这次加载的确认结果，`state` 来自随后读取的 Studio 快照。工作区不匹配等普通失败返回 `success: false`，文本负载含 `error`。桌面参数校验失败可附 `issues`。renderer 捕获的加载异常可通过 RPC 错误 `STUDIO_NOT_READY` 返回。 [studio_get_state](studio-get-state.md)

### 版本身份与就绪确认

加载先写 renderer 的界面选中项，随后按工作区版本记录读取 GLB。匹配的 `modelLoaded` 更新 Studio 已加载身份，完成本次加载等待。顶层身份保留这次加载的结果，`state` 记录随后采样的视窗状态。同一工作区内快速切换版本时，两处身份可以不同。

已知确切目标时，用版本记录的规范文件名作比较。以相对路径传入 `fileName` 时，成功回包仍使用该记录的 `fileName`。按家族名或默认规则请求时，顶层 `fileName` 提供本次解析出的确切版本。确认该版本在采样时就绪，需要同时满足以下条件。

| 层级 | 确认条件 |
| --- | --- |
| 工具与本次加载 | 应答成功，文本负载 `loaded: true`，顶层 `assetId`、`fileName` 匹配目标。 |
| 采样时的视窗 | `state.ready: true`，且 `state.assetId`、`state.fileName` 与同一目标一致。 |

宿主检查调用作用域、句柄和工作区。两处版本相符和当前就绪由调用方按上述字段确认。后续需要使用当时的视窗状态时，可以再按目标核对一次。文件路径从版本记录取得，画面由截图或定向渲染另行取证。 [studio_get_state](studio-get-state.md) · [studio_capture_view](studio-capture-view.md) · [view_image](view-image.md)

## 执行与治理

1. **Runtime 转发。** Codex 以 `item/tool/call` RPC 送出线程、轮次、工具调用 ID、工具名和参数。Runtime 的 `forwardServerRequest` 先执行 `skillCredits.confirm(threadId, turnId, [])`，本轮已有的额度确认可能阻断转发。该分支追加的付费 Skill 清单为空，执行路径在桌面宿主内。Runtime 将 app-server 请求与桌面 `serverRequest.requestId` 关联，经 Electron `runtime:event` 送给 renderer。
2. **桌面选版。** `Dt` 校验调用信封。`vi` 核对活动线程、轮次和工作区，保存会话修订号与取消信号。`M0e` 核对 `assetId`，最多等待 5 秒取得 Studio 句柄。校验参数并找到目标后，`StudioHost` 先更新界面选中项。已就绪的同一目标可以直接返回。准备中的加载按线程、轮次（界面操作用 `user`）、工作区及文件复用同一启动请求。
3. **授权、加载和确认。** 需要启动新的加载请求时，有限文件大小在 0 至 200 MiB 内自动放行，超出或大小无效时由桌面面板确认，限时 60 秒。已经绑定到同一线程、工作区和文件的加载目标可复用，因此是否需要面板还取决于调用前的视窗状态。Studio 将登记版本的相对路径转为 `sparc3d-asset://workspace/<assetId>/<path>`。Electron 主进程的 `resolveAssetPath` 校验词法路径与真实路径均位于工作区内，再由 renderer 的 `GLTFLoader` 解析 GLB。加载等待时限另计。已知正数大小每 32 MiB 向上取整为一档，每档 60 秒，最多 300 秒。大小未知或非正数时为 120 秒。有效的 `modelLoaded` 回调须匹配视窗组件、加载代次、线程、工作区及目标所绑定的轮次。工具等待者还匹配工作区、版本文件名和加载代次。一份视窗只维护一个活动加载等待者，新的等待者可使原等待者以被取代结束。
4. **应答关联。** `M0e` 再检查调用是否仍有效，成功回包还需通过句柄和工作区复核。renderer 经 preload 的 `runtime:respond` IPC 和主进程 `serverResponse` 回到 Runtime 的 `handleServerResponse`，按桌面 `requestId` 找回原 app-server 请求。映射已清理时，迟到的桌面应答无法完成原请求。

### 取消、失败和重查

用户拒绝、模型解析失败、超时或调用过期时，界面可能已经选中目标。若视窗也由用户打开，取消 Agent 等待者后用户的加载可能继续。加载超时时原等待者以失败完成。若随后到达的 `modelLoaded` 仍匹配当前视窗和加载代次，Studio 可以更新为就绪，原应答仍为失败。

该工具等待本次本机加载终态。外层 `exec` 返回运行中的 `cell_id` 时，由 Code Mode 的 `wait` 续取同一执行单元。原加载失败、回执不明或两处版本分歧时，在有效会话中用 `studio_get_state({})` 重取视窗状态。确切目标已就绪时使用该状态，仍需要加载时按同一确切文件名发起新调用。 [studio_get_state](studio-get-state.md) · [wait](wait.md)

## 视窗导出与已有文件复制

本节记录同一桌面宿主的内部实现，供区分文件身份。以下函数、IPC 和事件都不是 `studio_load_revision` 的动作或参数，也不是新增 LLM Tool；在固定的五项 Studio 工具定义中没有 `studio_export_glb`。LLM 加载已登记版本、编辑器重新序列化、用户保存已有文件分别有独立结果。

### Studio 内部 GLB 序列化

编辑器的 `createExportMesh` 根据当前编辑状态选择对象；`createExportObject` 的多网格分支复制几何并按分支复用或克隆材质，再创建普通 Mesh，没有重建原 Skeleton 的通用逻辑。随后 `createPhysicalExportObject` 以 `mmPerUnit / 1000` 调用 `createUnitScaledExportObject` 创建缩放根，再写 `sparc3dPhysicalUnits={version:1,unit:"meter"}`。这些是编辑器的组包行为，不是原 GLB 的字节复制，也不保证 skin 保留。

**根据固定 renderer 重建的实际导出选项。** 这是内部 `GLTFExporter` 的参数，不是模型工具请求。此调用没有传入 `animations`；该发行内的导出器默认使用空数组，按该数组写动画。

```json
{
  "binary": true,
  "maxTextureSize": 8192,
  "includeCustomExtensions": false
}
```

内部导出先序列化生成 Blob，再创建 URL 并触发下载；触发点击不能证明已保存到磁盘。当前对象选择、几何、材质、尺度及导出器选项决定新文件，原文件名和视窗已加载状态均不证明新字节与原件一致。骨架、动作、形态键、贴图和实际尺寸须按新输出核对。通用组件还存在条件性的上传选项，未据此认定当前宿主已开启；普通已有文件复制不以云端生成或上传为前提。

### 已有工作区文件另存

`file:saveAs` 是 Electron IPC，参数 `assetId` 和 `path` 定位工作区源文件；目标由系统保存对话框选择。它不是 `studio_load_revision` 的可调用子动作。源文件可以是普通工程、压缩包或报告，不要求模型版本登记。

| IPC 参数 | 校验及默认值 |
| --- | --- |
| `assetId` | 必填，原始字符串非空、最多256字符，不去除首尾空白，无默认值。用于取得工作区目录，纯空白通过此参数检查不代表能解析有效工作区。 |
| `path` | 必填，原始字符串非空、最多4096字符，不去除首尾空白，无默认值。后续路径解析器兼容百分号编码、本地绝对路径及 `file:` URL，解析后必须在工作区内且为普通文件。 |

**根据已核实 IPC 重建的中性参数。** 示例使用源相对路径，不是外部保存目标；接受其他本地路径表示也不能绕过工作区边界。

```json
{
  "assetId": "asset_demo",
  "path": "exports/hi3d-sample.glb"
}
```

主进程要求可信 renderer，解析工作区词法路径和真实路径，确认普通文件。打开源句柄后再次检查文件身份；对话框取消返回 `{canceled:true}`。确定目标后，先打开并校验目标为普通文件，源／目标若为相同文件身份，直接返回成功；其他目标先截断再流式复制，完成返回 `{canceled:false,path}`，此时 `path` 为实际保存目标。两端句柄分别在 `finally` 关闭。它不返回 SHA-256 或持久任务 ID，也不生成质量报告。

**根据安装包分支重建的伪代码。** 省略平台对话框配置，保留源文件复验、取消、同文件及写入分支。

```python
async def save_workspace_file(args, sender):
    require_trusted_renderer(sender)
    source = resolve_regular_file_inside_workspace(args["assetId"], args["path"])
    with open_verified_source_handle(source) as handle:
        require_same_source_identity(source, handle)  # dev/ino 等身份检查
        target = await show_save_dialog(source.name)
        if target is None:
            return {"canceled": True}
        with open_regular_destination_without_truncating(target) as output:
            if not same_file_identity(handle, output):
                truncate(output, 0)
                await stream_copy_handles(handle, output)
        return {"canceled": False, "path": str(target)}
```

| 分支 | 输出与失败边界 |
| --- | --- |
| 解析或源句柄校验失败 | 抛错，不进入目标写入；路径和文件身份检查不等于内容摘要前后校验。 |
| 用户取消 | 返回取消，目标尚未打开；不表示原文件缺失，也没有待续查的复制任务。 |
| 目标复制失败 | 错误传播，可能留下空或部分目标；没有临时文件提交、事务回滚或自动删除目标。原调用无回执时先核对实际文件。 |
| 返回成功 | 确认同文件或复制完成，不解析容器、skin／clip或工程依赖。需严格对账时另查实际目标摘要。 |
| Blob 下载 | `will-download` 通过 `file:downloadEvent` 报告 `selecting/completed/cancelled/failed`。只有实际完成事件及目标路径才能证明本次磁盘下载完成，Blob URL 点击不是完成回执。 |

此类 IPC 没有公开给 LLM 的下载任务查询 Tool，不使用 `cell_id` 或 `jobPath` 恢复复制。代理提供文件链接、用户接受对话框及磁盘完成是不同状态；具体宿主事件或实际字节用于确认已保存。

### 内部实现的固定证据与核查范围

以下偏移均为固定 `app.asar` 内对应成员的零基 UTF-8 字节位置；归档 SHA 见本页[核查依据](#核查依据)。路径用于定位原文，前述组包和复制流程由这些分支逐段复核。 [安装包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

| 成员及偏移 | 实现 |
| --- | --- |
| `out/renderer/assets/index-CDPCug_K.js:2865989/2866809` | `createExportMesh/createExportObject` 与普通 Mesh 重建。 |
| 同 renderer `3206150/3207127/3209396` | 单位根缩放、物理 GLB 链与导出选项。 |
| 同 renderer `2942503/2961380/3284197` | 默认空动画、按列表写 clip及 Blob 点击。 |
| `out/main/index.js:100599/101148/180430` | 工作区文件解析、源句柄复验、保存对话框、同文件和复制。 |
| 同 main `100273/188722` | 本地路径解码兼容及 `assetId/path` 参数校验。 |
| 同 main `264515` | `will-download` 事件与终态回传。 |

只读抽取的 renderer SHA-256 为 `4ca3ecffe377be3014e38f807ed9f788fd9bb64ce86529687d896870757d6abc`。前序 REA 6.8.0 对该单成员的静态分析未执行 bootstrap，图为 partial；本节不根据缺失图边推定能力不存在。 [提取成员](<C:/Users/11408/AppData/Local/Temp/hi3d-studio-export-0yi501pk/index-CDPCug_K.js>) · [临时证据包](<C:/Users/11408/AppData/Local/Temp/hi3d-studio-export-0yi501pk/rea-evidence.json>)

源码核实了序列化参数、复制顺序及事件边界；前序宿主替身只覆盖取消／复制和下载状态分支，不等于实际桌面另存。真实 Studio 重新导出、各对象类型的 skin／clip／纹理保留、系统对话框、部分写入及最终目标摘要仍待实测。三个留存 GLB 和会话不覆盖这些分支。

## 实现伪代码

**根据安装包分支重建的伪代码。** 桌面绑定调用和加载请求。模型解析及视窗切换期间，根据线程、轮次、工作区及加载代次核对回调。回调只有属于本次有效加载时才可完成工具调用。下例概括 `vi`、`M0e`、工作区选择器和 `StudioHost` 的主要分支。

```python
async def studio_load_revision(args, call, desktop):
    scope = desktop.require_current_thread_turn_and_workspace(call)
    require(args.get("assetId") == scope.asset_id)
    studio = await desktop.require_studio_handle(timeout_seconds=5)
    scope.require_active_call()
    args = validate_load_arguments(args)
    versions = desktop.model_versions(scope.asset_id)

    exact_file = args.get("fileName") or args.get("revisionId")
    if exact_file is not None:
        version = versions.find_exact_file_or_path(exact_file)
    elif "modelName" in args:
        version = versions.highest_index_in_family(args["modelName"])
    else:
        version = versions.most_recently_modified()
    require(version is not None)

    studio.select_version(version)
    load = await studio.prepare_load_or_reuse_target(version, scope, call)
    require(load is not None)
    if studio.ready_for(scope.asset_id, version.file_name):
        loaded_identity = studio.confirmed_loaded_identity()
    else:
        loaded_identity = await studio.wait_for_matching_model_loaded(load, call)
    scope.require_active_call()
    require(loaded_identity.asset_id == scope.asset_id)
    state = studio.read_current_state()
    scope.require_current_view_and_asset(studio)
    return text_tool_result({
        "loaded": True,
        "assetId": loaded_identity.asset_id,
        "modelName": loaded_identity.model_name,
        "fileName": loaded_identity.file_name,
        "state": state,
    })
```

## 调用示例

**根据已核查的 schema 重建的工具参数。** 假定活动会话已绑定 `asset_demo`，其中存在指定版本。

```json
{
  "assetId": "asset_demo",
  "fileName": "hi3d-sample_2.glb"
}
```

**根据已核查的回包结构重建的成功负载。** JSON 为 `inputText.text` 解码后的内容。示例中的两处版本一致，未取得尺寸和部件统计。

```json
{
  "loaded": true,
  "assetId": "asset_demo",
  "modelName": "sample",
  "fileName": "hi3d-sample_2.glb",
  "state": {
    "ready": true,
    "assetId": "asset_demo",
    "modelName": "sample",
    "fileName": "hi3d-sample_2.glb",
    "arranged": false,
    "physicalSize": null,
    "parts": []
  }
}
```

## 核查依据

- **安装包静态实现。** `app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。renderer 成员 `out/renderer/assets/index-CDPCug_K.js` 第 58 行有 `gf`、`TN` 和文本应答封装 `on`。第 146–148 行有 `S0e`、`mS`、`Jr.findModelFile`、`M0e`、`Dt` 和 `vi`。`M0e` 和 `findModelFile` 的成员内零基 UTF-8 字节偏移分别为 `1092995` 和 `1108224`。第 5058 行的 `loadFromUrl` 负责 GLB 加载。第 5546 行，`D`、`T` 启动加载，`ve`、`mt` 处理加载确认及失败，`ri` 和 `O` 分别处理文件大小授权和加载计时。 [桌面安装包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
- **传输源码。** `out/main/index.js` 第 15、29 行的 `Ir`、`resolveAssetPath`、`runtimeRespond` 可复核本机读文件和应答 IPC，`out/preload/index.js` 第 1 行有 `respond`。Runtime 第 2 行的 `prepareAppServerParams`、`forwardServerRequest`、`forwardConfirmedServerRequest` 和 `handleServerResponse` 可复核注册、转发及回传。后者的原文件零基 UTF-8 字节偏移为 `3204319`。Runtime SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>)
- **宿主指导。** 随包工作区模板第 42 行指导模型使用 `studio_*` 完成需要用户在视窗中确认的操作。适用范围由宿主分派检查。 [工作区说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:42>)
- **模型可见声明。** 本机 rollout 第 2 行的 `additional_tools` 事件载有 `exec.description` 中的工具声明，原始描述与安装包逐字一致。 [声明记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:2>)
- **实际运行观测。** 第 164–167、497–500、946–949 行分别记录三次按文件名调用及 `loaded: true`、`state.ready: true`。第 489 行的登记回包给出第二个文件为 `210900336` 字节，超过 200 MiB。与其对应的加载记录证明该版本已就绪，是否新开授权面板及用户如何答复还需独立的桌面交互记录。 [实际调用](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:164>) · [大文件登记回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:489>) · [大文件加载回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:500>) 第 943–944 行的登记回包给出随后第 946–949 行加载的确切文件名。
- **离线复现。** 使用安装包中的 `M0e` 和替身 Studio 句柄，模拟加载返回 `hi3d-sample_2.glb`，随后快照读取到同工作区的 `hi3d-sample_3.glb`。工具仍成功回包，顶层身份与 `state.fileName` 各自保留原值。该复现覆盖桌面分派的回包校验，真实视窗切换的时序待测。
- **待查。** 大文件确认、加载超时、解析失败和中止的时序依据静态核查。可在 `ri`、`StudioHost.ve/mt` 与 `modelLoaded` 回调按同一 `requestId` 和加载代次收集确认、选版、就绪及应答的时间，复核拒绝、快速切换和迟到回调。
