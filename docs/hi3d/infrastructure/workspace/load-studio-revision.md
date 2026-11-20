# 加载指定版本并确认

本节点位于工作区基础设施层。它把任务要展示的模型版本加载到桌面 Studio，并根据视窗的实际就绪状态确认交接。核查对象为 `D:/install/Hi3DAgent.__hi3d-transaction` 中的 Hi3D Agent 1.2.11（Windows x64）和随包 Codex 0.166.0。

## 业务定义

| 项目 | 节点契约 |
| --- | --- |
| 触发条件 | 用户要求展示某个模型版本，或上游操作依赖某个版本已在 Studio 中就绪，例如检查指定版本的外观或摆盘。单纯询问「现在显示哪一版」时，先[读取当前视窗状态](read-studio-state.md)。 |
| 上游与输入 | 从[当前轮的工作区上下文](llm-context.md)取得活动工作区、线程和轮次，从[工作区素材与模型版本查询](query-assets-and-model-versions.md)或[生成后候选登记](../../atomic-nodes/preflight-generation.md#3d-候选的检查和登记)的回包取得目标版本。已知具体版本时使用确切文件名，并保留工作区相对路径及预期版本用于后续核对。 |
| 输出 | 加载成功时返回已加载的 `assetId`、`modelName`、`fileName` 和视窗 `state`。失败时保留原目标与错误依据，区分未挂载、目标查无结果、用户拒绝、超时和调用过期。 |
| 完成条件 | 本次工具应答成功，`loaded: true`，`state.ready: true`，顶层及 `state` 的工作区和文件名均与预期目标一致。已经就绪的相同版本可直接确认。 |
| 下游交接 | 交付确认过的加载版本和状态。需要处理磁盘文件时使用该版本的实际路径。视觉检查进入[获取模型的视觉证据](acquire-model-visual-evidence.md)，几何检查读取该版本的 GLB。 |

## Skill 绑定

通用桌面入口由随包 `templates/AGENTS.md` 第 42 行的工作区指令和 renderer 的 `mS` 开发者指令引导。前者要求用 `studio_*` 执行需要视窗确认的操作，后者说明如何选择 Studio 工具。以下 Skill 在任务选用对应路线时补充约束。 [工作区指令](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:42>) · [归档版本](../../upstream/1.2.11/README.md)

| 归档 Skill | 作用与选用条件 | SHA-256 |
| --- | --- | --- |
| [hi3d/SKILL.md](../../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | 执行普通图生 3D 时提供生成、下载和登记规则。需要展示新模型时，从登记结果取得确切版本。 | `4c268ae14ece561234682d564cdfa6264c1f121a9ea118137c0388a9240c217d` |
| [image-to-assembly/SKILL.md](../../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) | 选用静态装配时，用已加载版本定位要查看的粗模、部件或装配结果。该 Skill 的环绕与结构验收还要求实际观察证据。 | `cf4ec08dec0decfd69560a940cc26ea18fecf559ea87852c269fd2682555705f` |

## LLM Tools

模型可见描述原文、通用参数和实现由独立工具页维护。 [工具索引](../../tools/README.md)

| LLM Tool | 用途与调用条件 |
| --- | --- |
| [studio_load_revision](../../tools/studio-load-revision.md) | 目标版本已经确定且任务要求在 Studio 显示或操作该版本时调用。 |
| [studio_get_state](../../tools/studio-get-state.md) | 用户指代当前画面、调用前需要确认视窗是否已显示目标，或加载超时、用户切换视图后需要复核时调用。加载成功的回包已包含有效 `state` 时，可以直接交接。 |
| [user_interaction](../../tools/user-interaction.md) | 原指代无法解析、有多个候选且选错会影响任务时，向用户澄清。大文件加载确认由桌面加载分支自己处理。 |
| [exec](../../tools/exec.md) · [wait](../../tools/wait.md) | 当前会话通过 Code Mode 暴露 Studio 工具时，用 `exec` 发起调用。仅当返回在运行的执行单元时，使用其原 `cell_id` 续查。 |

`studio_load_revision` 与 `studio_get_state` 是桌面动态工具。`item/tool/call` 是 app-server RPC，`runtime:event` 与 `runtime:respond` 是 Electron IPC，`workspace/modelUpdated` 和 `modelLoaded` 分别是目录更新通知与视窗事件。工具注册来自安装包，调用选择来自模型及任务指令。已有生产记录观察到了状态查询和显式加载。

## Hi3D 实现

### 决策

普通 `turn/start` 和 `turn/steer` 带正文、附件和适用的 Skill 引用。已核查的组装器未自动附带实时视窗状态，也未发现按「当前模型」文本触发状态读取的规则。Agent 结合用户指代和下游需要选择工具。显式加载收到 `fileName` 时，按文件名或工作区相对路径精确匹配。仅传 `modelName` 时，取该家族数字序号最大的版本。两者均省略时，取所有版本中 `updatedAt` 最新的文件。明示的目标查无结果时返回失败，保留该指代供复核。 [轮次组装](llm-context.md#组装本轮正文和附件) · [目录 RPC](interfaces/model-catalog-rpc.md) · [加载工具契约](../../tools/studio-load-revision.md#参数与结果)

| 状态 | 来源 | 本节点用途 |
| --- | --- | --- |
| 工作区版本目录 | Runtime `Jg.listModels` 扫描工作区根目录的版本 GLB，合并登记元数据。桌面经 `workspace/open` 初始化列表，经 `workspace/modelUpdated` 增量更新。 | 将目标解析为家族、确切文件名和相对路径。 |
| 界面选中版本 | 桌面 `Jr.displayedFileName`。打开工作区、用户选版本或加载分支均可更新。`StudioHost.D` 在确认大文件和启动实际加载前先更新选择。 | 记录界面选择。该值可能早于实际加载变化。 |
| Studio 已加载版本 | `StudioHost` 的 `Z` 保存加载目标与代次，`h` 保存确认加载的身份，`d` 保存当前阶段。`StudioHost.ve` 处理有效 `modelLoaded` 后更新 `h` 和 `d`。 | 以 `getState()` 返回的实际身份和 `ready` 确认目标。 |

登记事件带有 `threadId` 和 `turnId` 时，当前工作区可设置自动展示请求。界面核对会话和工作区，并在该轮结束、页面可见时尝试加载。其他面板占用时可延后。这条界面路径影响后续查询可看到的版本。显式工具仍以自己的加载确认回包交接。来源见 `app.asar` 的 renderer `Jr.F` 第 147 行及 `ke/ct` 第 5546 行。 [发布模型文件的工具契约](../../tools/workspace-commit-model.md)

### 执行

**根据生产行为重建的 Code Mode 请求。** 假定上游已确认任务使用 `asset_example`，并要求加载 `hi3d-cat_3.glb`。实际会话可用的调用形式以该轮工具定义为准。

```javascript
const result = await tools.studio_load_revision({
  assetId: "asset_example",
  fileName: "hi3d-cat_3.glb"
});
text(result);
```

1. **注册与转发。** renderer 的 `mS` 将 `S0e` 随 `thread/start` 传给 Runtime，`prepareAppServerParams` 按工具名合并定义。模型调用后，app-server 发 `item/tool/call`，参数含 `threadId`、`turnId`、`callId`、工具名和工具参数。Runtime 的 `forwardServerRequest` 校验请求，并先进行共享会话额度检查 `skillCredits.confirm(threadId, turnId, [])`。额度门禁允许时，`forwardConfirmedServerRequest` 分配桌面 `requestId`，保存对应的 app-server 实例和原 RPC ID，再通过主进程的 `runtime:event` 交给 renderer。普通发送入口检查登录和 IPC 来源。已查 Studio 分派属于桌面处理链，未经过 Codex shell 审批。
2. **核对作用域及查找目标。** `Dt` 校验动态工具调用的外层参数。`vi` 检查活动线程、活动轮次及线程 `cwd` 与当前工作区相同，保存会话代次与取消信号。`M0e` 核对请求中的 `assetId`，只允许 `studio_load_revision` 在句柄尚未挂载时等待最多 5 秒。随后读取 `Jr` 的状态并解析版本。已经就绪的同一工作区、同一文件可以直接返回。新加载先设置界面选中项，再经过桌面授权钩子 `ri`。文件超过 200 MiB 或大小未知时询问用户，确认等待为 60 秒。共享会话额度与这项本地确认分别执行。
3. **加载本机 GLB。** `StudioHost.D/T` 绑定目标文件、工作区、线程、适用轮次和加载代次，把相对路径转换为 `sparc3d-asset://workspace/<assetId>/<path>`。同一启动请求可复用正在进行的授权和启动操作。Electron main 的 `Ir → resolveAssetPath` 解析工作区，检查词法路径和真实路径的包含关系，再向 renderer 提供本机文件。`loadFromUrl` 通过 Three.js `GLTFLoader` 装配场景。匹配的 `modelLoaded` 需通过组件键、加载代次、线程、工作区及适用轮次检查，才能写入已加载身份。等待者还须匹配工作区、文件名和加载代次，才能按目标完成。
4. **回传工具结果。** `M0e` 核对返回时的作用域、句柄和工作区。renderer 将结果序列化为 `contentItems` 中的 `inputText`，通过 preload 的 `runtime:respond` 传回原桌面 `requestId`。Runtime 的 `handleServerResponse` 消费对应记录并回到原 app-server RPC。生产样本的外层 `exec` 与其工具输出使用相同 `call_id`。桌面 `requestId` 与 app-server RPC ID 属于内部转发关联，分别维护。

**实现伪代码。** 概括新加载和复用分支，并单列调用方的交接校验。省略重复请求合并、面板交互及 JSONL 封装。

```python
async def load_in_studio(call, desktop):
    scope = desktop.capture_active_scope(call)
    scope.require_matching_thread_turn_and_cwd()
    scope.require_asset(call.args["assetId"])
    studio = await desktop.wait_for_handle(max_seconds=5, signal=scope.signal)
    scope.require_current()
    target = desktop.resolve_model_version(call.args)
    require(target is not None)

    studio.select_file(target.file_name)
    if not studio.ready_for(target.asset_id, target.file_name):
        await desktop.authorize_load_if_required(target, scope.signal)
        scope.require_current()
        pending = await studio.start_load(target, scope)
        await studio.wait_for_matching_model_loaded(pending, scope.signal)

    scope.require_current_handle_and_workspace(studio)
    return encode_loaded_result(target, studio.get_state())


def confirm_for_handoff(tool_success, payload, expected):
    require(tool_success and payload["loaded"] is True)
    state = payload["state"]
    require(state["ready"] is True)
    require(payload["assetId"] == state["assetId"] == expected.asset_id)
    require(payload["fileName"] == state["fileName"] == expected.file_name)
    return state
```

### 验收

| 要确认的结果 | 所需证据 | 下游动作 |
| --- | --- | --- |
| 工具已应答 | 回包属于同一次调用且返回成功。Code Mode 以外层 `call_id` 配对。 | 读取负载随附的加载结果。状态查询即使 `ready: false` 也可以成功结束。 |
| 视窗已就绪 | `state.ready: true`，并有已加载身份。 | 读取该时点的尺寸、部件统计和摆盘状态。 |
| 目标版本已确认 | `loaded: true`，顶层和 `state` 的 `assetId`、`fileName` 与解析出的目标一致。 | 需要路径时查版本目录或登记回包。几何检查读取 GLB，视觉检查另取对应版本的画面。 |

`state.ready` 来自 StudioHost 加载阶段，`assetId`、`modelName`、`fileName` 来自确认身份。`arranged` 优先取内置编辑器标志，`physicalSize` 与 `parts` 由模型管理器计算。回包没有实际文件路径、相机参数或画面像素。视觉下游按加载版本记录观察方向，再取得截图或定向渲染；截图的 `artifactId` 仍需解析为可读文件，Hi3D 的通用解析入口尚未核实。 [状态字段](read-studio-state.md#执行) · [截图工具结果](../../tools/studio-capture-view.md#参数与结果)

**根据已核查实现重建的成功负载。** 对应上面的请求，以下是 `contentItems[0].text` 解码后的示例。尺寸与部件统计取自视窗，示例省略具体测量值。

```json
{
  "loaded": true,
  "assetId": "asset_example",
  "modelName": "cat",
  "fileName": "hi3d-cat_3.glb",
  "state": {
    "ready": true,
    "assetId": "asset_example",
    "modelName": "cat",
    "fileName": "hi3d-cat_3.glb",
    "arranged": false,
    "physicalSize": null,
    "parts": []
  }
}
```

## 完成与恢复

| 情形 | 处置 |
| --- | --- |
| Studio 未挂载或加载参数不匹配 | 加载最多等待句柄 5 秒。只读状态查询在未挂载时立即失败，已挂载但尚无确认身份时可返回 `ready: false` 和空状态。目标文件或工作区不匹配时先核对归属与版本。 |
| 用户拒绝或确认超时 | 本次加载失败。界面可能已经选中目标，实际加载身份仍以查询为准。再次加载以用户当前意图为依据。 |
| 加载慢、解析失败或等待超时 | 已知正文件大小时每 32 MiB 向上取整为一档，每档 60 秒，最多 300 秒。大小未知或非正值时为 120 秒。编辑器内捕获的解析错误可能表现为外层超时。仍有效的迟到 `modelLoaded` 可使视窗随后就绪，原工具调用已失败。继续前查询当前状态，仅在任务仍需要时重试加载。 |
| 轮次取消、切换会话或视窗 | renderer 中止关联的调用，`M0e` 拒绝陈旧作用域及被替换的句柄。新加载代次使旧等待者失效。Runtime 收到原请求解决通知或实例退出时清理映射，无法关联的迟到回应会被忽略。在当前有效轮次重新确认。 |
| 同一工作区内切换版本 | 通用回包末端校验覆盖会话、句柄和工作区。已取得的状态是读取当时的快照。若后续操作指向「现在的画面」，切换后重新查询。已锁定的文件操作继续核对原版本及其路径。 |
| 上游生成或登记尚未完成 | 云端 `pending` 和提交不明沿[原生成作业](../../atomic-nodes/preflight-generation.md#完成条件与恢复)核对。原作业成功且结果有多个 GLB 时，按[候选检查和登记](../../atomic-nodes/preflight-generation.md#3d-候选的检查和登记)复用已核实的产物。取得登记后的确切文件名再加载。 |

结构化宿主失败通常以 `success: false` 和 `error` 文本负载回传，renderer 捕获的分派异常可经 `respondError` 返回 `STUDIO_NOT_READY`。本地视窗加载没有远端生成任务 ID。Code Mode 若已经提供 `cell_id`，先按原执行单元取得这次结果。

**按版本分歧走查。** 列表已选 `hi3d-cat_3.glb`，Studio 实际就绪的是 `hi3d-cat_2.glb`。用户说「检查当前模型」时，调用 `studio_get_state({})`。若同工作区回包为 `ready: true`、`fileName: "hi3d-cat_2.glb"`，交接 `_2`。若 `_3` 正在加载，返回 `ready: false` 时只报告未就绪，即使身份暂时仍为 `_2`。未挂载、作用域不符或调用过期时按工具错误处理。用户明确要求展示 `_3` 时，使用 `_3` 的确切文件名发起加载并核对成功回包。

## Vet3D 迁移与核查范围

Vet3D 可用供应商无关的 `workspaceRef`、`modelRef`、`revisionRef` 和 `fileRef` 表达目标。宿主分别维护已登记版本、界面选择和视窗确认的加载版本。为每次加载固定工作区、明确的版本引用、视窗实例与加载代次，完成事件匹配后再交付。待处理调用量、超时、取消原因和实际加载状态可与请求 ID 关联。需要证明加载的是某一份具体文件内容时，由 Vet3D 加入文件版本或内容指纹并在读取侧复核，这属于拟议设计。

验收用例应覆盖同一版本复用、选中新版但仍显示旧版、加载中保留旧身份、连续切换模型、会话切换引起的取消、用户拒绝大文件、超时后迟到回调，以及加载结果与预期版本不符。只读状态与写入操作分别核对。对「当前」的写入在作用域或视窗代次变化后重新解析；对固定版本的写入按其明确引用执行。

| 证据类别 | 已核实的范围与复核入口 |
| --- | --- |
| 安装版本与静态实现 | [桌面包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。[Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>) SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。ASAR 成员 `out/renderer/assets/index-CDPCug_K.js` 第 138、146–148 行为消息、注册和桥接，第 5058 行为 `loadFromUrl`，第 5546 行为 `StudioHost` 及 `ri`。`M0e` 和 `StudioHost` 的成员内零基 UTF-8 字节偏移分别为 `1092995` 和 `4708669`。`out/main/index.js` 第 15、29 行为文件协议和 IPC，`out/preload/index.js` 第 1 行为响应桥。Runtime 的 `handleServerResponse` 原文件字节偏移为 `3204319`。 |
| 实际运行观测 | 第 145–148 行从原作业候选中登记选定的 GLB。第 154–160 行模型已登记且可查到文件，视窗仍返回 `ready: false`。第 164–167 行对登记版本显式调用加载工具，回包确认该版本已就绪。第 943–949 行也观察到修订版登记后按确切文件名显式加载，第 953–954 行记录同轮次后续采样。两段都以显式工具应答确认加载。 [原作业候选登记与加载](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:145>) · [修订版登记后加载](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:943>) |
| 离线复现 | 对从指定 ASAR 提取的 `M0e` 和响应包装使用替身 Studio 句柄，验证未挂载、空状态、错误工作区、正常加载、取消、陈旧作用域、句柄替换，以及同工作区文件名变化仍可交付旧快照。该复现覆盖宿主桥的状态判断。 |
| 待验证与下一入口 | 登记事件驱动的自动展示时序、实际桌面的大文件确认、GLB 解析失败、加载竞争和超时后就绪尚缺真实轨迹。可沿 `workspace/modelUpdated`、`vi`、`StudioHost.D/T/ve/mt`、`modelLoaded`、`requestId` 和 IPC 回包关联实测。现有 rollout 能核对工具输出和后续采样，完整出站模型请求中的上下文字段还需请求侧记录。 |
