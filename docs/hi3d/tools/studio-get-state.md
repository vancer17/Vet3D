# studio_get_state

## 工具名称与注册来源

`studio_get_state` 是 Hi3D Agent 1.2.11（Windows x64）的桌面动态工具。Electron renderer 的 `mS` 在 `thread/start` 提交 `S0e` 中的工具定义。Runtime 将桌面工具与自己的动态工具合并，交给随包 Codex 0.166.0。注册随线程创建提交，读取发生在 Codex 显式发起工具调用时。该调用依赖当前活动线程中的 `StudioHost`。

本机运行记录中的模型可见声明位于 `exec.description` 内，调用入口为 Code Mode 的 `tools.studio_get_state`。 [exec](exec.md)

## 暴露给 LLM 的描述

以下内容为安装包中的 `description` 原文。

```text
读取 Hi3D 内置 Studio 视窗的当前模型、版本、摆盘状态、物理尺寸和部件统计；未加载模型时返回 ready=false、assetId=null，需要操作模型时先调用 studio_load_revision。此工具不读取 Bambu Studio 等外部切片软件。
```

此描述与 1.2.11 renderer 原包定义逐字一致。描述长 138 个字符，正文 UTF-8 字节的 SHA-256 为 `db9631447e355dc10553b058516d23613ced270ccab091e87d313377a75ed794`，排除围栏及两端换行。工具定义在 ASAR 成员 `out/renderer/assets/index-CDPCug_K.js` 的零基字节 `1092043`。 [原始 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

## 参数与结果

参数为无属性的对象 `{}`。模型可见 schema 声明 `additionalProperties: false`，桌面分派的状态读取分支直接取视窗状态。工作区、线程和轮次由宿主调用上下文确定。

| 字段 | 含义 |
| --- | --- |
| `ready` | `StudioHost.getState` 从加载状态 `d` 读取。`true` 表明采样时 Studio 已完成加载并进入就绪状态。 |
| `assetId`、`modelName`、`fileName` | 取自 Studio 保存的已确认加载身份 `h`，依次为工作区 ID、模型家族、版本文件名，均可为空。界面版本选择和工作区版本登记各自维护独立状态。 |
| `arranged` | 从编辑器读当前摆盘状态，编辑器未提供时读取 Studio 的摆盘状态。 |
| `physicalSize` | 可用时为 `{mmPerUnit, source, bboxMm: {x, y, z}}`。当前网格的世界坐标轴对齐包围盒跨度乘以模型管理器提供的 `mmPerUnit` 得到毫米值。`source` 缺失时为 `modelManager`。比例或边界框不可用时为 `null`。 |
| `parts` | `bt` 根据 `getAllMeshes()` 汇总。每项含 `name`，缺少名称时用 `part_<序号>`，可计算时附 `faceCount`。 |

成功结果使用 `{success: true, contentItems: [{type: "inputText", text: ...}]}`，`text` 为上述状态的 JSON 字符串。模型管理器默认在识别出受信的 `sparc3dPhysicalUnits` 米制标记时采用文件尺度，`source` 为 `file`，其余情况以初始最长边 75 mm 建立比例，`source` 为 `default-longest`。面数取索引计数除以三并向下取整，索引不可用时改用位置属性计数。统计不可用时仍可返回已加载身份。

### 使用视窗快照

工具应答、视窗就绪与目标身份各有字段。比较版本时，用工作区版本记录中的规范文件名和所属 `assetId`。定位文件使用版本记录的路径，确定相机状态需要相机数据，检查当前画面可使用截图或渲染。`ready` 只反映视窗加载状态。该快照提供视窗身份和显示统计，文件内容摘要、骨架、休止矩阵、权重、Action/NLA 与实际形变需从对应文件或工程取证。`physicalSize.source: "default-longest"` 的毫米尺度来自初始 75 mm 显示比例。`faceCount` 是视窗三角面统计，需要原生面数、原生边连接、边界、非流形、自交或水密证据时，应从实际候选文件另行测量。 [studio_load_revision](studio-load-revision.md) · [studio_capture_view](studio-capture-view.md)

| 观测 | 解释与续查 |
| --- | --- |
| 已挂载，无加载身份 | 工具成功，返回 `ready: false` 和空身份。已发起加载时可等待原调用结果，需要打开目标时可按其确切文件名加载。 |
| 有加载身份，`ready: false` | 模式切换期间可能仍有加载身份。以未就绪处理，在有效会话中重取快照。 |
| `ready: true`，身份匹配 | 可确认采样时目标 `assetId`、`fileName` 已在视窗就绪。 |
| `ready: true`，同工作区的文件名不同 | 快照记录的是该文件名。若仍需指定目标，使用其确切文件名发起加载。 |
| 同句柄、同工作区在采样后切换了版本 | 回传校验仍可通过，结果保留采样时的旧 `fileName`。后续操作按目标文件名重新核对实时身份。 |
| 未挂载、跨工作区、句柄已替换或调用已失效 | 读取失败或原调用中止。恢复有效会话和目标句柄后重新查询，此工具没有独立的状态查询任务可续查。 |

## 执行与治理

1. Codex 通过 `item/tool/call` RPC 发起查询，传递线程、轮次、工具调用 ID、工具名和参数。Runtime 的 `forwardServerRequest` 先执行 `skillCredits.confirm(threadId, turnId, [])`，本轮已有的额度确认可能阻断转发。该分支追加的付费 Skill 清单为空，执行路径在桌面宿主内。`forwardConfirmedServerRequest` 将原 app-server RPC ID 与桌面 `serverRequest.requestId` 关联，经 Electron `runtime:event` 送给 renderer。
2. renderer 的 `Dt` 校验调用信封，`vi` 校验活动线程、轮次及工作区，并绑定会话修订和取消信号。`M0e` 检查 Studio 句柄和加载身份。未挂载立即失败。已挂载但无加载身份时直接生成空状态，外层仍复核活动调用。加载身份存在时先拒绝跨工作区读取，再读取快照，回传前复核调用有效性、句柄及实时 `assetId`。
3. renderer 经 preload 的 `runtime:respond` IPC 和主进程 `serverResponse` 回到 Runtime，`handleServerResponse` 按桌面 `requestId` 完成对应的 app-server 请求。线程、轮次或会话失效可中止调用或拒绝晚到结果。Runtime 已清理请求映射时，迟到应答无法完成原请求。普通失败以 `success: false` 和含 `error` 的文本负载表示，未挂载、跨工作区和视窗已切换都走这类失败。renderer 捕获的分派异常可经 RPC 错误 `STUDIO_NOT_READY` 回传。

此工具在 renderer 记录调用并对视窗做一次只读采样。调用因会话失效而结束时，由当前有效会话重新查询。离线复现表明，同一句柄在同一工作区内若在采样后换到新版，原版本快照仍可通过校验。需要保证对象仍与快照一致的操作，应在执行前重新核对会话和版本。

## 实现伪代码

**根据桌面分派重建的伪代码。** 桌面先检查请求是否属于当前活动线程、轮次与工作区。已加载模型时，先核对工作区，再从当前句柄取状态快照，最后核对句柄和工作区归属。未加载模型时生成空状态，外层仍检查当前会话、轮次和工作区。

```python
async def studio_get_state(call, desktop):
    scope = desktop.require_current_thread_turn_and_workspace(call)
    result = await read_state(desktop, scope)
    scope.require_active_call()
    return result


async def read_state(desktop, scope):
    studio = desktop.studio_handle
    if studio is None:
        return tool_error("Studio is not mounted")
    scope.require_active_call()

    asset_id = studio.read_current_state()["assetId"]
    if asset_id is None:
        return text_tool_result({
            "ready": False,
            "assetId": None,
            "modelName": None,
            "fileName": None,
            "arranged": False,
            "physicalSize": None,
            "parts": [],
        })
    if asset_id != scope.asset_id:
        return tool_error("The displayed model belongs to another session")

    result = await dispatch_state_snapshot(studio)
    scope.require_active_call()
    if desktop.studio_handle is not studio or studio.read_current_state()["assetId"] != scope.asset_id:
        return tool_error("The Studio view changed during this tool call")
    return result
```

## 调用示例

**根据已核查的 schema 重建的工具参数。** 从当前会话读取 Studio 状态。

```json
{}
```

**根据已核查行为重建的空状态负载。** Studio 句柄已挂载，返回成功，`inputText.text` 解码结果如下。

```json
{
  "ready": false,
  "assetId": null,
  "modelName": null,
  "fileName": null,
  "arranged": false,
  "physicalSize": null,
  "parts": []
}
```

## 核查依据

- **安装包静态实现。** `app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。renderer 成员 `out/renderer/assets/index-CDPCug_K.js` 第 146–148 行的 `S0e`、`mS`、`M0e`、`Dt` 和 `vi` 覆盖注册、校验与分派。`M0e` 的成员内零基 UTF-8 字节偏移为 `1092995`。`StudioHost.getState` 与 `bt` 位于第 5546 行，成员内偏移分别为 `4717250` 和 `4722795`。尺寸计算的 `X6` 和 `getRealSizeMm` 位于第 4985、5054 行。 [桌面安装包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
- **传输源码。** ASAR 成员 `out/preload/index.js` 第 1 行的 `respond`、`out/main/index.js` 第 29 行的 `runtimeRespond` 及 Runtime 第 2 行的 `forwardServerRequest`、`forwardConfirmedServerRequest`、`handleServerResponse` 覆盖调用转发及应答。Runtime 的 SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>)
- **宿主指导。** 随包工作区模板第 42 行指导模型使用 `studio_*` 完成需要用户在视窗中确认的操作。适用范围由宿主分派检查。 [工作区说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:42>)
- **模型可见声明。** 本机 rollout 第 2 行的 `additional_tools` 事件载有 `exec.description` 中的工具声明，原始描述与安装包逐字一致。 [声明记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:2>)
- **实际运行观测。** 第 148 行已有正式文件的登记回包，第 154、160 行的 Studio 查询仍返回 `ready: false` 和空身份。第 523、528 行记录已加载快照，返回 `ready: true`、边界框和部件面数。两次观测分别核对当时的视窗状态。 [登记回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:148>) · [空状态查询](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:154>) · [就绪状态查询](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:523>)
- **文件与视窗的独立观测。** 同一次执行单元里，第 160 行记录本地命令已读到登记后的 GLB 和字节数，状态查询同时返回空身份。第 167 行的显式加载回包随后记录同一文件名的就绪快照。 [并列观测](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:160>) · [就绪快照](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:167>)
- **离线复现。** 使用从安装包提取的 `M0e` 和替身句柄复核未挂载、无加载身份、跨工作区、句柄被替换、调用中止及同工作区切换版本。模拟快照读取后由 `hi3d-sample_2.glb` 换至 `hi3d-sample_3.glb`，应答仍为 `hi3d-sample_2.glb`。
- **待查。** 实际桌面切版与取消时序可在 `vi` 和 `getState` 入口复测，按 `requestId` 对照读取时和应答前的视窗身份。尺寸精度可用物理尺寸已知的 GLB 对照 `getRealSizeMm` 的输出验证。
