# 定位原作业并校验续查资格

以 Hi3D Agent 1.2.11（Windows x64）、随包 Codex CLI 0.166.0 为核查基准。普通多视图 3D 作业和已受理的免费重试子作业共享结果查询入口。本节点从原作业引用出发，到桌面代理放行本次调用中同一任务的首次结果 GET 为止。

## 业务定义

| 项目 | 节点契约 |
| --- | --- |
| 触发条件 | 正式生成在同一次调用内进入等待，或调用方在 `pending`、本地中断、用户明确要求恢复后发起续查。提交受理不明时，先核对原记录里是否已有可用任务 ID。 |
| 上游 | [生成前预检与提交](preflight-generation.md#完成条件与恢复)交付原作业路径、已写盘的任务 ID 或受理不明的记录。[工作区与会话绑定](../infrastructure/workspace/bind-and-restore-workspace-session.md)提供当前线程所属工作区。免费重试从[已登记版本的重试意图](../infrastructure/workspace/import-or-register-model-version.md#已登记版本的免费重试)取得同一重试子作业路径。 |
| 输入 | 当前工作区、可追溯的 `jobPath`、该路径上的原作业记录和桌面当前登录上下文。显式调用可另有等待预算。已定稿的主图、补充参考、目标方向和必保特征仍关联原生成计划，本次 GET 只使用作业身份。 |
| 输出 | 通过时，使用账本的 `kind/task_id` 发送原作业结果 GET。拦截时交付可定位的原因，保留原任务或原提交意图。Hi3D 将这些判断包含在实际工具执行中，工具契约没有独立的资格结果字段。 |
| 完成条件 | 已定位原账本，路径、后端、ID、路由及账号环境通过校验，桌面代理放行并转发请求。「已定位」是过程事实。桌面在每次转发前重新核对会话。 |
| 下游 | 首次 GET 交给[执行单次查询并持久化观测](observe-job-once.md)，后续决定继续等待、停止或在观察到远端成功后进入[确认下载来源与恢复方式](confirm-download-source-and-recovery.md)。产物下载、登记、质量放行和 Codex 轮次各有自己的完成条件。 |

## Skill 绑定

| 归档 | 作用与选用条件 |
| --- | --- |
| [`hi3d/SKILL.md`](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | 普通图片与图生 3D 的通用入口。要求复用稳定的 `jobPath`，正常 `pending` 可沿原作业续查。查询报错时报告原因并结束本轮，等用户要求恢复后再查。提交不明且缺 ID 时先核对原任务历史。 |
| [`hi3d/references/calling.md`](../upstream/1.2.11/prebuilt-skills/hi3d/references/calling.md#查询错误) | 通用 Skill 的按需参考，给出 `adopt`、`wait`、查询错误优先级和同路径恢复规则。 |
| [`image-to-assembly/SKILL.md`](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) · [`head-reference/SKILL.md`](../upstream/1.2.11/prebuilt-skills/head-reference/SKILL.md) | 分别在选用静态装配或人像头部参考路线时约束上游输入和阶段验收。已有作业仍使用本节点的通用路径、账号及代理校验。 |

Runtime 建立有效 Skill 目录并交给 Codex。显式选用时由 Codex 读取入口正文，隐式选用时由模型按需读取，或沿用仍在有效历史中的正文。参考文档独立读取。Runtime 分派工具时另行通过 `r$` 定位受管脚本、检查入口的受管标记。生产样本观察到隐式读取 `hi3d/SKILL.md`，未观察到独立读取 `calling.md`。安装包、生产受管副本和仓库归档中的入口及参考文件内容一致，各自 SHA-256 为 `4c268ae14ece561234682d564cdfa6264c1f121a9ea118137c0388a9240c217d` 和 `03a40466e2a02ac12564daf2a961e4c0ea1578f209c6e7808bb16cfedc818d5f`。 [有效目录与正文读取](../infrastructure/workspace/llm-context.md#有效目录与选用) · [Skill 版本归档](../upstream/1.2.11/README.md)

## LLM Tools

| LLM Tool | 用途摘要与本节点的调用条件 |
| --- | --- |
| [`hi3d_api`](../tools/hi3d-api.md) | Hi3D Runtime 动态工具。持有原路径时，用 `action="query"` 获取一次观察，或用 `action="wait"` 在指定预算内等待。原记录无法使用且已从可靠来源找回 ID 时，可用 `action="adopt"` 建新本地记录。已登记模型的免费重试恢复由 `action="retry"` 按原 `retryRequestId` 定位同一子作业。 |
| [`exec`](../tools/exec.md) | 随包 Codex 的 Code Mode 工具。生产样本通过它调用 `tools.hi3d_api`，并用 JS 的 `text(r)` 交付实际工具结果。 |
| [`wait`](../tools/wait.md) | 随包 Codex 的 Code Mode 工具。仅当 `exec` 返回运行中句柄时，用原 `cell_id` 读取同一 JS 执行单元的输出。远端作业等待使用 `hi3d_api(action="wait")`。 |
| [`workflow_report`](../tools/workflow-report.md) · [`user_interaction`](../tools/user-interaction.md) | 前者仅在实际选用 Skill 且需要管理该工作流时使用，报告图节点的执行状态。后者适用于缺少恢复信息或需要明确授权另开生成时的独立交互。普通续查按路径和账号校验执行。生产样本的 `workflow_report` 调用用于该轮建图。 |

`query`、`wait`、`adopt`、`retry` 是同一 Runtime Tool 的动作。`kind` 是用于选择服务路由的请求枚举。`hi3d_api.py`、`hi3d_jobs.py` 是随包本地脚本，桌面 `GET /v1/session` 是脚本与代理之间的接口。模型可见描述与通用实现见各独立 Tool 页。

## Hi3D 实现

### 决策

显式续查以原 `jobPath` 为入口，从账本读 ID 和类型。即使调用方附带 `taskId` 或 `kind`，`query/wait` 的 CLI 参数也只交接账本路径及适用的等待选项。图像、视角、分类和指纹由原生成计划保留。用同样参数重入组合 `generate_3d` 时，会重新规划并比对指纹。已有有效 ID 但账本仍为 `submitting` 或 `submission_uncertain` 时，组合入口可能提前返回 `attention`，显式 `query/wait` 可按原 ID 校验并续查。提交代码先保存 ID，再写父任务信息和 `queueing/submitted_at`，所以这是合法的可恢复状态。 [提交和查询脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:192>) · [组合生成入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:11>)

**根据已验证行为重建的显式查询请求。** 路径指向当前工作区已有记录。若账本的 `kind` 为 `model`，放行时向代理发送 `GET /v1/model3d/result?jobId=<账本 task_id>`。

```json
{
  "action": "query",
  "jobPath": "hi3d/sample-model.json"
}
```

### 执行

| 步骤 | 执行者与数据交接 | 1.2.11 可复核入口 |
| --- | --- | --- |
| 1. 接收调用 | renderer 在空闲轮次发 `turn/start`，活跃轮次通过带 `expectedTurnId` 的 `turn/steer` 接入。模型在有效上下文中使用原作业引用。Codex 的 `item/tool/call` 提交当前 `threadId/turnId/callId`、工具名及参数。Runtime 从线程注册关联取得 `assetId/cwd`，校验工作区范围和动作 schema。 | renderer `Sn` 1122481、`turn/steer` 1122141。Runtime `item/tool/call` 3167092、`handleRuntimeDynamicTool` 3168308、工作区绑定 3190779。 |
| 2. 定位路径并初筛 | `Rg` 解析工作区内的路径，拒绝越界及符号链接路径段，在当前 Runtime 进程中按规范化绝对路径串行。预读账本后由 `Tg` 拦截特定的受理不明且无 ID 状态。其余经 `Kj` 分派为 `query --job …` 或 `wait --job … --seconds … --interval … --progress json`，并以 `SPARC3D_TOOL_WORKSPACE` 交付实际工作区根。 | Runtime `Rg` 2538057、`lt` 2548323、`Tg` 2500260、`Kj` 2503566、`r$` 2462032。 |
| 3. 核对账本与登录 | Python 校验路径范围、符号链接和存在性，读取 UTF-8 JSON，核对 `backend=hi3d-codex-v1` 和 `task_id` 格式 `[A-Za-z0-9_.-]{1,200}`。进入查询异常处理范围后，通过本地 `GET /v1/session` 取得账号环境并与账本的 `owner_id/environment` 比较。同一 Python 客户端可复用这份会话快照。随后按账本的 `kind` 选路由，3D 类型用 `jobId`，图片类型用 `taskId`。 | [工作区路径](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_storage.py:140>) · [查询前校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:269>) · [会话比对](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_client.py:50>) |
| 4. 转发到服务 | Electron 的 loopback 代理校验 Host、Bearer 和路由白名单，拒绝带 Origin 的请求，再将 `X-Hi3D-Account/X-Hi3D-Environment` 与当前桌面登录态比对。经过 `requestTool` 的 Cookie 校验后转发原 ID 的 GET。当前 `threadId/turnId` 在 `X-Session-Id/X-Turn-Id` 中用于请求关联。显式续查未发现与账本历史线程 ID 的相等校验。 | ASAR 主进程 `Pi` 212862、`_l.handle` 213798、`requestTool` 224263。Python 请求头见 `hi3d_client.py:79–103`。 |

**根据已验证行为重建的控制流伪代码。** 辅助函数名代表实际执行步骤。省略 stderr 事件和工具结果封装。无 ID 的通用拦截及积分不足特例由 `Tg` 判定。Python 的路径、后端与 ID 检查发生在可写查询诊断的异常处理范围之外。

```python
def prepare_result_query(workspace, job_path, client):
    path = resolve_inside_workspace(workspace, job_path)
    blocked = runtime_submission_guard(read_job_if_possible(path))
    if blocked:
        return blocked

    job = load_workspace_job(path)
    require_supported_backend(job)
    task_id = require_valid_task_id(job.get("task_id"))

    try:
        client.check_job(job)
        route, id_parameter = result_route_for(job["kind"])
        return desktop_proxy_forward_get(route, {id_parameter: task_id})
    except QueryPreparationError as error:
        save_query_diagnostic_and_stale_progress(path, job, error)
        return query_attention(job)
```

真实入口在同一 `try` 内发送请求并处理返回，Python 也会依据代理的 HTTP 拒绝响应记录查询错误。这里的伪代码止于资格判定和交接。

### 验收

- **本地资格与远端归属。** 路径、后端、ID 格式、路由和账号环境是代码校验。ID 是否确实来自本次原提交，依靠账本、工具收据或可靠历史核对。代理放行后的服务响应才能确认远端可访问性和最新状态。
- **权限、额度和调度。** 动态工具分派经过宿主的 `skillCredits.confirm(threadId, turnId, [])` 线程与轮次门禁。普通 `query/wait` 未发现专用授权面板、生成额度预扣或作业级熔断。查询错误后暂停恢复是 Skill 指导。同路径串行是进程内约束，显式重复调用可再发 GET。正常等待默认 1800 秒、每 30 秒查询，预算范围 0–3600 秒，间隔范围 5–300 秒。预算为 0 时也查询一次。Python 的会话请求超时为 20 秒，显式 `query` 的结果 GET 默认 90 秒，`wait` 内的单次结果 GET 按剩余预算限制在 1–20 秒。Runtime 子进程时限分别是 120 秒和等待预算加 30 秒。 [Runtime 门禁与分派，偏移 3167309、2503566](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [等待边界](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:336>)
- **系统状态与模型可见性。** `wait` 在本次查询写盘后才按变化发送进度，Runtime 的 `runtime/hi3dProgress` 更新桌面状态卡。进程结束时，进度行可能随缓冲的 `stderr` 和 `stdout` 返回。Code Mode 在脚本实际输出后，按外层调用的 `call_id` 交付结果，供后续采样。资格通过时没有独立的模型可见事件。重连或压缩后，按当前有效历史确认作业引用是否仍可用，必要时从原账本重新取得。 [工具状态进入采样的路径](../infrastructure/workspace/llm-context.md#形成模型可见内容) · [线程历史恢复](../infrastructure/workspace/llm-context.md#读取线程和恢复有效历史)

核查时将脚本运行状态、工具退出码、账本业务状态和远端新观察分别读取。`pending` 可对应退出码 0，`Script completed` 可对应嵌套工具错误。`last_queried_at` 在本地账号核对失败时也可能更新。默认查询摘要包含 `job_file`，Runtime 在取得解析路径时附 `jobPath`。完整账本通过工作区引用读取。 [摘要字段](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_progress.py:71>) · [工具返回与错误](../tools/hi3d-api.md#返回与错误)

## 完成与恢复

| 分支 | 触发条件 | 执行者 | 状态变化及写入顺序 | 可观察结果 | 交接或恢复方式 |
| --- | --- | --- | --- | --- | --- |
| 资格通过 | 原路径、ID、路由和桌面会话校验通过 | Runtime、Python、Electron | 沿用原账本，转发 GET，由后续查询处理写入结果 | 一次新的结果请求 | 等待新观察。普通 `pending` 沿原 `jobPath` 继续。 |
| 路径、后端或 ID 有误 | 越界、缺文件、坏 JSON 或 JSON 非对象、后端不符、ID 无效 | Runtime 或 Python | 查询前拦截，原账本保持原字节 | Runtime 校验错误，或 CLI 阶段错误、退出码 2 | 核对原路径、适配器或可靠的 ID 来源。 |
| 提交不明且无 ID | `submitting/submission_uncertain` 无有效 ID | `Tg` 或 Python | 保留原记录。Runtime 先按 ID 真值初筛，Python 再校验格式 | 普通分支为 `attention`，原因 `submission_uncertain_without_task_id`，并返回 `canQuery:false` 与 `requiresRegenerationConfirmation:true`。对普通生成，HTTP 200、业务码 `30010000` 且 `task_id_present/submission_has_task_id` 均为假值时，`Tg` 跳过通用提示，显式续查仍会在 Python 因缺 ID 停止 | 优先核对原任务历史。免费重试保留原 `retryRequestId` 与子作业。普通 3D 若决定另开生成，先取得用户明确确认，再使用新作业和输出路径。 |
| 登录、账号环境或路由拒绝 | 登录失效、账号环境错配、代理拒绝、账本 `kind` 无法路由 | Python 或 Electron | 查询异常处理保留旧 `state/result`，写入 `last_query_error`、`last_queried_at` 和陈旧进度，再原子替换账本 | `wait` 可返回 `attention`、退出码 2，`query` 返回带诊断的摘要。已有 `success` 可伴随 `stale:true` | 说明本次原因，结束当前轮。用户要求恢复后按原账号环境和原路径再查。 |
| 本地取消或执行超时 | 轮次中断、进程停止或超出本地执行预算 | Codex、Runtime、Python | 停止本地执行。保留已落盘记录，强制中断时可能缺新的诊断 | 工具中断、执行超时或返回 `attention`。正常等待预算耗尽可返回 `pending` | 活跃的 Code Mode 单元沿 `cell_id` 取回输出。单元失效后以原作业路径重新发起查询。 |
| 重复调用 | 多次恢复同一原作业 | Runtime、Python | 同一规范路径在当前进程排队，各次显式查询可以更新账本 | 同一 `task_id` 的多个观察 | 继续复用原作业。跨路径及跨进程的并发保护另行核对。 |
| 找回可信裸 ID | 原账本无法使用，已从可靠来源确认原 ID 与任务类型 | `hi3d_api(action="adopt")` | 先验任务类型，再读本地会话、校验 ID 并独占创建指定路径的 `created` 记录。原路径同名写入会被独占创建拒绝 | `adopted` 表示本地记录已建 | 以该记录再次进入显式 `query/wait`。远端可访问性由后续请求确认，原任务归属由来源证据支持。该记录无原计划指纹，组合生成重入会在同路径指纹校验处停止。 |

「恢复原作业引用」可作为跨轮条件流程维护。完整的恢复交接包含引用、已确认的任务 ID 和来源证据。仍缺可靠 ID 时保留提交意图，等待核对。 [归档恢复指导](../upstream/1.2.11/prebuilt-skills/hi3d/references/calling.md#查询错误) · [随包 `adopt_job`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:165>)

## Vet3D 迁移与核查范围

### 供应商无关的契约

为每个生成意图保存稳定的本地作业引用、工作区归属、适配器配置标识、远端任务 ID 和受理凭据。模型续查时只需给出本地引用。适配器在执行前读取作业并验证账号环境，传输层在转发时复核当前凭据。无 ID、重新登录和需人工核对是可恢复的客户端分支。重新生成使用新的提交意图。

分别保留最后一次可靠的远端观察与这次本地执行诊断。给模型交付轻量摘要，包含作业引用、观察时间、是否陈旧、已知状态和恢复条件。界面进度可以独立更新。新轮、重连或上下文压缩后，按作业引用重新取得必要摘要。原账本损坏或缺失时另存找回证据，下一次查询继续校验同一远端 ID。Vet3D 的 LLM、生图与 3D 供应商及 API 仍待选型。此契约使用业务语义，Hi3D 的字段仅用于说明该安装版本。

### 核查依据与缺口

当时运行的桌面来自 `D:/install/Hi3DAgent.__hi3d-transaction/Hi3D.exe`。下表 Runtime 偏移指 `resources/runtime/dist/runtime.mjs` 的 UTF-8 字节偏移。桌面偏移指 ASAR 内成员自身的字节偏移。ASAR SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`，Runtime bundle 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [Runtime manifest](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [Runtime bundle](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [Electron ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

| 证据级别 | 核查内容 |
| --- | --- |
| 安装包静态实现 | 上述 `Rg/Tg/Kj`、`query_job/adopt_job` 和 `_l.handle` 覆盖入口到转发。进度来自 Python 写盘后的 stderr，Runtime `az/nne` 对应 2549822、2546170，发布回调 3194145，工具回包 3196971，renderer 消费在 `out/renderer/assets/index-CDPCug_K.js` 1161925。 |
| 同版离线复现 | 使用随包 Python 和合成作业。本地账本为 `submission_uncertain` 且持有有效 ID 时，相同账号环境、新线程标识可到同一 ID 的模拟 GET，模拟处理中结果落为 `processing`。将本地旧 `success` 记录恢复到不同账号时，只请求模拟 `/session`，保留旧状态，写 409 查询诊断和 `stale:true`。另用包内代码验证 `Tg` 分流、代理会话切换和 `adopt` 独占创建。显式 `query/wait` 的 `dryRun:true` 无法保证离线，Runtime 会跳过 `Tg` 初筛，但它不被转成该 CLI 动作的离线参数。 |
| 本机运行观测 | 正常组合调用中，rollout 第 68–96 行发起生成并按 `cell_id` 等待。第 102 行记录动态工具事件，第 103 行才由外层工具回包交付原 ID、已下载文件、登记待处理标记和 stderr 中 12 条历史进度。第 816 行的压缩替换历史未保留原作业引用。已查样本未覆盖跨轮显式 `query/wait/adopt`。 [生产回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:103>) |
| 待实测 | 用既有测试作业从新轮或宿主重启后显式续查，关联工具调用、实际结果 GET、作业落盘和后续模型请求。服务端对跨线程、其他账号、过期 ID、限流和任务历史查找的真实行为，需另用授权样本核对。 |
