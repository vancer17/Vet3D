# studio_arrange

## 工具名称与注册来源

`studio_arrange` 是 Hi3D Agent 1.2.11（Windows x64）的桌面动态工具。Electron renderer 的 `mS` 在 `thread/start` 提交 `S0e` 中的定义。Runtime 合并并转交调用，renderer 的 `vi` 和 `M0e` 将调用交给当前工作区的 `StudioHost`。

## 暴露给 LLM 的描述

以下内容为安装包中的 `description` 原文。

```text
进入 Studio 完整智能摆盘界面并执行摆盘；超床、取消等需要用户决策的步骤保留在面板中。
```

## 参数与结果

| 参数 | 必填性 | 可用范围与缺省行为 |
| --- | --- | --- |
| `profileId` | 可选字符串。 | 指定摆盘档位 ID。工具 schema 未列出允许的 ID。显式调用省略时由编辑器取当前档位。 |
| `plateMode` | 可选字符串。 | 模型可见枚举为 `single`、`multi`，没有声明默认值。进入摆盘界面时的自动摆盘取编辑器当前模式。显式调用省略时传入未定义值。 |

空对象有效，模型可见 schema 声明 `additionalProperties: false`。工具作用于当前工作区在 Studio 中已加载并就绪的模型，参数中没有模型或工作区选择项。它可能切换到摆盘面板，执行本地摆盘并更新编辑器布局。需要用户决策的界面仍可保留。

布局求解器可从源网格构造临时三角采样，用来计算摆放朝向。结果应用到对象姿态。该分支保留源网格的面连接，不导出新网格文件。 [摆盘求解定位](#核查依据)

公开的 `single`、`multi` 会原样传入编辑器摆盘实现。底层算法的专用分支比较 `single-plate`、`auto-merge`，静态调用链中未见公开枚举到这两个内部值的转换。公开枚举对实物样例的盘数和布局影响仍待实测。

桌面把业务负载序列化为 JSON，置于响应的 `contentItems[0].text`，对应项类型为 `inputText`。已核查的分支如下。

| 负载 | 含义 |
| --- | --- |
| `{status: "arranged", plates}` | 当前 Studio 会话收到摆盘事件。宿主取事件中 `plates` 或 `plateCount` 的数值或数组长度，缺失时返回 `1`。已核查的编辑器结果把盘数放在 `batchCount`，经过此路径会触发宿主的 `1` 回退。编辑器发现超床时也可能发出摆盘事件并保留超床对话框，所以此状态只确认收到事件。 |
| `{status: "oversize-pending", message}` | 宿主等待摆盘事件的 120 秒定时器到期。工具外层在此分支仍返回 `success: true`。此结果无法判断模型是否超床或布局是否最终生效。 |
| `{status: "failed", message}` | 宿主无法继续，例如已有摆盘等待者、摆盘能力不可用、切换视图时模型加载失败、等待被中止或显式调用编辑器抛错。编辑器还会检查打印机、网格和物理尺寸等前置条件。工具外层返回 `success: false`。 |
| `{error, issues?}` | 参数校验失败时附带 `issues`。Studio 未挂载、未加载模型、已显示其他工作区的模型、轮次中止或调用过期等情况也可返回错误。 |

安装包的结果结构声明另含 `cancelled` 和可选 `layoutArtifactId`。已核查的宿主返回分支未构造这两项。编辑器有独立的取消动作，轮次中止会结束桌面等待，具体的面板取消结果仍需通过实际会话核对。

## 实现伪代码

桌面先核对当前线程、轮次和工作区，Studio 未挂载时立即返回错误，已挂载时核对其中模型所属的工作区。宿主通过 Studio 视图会话编号匹配摆盘事件。首次切换到摆盘面板后，编辑器根据模型尺寸、当前打印机、档位和摆盘模式触发自动摆盘。自动阶段返回 `failed` 时直接结束。其余情况下，只要有一个非空选项，宿主就会按请求参数再次触发摆盘。已经处于摆盘面板时，宿主直接调用编辑器。

**实现伪代码。** `pack_result` 表示将业务负载封装为工具响应，异常路径由桌面分发器返回错误。

```python
async def studio_arrange(raw_args, call, desktop):
    scope = desktop.require_current_thread_turn_and_workspace(call)
    studio = desktop.require_mounted_studio()
    require(studio.get_state()["assetId"] == scope.asset_id)
    args = validate_arrange_args({} if raw_args is None else raw_args)
    require(studio.is_ready(), "Studio has not loaded a model")

    with studio.end_wait_on_abort(call.signal):
        if studio.mode != "arrange":
            result = await studio.enter_arrange_and_wait(
                model_timeout_seconds=60,
                arrange_event_timeout_seconds=120,
            )
            if result["status"] != "failed" and (
                args.get("profileId") or args.get("plateMode")
            ):
                result = await trigger_and_wait(studio, args)
        else:
            result = await trigger_and_wait(studio, args)

    scope.require_current_view(studio)
    call.signal.throw_if_aborted()
    return pack_result(result, success=result["status"] != "failed")


async def trigger_and_wait(studio, args):
    if not studio.can_trigger_arrange():
        return {"status": "failed", "message": "Studio arrange unavailable"}
    if studio.has_arrange_waiter():
        return {"status": "failed", "message": "Studio arrange busy"}
    waiter = studio.begin_arrange_wait(
        view_session_id=studio.view_session_id,
        timeout_seconds=120,
        timeout_status="oversize-pending",
    )
    try:
        await studio.editor.trigger_arrange(
            args.get("profileId"), args.get("plateMode")
        )
    except EditorError as error:
        waiter.clear()
        return {"status": "failed", "message": str(error)}
    return await waiter.result()
```

`begin_arrange_wait` 表示宿主建立唯一的本地等待者，已有等待者时返回忙碌失败。切换面板的模型加载和摆盘事件分别有 60 秒与 120 秒的等待，后者从创建等待者起计时。显式路径还要等待编辑器的调用返回，因此 120 秒只限定事件等待者的计时。视图变更和轮次中止会清理等待。摆盘事件必须匹配当前视图会话才能完成等待。

执行与等待都发生在桌面。工具没有公开任务 ID、查询动作或跨轮恢复接口。返回 `oversize-pending` 时，宿主清除事件等待者，计时器分支未调用编辑器取消。可查看当前面板，并用状态工具重新读取当前 Studio 的模型及就绪状态。后续再次调用摆盘会发起新的编辑器操作。 [视窗状态工具](studio-get-state.md)

## 调用示例

**根据已核查的 schema 重建的工具参数。** 假定当前 Studio 已加载一个就绪的示例模型，使用当前界面配置。也可以传入 `{"profileId": "surface"}` 来显式请求 `surface` 档位。

```json
{}
```

**根据已核查的返回分支重建的业务负载。** 下例表示宿主收到摆盘事件。

```json
{
  "status": "arranged",
  "plates": 1
}
```

## 核查依据

- 安装包为 `D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar`，SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。
- renderer 成员 `out/renderer/assets/index-CDPCug_K.js` 第 58 行包含 `EN` 参数检查、结果声明及 `on` 响应包装。第 146 至 148 行包含 `S0e`、`mS`、`M0e`、`vi` 的定义、注册及分发。第 5508 行的 `LPe`、`_Pe` 和第 5515 行的编辑器处理模式、摆盘事件和超床界面。第 5546 行的 `StudioHost`、`pe`、`le`、`Me`、`pt` 管理视图、计时及结果。
- 同一成员的零基 UTF-8 字节 `4209383` 附近可查 `gL(E)` 临时采样及 `wPe(z, ne)` 姿态应用。隔离复核中源网格索引保持原状。 [桌面安装包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
- 注册、参数、事件和超时分支来自对安装包的静态核查。不同盘模式的实际布局、面板取消后的可见结果及超时后的编辑器状态仍需桌面实测。
- **模型可见声明。** 本机 rollout 第 2 行 `additional_tools` 事件中的 `exec.description` 含注册原文。该样本的工具调用轨迹未覆盖打印摆盘。 [声明记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:2>)
- **待实测。** 比对不同公开盘模式的实际布局、面板取消后的可见结果，以及等待超时后编辑器中的摆盘状态。
