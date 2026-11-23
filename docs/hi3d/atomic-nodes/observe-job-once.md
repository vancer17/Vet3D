# 执行单次查询并持久化观测

核查基准为 Hi3D Agent 1.2.11（Windows x64）及随包 Codex CLI 0.166.0。本节点从原作业的结果请求获准发送开始，覆盖响应判读、快照写盘和结果交接。一次调用可取得仍在处理的有效观测，也可只写入本次查询诊断。

## 业务定义

| 项目 | 节点契约 |
| --- | --- |
| 触发条件 | 显式 `hi3d_api(action="query")`，或 `wait`、组合生成、组合免费重试内部的一次查询。无聚合产物缓存的 `download` 也使用此路径刷新同一任务。 |
| 上游 | [定位原作业并校验续查资格](locate-job-and-qualify-resume.md)交付工作区内的原 `jobPath`、账本中的 `kind/task_id`、当前账号环境及获准转发的结果请求。查询处理也会记录发生在结果 GET 前的账号复核错误。 |
| 输入 | 原账本、当前调用的会话关联信息和结果接口响应。本次请求用账本 ID 定位。主图、补充参考、目标方向和必保特征保留在原提交计划，GET 只传原任务身份。 |
| 输出 | 持久化的新观测、本地查询拒绝或陈旧快照，以及适合调用方的作业摘要。Python 另在该进程内返回本次原始 `data`，供带检查的下载路径消费。 |
| 完成条件 | 经校验的观测已成功替换账本时，可交给下游判定。查询诊断成功写盘时，可据此停止或恢复。持久化失败由调用方处理，未经提交的观测不能用于交付。 |
| 下游 | `wait` 和组合动作把已持久化的观测或诊断交给[调度等待并决定交接](schedule-wait-and-handoff.md)。显式 `query` 交付摘要，由调用方决定下一步。[下载来源检查](confirm-download-source-and-recovery.md)也可调用单次查询刷新远端候选。 |

## Skill 绑定

| 归档 | 作用与选用条件 |
| --- | --- |
| [`hi3d/SKILL.md`](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | 普通图片生成和图生 3D 的通用入口。正常 `pending` 沿原作业继续。查询报错后报告具体原因、结束当前轮，待用户明确要求恢复时再查。 |
| [`hi3d/references/calling.md`](../upstream/1.2.11/prebuilt-skills/hi3d/references/calling.md#查询错误) | 处理查询错误时按需读取的参考，说明 `last_query_error`、陈旧进度、明确拒绝和同路径恢复的判读。 |
| [`image-to-assembly/SKILL.md`](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) · [`head-reference/SKILL.md`](../upstream/1.2.11/prebuilt-skills/head-reference/SKILL.md) | 分别在选用静态装配或头部参考路线后，约束该路线的输入和产物验收。结果观测使用通用查询和写盘判据。 |

Runtime 向 Codex 提供有效 Skill 目录。新轮的显式选择会读取入口正文，隐式选择可按需读正文或沿用有效历史中的正文。参考文件单独读取。安装包、生产受管副本与仓库归档中的通用入口及调用参考各自哈希一致。生产样本观察到隐式读取 `SKILL.md`，未观察到单独读取 `calling.md`。分派时 Runtime 的 `r$` 另外校验受管入口并定位脚本。状态机和写盘条件由代码执行。Skill 指导调用方如何解释错误和何时恢复。 [有效目录与正文加载](../infrastructure/workspace/llm-context.md#有效目录与选用) · [归档版本](../upstream/1.2.11/README.md)

## LLM Tools

| LLM Tool | 本节点的用途与条件 |
| --- | --- |
| [`hi3d_api`](../tools/hi3d-api.md#查询与等待诊断) | Hi3D Runtime 动态工具。需要一次观察时用 `query`，在给定预算内等待时用 `wait`。组合 `generate_3d/retry` 内部调用本节点。无聚合缓存的 `download` 会另取一次新鲜观察。生产样本覆盖组合调用，显式 `query/wait` 已离线复现。 |
| [`exec`](../tools/exec.md) | 在启用 Code Mode 时承载嵌套调用。生产中脚本 await 后执行 `text(r)`，交付实际返回内容。 |
| [`wait`](../tools/wait.md) | Code Mode 交回运行中句柄时，按原 `cell_id` 取得后续输出。远端任务的一次查询由 `hi3d_api` 的动作或其内部脚本执行。 |

`query/wait/download` 等是 `hi3d_api` 的动作。`kind` 是路由枚举。`query_job`、`wait_job`、`save` 是随包 Python 函数，`runtime/hi3dProgress` 是桌面通知。已选 Skill 可以用 [`workflow_report`](../tools/workflow-report.md) 报告工作流状态。作业观察的证据来自原账本和实际工具回包。

## Hi3D 实现

### 决策

**新鲜结果的判据。** Python 接受 HTTP 200、`str(code) == "200"`、对象形式的 `data`，以及严格整数 `data.status`。3D 接受 `0`（处理中）、`1`（成功），图片还接受 `2`（生成失败）。`record_parent` 在更新状态前核对响应中的可选 `parentId`。已有父链冲突会进入查询异常。请求用原 `task_id`，1.2.11 的结果分支未比对响应回显的 `jobId`。离线回放验证了响应回显异于请求时仍能保存观察，账本的原任务 ID 保持不变。 [父链校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:18>) · [结果分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:269>)

**本地查询拒绝。** HTTP 200 携带可按 1–12 位十进制数字解析的非 200 业务码，且来源未标为 `desktop-proxy` 时，客户端清除旧结果并写 `failed/query_failed:true`。未知数字码和系统忙也符合这项条件。该状态足以停止本次等待。远端生成引擎是否终止须另有服务证据。HTTP 429、网络错误、响应形状无效或代理拒绝走查询不可用分支。 [错误归一化](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_storage.py:80>) · [本地失败写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:256>)

**根据已验证行为重建的调用。** 示例假定当前工作区已有记录。脚本从账本读 `kind/task_id`。对普通 3D，桌面代理路由是 `GET /v1/model3d/result?jobId=<task_id>`。

```json
{
  "action": "query",
  "jobPath": "hi3d/sample-model.json"
}
```

### 执行

| 跳转 | 执行者、触发与数据交接 |
| --- | --- |
| 分派并发请求 | Codex 的 `item/tool/call` 交付参数和当前 `threadId/turnId/callId`。Runtime 按线程取 `assetId/cwd`，从工作区解析 `jobPath`，由 `Kj` 分派给随包 Python。Python 将账本 ID 编入结果路由，并以 `X-Session-Id/X-Turn-Id` 传递当前调用的关联信息。工具调用 ID 用于宿主与工具回传。 |
| 桌面代理接收结果 | Electron 复核路由、登录态、账号环境和 Cookie，向配置的服务转发同一 ID。收到完整响应后，`requestTool` 写 `model3d_result_response` 诊断。诊断发生在 Python 写盘之前。代理可保留上游 HTTP 状态并归一化业务错误。非法 JSON、重定向或传输异常可返回带 `desktop-proxy` 来源的 502。HTTP 401 或业务 401 进入登录失效处理。 |
| 判读并保存 | `query_job` 校验包络和父链，再按新鲜结果、拒绝或不可用写入字段。最后更新 `last_queried_at`，计算 `progress`，在同目录写临时文件并 flush/fsync，执行 `os.replace` 后清理临时文件。保存调用位于查询异常处理范围之外。 |
| 回传并交接 | `query` 返回 `job_summary`。 `wait` 在保存后发出符合条件的进度，继续等待或交付 `{result, job}`。Runtime 用 `ge` 包装 `exitCode/stdout/stderr?`，沿原 RPC ID 应答。Code Mode 由实际脚本输出形成模型可见结果。一次观察可以在 Python 等待期间完成，模型在该工具的后续回包中取得结果。 |

**按安装包行为重建的伪代码。** 省略已在上游执行的路径与 ID 校验及工具包装。有效结果路径先写内存中的状态，再投影或脱敏结果。异常处理追加诊断，已发生的字段更新没有事务回滚。最终保存完成后才交付本次进程内结果。

```python
def observe_once(client, path, timeout):
    job = load_and_validate_job(path)
    data = {}
    try:
        client.check_job(job)
        http_status, body = get_result(client, job["kind"], job["task_id"], timeout)
        data = body.get("data")
        if valid_status_envelope(http_status, body, job["kind"]):
            record_parent(job, data)
            clear_first_terminal_if_previous_query_error(job)
            job["state"] = map_status(data["status"])
            store_projected_result(job, data)
            job["result_observed_at"] = now()
            job.pop("last_query_error", None)
            set_first_terminal_if_needed(job)
        else:
            error = describe_response_error(http_status, body)
            rejected = (
                http_status == 200
                and error.get("code") is not None
                and error["code"] != 200
                and error.get("error_source") != "desktop-proxy"
            )
            record_query_failure(job, error, business_failure=rejected)
    except Exception as error:
        record_query_failure(job, describe_exception(error))
        data = {}

    job["last_queried_at"] = now()
    job["progress"] = progress_snapshot(job)
    atomic_save(path, job)
    return job, data if isinstance(data, dict) else {}
```

### 验收

- **时间与状态。** `result_observed_at` 在有效状态和明确业务拒绝时更新，进度里的 `observed_at` 取该值。`last_queried_at` 记录客户端尝试时间，账号比对失败时也可能更新。首次本地终态时间按需设置，若旧 `error.phase` 是 `query`，下一次有效观察会先清除旧的首次终态时间。两个时间均来自客户端 UTC。遇到畸形 URL 导致处理异常时，`state` 可为新值而结果和观察时间仍旧。此时优先读本次错误和 `stale`。 [字段写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:256>) · [时间与进度投影](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_progress.py:18>)
- **权限与数据。** 工作区、路径和登录会话由 Runtime、Python 与代理校验。桌面结果请求有 600 秒代理上限，通用结果转发分支的预缓冲上限是 8 MiB。错误诊断保留可解析的错误码、受限追踪 ID 和脱敏原因。`public_record` 对结果按字段名、URL 和可解析的嵌套 JSON 规则脱敏。账本中的 URL 查询部分被替换，片段被移除。默认摘要排除原始 `data`。无聚合缓存的下载路径另取本次原始地址，通过当前状态和候选校验后才使用。 [会话和传输](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_client.py:30>) · [脱敏实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_storage.py:68>) · [下载候选校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:175>)
- **等待与权限决策。** 普通查询使用通用线程、轮次门禁。显式结果 GET 默认 90 秒，`wait` 内单次 GET 按剩余预算取 1–20 秒，会话 GET 单独为 20 秒。Runtime 进程预算分别为 120 秒和 `seconds + 30` 秒。单次查询错误会停止本次等待。正常轮询、用户明确恢复和组合重入均使用原任务。已查路径未发现失败后自动重提、作业级熔断或 429 自动退避。服务端限流窗口待实测。 [执行预算](../tools/hi3d-api.md#动作的执行预算) · [等待实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:336>)
- **进度与交付。** `wait` 在写盘后发送首个 `stderr` 快照。后续在状态、阶段、队列位置或陈旧标记改变时发送，也在百分比从有值转为空值、从空值转为有值或变化达到 10 个百分点时发送。Runtime 与 renderer 按当前工作区、轮次和调用投影到桌面。模型从脚本实际输出获得摘要，可能在工具结束时收到缓冲的历史进度。独立 `query` 无等待进度回调。 [进度输出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_progress.py:55>) · [模型可见结果](../infrastructure/workspace/llm-context.md#形成模型可见内容)
- **账务与重试。** 普通查询不产生新生成的本地扣费估算。符合条件的新增失败观察可触发已有任务的桌面本地退款对账，需匹配账号、环境和原扣费记录。该事件能说明客户端估算账本的变化，服务端退款仍待查。组合免费重试可按原 `retryRequestId` 更新次数缓存，缺有效次数时可触发独立额度 GET。通用结果收尾可从既有 GLB 补记文件来源。 [免费重试与结果复用](../tools/hi3d-api.md#免费重试与结果复用) · [已登记版本的重试意图](../infrastructure/workspace/import-or-register-model-version.md#已登记版本的免费重试)
- **历史与恢复。** 有效工具回包可进入后续采样。生产 Memory 开关缺省，`stage1_outputs/jobs` 均为零，已查路径未发现 Memory 读取或注入。生产压缩后的替换历史未保留相关账本路径和任务 ID。重连可以读回会话记录，原作业路径用于读回最后观察、诊断及任务身份。进度侧车仅保存用于显示的元数据。旧 GET 和逐条进度事件的自动回放未获证实。 [线程历史恢复](../infrastructure/workspace/llm-context.md#读取线程和恢复有效历史) · [Memory 核查](../infrastructure/workspace/llm-context.md#独立-memory-的核查)

## 完成与恢复

| 分支 | 触发条件 | 执行者 | 状态变化及写入顺序 | 可观察结果 | 交接或恢复方式 |
| --- | --- | --- | --- | --- | --- |
| 有效处理中 | 3D 成功包络且 `status=0` | `query_job` | 写 `processing`、脱敏结果和新观察时间，清旧查询错误，发布前先保存 | `query` 退出 0，`wait` 可在预算耗尽时回 `pending/0` | 以同一 `jobPath/task_id` 继续观察 |
| 有效成功 | 3D 成功包络且 `status=1` | `query_job` | 写 `success` 和新观察，按需设置首次本地终态时间再保存 | 新鲜成功，退出 0 | 进入下载来源检查。文件、登记与质量各自验收 |
| 本地查询拒绝 | HTTP 200、可解析的非 200 数字业务码、来源未标为桌面代理 | Python | 写 `failed`、`error.phase:"query"` 和 `query_failed:true`，清旧结果，更新本地观察并保存 | `stale:false`，退出 1 | 按原因结束等待。内容拒绝阻断交付，用户明确要求复查时沿原作业 |
| 查询不可用 | 登录失效、账号环境冲突、429、5xx、无效包络、错误父链或传输超时 | 代理、Python | 写本次查询诊断与陈旧进度，通常保留旧状态、结果和观察时间。处理中途出错时，以已保存的字段和旧观察时间核对 | `wait` 为 `attention/2`，摘要可仍含旧 `success` | 按原因恢复。用户明确要求继续后按原路径查询 |
| 本次保存失败 | 序列化、临时文件写入或替换失败 | `save`、CLI | 查询处理结束后保存异常，未完成替换时旧账本仍在 | 阶段错误、退出 2，未发本次保存后的进度 | 读回最后一份有效记录，以原 ID 重做一次观察 |
| 待用户或受理不明 | 查询报错需用户恢复，或上游缺可用 ID | 模型、用户，或上游 Runtime/Python | 保留原作业及提交意图。缺 ID 时从资格检查分支处理 | 诊断或 `canQuery:false` | 先找回可信任务引用。另开生成是独立提交决策 |
| 本地取消或守护超时 | 轮次中断、进程超预算或异常退出 | Runtime、Python、Electron | 结束本地执行，保留已完成的替换。回包可能晚于写盘或未交付 | 工具错误或 `attention/phase:process` | 优先确认磁盘快照，必要时重发原 ID 的 GET |
| 重复观察 | 同路径再查、轮询继续或下载前刷新 | Runtime、Python | 同一 Runtime 按规范路径串行，每次可更新快照。有效新观察可替代旧的本地终态 | 同一 ID 对应不同时间的观察 | 重用原路径，按最新观测和本次诊断继续。跨路径与跨进程互斥需另查 |

CLI 退出 0 可表示一次处理中观察已经保存。外层 `Script completed` 只确认 JS 执行单元结束。下游使用**当前有效观测、陈旧标记、查询错误来源和保存结果**决定继续。由组合调用交付的后续登记错误应按相应阶段处理。 [回包和退出码](../tools/hi3d-api.md#返回与错误) · [执行单元输出](../tools/wait.md#关联终止与恢复)

## Vet3D 迁移与核查范围

### 供应商无关的契约

给每次观察保留稳定作业引用、适配器配置、远端 ID、请求关联和观察时间。保存最后一次有效远端观察以及本次尝试的独立诊断。业务拒绝应保留其作用对象和来源。只有供应商契约给出可信远端终态时，才将状态标为生成终态。遇到回显 ID 时按适配器契约校验绑定，账户或路由检查沿用原作业上下文。

先校验、分类并构造完整快照，再提交同一个持久化更新。写入完成后发布进度和可供模型读取的摘要。这样即使序列化或脱敏失败，旧观测仍可独立恢复。保留只用于短期传输的候选访问材料。下载、版本登记和质量放行各持有其证据与交接条件。

**Vet3D 设计示例。** 当前尝试失败时仍可保留最后一次可信远端状态。字段使用业务语义，具体 LLM 与 3D 服务 API 待选型。

```json
{
  "jobRef": "jobs/example-3d",
  "lastObservation": {"state": "succeeded", "observedAt": "2026-11-11T03:43:28Z"},
  "latestAttempt": {"outcome": "unavailable", "retryable": true},
  "stale": true
}
```

### 可复核位置与证据边界

实际运行副本位于 `D:/install/Hi3DAgent.__hi3d-transaction`。下文偏移均为零基 UTF-8 字节偏移。Runtime 指 `resources/runtime/dist/runtime.mjs`，桌面指 `resources/app.asar` 的 `out/main/index.js`。随包 Python 文件位于 `resources/runtime/prebuilt-skills/hi3d/scripts/`。 [安装清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [版本归档](../upstream/1.2.11/README.md)

| 证据类型 | 内容与位置 |
| --- | --- |
| 安装包静态实现 | Runtime 的 `item/tool/call`、工作区绑定和 `Kj` 位于 3167092、3190779、2503566。`nne`、进度通知、`ge` 应答分别位于 2546170、3194145、3196971。桌面 `_l.handle`、账号环境复核、代理超时分别位于 213798、214410、215259，`requestTool` 及预缓冲与结果日志分别位于 224263、226263–226826。进度消费见 renderer `out/renderer/assets/index-CDPCug_K.js` 1161930。本地退款的 Runtime、桌面入口分别位于 2541466、121094。 [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| 随包 Python 路径 | `hi3d_jobs.py:269–355` 负责查询、分类和等待。`hi3d_storage.py:175–241` 负责同目录原子替换和脱敏。`hi3d_api.py:210–219,236–258` 区分摘要及 CLI 阶段错误。 [结果处理](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:269>) · [保存与脱敏](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_storage.py:175>) · [CLI 回包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_api.py:210>) |
| 离线复现 | 随包 Python 与进程内模拟传输复现 `status=0, position=4` 写 `processing/stage:queueing`、`status=1` 脱敏、父链冲突，以及同一业务码在 HTTP 429 与 HTTP 200 的不同写法。未知数字码和系统忙也可写本地 `failed`。畸形 URL 可留下新状态、旧结果与 `stale:true`。模拟 `os.replace` 失败时原账本字节不变，临时文件清理且无保存后进度。桌面代理分流另经提取代码与合成响应验证。上述实验均在本地完成。 [随包失败分流测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/tests/runtime/test_account.py:56>) |
| 运行观测与推断 | 生产第 103 行的工具回包含 12 条进度、原任务 ID、三个下载文件及 `attention/register-model`。桌面第 1506 行与首次终态观察时间对应，第 1507 行与账本最终观察时间对应。结合无聚合缓存的下载刷新链，可推断先观察成功，再为下载刷新。脱敏日志自身无原作业 ID 或数值 `data.status`。 [生产工具回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:103>) · [桌面结果日志](<D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:1506>) |
| 待实测 | 用授权的既有测试作业，从新轮或重启后执行桌面显式查询，关联实际 GET、账本替换、回包和下一次模型采样。真实服务 429、过期、账号撤销、取消和退款须分别核对。Windows 强制中断后的恢复与跨进程并发也待验证。 |

**离线复核步骤。** 在临时工作区建立带有效 ID 和相同账号环境的合成账本。使用随包 Python 的 `hi3d_api.execute`，为 `Client(opener=...)` 提供进程内模拟传输。模拟本地会话成功，记录结果请求中的原 ID，并分别执行下表两组。先读磁盘快照，再对照返回的摘要和退出码。 [CLI 注入入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_api.py:119>) · [可注入传输](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_client.py:30>)

| 初始条件与模拟响应 | 预期结果 |
| --- | --- |
| 有效原 ID。执行 `wait(seconds=0)`，模拟 HTTP 200、`{"code":"200","data":{"status":0,"position":2,"percentage":30}}`。 | 仅一次结果 GET，落盘 `processing`、`stage:queueing`、`stale:false`，随后交付进度和 `pending/0`。 |
| 原账本已有成功。执行 `query`，以同一个 `{"code":1003,"domainCode":32001}` 分别模拟 HTTP 429 与 HTTP 200。 | 429 保留旧成功、结果及观察时间，标陈旧并退出 2。200 写本地 `failed/query_failed:true`、清旧结果并退出 1。 |
