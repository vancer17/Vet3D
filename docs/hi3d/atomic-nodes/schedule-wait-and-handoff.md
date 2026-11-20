# 调度等待并决定交接

以 Hi3D Agent 1.2.11（Windows x64）、随包 Codex CLI 0.166.0 为核查基准。Python 负责安排原作业的下一次查询，Runtime 约束本地子进程，Code Mode 控制何时把脚本输出交还模型。本节点以已写盘的本次观察和诊断决定继续等、停止或交给下载来源核验。

## 业务定义

| 项目 | 节点契约 |
| --- | --- |
| 触发条件 | 普通 3D 或免费重试子作业已受理，组合调用进入内部等待。已取得原作业引用时，也可显式发起 `hi3d_api(action="wait")`。独立 `query` 只做一次观察，后续动作由调用方根据摘要决定。 |
| 上游 | [定位原作业并校验续查资格](locate-job-and-qualify-resume.md)交付原作业引用和会话范围。[执行单次查询并持久化观测](observe-job-once.md)交付每次观察或诊断，等待循环可多次使用这段实现。 |
| 输入 | 当前工作区、稳定的 `jobPath`、账本中的 `task_id/kind`、账号环境和等待预算。组合调用还持有原输出目录和适用的登记参数。主图、补充参考、目标方向和必保特征留在原提交计划，结果查询只传原作业身份。 |
| 输出 | 正常处理中安排下一次同 ID 查询，预算到期交付 `pending` 和原作业摘要。查询不可用或失败时交付相应诊断。新鲜成功交付原作业引用及适用的原输出目录。 |
| 完成条件 | `wait_job` 依据写盘后的 `job_outcome` 停止循环，或业务预算到期。只有本次有效成功且无查询错误时放行下载交接。 |
| 下游 | 组合调用内部进入[确认下载来源与恢复方式](confirm-download-source-and-recovery.md)。分阶段调用先让模型取得摘要，再用原 `jobPath`、`outputDir` 发起下载。文件可用性、模型登记、质量放行和 Codex 轮次各有自己的完成条件。 |

## Skill 绑定

| 归档 | 选用条件与作用 |
| --- | --- |
| [`hi3d/SKILL.md`](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#3d-任务工作流) | 普通图生 3D 的通用入口。指导组合调用优先等待同一工具，普通 `pending` 沿原路径继续，查询报错后报告本次原因、结束当前轮，等用户明确要求恢复。没有可靠百分比时显示不定进度。 |
| [`hi3d/references/calling.md`](../upstream/1.2.11/prebuilt-skills/hi3d/references/calling.md#查询错误) | 通用 Skill 的按需参考，说明等待参数、查询错误优先级、陈旧快照及同路径恢复。 |
| [`hi3d/references/desktop-free-retry.md`](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-free-retry.md) | 从已登记模型发起免费重试时使用。宿主持久化 `retryRequestId` 对应的子作业与输出目录，受理后按子任务 ID 查询。 |

Runtime 向 Codex 提供有效 Skill 目录。新轮显式选择会载入入口正文，隐式选择可按需读取正文或沿用有效历史中的版本。参考文件独立读取。安装包、生产受管副本与仓库归档的通用入口和 `calling.md` 各自哈希一致。生产 rollout 有隐式读取入口的回包，未观察到单独读取 `calling.md`。分派阶段 Runtime 的 `r$` 另行核对受管标记并定位脚本。领域 Skill 仅在选用对应路线后约束输入、阶段和验收。等待退出由通用代码判定，用户何时要求恢复由 Skill 指导和实际答复决定。 [有效目录与读取时机](../infrastructure/workspace/llm-context.md#有效目录与选用) · [版本归档](../upstream/1.2.11/README.md) · [生产入口读取](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:19>)

## LLM Tools

| LLM Tool | 调用条件与用途 |
| --- | --- |
| [`hi3d_api`](../tools/hi3d-api.md#查询与等待诊断) | Runtime 动态工具。组合 `generate_3d/retry` 在内部等待。调用已返回 `pending` 或需受控恢复时，按条件用原作业 `wait` 或单次 `query`。分阶段取得成功摘要后可用 `download` 承接。生产此次实际调用的是组合 `generate_3d`。 |
| [`exec`](../tools/exec.md) | 当前轮启用 Code Mode 时承载嵌套调用。生产脚本用 `await tools.hi3d_api(...)` 取得结果，再以 `text(r)` 将其交付模型。 |
| [`wait`](../tools/wait.md#关联终止与恢复) | Code Mode 交回 `Script running with cell ID …` 时，按原 `cell_id` 读取同一 JS 执行单元。业务等待由 `hi3d_api(action="wait")` 或组合调用内部的 `wait_job` 执行。 |
| [`workflow_report`](../tools/workflow-report.md) | 仅在已选用 Skill 且需要报告工作流图时使用。它报告图节点状态，作业交接依据仍来自实际查询和工具结果。 |

`generate_3d`、`retry`、`query`、`wait`、`download` 是 `hi3d_api` 的动作，`kind` 是作业类型枚举。`wait_job`、`query_job`、`download_job` 是随包 Python 函数。`item/tool/call` 是调用协议，`runtime/hi3dProgress` 是桌面通知。工具描述和通用参数以独立 Tool 页为准。

## Hi3D 实现

### 决策

组合 `generate_task` 先提交或按同路径、同指纹复用作业，再用原状态判断是否进入 `wait_job`。本地 `submission_uncertain` 或明确失败可使组合动作提前结束。有有效 ID 的受理不明账本仍可显式 `query/wait`。等待循环每次都以本次保存的观察或查询诊断调用 `job_outcome`。优先处理查询错误，其次看终态，最后判断处理中和剩余预算。 [组合生成入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:22>) · [结果优先级](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:323>)

**根据已验证行为重建的分阶段等待请求。** `jobPath` 指向当前工作区中已保存的作业。每次 GET 从账本读同一任务 ID，常规 3D 路由是 `GET /v1/model3d/result?jobId=<task_id>`。组合调用在同一进程传递原路径和输出目录。

```json
{
  "action": "wait",
  "jobPath": "hi3d/model-job.json",
  "seconds": 60,
  "interval": 30
}
```

### 执行

| 层 | 计时起点、执行与超时结果 |
| --- | --- |
| **Python 轮询** | `wait_job` 用单调时钟计算截止时间。默认预算 1800 秒、间隔 30 秒，范围分别为 0–3600 和 5–300。首次通过资格检查后即使预算为 0 也尝试结果 GET。每次 GET 的超时按剩余预算钳制在 1–20 秒，会话握手另有 20 秒超时。处理中且未到期时只睡实际剩余时间与间隔中的较小值，到期后退出。 |
| **Runtime 进程时限** | `Rg` 按规范化 `jobPath` 排队，`az` 启动子进程后才开始计时。独立 `query` 为 120 秒，独立 `wait` 为 `seconds + 30` 秒，组合 `generate_3d/retry` 为 `seconds + 1230` 秒。守护超时可经 `Jj` 返回 `attention/2`、`phase:"process"` 及已知作业引用。 |
| **Code Mode 输出等待** | `exec` 首次让出后可返回 `cell_id`。外层 `wait` 的 `yield_time_ms` 控制本次取输出的等待时长，处理器默认为 10 秒，宿主可应用宽限和上限。`max_tokens` 控制交付量。每次等待有新的外层 `call_id`，继续使用同一 `cell_id`。生产正式调用先让出约 1 秒，后续每次请求 120 秒的等待预算。 |

已发出的查询可以在业务截止时间之后才返回。实现仍先采用该次有效观察，得到终态就按终态返回。独立 `query` 和无缓存下载的刷新 GET 默认各有 90 秒请求超时。桌面代理还有自己的 HTTP 守护。三层计时可分别结束，`Script running` 只说明 JS 单元仍可等待。 [轮询实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:336>) · [Runtime 分派时限](../tools/hi3d-api.md#动作的执行预算) · [Code Mode 参数与结果](../tools/wait.md#参数与结果)

**根据随包实现重建的调度伪代码。** `observe_and_save` 代表 `query_job`。辅助函数名为示意。每次有效或异常观察先写盘，随后才有进度回调和等待决策。读取、资格或写盘异常可由外层处理。

```python
def wait_until_handoff(job_path, seconds, interval, clock, sleep, on_progress):
    if not 0 <= seconds <= 3600 or not 5 <= interval <= 300:
        raise ValueError("invalid wait budget or interval")

    deadline = clock() + seconds
    previous_progress = None
    while True:
        timeout = max(1, min(20, deadline - clock()))
        job = observe_and_save(job_path, timeout)

        progress = job["progress"]
        if on_progress is not None and progress_changed(previous_progress, progress):
            on_progress(progress)
            previous_progress = dict(progress)

        outcome, exit_code = job_outcome(job)
        if outcome != "pending" or clock() >= deadline:
            break
        sleep(min(interval, max(0, deadline - clock())))
        if clock() >= deadline:
            break
    return {"result": outcome, "job": job}, exit_code
```

Runtime 通过 `item/tool/call` 接收当前线程、轮次及内层调用，校验工作区并启动脚本。每次查询用工作区账本定位原 ID。桌面代理在每次转发时检查当前登录账号和环境。状态或队列等变化触发 Python 进度回调，Runtime 从 `stderr` 转成桌面事件并携带 `assetId/threadId/turnId/callId/taskId` 等关联字段。renderer 只接受对应轮次的数据。进程结果沿原内层调用返回。模型从脚本的实际输出和后续有效历史获得摘要，最终回包也可能带缓存的 `stderr`。 [原作业资格检查](locate-job-and-qualify-resume.md#执行) · [进度输出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_progress.py:55>) · [形成模型可见内容](../infrastructure/workspace/llm-context.md#形成模型可见内容)

### 验收

- **结果与放行。** 3D 查询有效响应要求 HTTP 200、业务码 200、对象型 `data` 与整数状态 0 或 1。共享图片路径另识别 2 为生成失败。查询错误优先于账本 `state`。下载入口有聚合 `artifact` 时校验账号及缓存，无聚合缓存时重新 GET，并要求新鲜成功、无查询错误和可用 HTTPS 候选。同计划重入组合生成时，下载复用缓存之前仍会先经过等待查询。 [单次观察判读](observe-job-once.md#决策) · [组合下载交接](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:175>)
- **权限、配额与重试。** 普通结果查询沿用宿主门禁、原账号环境和代理白名单，未观察到普通等待打开专用确认面板或预扣新生成额度。Runtime 可能对明确失败的新观测发布原作业的本地额度对账，本地事件只更新桌面用量估算。免费重试按原意图和固定子作业处理。已查客户端对结果 HTTP 429 按查询错误停止，未发现针对作业的自动退避或熔断。 [代理响应归一化](../tools/hi3d-api.md#桌面结果代理的响应归一化) · [本地额度对账](../tools/hi3d-api.md#本地对账与来源补记)
- **取消与恢复。** 桌面停止轮次时，Runtime 按线程和轮次中止本地进程，关闭连接时可中止当次桌面 HTTP。已受理的远端作业可继续。Code Mode 的 `terminate:true` 是另一条本地执行单元终止路径，向外部桌面工具的实际传播仍待实测。重连可读回线程和转录，原作业身份仍以账本为准。生产独立 Memory 未启用，已核实的压缩替换历史缺少原作业引用，已查实现没有自动重启旧轮询的证据。 [执行单元终止](../tools/wait.md#关联终止与恢复) · [线程和有效历史恢复](../infrastructure/workspace/llm-context.md#读取线程和恢复有效历史) · [Memory 核查](../infrastructure/workspace/llm-context.md#独立-memory-的核查)

独立等待的成功表示可进入下载核验。新完成的组合调用要等下载返回。启用自动登记时，Runtime 再核对是否只有一个符合路径约束的 GLB，并尝试提交版本。代码单元完成、进程退出码、下载文件、登记回执、质量验收和 `turn/completed` 分别记录，状态卡的完成可以先于下载或登记的返回。 [运行时自动登记](../tools/hi3d-api.md#已下载-3d-产物与登记)

## 完成与恢复

| 分支 | 触发条件 | 执行者 | 状态变化及写入顺序 | 可观察结果 | 交接或恢复方式 |
| --- | --- | --- | --- | --- | --- |
| 正常继续等 | 新观察仍为处理中，剩余预算大于 0 | Python | 保存观察和进度，按变化发快照，睡到下次查询 | 账本 `processing`，界面可显示排队 | 同一进程、同一作业继续 GET。 |
| 正常到期 | 最后一次有效观察仍在处理，达到预算 | Python | 保留最后有效观察，退出本次等待 | `pending`，退出码 0 | 用原 `jobPath` 继续等。组合调用可按同计划重入。免费重试沿原 `retryRequestId` 及固定子作业。 |
| 成功交接 | 本次保存的观察有效成功，且没有查询错误 | Python、组合流程或模型 | 保存成功后返回摘要或内部交给下载 | 独立 `wait` 返回 `success/0`，组合可能仍运行 | 核对原输出目录和候选来源。有聚合缓存则复验，无缓存则另取新鲜结果。 |
| 查询不可用，待用户恢复 | 账号环境、传输、代理、限流或结果结构异常 | Python、模型 | 写查询诊断、尝试时间和陈旧进度。旧结果可被保留 | `wait` 为 `attention/2`，`query` 为带诊断的摘要。账本的 `success` 可伴随 `stale:true` | 报告本次原因并结束本轮。待用户明确要求后，用正确账号环境和原作业恢复。 |
| 业务拒绝或生成失败 | HTTP 200 内含可解析的非成功业务码且错误来源未标为 `desktop-proxy`，或共享图片路径收到有效生成失败 | Python、模型 | 查询拒绝置本地 `failed`，清旧结果并记录 `query_failed:true`。图片生成失败记录生成阶段诊断 | `failed/1`。查询拒绝分支确认客户端对本次查询的判定，生成引擎状态需要其他服务证据 | 停止等待，保留原作业。需要复查时按原 ID 发起显式查询。 |
| 本地中断、守护超时或保存失败 | 用户停止、子进程时限到期，或账本更新异常 | Codex、Runtime、Python | 停止执行或返回异常，磁盘可能保留旧记录，也可能已经写入本次观察 | 本地工具错误或 `attention`。进程异常可带 `phase:"process"` | 执行单元仍有效时按 `cell_id` 取输出，否则读回最后有效账本并续查。 |
| 受理不明或重复调用 | 缺少有效 ID，或相同路径重复进入 | Runtime、Python | 无 ID 时保存原意图并停止。相同路径的正常调用在当前进程内串行，组合重入比对指纹 | `attention/canQuery:false`、阶段错误，或同一任务的多个观察 | 核对原任务历史。已保存有效 ID 可显式续查。另开生成按独立提交意图处理。 |
| 交接后受阻 | 下载刷新不可用、缺候选或模型登记失败 | 下载脚本、Runtime | 下载刷新可写入新诊断。登记失败保留已经下载的文件和作业记录 | 组合可回 `attention/download/2`、`failed/download/1` 或 `attention/register-model/1` | 按失败阶段恢复。登记按实际 GLB 或已有登记回执处理，最终交付仍需质量验收。 |

免费重试意图由 Runtime 单独维护。首次受理的子作业写盘后，组合重试可在首次查询之前发出 `submitted` 进度。已取得登记回执时可直接复用。`Cg.complete` 可把仍在等待或登记需处理的意图记为 `interrupted`。恢复继续使用同一 `retryRequestId`，子作业状态由实际查询确认。 [子作业受理与进度](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:73>) · [免费重试结果与复用](../tools/hi3d-api.md#免费重试与结果复用)

## Vet3D 迁移与核查范围

### 供应商无关的契约

- 作业调度使用持久作业引用和单调时钟，分别记录本次等待预算、单次网络预算与宿主执行时限。界面和模型可以有自己的结果读取节奏，继续同一作业使用同一远端任务身份。
- 保存可追溯的最近有效观察、本次本地诊断与新鲜度。先落盘，再向界面发布进度或向模型交付摘要。预算到期返回可续查引用，确认成功后交给独立的候选获取与文件验证。
- 中断后恢复同一作业与已绑定输出。按适配器和工作区隔离，按原意图防止重复提交。用户另行授权的新生成使用新的作业记录。LLM、生图与 3D 供应商及 API 仍待选型，字段名以所选适配器的实现为准。

### 安装包依据与验证

核查副本位于 `D:/install/Hi3DAgent.__hi3d-transaction/resources`。下列 Runtime 和 ASAR 偏移是各自文件或成员的零基 UTF-8 字节偏移。Runtime bundle SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。桌面 ASAR 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。 [版本清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [Runtime bundle](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [Electron ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

| 证据级别 | 核查内容 |
| --- | --- |
| 安装包静态实现 | 随包 `hi3d_jobs.py:269–355` 含观察和调度，`hi3d_generation_workflow.py:22–59,73–107` 含组合交接，`hi3d_artifacts.py:175–190` 含缓存及下载刷新。Runtime `Kj/Rg/az/Jj` 位于 `2503566/2538057/2549822/2499118`，进度解析、发布及回包位于 `2546170/3194145/3196971`，中止位于 `3155096`，免费重试意图状态归并见 `2573045`。ASAR `out/main/index.js` 的桌面转发和结果代理见 `191036/213798/224263`，renderer `out/renderer/assets/index-CDPCug_K.js` 的进度消费见 `1161925`。 |
| 离线复现，正常路径 | 临时工作区内运行随包 Python 的 `generate_task → wait_job → download_job`，注入假时钟、假 HTTP 和本地候选文件。同计划复用原作业。60 秒预算、30 秒间隔下，先保存处理中，睡 30 秒后保存成功，下载检查同 ID 的第三次结果响应后形成 `artifact`。另测预算 5 秒、间隔 30 秒，只睡 5 秒并返回 `pending/0`。 |
| 离线复现，边界路径 | 首次结果成功，下载刷新超时，得到 `attention/download/2`。账本保留旧成功及新的陈旧标记，没有取文件或写聚合清单。另从包内进程调度函数注入假子进程和虚拟定时器，复现 watchdog 结束本地进程、返回携带原作业引用的 `attention/process/2`。这些验证覆盖客户端状态、顺序和回包。 |
| 本机运行观测 | 正式生成在生产 rollout 第 68 行发起，第 70 行给出 `cell_id`。同一单元续读五次，前四次只有运行状态。第 102–103 行回内层失败事件及外层 `Script completed`，业务为 `attention/register-model`，仍带下载文件和 12 条历史进度。第 145–148 行独立登记，之后才有轮次终态。桌面日志第 1506、1507 行的两次结果响应相隔约 0.24 秒，与账本首次终态及最后观察时间相符。脱敏日志缺任务 ID，配对依赖时序交叉印证。 [正式生成与回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:68>) · [结果响应日志](<D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:1506>) · [轮次终态](<D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:1752>) |
| 待实测 | 用已有测试作业核对独立跨轮或冷重启续查。用可控延时验证 Code Mode 终止经桌面到实际请求的传播、Windows 进程终止后的账本状态。真实额度、免费重试、远端限流及服务端取消行为需另行取证。 |
