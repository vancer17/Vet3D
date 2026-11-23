# hi3d_api

## 工具名称与注册来源

`hi3d_api` 是本机 Windows x64 版 Hi3D Agent **1.2.11** 的 Runtime 动态工具。Runtime 的 `Vg` 汇总 `dz[0]`，`prepareAppServerParams` 按名称合并 Runtime 与 renderer 提供的工具，由 Runtime 同名定义覆盖，再经 `thread/start.dynamicTools` 交给随包 Codex 0.166.0。宿主可通过 RPC `tools/dynamicSpecs` 读取 Runtime 定义。两份生产 rollout 第 2 行实际暴露的是 Code Mode 下的 `tools.hi3d_api`。桌面账号代理承担远端请求，随包 Python 负责参数规划、组包、作业记录、轮询和下载。 [注册和调用证据](#核查依据)

## 暴露给 LLM 的描述

工具名为 `hi3d_api`。下面是模型可见工具定义中 `description` 字段的原文。

```text
Use the Runtime-managed Hi3D entry point for text-to-image, single- or multi-image editing, image-to-3D, texturing, relief, part splitting, and multicolor processing. On desktop, prefer generate_image or generate_3d to validate, submit, wait, and download with the current account in one call; a separate dryRun is optional. Runtime opens missing parameter panels. On parameters_selected, call hi3d_api with next_call; on cancelled, stop. For a single GLB generated in the formal generate_3d call, provide registerName and tag4 (null is valid) to register it automatically after download; provide workflowNodeId to assign the model to its responsible workflow node. Registration does not complete the node; report completion through workflow_report after all work for that node is finished. For every image or 3D generation, set targetName to the concise target/object name only, preserving the chosen language and casing; do not include words such as image generation, model generation, progress, or a percentage. Reuse the exact targetName when the same object continues from image generation to 3D or resumes from a saved job. Every newly generated file name must start with hi3d-. For pending work, keep the same job and resume with the same generate_3d arguments or wait/download without submitting again. If a query reports an error, explain its specific reason in the user's language and end the current turn; do not repeat query/wait or resubmit unless the user explicitly asks. Keep numeric error codes in the job diagnostics; show them only if requested. The client status card shows generation progress; do not repeat unchanged status in chat while waiting. Every local path must remain inside the current workspace.
```

## 参数与结果

顶层 `action` 必填，Runtime 拒绝未知的顶层字段。其他字段由动作决定是否必填。下表中的动作均属于 `hi3d_api`。

| `action` | 必填及关键条件 | 结果与副作用 |
| --- | --- | --- |
| `defaults` | 无额外必填字段。 | 返回随包 `defaults.json`，读取本地快照。 |
| `balance` | 无额外必填字段。 | Runtime 直接返回 `supported: false` 和到账号菜单查看积分的提示，无余额查询请求。 |
| `generate_image` | `prompt`、`outputPath` 必填。`images`、`imageMode`、`jobPath` 可选。 | 校验、提交、等待、下载原件。单张可识别图片时导出 PNG，多张时返回原件列表。 |
| `text_to_image`、`image_to_image` | 两者均要求 `prompt`、`outputPath`。前者拒绝本地 `images`，后者至少需要一张本地图片。 | 兼容动作，复用 `generate_image` 的执行和作业路径规则。 |
| `generate_3d` | `jobPath`、`outputDir` 必填。`kind` 默认 `model`，可选 `relief`、`split`、`multicolor`。具体输入由场景决定。已有网格仅贴图使用 `kind: "model"` 和 `settings.generation_type: "texture"`。 [仅贴图参数门禁](#仅贴图参数门禁) | 校验、选择参数、提交、等待和下载。正式调用可用 `registerName` 与显式 `tag4` 自动登记唯一符合路径要求的 GLB，成功后附 `registeredModel`。若需调用方处理登记，见 `register-model` 结果。 |
| `submit` | `kind`、`jobPath` 必填。`kind` 另接受 `text-to-image`、`image-edit`，可用 `request` 和 `settings` 提供原生参数。 | 正式调用返回 `reused` 和 `job`，提交后由同一作业继续查询。 |
| `adopt` | `kind`、`taskId`、`jobPath` 必填。工具参数描述要求 ID 已绑定当前会话。 | Python 先验类型、取得本地登录账号与环境，再校验 ID 格式，独占创建 `created` 记录，返回 `adopted` 和 `job`。任务归属由调用方核对，远端可访问性由后续查询确认。 |
| `query` | `jobPath` 必填。按该账本的 `kind/task_id` 查询一次。 | 返回任务摘要，业务字段为 `state/progress/last_query_error` 等。无 `wait` 的 `result` 包装。 |
| `wait` | `jobPath` 必填。`seconds`、`interval` 可选，使用同一作业 ID 轮询。 | 返回 `{result, job}`，其中 `job` 为摘要。通过资格检查后，即使预算为 0 也尝试查询一次。 |
| `download` | `jobPath`、`outputDir` 必填。 | 成功返回 `cached` 和 `artifact`，其中 `artifact.files` 记录实际文件。刷新查询的失败可返回带作业摘要的下载阶段诊断。缓存校验或文件操作失败可返回阶段错误。图片原件下载后的 PNG 转换由组合图片动作处理。 |
| `retry_quota` | `fileName` 必填，使用当前工作区已登记版本的确切文件名。 | 读取同一重试链的额度，返回 `state`、`supported`、`remaining`、`eligible`、`can_retry` 等字段。`state` 为 `ready` 时外层 `success` 为 `true`，不可用或未知时 `remaining` 为 `null`。只读查询可更新额度缓存。 |
| `retry` | `retryRequestId`（UUID）必填，由宿主或 [`model_retry_prepare`](model-retry-prepare.md) 提供。校验仅额外接受 `targetName`，实际执行使用 Runtime 从原版本生成的显示名。 | 使用持久化意图分配的子作业提交、等待和下载，通过唯一 GLB 分支自动登记。原作业及文件保留。已完成的同一意图可返回已有版本。 |

### 共用字段与条件

| 字段 | 类型、默认值与条件 |
| --- | --- |
| `images`、`imageUrl`、`mesh`、`meshUrl` | 本地路径须在当前工作区。图片最多四个，支持 PNG、JPEG、WebP，每张上限 40 MiB。`imageUrl` 的工具描述面向公开 HTTPS 浮雕输入，`meshUrl` 为公开 HTTPS 网格地址。规划器校验 URL 且禁止同一类输入同时用本地文件和顶层 URL。 |
| `views`、`imageSlots` | `views` 取 `front`、`back`、`left`、`right`。`imageSlots` 仅用于 3D，取整数 `0` 至 `3`。多张本地图用于 3D 时，两者须提供其一，非空数组互斥。提供的数组须与 `images` 等长，且值各自唯一。Runtime 将空数组视为省略。单张本地 3D 输入省略两者时使用槽 `0`。图片任务中的具名 `views` 用于 `MULTI_VIEW_EDIT` 文件组包。 |
| `prompt`、`imageMode` | 组合图片动作要求非空提示词，随包 Python 校验最终请求的提示词上限为 4000 字符。普通图片动作有本地图时默认按 `edit`，首图为主图，余图为参考。`reference` 使用文生图任务类型并将所有本地图作为参考。没有本地 `images` 时，组合图片动作选择文生图任务类型。 |
| `imageModel`、`aspectRatio` | 可指定图片模型名或别名。随包默认 `GPT Image 2`，原生 `request.modelName` 可覆盖基础模型名。比例可取 `1:1`、`16:9`、`9:16`、`4:3`、`3:4`，未传时 CLI 基础值为 `1:1`，基础图片数量为 1。 |
| `request`、`settings` | `request` 为原生对象。图片请求包含 `editTaskType`、`modelName`、`prompt` 等，3D 请求包含 `scene`、`version`、`otherParam`。`settings` 接受字符串、数字和布尔值，用于覆盖请求参数或携带面板选项。列表和对象放在原生 `request`。身份、计费及回调字段由服务端管理。 |
| `outputPath`、`outputDir`、`jobPath` | `outputPath` 为组合图片动作的工作区 PNG 路径，文件名须以 `hi3d-` 开头。图片动作省略 `jobPath` 时，从解析后的输出路径派生 `.hi3d/jobs/<hash>.json`，恢复时使用返回的实际作业路径。Runtime 在显式生图预检时也校验输出文件名，新作业拒绝已存在的 PNG 输出路径。`outputDir` 是 3D 输出或独立下载目录。 |
| `targetName` | 可选单行字符串，去除两端空白后为 1–80 字符。工具描述要求生成及续跑时沿用同一简短对象名，供客户端进度卡显示。`retry` 的显示名由 Runtime 从原版本名称截取。 |
| `registerName`、`tag4`、`workflowNodeId` | 仅在调用正式 `generate_3d` 时可显式提供。`registerName` 与 `tag4` 必须成对，`tag4: null` 合法。可附本轮已有 `workflowNodeId` 记录产物归属。`retry` 的家族名和分类来自持久化意图。类别枚举见 [`image_classification`](image-classification.md)。 |
| `taskId`、`kind` | `adopt` 接收显式的 ID 和类型。Python 的 ID 格式为 `[A-Za-z0-9_.-]{1,200}`。显式 `query/wait` 必须提供 `jobPath`。同一工具 schema 可接受合法的额外 `taskId/kind`，查询分派只从账本读身份及路由。 |
| `dryRun`、`seconds`、`interval` | `generate_image`、其兼容动作、`generate_3d` 和 `submit` 支持 `dryRun: true`，构造本地计划。`query`、`wait`、`download` 的 CLI 分派不会传 `--dry-run`。其中 `dryRun:true` 可以绕过 Runtime 的无 ID 初筛，已有作业仍可能发 GET。等待预算默认 1800 秒，范围 0–3600。轮询间隔默认 30 秒，范围 5–300。两者接收数值，可含小数。 |

普通 3D 的随包默认配置为 `general/v3.0`、`generationType=both`、`modelType=standard`、2048 档、PBR 和 GLB。面板的默认选项为 `v3.0:quality` 与 `both`，与原生请求字段由 Python 转换。实际可用配置以当前服务为准。 [桌面参数契约](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-parameters.md) · [参数面板](../upstream/1.2.11/prebuilt-skills/hi3d/references/web-option-gates.md)

### 参数选择与请求规划

普通 `kind="model"` 的面板以 `settings.model_type` 和 `settings.generation_type` 为选择依据，只生成缺项的问题。只填写原生 `request.version` 或 `request.otherParam` 中的模型和生成类型时，面板仍会询问缺失的选择。3D 规划以原生 `request` 或随包默认对象为基础，再叠加由 `settings` 转换出的字段。组合图片动作以图片任务的基础参数为起点，依次叠加原生 `request` 与转换后的 `settings`。文生图和图生图的选项检查直接返回 `ready`，随后照常验证请求。 [原生映射及选择规则](../upstream/1.2.11/prebuilt-skills/hi3d/references/web-option-gates.md) · [桌面请求契约](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-parameters.md)

随包 Python 先计算选项状态，再构造并校验计划。即使需要选择参数，非法视角、路径或不匹配的图片数量也会在返回待选状态前报错。图片检查读取扩展名、字节数和 SHA-256。图像是否可解码、视角标签是否符合画面、以及主体和画质均由其他检查确认。

### 仅贴图参数门禁

| 条件 | 已核实的客户端行为 |
| --- | --- |
| 显式选择 `settings.generation_type="texture"` | 随包 Python 同时写入 `scene="texture"` 和 `otherParam.generationType="texture"`。桌面选项支持 `v3.0:quality` 和 `v3.0:master`，分别映射到原生 `modelType="standard"` 和 `"quality"`，`voxelResolution` 为数值 `2048`。与 v2.0 或 v2.1 组合在参数门禁直接失败。 |
| 缺少参数选择 | 只提供 `generation_type="texture"` 时，预检已构造 texture 请求，面板只补问 `model_type`。省略生成内容时，面板推荐 `both`。旧 `request_type=2` 可映射 texture 请求，但单独设置仍需面板选择。原生 `request` 内的参数也不代替显式选择。 |
| 网格与参考图 | 常规路径用 `mesh` 提供已有 GLB，用 `images` 提供参考图，并按需配对 `views` 或 `imageSlots`。显式 texture 选项已知无网格时先报错，随后的请求规划再检查参考图和网格是否齐全。`images` 最多四张，`views` 限于前、后、左、右。公开参数未定义局部选面、材质槽、遮罩或顶视图字段。 |
| 低层原生输入 | 原生 `request` 使选项门禁将网格是否存在交给请求规划判断。规划器接受 `otherParam.meshUrl`（兼容 `mesh_url`）以及 `multiViewSourceImageList` 或 `multiViewInfo`，并允许非空 `parentGenerateId` 跳过图和网格的存在性检查。此行为仅证明客户端可组包，任务访问权限及云端可用性待实测。 |

**正式提交前核对展开后的请求。** 常规仅贴图用显式 `settings.model_type` 和 `settings.generation_type="texture"`。展开后的 `request` 应同时满足 `scene="texture"`、`version="v3.0"`、`otherParam.generationType="texture"`，且网格、参考图和方向槽与本次意图一致。`consent.result: "ready"` 表示选择已补齐并完成本地规划。离线将旧 `request_type=2` 或原生 texture 请求与面板 `generation_type=both` 混用时，仍可返回 `ready`，此时 `scene` 留在 `texture` 而 `generationType` 变成 `both`。这个组合还可带 `version="v2.1"`。遇到字段冲突时，按确认的生成内容整理成一套一致参数，再预检。冲突组合的服务端处理待实测。 [面板映射与门禁](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/web_option_gates.py:485>) · [兼容参数和覆盖顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_parameters.py:82>)

本地文件走 multipart，已有网格附在参考图之后作为单独的 `mesh` 文件字段。低层 Python 也接受顶层 HTTPS `meshUrl`，将其放入 `otherParam.meshUrl`。低层对 3D 的 `imageUrl` 将地址放入 `multiViewSourceImageList` 的首槽，公开 Tool 的字段说明则面向浮雕。无本地文件时正式请求直接发送原生 JSON。随包 Skill 的独立纹理路径以 GLB 表述，Python 文件校验使用通用网格扩展名及 200 MiB 限制。 [选项展开与门禁](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/web_option_gates.py:485>) · [请求规划](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_parameters.py:140>) · [请求体选择](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:182>) · [随包独立纹理契约](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-parameters.md#独立纹理)

### 返回与错误

Runtime 的动态工具应答含 `success` 和 `contentItems`。常见应答有一个 `type: "inputText"` 的内容项，其中 `text` 为 JSON 字符串。进程路径通常含 `exitCode`、`stdout` 及可选 `stderr`，`ge` 用 `exitCode === 0` 设置该路径的 `success`。业务结果在 `stdout` 的 JSON 中。工具入参、工作区或宿主分派失败时，`text` 可直接编码为含 `error` 的对象。使用 Code Mode 时，内层结果由脚本处理，再由脚本实际输出的内容交给下一次模型采样。 [Code Mode 返回契约](exec.md#参数与结果)

| 业务结果 | 读取方式与处理 |
| --- | --- |
| 本地预检 | 三条显式预检路径的 Python 返回均含 `dry_run` 和 `consent`。组合图片另含 `kind`、`request`、`file_count`、`model`、`image_count` 和 `aspect_ratio`。组合 3D 另含 `kind`、`request`、`image_slots` 和 `file_count`。分阶段 `submit` 返回展开计划，含 `backend`、`kind`、`parameters`、`files` 和 `fingerprint`。Runtime 在解析出作业路径时补充 `jobPath`。 |
| 参数待选 | 正式调用返回顶层 `result: "waiting_choice"`，显式预检把这一状态放进 `consent.result`。Runtime 识别两种形式，通过 `interaction/request` 打开偏好面板。用户作答或超时采用推荐值后，返回 `result: "parameters_selected"`、`interaction`、`next_call` 和 `next_action`。取消返回 `result: "cancelled"`、`interaction` 和 `next_action`。续调参数保留原有的 `dryRun`、输入和路径。 |
| `pending` | 组合调用或 `wait` 在预算耗尽时返回当前作业摘要。常规生成保留原 `jobPath`，恢复时查询或等待该任务。免费重试保留原 `retryRequestId`，由 Runtime 解析同一子作业。 |
| `success` | 组合调用返回 `task_id`、`job_file` 和 `files` 等。图片组合调用在单图成功导出后还返回 `path`、尺寸及 `originals`，多张时返回 `images`。是否符合视觉要求由调用方检查。 |
| 3D 产物已下载，自动登记需处理 | `stdout` 为 `result: "attention"`、`phase: "register-model"`，工具响应的 `success` 为 `false`，封装内的 `exitCode` 为 `1`。负载保留 `task_id`、`job_file`、`jobPath` 和 `files`。下载与登记分别核对。 [已下载 3D 产物与登记](#已下载-3d-产物与登记) |
| 其他 `attention`、`failed` 或直接错误 | 优先查看当前 `last_query_error`，其次查看作业 `error` 或顶层错误。网络或查询异常可保留上次已知进度并标 `stale`，明确拒绝或远端失败走相应失败分支。缺少任务 ID 的不明提交见下方恢复分支。 |

Python 正式调用的 `waiting_choice` 和本地校验异常均可返回退出码 2。前者有 `result` 和面板参数，异常负载包含 `error_type`、`error`、`message`、`phase`，并可能附 `job_file`。面板被 Runtime 接管后，有效作答、超时默认和面板取消均以 `exitCode: 0` 返回各自的 `stdout` 业务结果。续调或停止由调用方根据业务结果决定。

面板内取消属于这次工具的正常业务应答。若整个对话轮被取消，`cancelInteractions` 清理匹配线程和轮次的待答请求。Runtime 经 `ge` 直接返回 `{"status":"cancelled","source":"user","answers":{}}` 作为内容项，并发出 `serverRequest/resolved`。这条清理路径没有 `exitCode`、`stdout` 或 `next_call`。对话轮终态由相应的 `turn/completed` 确认。终止本地等待后，远端已受理的任务仍可能继续。

支持显式预检的生成和提交动作会将 `dryRun` 转成 `--dry-run`，在 Python 创建远端客户端前完成本地校验并返回。`query`、`wait` 和 `download` 仍按已有作业执行。传原生 `request` 时，Runtime 可写入并清理临时请求文件。参数未齐全时仍可能有本地面板交互。正式提交会登记账号环境和作业，新增生成可能消耗账户积分。下载写入本地产物，启用自动登记时还会更新模型注册表。带进度输出的动作由 Runtime 向客户端转发进度。

`balance` 和本地预检均未检查实时积分或预留额度。普通 `query/wait` 不产生新生成的本地积分估算或预扣，已有任务的对账另见下文。普通生成在已核实的客户端路径中未发现逐笔扣费确认令牌或提交前的额度扣留。业务码 `30010000` 对应积分不足，`30010001` 对应扣费确认要求，后者的 `next_action` 要求取得用户同意后再考虑提交。业务码 `1003` 带领域码 `10030106` 或 `10030107` 时，分别映射为套餐并发上限和功能额度耗尽。错误映射产生诊断和处理指引，工具说明要求按需向用户展示数字代码。 [查询状态与副作用](#查询与等待诊断)

### Runtime 分派与会话校验

Codex 的 `item/tool/call` 交付工具名、参数、调用 ID、`threadId` 和 `turnId`。Runtime 先经 `skillCredits.confirm(threadId, turnId, [])` 检查线程与轮次，再从注册表取工作区 `assetId/cwd`，由 `p$` 校验参数。配置开启或已有待确认时，通用门禁可等待或拒绝调用。1.2.11 发行默认关闭 Skill 积分确认和累计提醒，普通查作业未发现专用授权面板。`Rg` 校验规范化路径、工作区边界及符号链接路径段，同一进程内按规范化绝对路径串行。`Kj` 分派为 `query --job …`、`wait --job … --seconds … --interval … --progress json` 或其他动作，`az` 直接启动随包 Python。该进程由 Runtime 和桌面代理治理。 [Codex shell 的执行策略](exec-command.md) · [Runtime 分派证据](#核查依据)

Python 通过已配置的 `127.0.0.1` HTTP 代理发请求，校验本地代理凭据和工作区，使用当前调用的 `X-Session-Id/X-Turn-Id` 关联日志。首个会话请求 `GET /v1/session` 取得账号与环境。独立查询将其与原账本的 `owner_id/environment` 比对。一个 Python 客户端可缓存此上下文。Electron 每次转发仍核对 Host、Bearer 和路由，拒绝带 Origin 的请求，并比较 `X-Hi3D-Account/X-Hi3D-Environment` 与当前桌面登录态。登出会导致 401，账号环境切换可导致 409。桌面核对 Cookie 后向所配置的服务转发。当前线程、轮次 ID 用于关联请求。独立查询未发现与原提交线程 ID 的等值检查。 [工作区路径](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_storage.py:140>) · [会话和请求实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_client.py:30>) · [桌面代理锚点](#核查依据)

动态调用的 `callId` 关联工具活动，Runtime 应答沿原 app-server RPC ID 返回。会话积分确认停止时，Runtime 可以在启动 Python 前返回 `success:false` 和 `Conversation credit confirmation was stopped.`。通过门禁后，`r$` 用 Skill 的受管标记核对脚本来源。随包 Codex 另支持按工具匹配的前置 Hook。已核对该 Hook 的启动配置和 shell 入口，本机样本中此动态工具的逐调用命中情况仍待核对。 [Codex 嵌套分派](exec.md#嵌套路由与结果交付) · [随包积分 Hook](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/hooks/skill-credit.cjs:1>) · [Runtime `r$` 原始字节偏移 2462032](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)

### 桌面结果代理的响应归一化

Electron 主进程的 `requestTool` 用桌面 Cookie 发送结果 GET。通用结果分支最多预缓冲 8 MiB。收到完整响应并复核会话后，先写 `model3d_result_response` 诊断，再由 `_l.handle` 校验和组织给 Python 的 JSON。诊断记录 HTTP 状态、业务码和字段名等摘要，不能独立确认任务 ID、业务状态已验收或作业已写盘。 [桌面代理偏移](#核查依据)

| 客户端收到的上游情形 | 代理交给 Python 的形态 |
| --- | --- |
| 可转发的成功 JSON | 保留原响应数据及 HTTP 状态。是否为有效作业观察由 Python 再检查业务码、`data` 和严格整数状态。成功数据的持久化脱敏在 Python 完成。 |
| HTTP 200 携带可归一化的非 200 业务错误 | 保留 HTTP 200，投影错误码、可用追踪 ID 和受限原因，并附 `error_source: "upstream"`。Python 根据归一化后的业务码判读。 |
| 上游 HTTP 429 或其他非成功状态 | 通常保留 HTTP 状态和归一化错误。429 的 `Retry-After` 不透传给 Python，已查工具路径未根据它安排重试。 |
| HTTP 401 或归一化为 401 的业务响应 | `requestTool` 层返回的 401 进入桌面会话失效处理。该层发现 Cookie 缺失或版本变化时也可在发送前构造 401，`_l.handle` 仍可能标为 `upstream`。该字段可用于客户端分支判读，真实服务器是否应答需另查请求证据。恢复原登录环境后可沿原作业再次查询。 |
| 畸形的成功 JSON、被拒绝的重定向、传输异常 | 当本地响应仍可写时，可返回 HTTP 502 和 `error_source: "desktop-proxy"`。读取错误来源可区分该分支与上游返回的 HTTP 502。 |

Python 的 `Client._send` 在 `HTTPError` 时仍尝试读取 JSON 对象，将 HTTP 状态与正文交给查询分类。本文涉及的是客户端可见的转发及归一化结果。上游对其他账号、过期 ID 和限流的实际策略需要服务实测。 [Python 请求与解析](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_client.py:79>)

### 动作的执行预算

| 动作 | Runtime 交给 Python 的参数 | Runtime 子进程时限 |
| --- | --- | --- |
| `query` | `query --job …`，分派使用 CLI 的默认摘要输出。完整输出仅见 CLI `--output full`。 | 120 秒 |
| `wait` | `wait --job … --seconds … --interval … --progress json`，使用默认摘要。CLI 可另外指定 `--output full`。 | `seconds + 30` 秒 |
| `adopt` | `adopt <kind> <taskId> --job …` | 120 秒 |
| `download` | `download --job … --out …`。使用固定预算，命令没有进度或离线参数。 | 600 秒 |
| `submit` | `submit <kind> --job …`，追加本次计划参数。 | 600 秒 |
| `generate_3d`、`retry` | 组合执行，追加计划、输出路径、等待参数和 JSON 进度。`retry` 的计划来自本地意图，模型通过 `retryRequestId` 选择意图，等待参数由 Runtime 分派。 | `seconds + 1230` 秒，默认 3030 秒 |

Runtime 的时限从 `az` 启动子进程时计算，`Rg` 中按作业路径排队的时间另计。`az` 分别收集至多 1 MiB 的 `stdout`、`stderr`，超时、输出超限或接到中止信号时结束本地进程。守护超时可由 `Jj` 封装成 `attention/2`、`phase: "process"` 和已知作业引用。整轮取消可通过 Runtime 的线程、轮次控制器终止本地等待，并可能以只有 `error` 的工具应答结束。本地连接关闭可经代理信号中止当次桌面 HTTP。中断后可以用已写盘的作业和检查点恢复，远端状态需重新查询。Code Mode 的输出等待另由 [`wait`](wait.md#关联终止与恢复) 控制。 [进程与取消锚点](#核查依据)

#### Python 轮询的截止顺序

组合调用在提交或复用作业后进入 `wait_job`，到该函数入口才用单调时钟计算轮询截止时间。通过资格检查时，`seconds=0` 也会尝试一次结果 GET。单次结果 GET 的超时取剩余预算，限制在 1–20 秒。会话握手另有 20 秒请求超时，显式 `query` 和无缓存下载的结果刷新 GET 默认各有 90 秒。 [CLI 分派与查询](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_api.py:204>) · [Python 等待预算](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:336>)

每次查询先保存账本，再按变化发进度并判读 `job_outcome`。已发出的请求即使在业务截止后才返回，也先采用该次有效观察或诊断。若观察为终态或查询出错，立即返回。若仍在处理且时间未到，则睡 `min(interval, 剩余时间)`。睡醒已经到期时直接返回 `pending/0`，无需再发一次结果 GET。业务轮询预算结束与 Runtime 守护超时分别对应正常 `pending` 和本地进程异常。 [截止检查顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:343>)

## 实现伪代码

**实现伪代码。** Runtime 先校验工具参数及工作区，再按动作分派。图片和 3D 的生成动作共用本地规划、提交和作业恢复。`submit` 返回作业，组合生成动作按作业状态继续等待及下载。下例包括 Runtime 和 Python 的分派以及面板响应。省略通用响应封装、`adopt`、免费重试及 3D 自动登记。

```python
def execute_generation_or_resume(args, workspace):
    validate_runtime_arguments(args, workspace)
    job_path = resolve_job_path(args, workspace)
    protected = check_submission_guard(args, job_path)  # 适用动作的非 dryRun 分支
    if protected is not None:
        return protected

    if args.action in ("query", "wait", "download"):
        job = load_existing_job(job_path)
        return run_existing_job_action(args, job, job_path)

    kind = select_task_kind(args)
    gate, overrides = evaluate_parameter_choices(kind, args.settings)
    plan = build_and_validate_plan(kind, args, overrides)
    if args.dryRun:
        return format_preview_for_action(args.action, plan, consent=gate)
    if gate["result"] == "waiting_choice":
        return gate

    job, reused = submit_or_reuse(job_path, plan, action=args.action)
    protected = check_submission_guard(args, job_path)
    if protected is not None:
        return protected
    if args.action == "submit":
        return {"reused": reused, "job": job}
    if should_stop_combined_generation(job):
        return describe_job_outcome(job)

    outcome = wait_using_saved_task_id(job_path, args.seconds, args.interval)
    if outcome["result"] != "success":
        return outcome
    files = download_for_saved_task(job_path, args)
    return format_generation_result(kind, args, job_path, files)


def handle_generation_result(call, result):
    gate = result if result.get("result") == "waiting_choice" else result.get("consent")
    if gate is None or gate["result"] != "waiting_choice":
        return result

    panel = validate_preference_payload(gate["user_interaction"])
    # 宿主请求 ID 关联原调用、原参数和已校验的面板。
    response = await_valid_host_response(call, panel)
    if response.status == "cancelled":
        return {"result": "cancelled", "interaction": response}

    original = call.arguments
    settings = {**original.get("settings", {}), **response.answers}
    return {
        "result": "parameters_selected",
        "interaction": response,
        "next_call": {**original, "settings": settings},
    }
```

Runtime 关联 `requestId`、原工具调用及面板参数。面板参数无法通过校验时，Runtime 返回工具错误。无效回答会保留待处理记录，有效回答完成原调用，宿主返回错误时则向原调用转发错误。面板超时默认由宿主提交为回答，Runtime 按同一回包机制生成 `next_call`。调用方据此再次调用，重新执行校验。宿主请求与 [`user_interaction`](user-interaction.md) 共用面板协议，预检分支由 Runtime 直接发起该请求。

### 作业持久化与恢复

计划指纹来自 `backend`、`kind`、组包参数和按顺序排列的文件记录。组包参数包括展开后的请求及适用的槽位，文件记录包含字段名、路径、字节数和 SHA-256。组合生成的预检返回计划摘要，`submit` 的预检还返回指纹。正式调用基于当时的输入重新规划。已有 `jobPath` 时，Python 比对后端和指纹，一致时复用原作业并跳过组包及 POST，冲突时保留原记录并报错。输出位置和账号环境分别检查。Runtime 按解析后的作业路径串行处理，Python 以独占创建防止其他进程覆盖原记录。

**实现伪代码。** 新作业先生成实际请求体，multipart 在此检查字节数、SHA-256 和 512 MiB 上限。组包成功后执行会话校验，持久化提交意图并发一次 POST。HTTP 200 且业务码为 200 时，从响应的 `data` 读取图片 `taskId` 或 3D `jobId`。有效 ID 先以 `submitting` 状态写盘。父任务信息处理后再更新为 `queueing`。初次写入独占创建并 `fsync`，后续更新以临时文件替换原文件。

```python
def create_new_job(path, plan, client):
    with assemble_and_verify_request(plan) as request:
        account = client.session()
        job = write_exclusive(path, plan, account, state="submitting")
        phase = "request"
        try:
            response = post_once(client, plan.kind, request)
            if has_success_envelope(response):
                phase = "task_id_validation"
                job.task_id = validated_task_id(response, kind=plan.kind)
                phase = "task_id_persistence"
                save(path, job)
                record_parent_fields(job, response)
                phase = "state_update"
                job.state = "queueing"
            else:
                job.state = classify_submission_status(response)
                job.error = response_diagnostics(response, phase)
        except Exception as error:
            job.state = "submission_uncertain"
            job.error = exception_diagnostics(error, phase)
        save(path, job)
        return job
```

查询与下载沿用同一任务 ID，并核对作业绑定的账号环境。账号代理路由如下。

| 任务 | 提交 | 查询 |
| --- | --- | --- |
| 图片 | `POST /v1/image-task/img-edit` | `GET /v1/image-task/image-edit/result?taskId=…` |
| 3D | `POST /v1/model3d/submit` | `GET /v1/model3d/result?jobId=…` |
| 3D 免费重试 | `POST /v1/model3d/retry` | 使用重试产生的新 `jobId` 查询同一 3D 结果路由。 |

| 作业情况 | 处理与返回 |
| --- | --- |
| `pending` | `wait` 耗尽预算后返回原作业的最后状态。用原 `jobPath` 继续 `query` 或 `wait`，脚本从账本读取同一任务 ID。确认成功后从原作业下载。未形成聚合 `artifact` 时，下载在取得新鲜候选后绑定输出目录，续传使用原绑定目录。 |
| `submitting` 或 `submission_uncertain`，原账本有有效 ID | 将原 `jobPath` 传给显式 `query` 或 `wait`，由工具从该账本读取 `task_id`。以相同计划重入组合生成可能直接返回 `attention`。即使异常发生在保存 ID 后，也保留已取得的 ID。 |
| `submitting` 或 `submission_uncertain`，原账本缺 ID | 对应后端且 `task_id` 为假值时，Runtime 的 `Tg` 通常返回 `attention`、`reason: "submission_uncertain_without_task_id"` 和 `canQuery: false`。非空但格式非法的 ID 由 Python 拒绝。若从可靠历史确认同一任务的远端 ID，使用 `adopt` 传 `kind`、`taskId` 和一个新的 `jobPath`，保留原账本，随后用新路径显式查询。仍无法确认 ID 时保留原记录待核对。普通生成的 `requiresRegenerationConfirmation` 是模型可见指令，要求在另开作业前取得用户确认。3D 在当前轮提示风险并征求确认，图片先结束当前流程，待用户要求恢复或重试后再征求确认。免费重试优先走独立保护分支，保留原意图和子作业并核对原次数。 |
| `submission_rejected` 或已知未取得 ID 的积分不足 | 普通生成得到可分类的 HTTP 4xx 时记录明确拒绝。网络异常、其他非成功响应和无有效 ID 的成功响应通常记为 `submission_uncertain`。普通生成收到 HTTP 200、业务码 `30010000` 且 `task_id_present/submission_has_task_id` 均为假值时，`Tg` 跳过通用提示，保留积分不足诊断。若随后显式续查该无 ID 账本，仍在 Python 的 ID 校验处结束。 |
| 查询报错 | 优先读 `last_query_error`。按[查询与等待诊断](#查询与等待诊断)区分查询不可用和客户端判定的查询业务拒绝。 |

`taskId` 的模型可见字段说明要求使用已关联当前会话的 ID，调用方应以原工具回执或可靠历史核对。实际 `adopt_job` 校验 `kind`，读取本地 `/session` 的账号环境，校验 ID 格式并独占创建 `state: "created"` 的账本。同路径重复创建会保留原文件。该实现以本地创建作为 `adopted:true` 的完成条件，下一次显式 `query/wait` 才核实远端可访问性。与原提交的关联仍需依靠来源证据。新账本无原计划指纹，用其路径重入组合生成会触发指纹保护。 [模型可见字段](exec.md#暴露给-llm-的描述) · [本地创建与复用校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:165>)

普通提交每次新建作业只发一次 POST。`requiresRegenerationConfirmation` 指导模型取得用户确认，已查客户端新路径提交未发现与原作业绑定的确认凭据校验。服务端幂等与扣费仍需真实服务证据。

**参数确认和首次执行。** 预检收到 `parameters_selected` 时，`next_call` 合并面板答案并保留原调用的 `dryRun`。核对展开后的请求后，以已确认的网格、参考图顺序、方向、设置、`jobPath` 和 `outputDir` 正式调用，并去掉 `dryRun: true`。面板取消时停止本次请求。首次正式 `generate_3d` 执行时，已存在的 `outputDir` 须为空目录。预检可返回 `ready`，而正式调用仍因目录非空返回 `Use a new output directory`。已有作业的下载继续按原目录绑定和缓存规则处理。 [仅贴图参数门禁](#仅贴图参数门禁) · [参数面板回包](#返回与错误) · [正式执行目录检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:19>)

正式提交后的计划由原账本固定。调整网格、图序、槽位或设置后，如果计划指纹变化，沿用原 `jobPath` 会命中指纹冲突。查询错误按 Tool 描述结束当前轮，用户明确要求继续时仍用原作业。确认任务成功后，下载和登记分别按各自的恢复条件处理。 [下载与登记回包](#已下载-3d-产物与登记)

### 已下载 3D 产物与登记

独立 `wait` 的 `success/0` 表示已观察到任务成功并写入账本，回包交付作业摘要。需要文件时，用原 `jobPath` 和已绑定或规划的 `outputDir` 调用 `download`。组合 `generate_3d/retry` 在内部得到 `waited.result == "success"` 后才调用 `download_job`，下载返回后才组装成功回包。同计划重入且进入等待的组合调用，先有当前等待查询，再核对下载缓存。聚合缓存只省去下载阶段自己的结果刷新 GET。 [组合生成交接](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:34>) · [组合重试交接](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:84>) · [缓存及刷新分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:175>)

带 `registerName` 和显式 `tag4` 的正式 `generate_3d`，以及成功解析出执行计划的 `retry`，均可进入 `registerGeneratedModel`。进程退出码为 `0` 且下载结果为 `success` 时，Runtime 从 `files` 筛出位于工作区内、可解析为普通文件的 `.glb` 路径。筛选按列表项计数，同一路径重复出现也会计为多项。恰有一项时才交给 `commitExport` 校验导出路径并登记。此分支按数量决定是否尝试登记，候选角色、模型内容及质量需要独立证据。 [Runtime 中的自动登记实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [Runtime 字节偏移](#核查依据)

`commitExport` 返回后，自动分支等待注册表刷新，再按可选 `workflowNodeId` 挂接图产物。只有返回了新版本时才记录 Skill 产物并发送 `workspace/modelUpdated`。回包中的 `registeredModel` 是登记结果，可能来自同任务或同内容复用。需要确认具体字节时，应对照实际 `fileName` 和所选候选的 SHA-256。 [版本复用规则](workspace-commit-model.md#实现伪代码)

零项、多项或登记异常返回 `attention` 与 `phase: "register-model"`，保留原任务和下载文件列表。登记后的刷新也可能触发此结果。恢复时以原 `jobPath`、`task_id` 和 `files` 对账，先确认是否已有匹配的正式文件，再用选定的原导出恢复登记。上游下载和登记回包各自确认。 [显式登记的回执与恢复](workspace-commit-model.md#参数与结果)

存在多份合规 GLB 时，按原下载清单和各实际文件确认用途，再把选定路径传给独立登记工具。 [下载诊断](#查询与等待诊断) · [登记失败与重入](workspace-commit-model.md#失败与重入)

已有聚合 `artifact` 时，`download` 核对账号环境，复验顶层文件、`artifact.files` 各项和已有的可选 `cover`。每项均核对输出根范围、大小及 SHA-256。新聚合记录顶层继承首项文件字段，完整结果列表由 `artifact.files` 提供。复验通过返回 `cached: true`，跳过远端结果查询及原 `download_output` 的等值比较。文件缺失或变更时返回缓存校验错误。未形成聚合 `artifact` 时，则刷新原结果，并要求已绑定的 `download_output` 与解析后的请求目录一致。 [缓存校验与下载实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:120>)

无聚合缓存时，刷新同一任务后还需要本次有效成功、账本无本次查询错误和可用 HTTPS 候选。组合调用的下载异常会重读账本。已保存明确查询拒绝时回 `failed/1`，其余下载异常回 `attention/2`，两者均可带 `phase: "download"`。首次等待的成功进度可以先到。读取最新回包和 `last_query_error`，再确认候选文件是否可用。 [组合下载异常处理](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:45>) · [下载前的刷新门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:182>)

独立 `download` 执行前读取旧 `last_queried_at`。下载抛错后重读账本，只有读到 `last_query_error` 且该时间与旧值不同，才使用 `job_outcome` 返回 `{result, phase: "download", job}`。业务拒绝为 `failed/1`，本次查询不可用为 `attention/2`。缓存校验失败、账本保存失败或有效成功但没有可用 HTTPS 候选等异常，可落到通用 `error_type/error/message/phase/job_file` 形态，退出 2。缺少候选时，账本可以已保存 `success`。已有缓存通过本地复验时也可返回 `cached: true`，账本中的旧查询错误不会因此清除。 [独立下载的错误分流](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_api.py:220>) · [查询刷新与候选门禁](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:175>)

需要先验收外观时，省略自动登记字段，下载后选定符合 `workspace_commit_model` 的 `exports/` 路径和命名要求的 GLB，再用其实际路径登记。需要另行导出时，保留原下载记录和文件引用，并按登记工具要求核对导出路径。 [本地登记工具](workspace-commit-model.md)

常规生成仍在等待时，带原作业路径、原参数和原登记配置重入 `generate_3d`，可继续同一作业并保留自动登记分支。`registeredModel` 是实际登记的版本引用，可能由可信同任务来源复用而来。将验收证据交给下游前，读取 `registeredModel.path` 的 GLB，并将其 SHA-256 与已验收候选对账。摘要不同时，应对实际返回的文件另行验收。自动登记完成与文件通过验收分别确认。 [作业持久化与恢复](#作业持久化与恢复) · [登记的文件身份与复用](workspace-commit-model.md#文件身份与复用)

### 免费重试与结果复用

`retry_quota` 按环境、账号和根任务 ID 定位同一重试链。需要向代理查询时，Runtime 以链内最近创建且已有 `taskId` 的重试记录作为查询对象。没有这样的记录时取所指定版本的 `source.taskId`。将该值作为 `GET /v1/model3d/result` 的 `jobId`。免费重试的提交则用原任务的根 ID 作为 `parentGenerateId`，服务受理后产生新的 `jobId`。

桌面代理的 `POST /v1/model3d/retry` 接受大小受限的 JSON，要求唯一字段 `parentGenerateId` 通过 ID 校验。主进程 `requestTool` 将该请求转到服务的 `/aigc/api/generate/img2model3d-url`。子任务结果继续使用普通 3D 查询路由。 [桌面代理锚点](#核查依据)

`retry` 在原线程中解析 `retryRequestId`，使用意图固定的子作业、输出目录、原家族及分类。新提交把返回的 `jobId` 存为子作业 `task_id`。非复用的新子作业有已写盘的 ID 且启用进度回调时，可在首次等待 GET 之前发 `submitted`。其后的等待和下载使用子任务 ID。 [意图创建与参数](model-retry-prepare.md) · [子作业提交及进度](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:73>)

Runtime 的 `Cg.complete` 将工具回包归并为本地意图状态。有 `registeredModel.fileName` 时记 `completed`。缺 ID 的受理不明原因对应 `submission_uncertain`，`result: "failed"` 对应 `failed`，其余可记 `interrupted`，包括 `pending/0` 或登记待处理。远端子任务状态由作业查询确认。正常到期、本地中断或回执不明后，沿用同一个 `retryRequestId`，由 Runtime 找回同一子作业。受理不明且缺子任务 ID 时返回 `attention` 和 `reason: "submission_uncertain_without_task_id"`，保留原意图和子作业，结合已有记录核对受理结果及额度。 [意图状态归并锚点](#核查依据) · [随包恢复约定](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-free-retry.md)

Runtime 执行重试计划前会核对已有登记。若同一意图已完成，可返回 `result: "success"`、`reused: true`、`registeredModel`、`task_id` 和 `jobPath`。若下载成功但登记返回 `phase: "register-model"`，可选定原下载文件，以原家族显式登记。Runtime 依版本的家族、子任务 ID、作业路径、根任务、账号、环境和原线程来对账，需要保留匹配的下载来源。 [本地登记工具](workspace-commit-model.md)

组合 `retry` 在进度和收尾分支携带本地重试意图，可经 `Cg.observe` 更新次数缓存和发出 `model/retryQuotaChanged`。缺少有效次数时可另发额度校准 GET。该请求读取额度，普通 `query/wait` 查询重试子作业路径时仍走作业快照流程，未接入这个意图观察器。 [免费重试观察与额度锚点](#核查依据)

### 查询与等待诊断

`query/wait` 首先读账本。工作区路径、JSON、后端和 ID 格式出错时，CLI 可返回 `phase: "query"` 或 `"wait"`、`error_type` 和退出码 2。原账本保持原字节。进入查询处理后才校验账号环境、选择账本 `kind` 对应的路由并尝试发送 GET。有效响应要求 HTTP 200、`str(code) == "200"`、对象形式的 `data` 和受支持的严格整数 `data.status`。3D 接受 0（处理中）和 1（成功），图片额外接受 2（生成失败）。`record_parent` 核对 3D 响应的可选 `parentId` 和已有父链。已核查的响应分支沿用请求的账本 ID，未比对响应里回显的 `jobId`。 [父链验证](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:32>) · [查询与错误写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:256>) · [CLI 错误封装](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_api.py:210>)

**实现伪代码。** 以已启动 Python 动作为起点，展示一次观察的写盘顺序。轮询复用同一作业路径，每次用返回的状态决定是否继续。省略底层 HTTP 与工具封装。

```python
def observe_job(path, client, timeout):
    job = load_workspace_json(path)
    require_supported_backend(job)
    task_id = require_valid_task_id(job.get("task_id"))

    try:
        client.check_job(job)
        response = get_result(client, job["kind"], task_id, timeout)
        apply_observation_or_query_error(job, response)
    except Exception as error:
        record_query_exception(job, error)

    job["last_queried_at"] = now()
    job["progress"] = progress_snapshot(job)
    replace_job_file_atomically(path, job)
    return job
```

查询处理中的账号、路由或传输异常可留下 `last_query_error` 和陈旧进度。`last_queried_at` 记录查询尝试时间，账号核对失败时也会更新。`progress.observed_at` 对应作业结果的观察时间。默认摘要输出存在的 `backend`、`kind`、`task_id`、`parent_task_id`、`state`、`progress`、`error` 和 `last_query_error`，另加 `job_file` 与条件性的 `next_action`。有查询错误时，查询恢复指引优先于图片失败指引。独立 `query` 直接返回摘要，`wait` 将摘要放在 `{result, job}` 的 `job` 中。Runtime 在取得有效作业路径时可补顶层 `jobPath`。脱敏的 `result`、账号环境及 `last_queried_at` 留在账本。 [进度字段](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_progress.py:18>) · [默认摘要](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_progress.py:71>)

有效的处理中或成功观测经 `public_record` 按字段名、URL 和可解析的嵌套 JSON 规则脱敏后写入 `job.result`。直接 HTTP(S) URL 保留路径，查询部分被替换，片段被移除。图片的有效失败观测只保存指定的数值状态字段。`query_job` 还返回当次进程内的原始 `data`，显式 `query/wait` 丢弃这一返回值。随包 CLI 的 `--output full` 输出经过脱敏的账本。无缓存的 `download` 可用当次原始 `data`，继续下载前要求新鲜成功、无查询错误且存在可用 HTTPS 地址。下表退出码为随包 Python 路径的返回值。 [结果脱敏](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_storage.py:200>) · [图片失败结果投影](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:292>) · [CLI 摘要和完整输出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_api.py:210>)

| 诊断 | 客户端记录 | 当轮处理和下次入口 |
| --- | --- | --- |
| 等待预算到期，任务仍在处理 | `result: "pending"`，退出码 `0`，保留原作业。 | 按原 `jobPath` 续 `wait` 或 `query`，成功后下载原作业的产物。相同调用计划重入组合动作时按原指纹复用。 |
| 查询网络异常、代理异常、账号环境不匹配或响应缺少有效状态 | 若在更新作业状态和结果之前失败，保留上次已知状态和结果。写入 `last_query_error`，将进度标记为过期。`wait` 返回 `attention`、退出码 `2`。`query` 返回带该诊断的摘要、退出码 `2`。 | 说明具体查询原因，结束当前轮。用户明确要求继续时，用原账号环境和原 `jobPath` 恢复。有效的任务查询可清除这次查询错误。 |
| 客户端判定查询业务拒绝 | HTTP 200 内的 `code` 转成字符串后匹配 1–12 位十进制数字，解析值异于 200，且错误来源未标记为 `desktop-proxy`。代码无需命中已知错误映射。保存 `last_query_error.query_failed: true` 和 `job.error.phase: "query"`，清除旧 `result`，本地作业变为 `failed`，退出码 `1`。 | 按查询诊断说明原因并结束本轮。此分支确认本次查询被客户端判为业务失败，生成引擎的实际状态仍需其他服务证据。与原计划相同的组合调用会直接返回失败。用户明确要求复查时，可用原作业显式查询同一任务。 |
| 账本保存失败 | `save` 在查询异常处理范围外执行。序列化、写临时文件或替换失败可向 CLI 抛出，返回带原动作 `phase` 的阶段错误及退出码 `2`。此回包没有 `{result, job}` 包装。未完成替换时，旧账本仍在，等待回调没有发出本次保存后的进度。 | 读回磁盘上最后一份有效记录，按错误原因恢复，再沿同一 `jobPath/task_id` 获取观察。 |
| 图片任务生成失败 | 查询本身有效，返回体为 `code=200` 且 `data.status` 为整数 `2`。Python 记录 `job.error.phase: "generation"`，`wait` 返回 `failed`，退出码 `1`。 | 报告生成失败并停止本轮图片流程。同计划重入组合动作仍返回失败。保留原任务和已得产物，是否再发生成请求由后续用户指示决定。 |
| 作业生成成功，下载或本地导出未完成 | 组合动作下载异常通常返回 `attention`、`phase: "download"`。若下载刷新任务状态时触发明确的查询拒绝，仍保留查询失败的诊断。PNG 导出由桌面 Runtime 在原件下载后单独执行。 | 先查失败环节。下载使用同一作业和已绑定目录，刷新结果地址并校验缓存、检查点或现有文件。原件已经可用时，可从保留的原件检查并处理本地导出。归因于查询异常时，按对应查询分支停止本轮。 |
| 已下载的候选实际看图不合格 | API 作业仍记录生成成功，视觉问题写入调用方的候选评审。 | 按所选 Skill 和已有授权提交定向修订。改动提示词或输入会改变计划指纹，因此使用新的作业路径和输出版本。保留原作业、原候选和缺陷证据。 |

有效状态进入处理分支后，代码先赋值 `state`，再脱敏并保存结果。若结果处理在赋值后抛错，异常处理会保留已发生的内存字段更改，再记录 `last_query_error`。同版模拟响应已复现新 `state: "success"`、旧结果与旧观察时间、`stale: true` 同时落盘。读取摘要时以本次诊断与新鲜度判断后续动作。 [状态赋值及异常处理](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:288>) · [业务码解析](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_storage.py:80>)

已有账本的更新是先序列化，再写入同目录临时文件并 flush/fsync，最后 `os.replace`，随后清理临时文件。将替换操作注入 `PermissionError` 后，已复现旧账本字节不变、临时文件清理和退出码 2。若在替换成功后才出现进度回调或输出错误，磁盘可能已经有新观测。恢复时应核对磁盘，工具回包缺失不足以判断保存结果。 [保存与清理](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_storage.py:175>) · [写盘后才报告进度](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:317>)

轮询遇终态、查询错误或等待预算耗尽即返回。整轮取消沿线程与轮次停止本地子进程，已受理的远端作业可继续。同一路径的查询在当前 Runtime 中串行，多进程或跨路径调用各自校验。已查实现的串行范围是本地路径，未发现按远端 ID 全局合并或作业级熔断。 [执行预算](#动作的执行预算) · [Runtime `Kj/Jj/az`](#核查依据)

`wait` 在写入账本后按变化发送 `stderr` 进度，Runtime 解析后以 `runtime/hi3dProgress` 向桌面发布。独立 `query` 没有等待进度回调。Runtime 可在 `.hi3d/progress/` 保存显示用的目标名和生成类型。进程正常结束时缓存的 `stderr` 也可随工具回包交付。 [进度与进程锚点](#核查依据) · [外层回包](exec.md#参数与结果)

下载完成的作业记录含 `artifact.files`，其中保存实际产物路径和 SHA-256，可用于把原件追溯到原任务 ID。来源见 `hi3d_jobs.py:256–355`、`hi3d_generation_workflow.py:22–59`、`hi3d_artifacts.py:115,175–261` 以及 Runtime 的 `Kj`。 [Skill 的失败与续跑规则](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) · [生成结果使用约定](../upstream/1.2.11/prebuilt-skills/hi3d/references/calling.md)

#### 本地对账与来源补记

- **退款对账。** `Rg` 在有效进度回调和收尾时重读账本。非预检调用观察到新的 `result_observed_at`，作业为 `failed`，有可用的任务 ID、账号和环境，且无查询错误或错误已标为 `query_failed:true` 时，可发 `runtime/hi3dRefunded`，同次调用最多一次。桌面按当前环境接收该事件，`refundHi3d` 匹配当前账号和既有本地扣费记录，检查是否已经返还，再保存估算账本并发布用量变化。事件表明 Runtime 发起了本地对账，桌面估算账本的变更以保存结果为准。实际退款需服务侧确认。 [退款分派与桌面对账锚点](#核查依据)
- **来源补记。** 收到包含 `jobPath` 的子进程结果时，Runtime 的 `recordHi3dDownloads` 可读取工作区内已保存的 `success` 作业与 `artifact.files`，检查已有 `.glb` 文件路径和 SHA-256 后补记来源。旧 `success` 带陈旧诊断时仍可能补记。来源记录对应已有文件的校验，新鲜观测与模型版本登记各有判据和回执。 [来源补记锚点](#核查依据) · [独立模型登记](workspace-commit-model.md)

### 图片请求与组包

**实现伪代码。** 图片生成先按动作、是否提供本地 `images` 和 `imageMode` 选择任务类型。随后在基础参数上应用原生 `request` 与 `settings`，校验最终的 `editTaskType`、提示词、图片路径与标签。下面是通过校验后的本地图组包。

```python
def build_image_parts(request, kind, images, views):
    if not images:
        return json_body(request)

    parts = [json_part("request", request)]
    if request["editTaskType"] == "MULTI_VIEW_EDIT":
        view_keys = map_and_validate_view_keys(views, images)
        parts.append(json_part("viewKeys", view_keys))
        for image in images:
            parts.append(file_part("viewImages", image))
        return multipart(parts)

    for index, image in enumerate(images):
        field = "baseImage" if kind == "image-edit" and index == 0 else "referenceImages"
        parts.append(file_part(field, image))
    return multipart(parts)
```

`MULTI_VIEW` 和 `MULTI_VIEW_3VIEWS` 的桌面组包以首图 `baseImage` 为主体基准，其余图片作为 `referenceImages`，参考图不附具名方向。`MULTI_VIEW_EDIT` 的 `viewKeys` 表示每个文件的方向，`request.editedViewKeys` 表示要修改的方向。比如同时上传正面和左侧文件时，可将两者的方向都写入 `viewKeys`，并只把左侧写入 `request.editedViewKeys`。服务器实际是否保留其他方向须检查返回图。

组合图片动作成功时将原件保存到 `<outputPath>.originals`。只有一张可识别的图片时，Runtime 再导出到指定 PNG。多张图返回原件路径供 Agent 查看和选择，桌面文件列表没有逐张方向标签。任务成功和视觉验收应分别记录。

### 3D 本地文件组包

Runtime 的 `Kj` 按调用顺序将 `images` 中的每条工作区路径转发为一个 `--image` 参数。非空的 `views` 或 `imageSlots` 转发为逗号分隔的 `--views` 或 `--image-slots`。Python 按索引处理文件和方向。具名方向使用客户端映射 `front=0`、`back=1`、`left=2`、`right=3`。显式数字槽保留原值和顺序，槽位可以不连续，缺位无需填充。客户端组包只能核实数字如何传递，云端对显式槽值的解释需用实际结果验证。 [桌面参数契约](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-parameters.md)

**实现伪代码。** 概括 `generate_3d` 和 3D `submit` 共用的本地图分支。`request` 已完成参数规划。入参已通过 Runtime 类型检查，空数组按省略处理。网格和 URL 输入在其他分支处理。

```python
def plan_local_3d_files(request, images, views=None, image_slots=None):
    require(1 <= len(images) <= 4)
    require(not (views and image_slots))

    slot_for = {"front": 0, "back": 1, "left": 2, "right": 3}
    if views:
        require_unique_values(views, count=len(images), allowed=slot_for.keys())
        slots = [slot_for[view] for view in views]
    elif image_slots:
        require_unique_values(image_slots, count=len(images), allowed=range(4))
        slots = list(image_slots)
    else:
        require(len(images) == 1)
        slots = [0]

    files = [inspect_workspace_image(path, field="images") for path in images]
    return {"request": request, "imageSlots": slots}, files


def encode_local_3d_files(parameters, files):
    parts = [json_part(name, value) for name, value in parameters.items()]
    for index, file in enumerate(files):
        name = f"input-{index}{suffix_from_path(file.path).lower()}"
        parts.append(file_part("images", name, read_and_verify(file)))
    return multipart(parts)
```

长度不匹配、重复方向或槽位、缺少多图方向、路径无效，或文件扩展名与大小不符合限制时，规划返回本地错误。规划记录每个实际路径的字节数与 SHA-256，方向取自输入参数。组合 3D 预检在 `image_slots` 返回槽位，分阶段 `submit` 预检将其放在 `parameters.imageSlots`，同时返回 `files`。新任务正式提交时，multipart 先写入 JSON 字段 `request` 与 `imageSlots`，再按原顺序写入重复的 `images` 文件字段。上传名称按顺序生成，如 `input-0.png`。组包读取所传路径的字节并复核大小和哈希，发生变化时在创建远端任务前报错。计划指纹包含数组顺序，重排改变指纹后用原 `jobPath` 正式调用会触发计划不匹配。

## 调用示例

**根据已验证行为重建的多图预检请求。** 示例假定工作区已有两张参考图。随包规划器将 `left` 和 `front` 转成 `image_slots: [2, 0]`，并在 `consent.result` 返回 `ready`。正式组包时，`input-0.png` 取 `inputs/left.png` 的字节，`input-1.png` 取 `inputs/front.png` 的字节。省略 `generation_type` 后，预检仍会规划请求，并在 `consent` 返回需要补选该项的状态。

```json
{
  "action": "generate_3d",
  "targetName": "茶壶",
  "images": ["inputs/left.png", "inputs/front.png"],
  "views": ["left", "front"],
  "settings": { "model_type": "v3.0:quality", "generation_type": "both" },
  "jobPath": "hi3d/model-job.json",
  "outputDir": "exports/hi3d-model",
  "dryRun": true
}
```

**根据离线复现重建的仅贴图预检请求。** 示例使用工作区内的已有 GLB 和两张参考图。预检返回 `consent.result: "ready"`、`image_slots: [0, 2]` 和 `file_count: 3`。正式组包按 `request`、`imageSlots`、两份 `images`、`mesh` 的顺序写入。该示例核实请求内容，云端实际产物仍需另行检查。 [仅贴图参数门禁](#仅贴图参数门禁)

```json
{
  "action": "generate_3d",
  "kind": "model",
  "targetName": "椅子",
  "mesh": "hi3d-chair_1.glb",
  "images": ["inputs/front.png", "inputs/left.png"],
  "views": ["front", "left"],
  "settings": {"model_type": "v3.0:quality", "generation_type": "texture"},
  "jobPath": "hi3d/chair-texture.json",
  "outputDir": "exports/hi3d-chair-texture",
  "dryRun": true
}
```

**根据已验证行为重建的预检请求。** 示例假定工作区内已有 `inputs/reference.png`。本次调用构造图片编辑计划，单独预检返回的是参数和文件数量等计划信息。

```json
{
  "action": "generate_image",
  "targetName": "茶壶",
  "prompt": "保留茶壶轮廓，将背景改为纯白。",
  "images": ["inputs/reference.png"],
  "imageMode": "edit",
  "aspectRatio": "1:1",
  "jobPath": "hi3d/image-job.json",
  "outputPath": "exports/hi3d-preview.png",
  "dryRun": true
}
```

**根据已核查 schema 重建的 3D 自动登记请求。** 示例假定当前工作区已有参考图，并使用 `tag4: null` 表示无适用类别。正式处理完成后，只有下载列表筛得唯一符合条件的 GLB 且登记成功才返回 `registeredModel`。

```json
{
  "action": "generate_3d",
  "targetName": "茶壶",
  "images": ["inputs/front.png"],
  "settings": {"model_type": "v3.0:quality", "generation_type": "both"},
  "jobPath": "hi3d/teapot-model.json",
  "outputDir": "exports/hi3d-teapot",
  "registerName": "茶壶",
  "tag4": null
}
```

**根据已验证行为重建的等待请求。** 假定同一路径的正式调用已经提交并返回 `pending`。等待动作读取原作业中的任务 ID。

```json
{
  "action": "wait",
  "jobPath": "hi3d/image-job.json",
  "seconds": 120,
  "interval": 15
}
```

**根据离线复现重建的独立查询。** 合成账本已有有效任务 ID。模拟 HTTP 200 返回 `{"code":"200","data":{"status":0,"position":2,"percentage":30}}` 后，账本写为 `processing`，CLI 退出码为 0。解码后的 `stdout` 直接给出摘要，其中 `progress.stage` 为 `queueing`，`progress.stale` 为 `false`。

```json
{
  "action": "query",
  "jobPath": "hi3d/example-job.json"
}
```

**根据离线复现重建的零预算等待。** 合成账本已有有效 ID，状态仍为 `submission_uncertain`。账号环境匹配时，模拟传输收到 `/session` 和原 ID 的结果 GET。模拟结果仍在处理，`stdout` 返回 `{result: "pending", job: …}`，`exitCode` 为 0，账本写为 `processing`。

```json
{
  "action": "wait",
  "jobPath": "hi3d/model-job.json",
  "seconds": 0
}
```

另用合成的 `status: 0`、`percentage: 100` 复现，业务仍为 `pending/0`。单次响应为有效 `status: 1` 时，同一等待动作返回 `success/0`，文件交接由后续 `download` 承接。

**根据离线复现摘取的独立查询摘要。** 在另一合成场景中，以 `{"action":"query","jobPath":"hi3d/model-job.json"}` 查询一份旧状态为成功的账本。当前账号错配，仅请求本地 `/session`，工具返回 `exitCode: 2`。下列为 `stdout` 中的部分字段，`success` 是最后一次可靠的远端状态，本次未获得新观察。

```json
{
  "state": "success",
  "progress": { "stage": "query_error", "stale": true },
  "last_query_error": { "code": 409 }
}
```

**根据离线复现重建的独立下载错误。** 用 `{"action":"download","jobPath":"hi3d/example-job.json","outputDir":"exports/sample-model"}` 下载无聚合缓存的合成作业。模拟结果 GET 返回 HTTP 503。本次查询诊断保存后，CLI 返回 `{result: "attention", phase: "download", job: …}`，退出 2。把结果改为有效成功但省略输出地址时，CLI 仍退出 2，回包为带 `phase: "download"` 的阶段错误，账本保留新成功观察。

**根据离线复现重建的组合回包节选。** 已有原作业，`generate_3d` 使用同一计划重入。首次结果查询观察到成功，进入无缓存下载时，用原任务 ID 刷新结果超时。以下是 `stdout` 的关键字段，`exitCode` 为 2，账本仍保留最近一次成功及本次查询诊断。此次没有绑定下载目录或获取文件。

```json
{
  "result": "attention",
  "phase": "download",
  "job": {
    "state": "success",
    "progress": { "stage": "query_error", "stale": true }
  }
}
```

**根据已校验参数重建的本地记录创建示例。** 假定调用方已经从可靠记录确认该任务 ID。指定尚未占用的路径。`adopted` 确认本地账本创建。需要确认服务端最新状态时，另用该路径执行 `query`。

```json
{
  "action": "adopt",
  "kind": "model",
  "taskId": "example-job-001",
  "jobPath": "hi3d/recovered-job.json"
}
```

**根据已核查 schema 重建的免费重试请求。** 假定宿主或准备工具已为当前会话提供该意图 ID。

```json
{
  "action": "retry",
  "retryRequestId": "66dd624b-f618-4da0-b991-dda7a2d1a7bb"
}
```

## 核查依据

- **安装包静态核查。** Windows x64 版 1.2.11，随包 Codex 0.166.0。Runtime 为 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs`，SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。以下是原始 UTF-8 零基字节偏移。`dz[0]` 的定义自 `2522079` 开始，`p$` 参数校验位于 `2528182`，`Vg` 汇总与 `tools/dynamicSpecs` 分别位于 `2671149` 和 `2725778`，线程参数合并位于 `3156356`。`description` 原文与两份生产 rollout 第 2 行的嵌套声明一致，SHA-256 为 `e3f9a2574251014e009b83ddb6b49c67ec45995e01fcbd3a633c2283f1a1b710`。 [Runtime 原始文件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)
- **分派和进程。** 动态调用路由、通用门禁和按线程绑定工作区在 `3167092`、`3167309`、`3190779`。`Rg/lt` 在 `2538057/2548323`，`Tg/Kj` 在 `2500260/2503566`，`cd/az` 在 `2501969/2549822`。显示元数据见 `tne` `2536991`。进度解析函数 `nne` 位于 `2546170`，进度发布位于 `3194145`，`ge` 及其进程应答调用位于 `2108731/3196971`。进程异常格式见 `Jj` `2499118`，取消见 `abortThreadCalls` `3155096`。额度估算、来源补记和自动登记见 `2516448`、`2693701`、`3201572`。
- **桌面代理。** `app.asar` 的 SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。成员 `out/main/index.js` 内的 `Pi` 白名单、`_l.handle`、账号环境门禁和 `requestTool` 分别位于字节偏移 `212862`、`213798`、`214410`、`224263`。合成 401 与会话失效处理见 `225193`、`215895`。响应缓冲和诊断见 `226263`、`226826`，错误归一化见 `216626–217291`，向本地调用方发送的头见 `217582`。取消传播见 `215259`、`225794`。 [Electron ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
- **本地副作用。** Runtime 重读最新账本、通知退款及补记来源的原始字节偏移为 `2541466`、`3194800`、`2693701/3195125`。桌面主进程的退款接收和 `refundHi3d` 分别位于 `315935`、`121094`。组合重试观察器 `Cg.observe` 与额度入口位于 Runtime 的 `2570204`、`2560056`。 [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [Electron ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
- 参数面板与续调在 `runtime.mjs` 的 `handleRuntimeDynamicTool`、`handleServerResponse` 及响应校验函数 `fg`。面板请求注册可从原始 UTF-8 字节偏移 `3195943` 定位，`next_call` 字段从 `3205415` 开始。
- 免费重试静态核查见同一 Runtime 中的 `Cg.quotaTask`、`plan`、`reconcileRegistered` 和 `complete`。零基 UTF-8 字节偏移 `2559588` 为 `quotaTask`，`3191534` 为 `retry_quota` 分派，`3192199` 和 `3192344` 为重试结果对账与复用，`2573045` 为工具回包归并到本地意图状态的分支。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)
- 随包实现位于 `resources/runtime/prebuilt-skills/hi3d/scripts/`。规划及预检见 `hi3d_api.py:126,177,236`、`web_option_gates.py:620,667`、`hi3d_image_workflow.py:18` 和 `hi3d_parameters.py:61,143,192,198`。会话核验、提交、查询、下载和积分诊断见 `hi3d_client.py:50,79`、`hi3d_jobs.py:165,192,269,323,336`、`hi3d_storage.py:43,80,175`、`hi3d_generation_workflow.py:11` 及 `hi3d_artifacts.py:175`。Runtime 无 ID 的保护见 `runtime.mjs` 的 `Tg`（原始 UTF-8 字节偏移 `2500260`），整轮取消的待答请求清理见 `cancelInteractions`。
- **离线核查。** 使用合成 PNG 和模拟客户端验证了预检、待选与校验错误、图片和 3D 组包、同路径复用及指纹冲突。提交故障注入覆盖了明确拒绝、受理不明、响应缺 ID 及 ID 先写盘后出错。使用随包 Python 真 `Client` 配合进程内模拟传输，复现了 `wait(seconds=0)` 沿原 ID 观察、账号错配保留陈旧快照、无效 ID 不发请求，以及 `adopt` 只访问本地会话并独占建账本。隔离代理门禁复现了会话建立后账号或环境切换返回 409。这些实验未连接远端。
- **仅贴图离线复现。** 使用随包 Python 在合成工作区复现了独立纹理的 DTO、引用图槽位及网格字段顺序，验证了缺网格、缺图、显式 texture 与 v2.1 组合、只选择部分参数，以及面板 `both` 混用旧枚举或原生 texture 参数的冲突分支。预检未创建远端客户端或作业账本，非空目录的首次正式调用在执行阶段被拒绝。通过模拟传输复现提交前写盘、同计划复用和受理不明时无第二次 POST，另验证纯 URL 计划的 JSON 请求体。 [参数规划入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_api.py:177>) · [执行阶段目录检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:19>) · [请求体与作业落盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:182>)
- **代理与保存的隔离复现。** 使用从 ASAR 提取的代理处理器和模拟响应，覆盖成功、HTTP 200 业务错误、429、401、畸形 JSON 与传输异常。随包 CLI 配合模拟传输验证了直接摘要和包装摘要、下载仅在新查询诊断写入时使用业务错误包装，以及 `os.replace` 抛 `PermissionError` 时各动作返回阶段错误。替换失败的夹具保留旧账本字节，并清理临时文件。另复现了保存完成后进度回调失败，此时新账本仍在。这些实验覆盖客户端分支。 [随包账户与查询测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/tests/runtime/test_account.py:106>)
- **等待和交接的隔离复现。** 随包 Python 配合假时钟验证睡到截止点即返回 `pending/0`，以及已发请求在截止后返回有效成功时仍采用该结果。临时工作区和模拟传输还验证了组合等待成功后的下载刷新。刷新超时会保留旧成功、保存陈旧诊断并回 `attention/download/2`。另一次复现先形成聚合缓存，再以同计划重入，确认仍执行一次等待 GET，之后复用原文件。使用假的子进程和定时器执行安装包中的 `az/fz/Jj` 逻辑，复现守护超时将已有作业引用随 `attention/process/2` 交付。该实验覆盖包内管理逻辑和回包形态。 [时间判据](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:343>) · [下载交接与异常](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:34>)
- **自动登记的隔离复现。** 用替身目录校验和注册表运行安装包的 `registerGeneratedModel`。一项符合条件的 GLB 加一项非 GLB 时返回 `registeredModel`。零项、多项、重复路径或注册表刷新抛错时返回 `exitCode: 1` 和 `attention/register-model`，原任务与文件列表仍在负载中。实验覆盖 Runtime 包装逻辑，真实文件及桌面状态另由运行记录核对。
- **实际运行观测。** 2026-11-11 活跃 rollout 第 53–62 行记录正式生成收到 `parameters_selected`、`defaulted/assistant_default` 和 `next_call`。第 68 行以补齐后的设置重新调用，同一作业第 102–103 行返回两个 GLB 和一张 WebP，自动登记返回 `attention`、`phase: "register-model"`。第 145–148 行记录选定的本地 GLB 由独立登记工具成功登记。 [参数续调回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:62>) · [自动登记回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:103>)
- **待实测。** 现有生产样本覆盖组合生成与执行单元等待。独立跨轮或重启后的 `query/wait/download/adopt` 可用已有测试作业实测，关联实际请求、账本变化和模型回包。Windows 强制中止的传播、服务端权限、真实限流与超时受理，以及云端计费和退款仍需分别核对。已查样本的生成内容为 `both`，独立纹理的云端输出、PBR 通道、画质及源几何、UV、绑定和动画的保留情况仍待实测。独立 `retry_quota/retry` 的服务响应及成功登记、云端对槽位的解释与成品质量也待实机核查。
- **Skill 指导。** 参数选择、图片生成和免费重试的调用约定见随包文档。 [hi3d Skill 原文](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) · [桌面参数契约](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-parameters.md) · [图片生成参考](../upstream/1.2.11/prebuilt-skills/hi3d/references/image-generation.md) · [免费重试契约](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-free-retry.md)
