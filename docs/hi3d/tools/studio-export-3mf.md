# studio_export_3mf

## 工具名称与注册来源

`studio_export_3mf` 是 Hi3D Agent 1.2.11（Windows x64）的桌面动态工具。Electron renderer 的 `S0e` 声明工具定义，`mS` 将它加入 `thread/start` 的 `dynamicTools`。Runtime 合并动态工具定义并转发 `item/tool/call`。桌面收到调用后，通过 `M0e` 操作当前 `StudioHost`，以本次调用的请求 ID 回传结果。

## 暴露给 LLM 的描述

以下内容为安装包中的 `description` 原文。

```text
打开 Studio 打印计划面板；下载或发送由用户在面板中确认。
```

## 参数与结果

模型可见 schema 为 `{"type":"object","properties":{},"additionalProperties":false}`。参数为 `{}`，无必填字段、可选字段或字段默认值。当前桌面分发分支直接操作 Studio，未额外解析工具参数。模型、工作区和当前线程由桌面状态确定，打印设置及下载或发送选项由面板处理。

桌面工具返回 `{success, contentItems: [{type: "inputText", text: "<JSON>"}]}`。常见结果如下。

| 情况 | `success` | `text` 中的 JSON 负载 |
| --- | --- | --- |
| 已触发 Studio 打印计划入口。 | `true` | `{opened: true, note: string}`。备注提示用户可以在面板中下载或发送，并提及 `artifact/registered` 事件。 |
| `openPrintPlan` 拒绝调用，或分发器收到 `status: "failed"`。 | `false` | `{opened: false, error: string}`。当前 Host 在成功发出触发后返回 `undefined`。 |
| Studio 未挂载、模型未加载或未就绪、工作区不匹配、线程或轮次已失效、调用中止或视图变化。 | `false` | `{error: string}`。 |

`opened: true` 确认桌面已发出打开操作。当前 Host 发起内部异步触发后立即完成自身调用。模型未摆盘时，内部触发等待用户选择，用户可取消或先摆盘。非 SLA 路线的材料列表为空时，内部触发报错。只有内部触发到达面板显示逻辑才会打开打印计划。

工具调用的直接副作用是启动上述界面流程。后续有两条独立的用户操作路径。

- **下载。** 单盘生成一个 `.3mf`。多盘可下载合并的 `.3mf`，或下载包含各盘 `.3mf` 的 `.zip`。Electron 打开保存对话框并通过 `file:downloadEvent` 报告 `selecting`、`completed`、`cancelled` 或 `failed`。以 `completed` 事件中的实际 `path` 确认文件保存。此路径由下载事件确认，工具回包仍表示入口触发。
- **发送至切片器。** 非 SLA 路线支持此操作，发送生成一个 `.3mf`，多盘使用合并模式。桌面把字节写入当前工作区，登记角色为 `export-3mf` 的文件产物，并用登记回执的 `assetId`、`artifactId` 和 `path` 调用 `files.openInSlicer`。`artifact/registered` 确认工作区产物已登记。主进程接着请求系统打开目标切片器，再调用 Runtime 的 `print/send` 记录交接。切片器实际读取和解析文件由外部程序确认。

在已核查的普通 3MF 组包分支中，`validate3MFComponents` 在生成模型 XML 前检查顶点坐标是否为有限数、三角面引用的顶点索引是否有效，以及可选的调色板索引是否有效。组包校验没有水密门槛。调用方可以单独核查边界、自交和可打印性。面板响应、文件输出和产物登记各有证据。

## 实现伪代码

桌面先核对活动线程、轮次、工作区和 Studio 所加载的模型，再触发打印计划。分发后仍会核对调用与视图状态。以下实现伪代码保留了 Host 调用与内层异步流程的边界。

```python
async def studio_export_3mf(call, desktop):
    scope = desktop.require_current_thread_turn_and_workspace(call)
    studio = desktop.require_mounted_studio()
    if studio.asset_id is None or not studio.is_ready():
        return text_tool_result(False, {"error": "Studio has not loaded a model"})
    if studio.asset_id != scope.asset_id:
        return text_tool_result(False, {"error": "The displayed model belongs to another session"})

    try:
        outcome = await studio.open_print_plan()
        if outcome and outcome["status"] == "failed":
            result = text_tool_result(False, {
                "opened": False,
                "error": outcome.get("message", "failed"),
            })
        else:
            result = text_tool_result(True, {"opened": True, "note": export_panel_note})
    except Exception as error:
        result = text_tool_result(False, {"opened": False, "error": str(error)})
    return desktop.check_scope_and_respond(call.id, scope, studio, result)


async def open_print_plan():
    trigger = require_embedded_export_trigger()
    start_without_waiting(trigger)


async def embedded_export_trigger():
    if not model.is_arranged():
        choice = await ask_user_how_to_proceed()
        if choice == "cancel":
            return
        if choice == "arrange-first":
            await arrange_model()
    if not selected_printer_is_sla() and not configured_materials():
        raise Error("no materials configured")
    show_print_plan()
```

桌面以本次动态工具调用的请求 ID 对应一次入口响应。当前实现没有导出任务 ID、`pending` 结果、查询参数或恢复动作。等待用户选择时，交互仍由已经触发的界面处理。保存结果由 Electron 下载事件确认。发送分支使用工作区 ID 和产物 ID 核对登记回执，再核对切片器打开与 Runtime 交接结果。

## 调用示例

**根据已核查的 schema 重建的工具参数。** 假定活动工作区中的示例模型已在 Studio 加载并就绪。

```json
{}
```

**根据已核查的返回结构重建的成功负载。** `note` 保留宿主在该分支的原始提示。`opened` 在面板异步触发后即可返回，实际可见状态及用户操作结果由桌面跟踪。

```json
{
  "opened": true,
  "note": "The print plan panel is open. The user can download or send files from the panel; outputs are registered through artifact/registered events."
}
```

## 核查依据

- **安装包静态实现。** `app.asar` 的 SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。renderer 成员 `out/renderer/assets/index-CDPCug_K.js` 内零基 UTF-8 字节偏移 `1091855`、`1092683`、`1092995` 分别为工具定义、注册入口和分派。第 5508、5515、5546 行包含下载实现、内嵌打印计划入口及 `StudioHost` 的打开、写入和发送逻辑。发送入口 `ue` 位于 `4712090`，文件登记前的调用 `Ce` 位于 `4712488`。主进程成员 `out/main/index.js` 第 29 至 30 行包含 `fileWriteArtifact`、`fileOpenInSlicer` 及 `will-download` 处理。 [桌面安装包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
- renderer 成员内的零基 UTF-8 字节偏移 `4223602`、`4558955`、`4633373`、`4712090` 附近分别是单盘及多盘文件分支、面板下载选项、下载和发送触发、宿主登记与发送回调。主进程成员内偏移 `181200`、`264515` 附近可核对切片器 IPC 和下载终态事件。
- **Runtime 静态实现。** `manifest.json` 标注版本及平台为 `1.2.11 win32 x64`。同目录下 `dist/runtime.mjs` 的 SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`，其中 `prepareAppServerParams` 合并动态工具，`artifact/register` 持久化登记并发出通知，`print/send` 校验已登记文件并保存本地交接状态。 [版本清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>)
- **模型可见声明。** 本机 rollout 第 2 行 `additional_tools` 事件中的 `exec.description` 含注册原文。该样本的工具调用轨迹未覆盖打开打印计划。 [声明记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:2>)
- **离线复现。** 用替身函数隔离执行 `StudioHost.openPrintPlan`，确认缺少触发函数会拒绝，触发函数仍待完成时 Host 已返回 `undefined`。实际面板状态、文件保存和外部切片器启动仍待桌面验证。
