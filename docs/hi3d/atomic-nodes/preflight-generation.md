# 生成前预检

分析对象为 Hi3D Agent 1.2.11（Windows x64）。本次复核使用原安装目录 `D:/install/Hi3DAgent` 的事务备份。本文以已有参考图的多视图 3D 生成作为主例，并说明图片生成共用的预检分支。Vet3D 的计划冻结机制是拟议设计。

## 业务定义

当任务准备发起一次图片或 3D 生成时，先检查输入和参数能否组成可提交的请求。参数选择、请求校验和正式提交前的完整性检查都属于这段链路。用户更换输入、生成目标或影响提交的配置时，重新规划受影响的请求。

| 项目 | 节点契约 |
| --- | --- |
| 触发条件 | 已确定要发起一次图片生成、图片编辑或 3D 生成，并具备该动作所需的输入引用。仅检查计划时可显式预检。更换文件、方向或影响提交的配置后，重新检查受影响的计划。 |
| 上游 | 从[构建当前轮的工作区上下文](../infrastructure/workspace/llm-context.md)取得线程绑定的工作区及素材引用；需要既有文件或模型时，从[查询工作区素材与模型版本](../infrastructure/workspace/query-assets-and-model-versions.md)解析实际路径。[确认建模主体](confirm-modeling-subject.md)交付主体与姿态。图片请求接收[生成新视角](generate-new-view.md)或[编辑已有视角](edit-existing-view.md)准备的主图、补充参考、目标方向和必保特征。多视图 3D 使用[整组视图验收与定稿](review-and-finalize-view-set.md)选定的版本和用途，并接收[多视图按位置配对](pair-multiview-inputs.md)交付的实际文件、顺序及方向。 |
| 输入 | 工作区内的输入引用、视图语义与图片角色、生成目标、用户已选参数、作业标识及输出位置。多视图计划附带可追溯的定稿版本依据。Hi3D 的普通工具参数只传文件及方向，领域审查记录另由调用方保留。 |
| 输出 | Hi3D 可返回展开后的请求及选项状态、待选参数或校验错误。`waiting_choice` 由宿主面板答复驱动，远端 `pending` 通过已有任务 ID 续查。Vet3D 可统一预检输出为 `ready`（可交接计划）、`needs_input`（待选项和原输入引用）及 `invalid`（字段级错误）。 |
| 完成条件 | 请求通过本地检查，必要选项已经确定。显式预检到此返回。正式生成检查输出位置，新作业复核上传字节及账号后进入远端提交。可复用的已有作业按原记录恢复。 |
| 下游 | 交付实际参与生成的输入及其顺序、角色、方向、已解析参数和作业路径。作业进入提交、等待和下载。产生的图片候选按目标提供给自己的视觉审查，补图或修订结果交给整组验收决定是否进入定稿。下载后的 3D 产物进入[候选检查、登记与加载](#3d-候选的检查和登记)。 |

预检检查可提交性。一次任务可在补图和后续 3D 提交前分别进入预检。视图组的主体、姿态、视角内容、质量和入选版本由整组验收确认。预检检查配对后的请求字段、后端能力和当前待上传文件，额度、服务受理和生成结果由后续服务与验收环节确认。

上游查询交付素材路径和模型版本的选择依据。模型家族的最高序号、工作区最近修改的版本和 Studio 实际加载的文件可以各自指向不同模型版本。只有请求以「当前视窗里的模型」为生成输入时，先[读取当前视窗状态](../infrastructure/workspace/read-studio-state.md)，核对工作区和已就绪的 `fileName`，再将版本解析为实际文件。无法确认视窗版本时先解决指代，已有明确路径的输入按文件预检。需要为已有模型生成纹理时，将选定 GLB 的实际路径传入 `mesh`。预检按本次调用参数重新核对工作区路径、文件大小和 SHA-256。 [原生输入字段](../tools/hi3d-api.md)

## Skill 绑定

下表链接到仓库内归档的 [Hi3D Agent 1.2.11 原文快照](../upstream/1.2.11/README.md)。

| Skill 文档 | 作用与选用条件 | SHA-256 |
| --- | --- | --- |
| [`hi3d/SKILL.md`](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | **通用入口。** 指导图生 3D、图片生成、参数选择与作业恢复。普通多视图使用用户真实提供且标明方向的图片，包含正面。归档 Skill 指导先显式 dry-run，并将待选参数交给宿主。1.2.11 桌面 Runtime 给常规生成另行注入直接使用内置预检的指导，并自行打开参数面板。 | `4c268ae14ece561234682d564cdfa6264c1f121a9ea118137c0388a9240c217d` |
| [`image-to-assembly/SKILL.md`](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) | **静态装配领域 Skill。** 选用部件建模、配准和装配路线后，按部件检查视图、来源、方向和生成前粗模环绕。`reviewed_submit.py --backend runtime` 是本地交接脚本，验证方向清单及输入哈希后返回宿主调用参数，再由通用工具执行。 | `cf4ec08dec0decfd69560a940cc26ea18fecf559ea87852c269fd2682555705f` |
| [`head-reference/SKILL.md`](../upstream/1.2.11/prebuilt-skills/head-reference/SKILL.md) | **人像头部参考图领域 Skill。** 仅在选用头部参考图流程时先确定转正或保留原姿态的基准，再按评审契约核对实际图像、提示词和输入版本。必查项通过并按该领域流程完成人工确认后，才交接图片。 | `7e7fa5b0cd74928feac546a64edb0d71c77d66f6e5756bfef8c528523af95795` |

普通整件多视图沿用通用入口。装配视图审查、粗模环绕、头部评审矩阵及对应本地脚本只在选用相应领域 Skill 后执行。 [装配视图规则](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/view-conventions.md) · [头部评审契约](../upstream/1.2.11/prebuilt-skills/head-reference/references/review.md)

## LLM Tools

模型可见描述、工具参数和通用实现维护在[独立工具索引](../tools/README.md)下。本表仅记录在本节点中的用途。

| LLM Tool | 用途摘要 | 调用时机与条件 |
| --- | --- | --- |
| [`hi3d_api`](../tools/hi3d-api.md) | 规划、提交和恢复图片或 3D 作业。 | 用 `defaults` 查看本地默认配置。普通生成走 `generate_3d` 或 `generate_image` 的内置预检，只检查计划时显式传 `dryRun: true`。收到 `parameters_selected` 时用 `next_call` 续调。有任务 ID 时从原记录 `query`、`wait` 或下载；从可靠来源找回原任务 ID 时可用 `adopt` 建立独立查询记录。 |
| [`user_interaction`](../tools/user-interaction.md) | 让宿主收集用户输入、偏好或授权。 | 需要另行澄清业务信息时显式调用。进入重复提交风险确认分支时用 `kind=confirmation`。内置生成参数面板由 Runtime 发出 `interaction/request`。 |
| [`view_image`](../tools/view-image.md) | 将本地图送入模型上下文供查看。 | 输入需要回到上游复审，或下游需要查看生成候选时使用。视觉结论由相应的审查环节记录。 |
| [`workflow_report`](../tools/workflow-report.md) | 上报 Skill 执行进度及产物归属。 | 本轮实际执行显式选择或隐式选定的 Skill 时使用。首次执行按工具约定用 `inspect`、`plan`，继续已中断的 Skill 作业时先用 `resume`。有对应节点时，用 `node` 上报实际预检状态。 |

`hi3d_api`、`user_interaction` 和 `workflow_report` 是 Hi3D Runtime 动态工具，`view_image` 由随包 Codex 提供。`generate_3d`、`generate_image`、`submit`、`wait` 属于同一工具的动作。`EDIT`、`MULTI_VIEW_EDIT` 等是原生请求枚举，Python 的 `build_plan`、`reviewed_submit.py` 是本地实现。

## Hi3D 的实现

### 决策

当前 Runtime 的工具定义支持直接调用 `generate_3d` 或 `generate_image`，也支持显式 `dryRun`。Runtime 注入的桌面指令要求常规生成直接调用正式动作，由同一次调用先在本地校验。显式 `dryRun` 用于查看展开后的计划，参数未齐全时仍可能触发本地面板。正式调用要求已配置桌面账号代理，实际账号校验在提交路径中发生。来源见 `resources/runtime/dist/runtime.mjs` 的 `dz[0]`、`Rg.run` 和 `Kj`。 [工具定义与预检分支](../tools/hi3d-api.md) · [归档 Skill 的参数面板规则](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#参数面板)

Python 分别处理选项与请求。桌面 Runtime 将 `settings` 传入 Python 的覆盖参数，普通 3D 从中提取 `model_type` 和 `generation_type`，只为缺少的选项生成问题。随包默认值或原生 `request` 中的 `modelType`、`generationType` 用于构造请求，面板门禁仍需对应的选择。普通 3D 推荐 `v3.0:quality` 和 `both`。`v3.0:quality` 映射为原生 `modelType=standard`，`v3.0:master` 映射为 `modelType=quality`。选择 `texture` 会转入贴图场景，并按选项检查档位和已有网格。浮雕和拆件使用各自的选项，多色及图片生成没有预定义的必选面板项。 [参数面板与原生映射](../upstream/1.2.11/prebuilt-skills/hi3d/references/web-option-gates.md)

**权限、额度与确认的执行位置。** Runtime 按线程和工作区检查动态工具请求。新作业组包后，Python 通过桌面代理的 `GET /v1/session` 取得当前账号和环境。Electron 主进程检查本机代理凭证、路由白名单和登录会话，再核对生成请求的账号和环境。网页会员选项的限制属于 Web 分支，桌面预检检查所选参数和输入是否兼容。已有作业按原账号和环境查询。 [桌面参数契约](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-parameters.md) · [参数门控范围](../upstream/1.2.11/prebuilt-skills/hi3d/references/web-option-gates.md)

工具转发会经过 `skillCredits.confirm` 的线程与轮次检查。1.2.11 发行包默认关闭付费 Skill 确认和累计积分提醒。普通生成提交前没有余额查询，账号菜单单独查余额。代理转发后，由服务响应报告余额不足（`30010000`）、扣费需确认（`30010001`）、套餐并发上限（`1003/10030106`）或功能额度耗尽（`1003/10030107`）。`30010001` 返回解释费用并取得明确确认的处理指引。偏好面板的超时默认只填写选项，独立确认需要用户明确接受。Runtime 观察到新任务 ID 已落盘后才发出本地用量估算，实际扣费以服务端为准。 [工具错误与副作用](../tools/hi3d-api.md#返回与错误) · [通用交互结果](../tools/user-interaction.md#参数与结果)

### 执行

1. **Runtime 校验工具入参。** 从工具调用的 `threadId` 查工作区注册表，将实际 `cwd` 经 `SPARC3D_TOOL_WORKSPACE` 交给随包 Python。检查动作、字段类型、条件必填项和本地路径。`generate_3d` 需要 `jobPath`、`outputDir`，省略 `kind` 时走 `model`。Runtime 把工具参数中的实际文件路径、视角、设置和原生请求传给 Python。多视图的路径由上游选定版本及其配对结果提供。实际读取以 `images` 中的路径为准，3D 槽位来自同序的 `views` 或 `imageSlots`。
2. **Python 计算选项状态并验证计划。** 先运行 `gate_parameter_overrides`，再运行 `build_plan`。普通 3D 从随包默认值或显式原生 `request` 构造请求，再叠加转换后的 `settings`。本地图须存在、非空，扩展名为 PNG、JPEG 或 WebP，每张最多 40 MiB，并计算 SHA-256。此处只检查文件和后缀，像素需由上游验收；会话可看图的范围更宽。当前桌面文件接口最多四张图。多张本地图须使用 `views` 或 `imageSlots` 之一，并与 `images` 逐项对应。具名方向限前、后、左、右，数字槽限 0–3，方向和槽位在各自列表内须唯一。即使缺选项，输入错误也会在返回 `waiting_choice` 前被拒绝。图片分支还校验最终请求中的任务枚举和 4000 字符提示词上限。 [导入与 3D 文件的交接](../infrastructure/workspace/import-reference-materials.md#作为-3d-输入的交接)
3. **挂起原工具调用并打开面板。** 正式调用缺选项时，Python 返回顶层 `waiting_choice`，退出码为 `2`。显式 dry-run 将同一状态放入 `consent`，退出码为 `0`。Runtime 校验 `preference` 面板，分配 `requestId`，将其与原工具调用、线程、轮次及已校验工具参数关联，再发出 `interaction/request`，等待桌面宿主答复。
4. **接收答复并产生续调。** 手动作答或点击采用推荐值返回 `answered/user`。生成参数面板的 60 秒只在界面可见、获焦、用户尚未编辑时累计。超时返回 `defaulted/assistant_default`，Runtime 校验答案是否逐项匹配默认值。有效答复返回 `parameters_selected` 和 `next_call`，只将答案合并进 `settings`。续调保留原图片、视角、作业与输出路径及 `dryRun`，由 Agent 发起第二次工具调用并重新规划。无效答复保留等待项，宿主错误转发给原调用。面板取消返回 `cancelled` 且无 `next_call`。整轮中断时，Runtime 按线程和轮次清理挂起的调用，返回外层取消状态并通知桌面关闭面板。
5. **正式提交前检查输出和输入。** 参数就绪时，显式 dry-run 在构造远端客户端前返回本地计划。Runtime 也会检查组合生图的输出文件名和路径，包含显式 dry-run。正式组合调用检查实际输出目录。没有可复用记录的新提交重读文件并组包，按本次正式计划复核字节数和 SHA-256，multipart 总量上限为 512 MiB。
6. **同路径串行与复用。** Runtime 按解析后的 `jobPath` 串行执行。Python 对比已有记录的后端和指纹，一致就跳过上传和 POST，按原作业结果继续处理，指纹冲突则拒绝覆盖。无 ID 的 `submitting` 或 `submission_uncertain` 记录可能在 Python 重算计划前被 Runtime 拦截。新作业经账号检查后排他创建初始记录，防止并发覆盖。图片未显式传 `jobPath` 时，Runtime 从解析后的 `outputPath` 推导路径，恢复以实际返回的作业路径及原输出位置为准。

**根据源码重建的首次提交写入顺序。** 图片从 `data.taskId` 取 ID，3D 从 `data.jobId` 取 ID。先持久化 ID 可在后续提交元数据处理失败时沿原作业恢复。

```text
复核并组包 → 通过桌面代理校验账号和环境 → 排他写入 submitting（无 ID）
→ POST → 校验 HTTP 200、业务 code 200、data 对象和 ID 格式
→ 保存 task_id（仍为 submitting）→ 处理父任务信息 → 保存 queueing 和 submitted_at
```

面板证据见 `runtime.mjs` 的 `handleRuntimeDynamicTool`、`handleServerResponse`、`cancelInteractions` 与 `fg`，以及 `app.asar` 的 `out/main/index.js:29` 和渲染器 `index-CDPCug_K.js:145,148`。权限和提交证据见 Runtime 的 `Gge`、`Rg.run`、`Tg`，桌面主进程的代理 `_l.handle`，以及随包 `hi3d/scripts/hi3d_api.py:126,177`、`hi3d_generation_workflow.py:11`、`hi3d_jobs.py:192`、`hi3d_storage.py:25,175`。 [工具返回与恢复](../tools/hi3d-api.md#实现伪代码)

**根据已验证行为重建的多视图请求。** 假定四个文件已经通过上游审查，`images` 和 `views` 同序绑定。正面图占用 `front` 槽，其余图提供对应角度的观测。普通 3D 请求没有独立的主图、辅助图或文本必保字段。主体基准和必保特征保留在上游记录，供选图和结果验收。这个请求已经填写两个面板选项，预期返回 `consent.result: "ready"`、四张图和槽位 `[0,1,2,3]`。

```json
{
  "action": "generate_3d",
  "targetName": "猫",
  "images": ["inputs/front.png", "inputs/back.png", "inputs/left.png", "inputs/right.png"],
  "views": ["front", "back", "left", "right"],
  "settings": {
    "model_type": "v3.0:quality",
    "generation_type": "both"
  },
  "jobPath": "hi3d/cat.json",
  "outputDir": "exports/hi3d-cat",
  "dryRun": true
}
```

**根据已验证行为重建的图片请求。** 已确认主体且另有补图需求时，可预检一张背面候选。首图是本次编辑主图，第二张只提供躯干比例和可见毛纹参考。`EDIT` 分支的目标方向和必保特征通过 `prompt` 传递。正式组包时首图映射为 `baseImage`，其余为 `referenceImages`。实际背面候选仍需生成并看图。定向修订已有视图时，`MULTI_VIEW_EDIT` 将本地图和对应方向组包为 `viewImages` 与 `viewKeys`，通过 `request.editedViewKeys` 指定要改的方向，保留项写入 `prompt`。 [图片生成参考](../upstream/1.2.11/prebuilt-skills/hi3d/references/image-generation.md) · [定向编辑节点](edit-existing-view.md)

```json
{
  "action": "generate_image",
  "targetName": "猫",
  "imageMode": "edit",
  "images": ["inputs/front.png", "inputs/left.png"],
  "request": { "editTaskType": "EDIT" },
  "prompt": "以首图锁定猫的身份和站姿，左侧参考仅约束躯干比例和可见毛纹。生成正对背部的一张图，只改变观察方向，保持体型、耳缘和尾部姿态。",
  "aspectRatio": "1:1",
  "jobPath": "hi3d/cat-back.json",
  "outputPath": "exports/hi3d-cat-back.png",
  "dryRun": true
}
```

**实现伪代码。** 下例概括 Python 返回、Runtime 挂起和异步回调。进入待选分支前，Python 仍须完成请求校验。`reply_tool` 向原调用发送工具结果，示例仅展示续调所需的业务字段。整轮中断走单独的清理逻辑。

```python
def execute_generation(args):
    gate, overrides = gate_parameter_overrides(args.kind, args.settings)
    if args.action == "generate_image":
        plan = image_plan(args, overrides)
    else:
        plan = build_plan(args, overrides)

    if args.dry_run:
        return preview(plan, consent=gate), 0
    if gate["result"] == "waiting_choice":
        return gate, 2

    return submit_or_resume(job_path=args.job_path, plan=plan)


def handle_generation_result(call, args, result):
    gate = result if result.get("result") == "waiting_choice" else result.get("consent", {})
    if gate.get("result") != "waiting_choice":
        return reply_tool(call, result)

    panel = parse_preference_panel(gate["user_interaction"])
    request_id = pending.register(call, args, panel)  # call 包含线程和轮次
    emit_interaction_request(request_id, panel)


def handle_panel_reply(request_id, response):
    entry = pending.get(request_id)
    if entry is None:
        return
    if response.is_host_error:
        pending.remove(request_id)
        return reply_error(entry.call, response.error)
    if not valid_preference_reply(entry.panel, response):
        return  # 保留等待项

    pending.remove(request_id)
    if response.status == "cancelled":
        return reply_tool(entry.call, {"result": "cancelled", "interaction": response})

    args = entry.args
    settings = {**args.get("settings", {}), **response.answers}
    return reply_tool(entry.call, {
        "result": "parameters_selected",
        "interaction": response,
        "next_call": {**args, "settings": settings},
    })
```

面板载荷无效时，`parse_preference_panel` 使原调用报错。有效结果完成原工具调用，Agent 再使用 `next_call`。整轮中断时，Runtime 向匹配的原调用直接返回 `{status: "cancelled", source: "user", answers: {}}`，并发出 `serverRequest/resolved`。 [工具的结果与回调契约](../tools/hi3d-api.md#返回与错误)

### 参数展开与就绪边界

普通 3D 以原生 `request` 或随包默认请求作底稿。面板选择先转换成原生键值，再随覆盖参数交给 `build_plan`。`build_plan` 先应用兼容的旧 `model`、`resolution`、`request_type`，再写其余覆盖项：`scene` 和 `version` 写入请求顶层，其余写入 `otherParam`。遇到缺项时的推荐值用于面板，原生底稿里已有 `modelType`、`generationType` 不会代替选项。 [原生选项映射](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/web_option_gates.py:485>) · [覆盖与字段校验](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_parameters.py:61>)

**根据离线实测重建的核心分支（实现伪代码）。** 此片段只展示 Python 的参数展开与控制流，实际返回还包含已选参数和计划摘要。Runtime 对首次 `waiting_choice` 的处理仍按前述面板流程执行。

```python
gate, overrides = gate_parameter_overrides(kind, settings, native=True)
plan = build_plan(kind, images=images, request=request, overrides=overrides)
if dry_run:
    return preview(plan, consent=gate), 0
if gate["result"] != "ready":
    return gate, 2
return execute_generation(create_client(), plan, job, output_dir)
```

| 观察到的组合 | 规划器行为 | 验收用途 |
| --- | --- | --- |
| 文件合法、必选项缺失 | Python 显式 dry-run 返回 `consent.result: "waiting_choice"`（退出码 0），同一输入正式调用返回顶层 `result: "waiting_choice"`（退出码 2）。Runtime 两者都可挂起原调用并等待面板答复；参数续调保留原 `dryRun`，取消则没有续调。 | 收到参数答案后仍需执行 `next_call`。原调用为 dry-run 时，续调只生成计划。 |
| 缺项且文件检查失败 | `build_plan` 抛错后不会返回待选状态。 | 先修实际文件或方向配对，再用原意图重试预检。 |
| 旧 `request_type=2` 或原生 `scene=texture`，又选 `generation_type=both` | `both` 会覆写 `otherParam.generationType`，但不会重设 `scene`。带现有网格时，两种底稿均可得 `scene=texture`、`generationType=both`、`version=v2.1` 并返回 `ready`。 | 检查顶层场景、版本与生成内容相符；清理旧字段和冲突底稿后重验。需要对现有网格仅贴图时，走单一贴图参数路线。 [仅贴图的校验条件](../tools/hi3d-api.md#仅贴图参数门禁) |
| 数值或未知高级字段 | 规划器拒绝服务端专有字段和已知过时字段；离线示例中 `face=-10`、`pbr=25`、`shading=27`、`format=9999` 和未知 `futureUnknown=1` 原样保留，仍为 `ready`。 | `ready` 表示选项齐备且本地计划可建。供交付的面数、PBR、着色、输出格式及服务接受范围仍需按业务约束和实际服务结果查验。 |

### 验收

显式 `generate_3d` 预检返回 `request`、`image_slots`、`file_count` 和 `consent` 等摘要。核对展开后的场景、版本、生成内容、高级参数和选项状态，并将槽位与原调用的文件数组逐项对照。正式提交前还要复核实际输出目录是否可用，新作业的既有输出目录须为空。需要检查计划中的具体文件、大小和哈希时，可查看分阶段 `submit` 的显式 dry-run 返回的完整计划和指纹。两类 dry-run 都在构造客户端和 multipart 之前返回。multipart 的字段、顺序和字节复核来自单独的离线组包测试。正式调用会按当时的文件重新规划并验证。图片能否解码、是否记录同一只动物、方向标签是否符合画面及哪份文件最终入选，见整组视图验收记录。云端输出质量随后独立核实。 [预检返回与计划复用](../tools/hi3d-api.md) · [整组视图验收与定稿](review-and-finalize-view-set.md)

显式 dry-run 展开当前计划，已有作业的指纹比对发生在正式路径上。指纹覆盖后端、任务类型、展开的参数和按顺序排列的文件记录，包括槽位、绝对路径、字节数及 SHA-256。账号和环境在代理层核对，输出位置由组合动作及下载恢复逻辑另行核对。 [工具的计划与复用契约](../tools/hi3d-api.md#实现伪代码)

装配桌面交接将审查哈希留在独立的审计对象。参数面板续调沿用原路径和方向，正式规划按路径当前的字节计算哈希，组包与本次计划比对。待选期间或交接后发现文件内容、方向或当前定稿版本变化时，保留原请求，交回整组验收与定稿。取得新定稿后重新配对和预检，已有远端作业仍按原输入和记录续查。 [配对异常矩阵](pair-multiview-inputs.md#验收)

## 完成条件与恢复

| 情形 | 处理方式 |
| --- | --- |
| `waiting_choice` | 等待本地面板答复。无效答复保留等待项，用户作答或采用默认值通过校验后用 `next_call` 续调。原 `dryRun: true` 仍只检查计划。 |
| 面板取消或整轮中断 | 面板取消结束待选请求。整轮中断清理匹配的等待项；已进入正式提交的操作按原作业记录判断受理和恢复情况。 |
| 输入或参数校验失败 | 修正具体字段或文件，重新预检。 |
| 当前输入与视图定稿不符 | 保留已有任务与原定稿。变更文件、方向或用途时先复审受影响的视图，重新取得定稿和配对。只改变生成参数时复用同一份定稿并重新预检。 |
| 已选路径失效或用户改选模型版本 | 回到工作区查询核对实际路径及版本。若本次操作仍以当前视窗为目标，重新确认已加载版本，再对新的输入预检。已有远端作业时保留其原输入和作业标识，用原作业记录续查。 |
| `ready` 且只做显式预检 | 交付本地计划及适用边界。需要正式执行时，由调用方使用正式参数进入生成入口。 |
| 远端作业返回 `pending` | 保留 `jobPath` 和已有任务 ID，用同一记录 `query` 或 `wait`。成功后从同一作业下载，组合调用已下载时直接使用返回文件。 |
| `submitting` 或 `submission_uncertain`，有任务 ID | 保留原请求及作业，用原账号、环境和 `jobPath` 显式 `query` 或 `wait`。同路径再次调用组合生成可能只返回 `attention`。 |
| 提交受理不明，缺任务 ID | 超时、5xx、响应解析异常或缺少有效 ID 通常记为 `submission_uncertain`。保留原请求及记录。Runtime 通常返回 `attention` 和 `canQuery: false`。从可靠来源找回原 ID 后，可用独立路径 `adopt` 再查询。`adopt` 写盘前校验任务类型、ID 格式和当前会话，任务存在性和远端可访问性在后续查询时核对，ID 的历史归属仍需独立证据。 |
| 提交被拒绝或服务报告额度错误 | 客户端取得可分类的 HTTP 4xx 时记为 `submission_rejected`。HTTP 200 带 `30010000` 且响应无任务 ID 迹象时，Runtime 保留余额不足诊断，Python 作业仍可能为 `submission_uncertain`。其他已识别业务错误按其类别和处理指引报告。 |
| 查询失败或作业明确失败 | 查询失败时报告具体原因并结束当前轮，保留最后一次已知状态。明确失败时保留任务及产物。用户明确要求恢复后，按原作业状态续查或处理重试。 |
| 成功取得图片候选 | 保存原作业的成功状态、候选版本和来源。补图或修订候选交给整组验收处理回填、质量修订和定稿，预检只接收后续新请求的输入。 |
| 3D 下载完成，返回 `attention` 且 `phase: "register-model"` | 保留原 `jobPath`、任务 ID 和下载文件。核实该分支的实际错误及产物。若有多份 GLB，按当前用途取得候选证据，再选定、登记和按需加载。见[下游交接](#3d-候选的检查和登记)。 |

**受理不明后的重生确认。** 缺 ID 的普通生成触发 `requiresRegenerationConfirmation` 时，Runtime 指示 Agent 说明重复生成和可能计费的风险。3D 分支可以直接询问；图片分支先停止当前流程，等用户明确要求重试或恢复后再询问。获得明确确认后，按指引使用新的作业与输出路径，并保留原记录。客户端强制保护原 `jobPath`，已核查的新路径 POST 未发现校验与原作业绑定的确认凭据。免费重试另行保留原重试意图并复核额度。 [通用工具恢复契约](../tools/hi3d-api.md#返回与错误) · [免费重试规则](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-free-retry.md)

[通用调用与查询错误规则](../upstream/1.2.11/prebuilt-skills/hi3d/references/calling.md) · [图片任务与质量修订](../upstream/1.2.11/prebuilt-skills/hi3d/references/image-generation.md)

### 3D 候选的检查和登记

1. **保留原作业身份和实际产物。** 读取返回的任务 ID、作业路径及文件清单，按工作区、原输出目录和作业记录中的文件路径、大小及 SHA-256 确认来源。已返回有效 `registeredModel` 时使用其确切版本。存在多个 GLB 时，1.2.11 的组合调用不能自动选定唯一文件，已下载文件仍留在原作业中。 [组合调用的结果与错误](../tools/hi3d-api.md#返回与错误)
2. **核对候选适用性并选定文件。** 以当前用途和候选清单中的确切文件为准，核对所需证据。WebP 可提供作业外观线索，归到某份 GLB 须有独立证据。必要检查尚无结果时，保留候选和待查原因。取得足够证据后，将选定文件及依据交给[主模型选定与交接](select-primary-model-and-confirm-handoff.md)。 [核对候选对当前任务的适用性](check-model-candidate-suitability.md) · [获取实际模型画面](../infrastructure/workspace/acquire-model-visual-evidence.md)
3. **登记并按需加载版本。** 已选 GLB 位于工作区 `exports/` 内且文件名符合工具约束时，将实际路径作为 `exportPath`，用 `workspace_commit_model` 登记。工具按已核实的路径和文件哈希匹配原生成来源。缺分类时补齐分类后沿用同一导出。登记应答不明时，先用版本记录和实物文件确认是否已有对应版本。成功后交付 `file.fileName`、`file.path` 及可用的原作业来源。任务需要在 Studio 显示时，按登记回包的确切版本调用 `studio_load_revision`，以 `loaded: true`、`state.ready: true` 和匹配的工作区及文件名确认加载。 [版本登记工具](../tools/workspace-commit-model.md#参数与结果) · [加载指定版本并确认](../infrastructure/workspace/load-studio-revision.md#验收)

**原作业产物的复用条件。** 原任务已成功、目标仍对应原作业、所选文件可访问且与作业记录匹配时，直接继续检查或登记该文件。需要恢复下载时沿用原账号、环境、`jobPath` 和输出目录。已有聚合 `artifact` 时，`download` 核对账号环境及输出根内的文件完整性，复验通过才返回 `cached: true`。未形成聚合清单时，刷新原任务并核对已绑定的输出目录。若目标已变更或确实需要新的生成结果，按新计划和作业标识处理。 [确认下载来源与恢复方式](confirm-download-source-and-recovery.md) · [随包调用规则](../upstream/1.2.11/prebuilt-skills/hi3d/references/calling.md)

**实际运行观测。** 本机活跃 rollout 第 102–103 行的组合工具回包为 `success: false`，负载含 `attention`、`phase: "register-model"`、原任务 ID 和三个下载文件（两份 GLB 和一张 WebP）。对应作业记录为 `state: "success"`。第 109–113 行读取作业 WebP。第 117–141 行枚举 GLB，Python 检查失败后改用 PowerShell，读取两份 GLB 的 JSON 声明计数和图像声明长度。未实际解码几何、贴图或逐份渲染。第 145–148 行选其中一份登记，回包中的来源可追溯到原任务。第 154–160 行确认登记文件已存在，Studio 仍返回 `ready: false`。第 164–167 行完成指定版本的显式加载。这一段沿用下载文件完成交接，未出现新的生成调用。 [登记分支回包](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:103>) · [原作业记录](</D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/hi3d/hi3d-cat-multiview.json>) · [选定文件并登记](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:145>) · [加载确认](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:164>)

## Vet3D 的迁移边界

Vet3D 的 LLM、生图模型、3D 模型及 API 均待选型。预检入口先使用业务语义，后端适配器负责能力检查和字段映射。

- **复核定稿用途和后端能力。** 图片编辑计划保存主体依据、操作主图和补充参考。多视图 3D 计划引用已定稿的视图版本及用途，核对参与建模的图像和槽位。任务要求五图参与重建时，四槽后端返回能力不匹配。若定稿已约定四图建模、顶视仅用于验收，预检沿用该用途。
- **从一套业务参数生成请求。** 先确定生成内容是几何、几何和外观，还是仅更新已有网格的外观，再检查网格前置条件、供应商档位与高级参数的类型、枚举及范围。由适配器从同一配置同时生成场景、版本和原生参数；收到冲突、未知或当前能力无法满足的选项时，在提交前返回具体字段错误。
- **把选择与计划版本关联。** 已选配置可直接写入计划并记录来源。缺少会影响执行的选择时才交给宿主，将答复绑定到原请求及输入版本。续调复核文件、方向和适配器配置，发现变化时重新预检。自动默认只用于可默认的参数选择，授权由独立答复承载。
- **冻结最终计划并登记提交意图。** 将「当前模型」等动态指代解析为具体版本。必要选项确定后，冻结规范化参数、工作区范围、有序输入记录、适配器及配置版本、输出位置和作业作用域。每条输入记录保存资产引用、实际文件哈希、角色和方向。按作业作用域及作业标识原子登记提交意图和指纹。同指纹恢复原任务，指纹冲突时保留原记录，新计划另用作业标识。
- **以任务 ID 和提交意图恢复。** 收到供应商任务 ID 后先持久化再处理其他元数据。响应丢失时保留原意图，先用供应商支持的任务查询或历史功能核对。仅当接口明确支持幂等重放时，才用同一幂等键重放同一请求。受理仍不明且需要另建作业时，提交层校验明确授权，将授权绑定到原作业、拟提交作业与最终指纹及约定的费用范围。计划或费用超出授权范围时重新确认。状态与接口字段待选型后映射。

**Vet3D 设计伪代码。** 这里的计划和作业标识是拟议的业务字段。

```python
def submit_preflighted_plan(plan, job_key, recovery_authorization=None):
    # job_key 包含作业作用域和作业标识
    existing = jobs.lookup(job_key)
    if existing is not None:
        return resume_if_same_fingerprint(existing, plan.fingerprint)

    checked = verify_frozen_inputs_and_output(plan)
    if checked.stale:
        return needs_preflight(checked.changed_fields)

    if plan.replaces_uncertain_job:
        verify_replacement_authorization(plan, job_key, recovery_authorization)

    reservation = jobs.reserve_or_load(job_key, plan.fingerprint)
    if reservation.existed:
        return resume_if_same_fingerprint(reservation.job, plan.fingerprint)
    return submit_once_and_record_task(reservation.job, checked.upload_input)
```

`submit_once_and_record_task` 使用已复核的上传输入，并先保存收到的任务 ID。`resume_if_same_fingerprint` 在指纹冲突时保留原记录；指纹一致时，有 ID 就续查，无 ID 就按原提交意图核对受理。重生授权由提交层验证。若复核发现已定稿图像的版本或内容有变化，`needs_preflight` 先将视图组交回上游复审，再用更新后的配对重新预检。

| 建议的 Vet3D 验收用例 | 预期行为 |
| --- | --- |
| 输入无效且缺少必要选项 | 先返回具体输入错误。修正后只询问仍缺少的选项。 |
| 显式预检的面板采用超时默认 | 校验答复与默认值一致，续调仍只返回预检计划。 |
| 面板取消或整轮中断 | 清理匹配的本地等待项，旧答复无法产生续调。已提交的作业仍可按原记录恢复。 |
| 用户要求五视图参与生成，后端只支持四槽 | 返回能力不匹配。任务允许顶视图只作验收时，将其用途写入计划。 |
| 待选期间换图或改变方向，或选项确定后更改适配器配置 | 图像或方向变化时，先完成整组复审、定稿和配对，再进行预检。仅适配器配置变化时，保留适用的定稿，重新检查能力和请求计划。 |
| 用户选择「当前模型」，Studio 加载的版本早于家族最高序号 | 计划记录已确认加载版本对应的实际文件。之后的提交和恢复使用计划中冻结的版本。 |
| 同一作业标识的请求并发到达 | 本地原子登记只产生一条提交意图，同指纹请求共享恢复路径。 |
| 同一作业标识提交不同指纹 | 拒绝覆盖原作业，返回计划冲突。 |
| POST 响应丢失，作业没有任务 ID | 保留待核对的意图。仅在接口支持幂等时重放原请求；另建作业校验绑定到最终计划的明确授权。 |
| ID 已落盘，后续提交元数据写入失败 | 用原记录和 ID 查询恢复，POST 次数维持为一次。 |
| 找回原任务 ID | 按账号、环境和任务来源建立独立恢复记录，经查询核实可访问性后续查。 |
| 请求校验通过但多张照片主体不一致 | 视觉检查仍保留冲突记录并阻止不合格的交接。 |

## 核查范围

- **静态核查。** 原安装目录在复核时为空，证据来自 `D:/install/Hi3DAgent.__hi3d-transaction` 中的 1.2.11 事务备份。Runtime SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`，`app.asar` 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`，均与此前归档一致。核对了动态工具入参、宿主回调、计时、代理账号与计费分支、Python 提交及恢复。`user_interaction`、`view_image` 和 `workflow_report` 在本节点的调用条件来自工具注册与指令。
- **离线核查。** 随包 Python 的 49 项测试通过。使用合成输入验证了请求与槽位、图片主辅图组包、缺项、非法方向、`mesh` 路径与哈希及规划后字节变化。另在临时工作区使用 1.2.11 的随包 Python 复验上表的两条缺项返回路径、非法后缀和超限、损坏 PNG、未知和越界高级参数及两种贴图底稿冲突；拦截任何远端客户端初始化，并确认没有作业文件或输出目录写入。隔离执行 Runtime 与渲染器片段验证了答复合并、默认值、取消和计时分支。模拟 POST 验证了无 ID 意图先写入、同路径复用、指纹冲突和错误响应。故障注入在首次 ID 落盘后中断提交元数据写入，显式查询用原 ID 恢复，全程一次模拟 POST。
- **Skill 指导。** 通用 Skill 规定参数与作业恢复的组织方式。装配和头部评审的输入审查随领域 Skill 选用。桌面内置预检和面板的分派由安装包实现。 [Skill 与桌面入口](#skill-绑定)
- **实际运行观测。** 本机 2026-11-11 活跃 rollout 第 53–55 行正式调用 `generate_3d` 并得到运行中的 Code Mode 单元。第 59–62 行按原 `cell_id` 续查，返回 `parameters_selected`、`interaction.status: "defaulted"`、`source: "assistant_default"` 及 `next_call`，其中采用 `v3.0:quality` 和 `both`。第 68 行按补齐的参数续调，保留原三张图片、视角、作业路径和输出目录。第 103 行取得同作业任务 ID 及下载文件。后续登记见[下游交接](#3d-候选的检查和登记)。 [首次调用与默认回包](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:53>) · [按原作业续调](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:68>)
- **待验证。** 生产记录覆盖默认值回包与续调。真实桌面显示和计时、手动作答与取消、账号权限的异常分支、超时请求的远端受理、从任务历史找回 ID、实际扣费与退款仍待实测。服务端可用参数、输出方向及画质依赖实际结果。Vet3D 五视图能力、计划冻结和供应商幂等语义待选型和实现后验收。
