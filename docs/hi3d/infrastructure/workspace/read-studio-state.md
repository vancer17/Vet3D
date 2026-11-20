# 读取当前视窗状态

核查对象为本机 Hi3D Agent 1.2.11（Windows x64）和随包 Codex 0.166.0。本节点位于工作区基础设施层，提供内置 Studio 已加载模型的身份、就绪状态和当前场景统计。

## 业务定义

| 项目 | 节点契约 |
| --- | --- |
| 触发条件 | 用户指代「当前模型」「我现在看到的版本」，任务依赖实际加载的模型，或加载、摆盘、修订后需要复核。只处理已明确的工作区文件时，可直接按文件引用执行。 |
| 上游与输入 | 接收[当前轮的工作区上下文](llm-context.md)提供的工作区、线程、轮次和用户指代。若任务包含领域评审，另核对本次采样所需的 Skill 正文、阶段依赖及媒体已经交付。若任务指定版本，从[素材与模型版本查询](query-assets-and-model-versions.md)取得预期模型引用。预期版本由调用方保留，`studio_get_state` 的工具参数为 `{}`。 |
| 输出 | 返回 Studio 当时的就绪状态、已加载的工作区和文件名、模型家族、摆盘标志，以及可用的尺寸与部件统计。无已加载身份时返回空状态。宿主不可用或作用域变化时返回工具错误。 |
| 完成条件 | 收到本次调用在当前作用域的成功回包，即取得快照。`ready: false` 表示这次读取已完成，模型尚未就绪。下游依赖某个具体模型时，须核实同一工作区内已就绪的实际加载版本，并核对任务所需的统计或证据。 |
| 下游交接 | 交付已确认的版本引用和本次观察到的状态。文件操作先将版本解析成实际路径。需要切换版本时进入[加载指定版本并确认](load-studio-revision.md)，需要核对外观时交给截图或渲染及视觉验收。只有生成输入确实引用当前模型时，才将解析出的文件路径交给[生成前预检](../../atomic-nodes/preflight-generation.md)。 |

## Skill 绑定

单独读取状态走桌面宿主通用入口。随包工作区 `templates/AGENTS.md` 第 42 行指导使用 `studio_*` 完成需要在视窗确认的操作。下表的生成和领域评审规则在相应 Skill 选用后适用。依赖领域评审时，核对有效修订的 `SKILL.md` 和当前阶段文件已通过输入片段或可读工具回包进入采样。 [Skill 选用](llm-context.md#有效目录与选用) · [阶段依赖](llm-context.md#阶段依赖) · [Hi3D Agent 1.2.11 归档说明](../../upstream/1.2.11/README.md)

| 归档 Skill | 作用与选用条件 | SHA-256 |
| --- | --- | --- |
| [hi3d/SKILL.md](../../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | **通用生成入口。** 任务同时执行生图或图生 3D 时，按其规则处理生成、候选、模型登记与原作业恢复。读取当前 Studio 状态由宿主工具提供。 | `4c268ae14ece561234682d564cdfa6264c1f121a9ea118137c0388a9240c217d` |
| [image-to-assembly/SKILL.md](../../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) | **静态装配领域 Skill。** 仅在选择部件重建、配准与装配时，按其要求完成粗模、部件和整体的环绕及结构验收。读取状态可以核对检查对象，放行仍使用实际环绕证据。 | `cf4ec08dec0decfd69560a940cc26ea18fecf559ea87852c269fd2682555705f` |
| [head-reference/SKILL.md](../../upstream/1.2.11/prebuilt-skills/head-reference/SKILL.md) | **头部参考图领域 Skill。** 仅在选择该图像流程时，按姿态基准、版本绑定和人工确认评审候选参考图。其图像评审以实际图像和逐项证据为依据。 | `7e7fa5b0cd74928feac546a64edb0d71c77d66f6e5756bfef8c528523af95795` |

## LLM Tools

模型可见描述原文、通用参数及实现由各独立工具页维护。 [工具索引](../../tools/README.md)

| LLM Tool | 用途摘要 | 本节点的调用时机和条件 |
| --- | --- | --- |
| [studio_get_state](../../tools/studio-get-state.md) | 读取内置 Studio 的已加载身份和统计。 | 用户指代当前模型、视窗操作依赖确切版本，或需要重新核对已加载结果时调用。 |
| [studio_load_revision](../../tools/studio-load-revision.md) | 将指定版本加载到 Studio 并返回确认状态。 | 任务要求显示具体版本，且查询发现目标尚未加载或加载了其他版本时调用。目标不明确时先解析版本。 |
| [studio_capture_view](../../tools/studio-capture-view.md) | 截取当前 Studio 画面并登记截图产物。 | 任务需要当前画面的视觉证据，且已核实视窗实际加载版本时调用。回包提供产物 ID 和尺寸。 |
| [user_interaction](../../tools/user-interaction.md) | 通过宿主收集用户输入。 | 当前模型不可解析，存在多个合理候选且选择会改变操作对象时，用于澄清指代。 |
| [view_image](../../tools/view-image.md) | 将指定本地图像提供给模型。 | 下游确需视觉验收，且已取得对应版本的截图或渲染文件路径时使用。 |
| [exec](../../tools/exec.md) | 承载 Code Mode 下的嵌套工具调用。 | 当前工具声明将 Studio 工具暴露在 `exec` 内时，以嵌套形式发起读取。 |
| [wait](../../tools/wait.md) | 按 `cell_id` 续查 Code Mode 执行单元。 | 仅当 `exec` 返回仍在运行的执行单元且需要取得本次结果时，用原 `cell_id` 续查。 |
| [hi3d_api](../../tools/hi3d-api.md) | 执行或恢复生成作业。 | 只在目标模型还依赖已有远端作业时，由生成流程按原记录使用 `wait`、`query`、`download` 或条件性 `adopt`。 |

`studio_get_state`、`studio_load_revision` 和 `studio_capture_view` 由桌面 renderer 提供并注册为动态工具。`item/tool/call` 是 app-server 的 RPC 方法，`runtime:respond` 是 Electron IPC，`modelLoaded` 是视窗加载事件。独立工具 `wait` 按 `cell_id` 查询执行单元，`hi3d_api` 的 `wait` 动作按生成作业查询。领域 Skill 的评审脚本属于本地实现。安装包提供注册证据，宿主契约和所选 Skill 提供调用条件，生产 rollout 记录了实际状态读取和加载。

## Hi3D 实现

### 决策

用户明确指定文件或版本时，由[工作区查询](query-assets-and-model-versions.md)解析路径。用户指代当前画面时，读取 Studio 当前确认加载的身份。工作区版本列表由 `workspace/open` 和 `workspace/modelUpdated` 更新，列表选中项可先于实际加载变化。普通 `turn/start` 发送本轮消息、附件和可选 Skill。此时模型要取得实时视窗状态，需等待新的状态工具回包。 [模型可见内容的组装](llm-context.md#形成模型可见内容)

### 执行

**根据生产行为重建的 Code Mode 请求。** `exec` 输入以下 JavaScript。传给 `studio_get_state` 的对象为空，线程、轮次和请求关联信息由宿主提供。

```javascript
const result = await tools.studio_get_state({});
text(result);
```

1. **注册和转发。** renderer 的 `mS` 在 `thread/start` 附加 `S0e` 中的工具定义，Runtime 的 `prepareAppServerParams` 将其与自己的动态工具合并。Codex 发出 `item/tool/call` 后，Runtime 转发桌面工具请求，并用请求 ID 保存原 app-server 调用的关联。renderer 的 `vi` 检查当前打开的线程、活跃轮次和工作区 `cwd`，记录会话代次和取消信号。
2. **读取当前句柄。** `M0e` 立即检查是否有已挂载的 `StudioHost`。未挂载时返回工具错误。已挂载但还没有已加载模型身份时，返回 `ready: false`、空身份、`arranged: false`、`physicalSize: null` 和空部件列表。已加载模型属于其他工作区时返回工具错误。取得结果后再次核对调用作用域、视窗句柄及工作区。
3. **从视窗内存取值并交付。** `StudioHost` 将加载目标和确认加载的身份分开保存。新加载代次开始时清除旧身份，`modelLoaded` 只有匹配当前代次、线程、工作区和适用轮次时才写入新身份并置为就绪。模式切换也可能使 `ready` 变为 `false`，同时保留原身份。renderer 把当时的状态编码为 `contentItems` 中的 `inputText` JSON，主进程经 IPC 转发，Runtime 按原请求 ID 交回 Codex。在样本的 Code Mode 路线中，外层 `custom_tool_call_output` 携带结果并与 `exec` 使用相同的 `call_id`，供后续采样使用。

**实现伪代码。** 概括状态查询路径。空状态分支返回后，外层仍核对会话作用域。错误在工具应答中与正常空状态分开表示。省略统一的额度门禁和消息封装。

```python
def read_current_studio_state(call, desktop):
    scope = desktop.capture_active_scope(call)
    if not scope.matches_thread_turn_and_cwd():
        return tool_error("inactive_context")

    studio = desktop.studio_handle
    if studio is None:
        return tool_error("studio_unmounted")

    loaded_asset = studio.get_state()["assetId"]
    if loaded_asset is None:
        return success(empty_state()) if scope.is_current() else tool_error("stale_context")
    if loaded_asset != scope.asset_id:
        return tool_error("different_workspace")

    snapshot = studio.get_state()
    if not scope.is_current() or desktop.studio_handle is not studio:
        return tool_error("stale_context")
    if studio.get_state()["assetId"] != scope.asset_id:
        return tool_error("workspace_changed")
    return success(snapshot)
```

`ready` 来自 `StudioHost` 的加载状态。`arranged` 优先取模型管理器的摆盘标志。`physicalSize.bboxMm` 是当前网格顶点经世界变换后的轴对齐包围盒跨度，乘以 `mmPerUnit` 得到毫米值。默认 `auto` 策略在 GLB 含受信的 `sparc3dPhysicalUnits` 米制标记时采用文件尺度，返回 `source: "file"`。其余情况以初始最长边 75 mm 建立换算比例，返回 `source: "default-longest"`。`parts` 来自模型管理器的网格列表，部件名可回退为 `part_1` 等，面数优先用三角形索引计数除以三向下取整，其次用位置属性计数，两者均不可用时省略 `faceCount`。统计不可用时，仍可返回已加载身份、空尺寸和空部件列表。

**根据已核查实现重建的成功负载。** 下例为 `contentItems[0].text` 解码后的 JSON，尺寸与面数为示例值。即使工作区已登记 `hi3d-cat_3.glb`，若 Studio 仍加载 `_2`，当前视窗状态仍应返回 `_2`。

```json
{
  "ready": true,
  "assetId": "asset_example",
  "modelName": "cat",
  "fileName": "hi3d-cat_2.glb",
  "arranged": false,
  "physicalSize": {
    "mmPerUnit": 25,
    "source": "default-longest",
    "bboxMm": { "x": 75, "y": 52, "z": 31 }
  },
  "parts": [{ "name": "body", "faceCount": 24000 }]
}
```

状态请求没有图片字段。主图和补充参考用实际素材引用随上游图像计划传递，目标方向和必保特征随生成或验收要求传递。需要当前画面时，将实际加载版本和观察目标交给[获取模型的视觉证据](acquire-model-visual-evidence.md)。该节点说明 Studio 截图、文件解析、像素交付和取证失败时的恢复方式。 [图片角色与方向](../../atomic-nodes/generate-new-view.md#业务定义)

### 验收

先确认回包属于当前工作区、线程和轮次发起的本次调用。已取得的快照按以下条件交接。

| 结果 | 验收与交接 |
| --- | --- |
| 工具失败 | 没有可交付的状态，按宿主错误或作用域变化定位。 |
| 成功，`ready: false` | 可报告本次状态已取得、视窗未就绪。需要实际模型版本的后续操作等待就绪。 |
| 成功，`ready: true`，加载版本与任务目标不符 | 可报告实际加载版本。需要操作目标版本时，先解析并按任务要求加载目标，再核对状态。 |
| 成功，`ready: true`，工作区和加载版本满足任务 | 交付实际加载版本及所需统计。按文件执行时解析实际路径，视觉验收另取得对应版本和方向的画面。 |

返回字段覆盖身份、就绪及场景统计。面板可见性、相机参数、图像像素和具体加载失败原因需另取证据。查询前后复核会话、句柄和工作区，当前实现的检查范围未包含同一工作区内的文件版本锁定或跨读取比较。 [状态工具返回](../../tools/studio-get-state.md#参数与结果)

## 完成与恢复

| 情形 | 处理方式 |
| --- | --- |
| `exec` 交回 `cell_id` | 用同一执行单元 ID 调用 Code Mode `wait`。原句柄失效且任务仍需要实时状态时，在当前作用域重新执行只读查询。 |
| Studio 未挂载、未就绪或版本不符 | 宿主未挂载时先处理宿主错误。`ready: false` 已完成本次读取，结合加载结果或桌面反馈判断空闲、加载中或失败。需要已就绪版本时，在加载状态变化后重新读取，或按任务要求加载指定版本。 |
| 恢复线程、切换活动轮次、视窗或工作区、加载新版本 | 任务仍指代「当前模型」时，重建调用作用域并读取新快照。旧读数保留为历史证据。明确指定的文件继续按其所属工作区和原版本核对。 |
| 上游生成返回 `pending` | 继续等待原 `jobPath`，使用已保存的远端任务 ID 查询。成功后从同一作业下载至原输出位置，取得需展示的已登记版本，再加载并读取状态。视窗查询本身没有远端作业。 |
| 上游提交状态不明 | 保留原请求、作业和候选记录。有任务 ID 时续查原任务，缺 ID 时先核对平台任务历史。后续处理沿用已确认的原任务。 |
| 候选已取得但未通过验收 | 保留原作业的成功状态、候选版本和失败证据。按实际问题修订图像或模型，复查修订后的证据。若修订需要再次生成，另建作业及输出位置。需要展示新模型时，登记并加载新版本后再次读取。 |
| 可以回填或交付 | 将已核实的状态和版本交给需要当前模型的下游。模型或图像候选须满足目标版本、方向、主体、姿态和必保特征等适用条件，并通过相应验收后，才回填或进入下一步。 |

[生成作业的完成与恢复](../../atomic-nodes/preflight-generation.md#完成条件与恢复) · [图片候选验收与修订](../../atomic-nodes/edit-existing-view.md#完成条件与恢复)

## Vet3D 迁移与核查范围

Vet3D 的 LLM、生图模型、3D 模型及 API 均待选型。工作区宿主应提供供应商无关的视窗快照，分别记录**已登记版本、用户所选版本和视窗已确认加载版本**。读取接口从调用上下文取得工作区、线程和轮次，输出可追溯的版本引用和加载阶段。视窗代次和读取时刻属于 Vet3D 建议新增的快照字段，Hi3D 1.2.11 的状态回包未暴露这两项。需要观察画面时，再取带相同版本和观察方向的证据。单位来源、相机状态及是否可见可按实际可用性记录，缺失时保留未知。

当用户指代「现在看到的模型」时，把返回的加载版本和视窗代次绑定到该次操作。写入或提交前，按操作语义核对原引用。用户切换版本后，依赖当前画面的操作应重新确认；已明确锁定某个文件的操作继续按该文件和版本处理。主体基准、补充参考、目标视角及必保特征仍由建模流程维护。

- **已静态核查。** 本机 `resources/app.asar` 的 SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。其中 `out/renderer/assets/index-CDPCug_K.js` 的 `S0e`、`mS`、`vi`、`M0e` 和 `StudioHost` 提供注册、作用域、状态与响应证据，`X6`、`getRealSizeMm` 和 `bt` 提供尺寸与部件统计证据。`out/preload/index.js`、`out/main/index.js` 和 Runtime 的 `forwardConfirmedServerRequest`、`handleServerResponse` 提供回传链路证据。
- **生产记录已核查。** 活跃样本 `rollout-2026-11-11T11-31-29-*` 的第 154→160、327→330 行记录两次成功返回 `ready: false` 和空身份。第 523→528 行记录一次 `ready: true`，含加载身份、尺寸和部件统计。三次调用均通过 `exec` 交付配对结果。 [状态工具核查依据](../../tools/studio-get-state.md#核查依据)
- **离线检查范围。** 示例请求、负载和分支使用合成值。模拟句柄覆盖未挂载、空状态、工作区不匹配、过期上下文、未就绪和成功返回。
- **仍待验证。** 真实桌面会话中的视窗切换和加载竞争、以已知尺寸的 GLB 校验单位换算和摆盘后读数、实际截图的版本与画面，以及截图路径交付。云端输出与画质在对应生成和视觉验收节点核查。
