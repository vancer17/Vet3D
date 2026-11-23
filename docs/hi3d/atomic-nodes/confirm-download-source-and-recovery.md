# 确认下载来源与恢复方式

以 Hi3D Agent 1.2.11（Windows x64）为核查基准，覆盖普通 3D 作业及已受理的免费重试子作业。节点根据原作业决定本次使用本地文件清单、刷新远端下载候选，还是保留记录并停止。已产生的工具调用、模型上下文和桌面进度由共享基础设施承载。 [工作区 LLM 上下文](../infrastructure/workspace/llm-context.md#形成模型可见内容)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 组合生成等待到远端 `success` 后进入下载，或调用方显式请求获取、恢复已有作业的产物。 |
| 上游和输入 | 原工作区、已保存的 `jobPath`、请求的 `outputDir` 和当前账号环境。作业提供 `backend`、`kind`、`task_id`、`owner_id`、`environment`，以及已存在的 `artifact` 或 `download_output`。免费重试使用已受理子作业的 `task_id`，根任务 ID 用于重试归属。 [前序提交与恢复](preflight-generation.md#完成条件与恢复) · [等待与成功交接](schedule-wait-and-handoff.md) · [单次查询及持久化](observe-job-once.md) · [免费重试作业归属](../infrastructure/workspace/import-or-register-model-version.md#已登记版本的免费重试) |
| 本地来源交接 | 作业有聚合 `artifact`，当前账号环境核对通过。将聚合记录及本次输出根交给后续复验。校验范围包含顶层文件、`artifact.files` 各项和已有的可选 `cover`。顶层字段写入方式见后续清单聚合。 |
| 远端来源交接 | 本次查询观察到原任务成功、没有 `last_query_error`、取得非空候选列表，并保存符合约束的 `download_output`。将原任务、绑定目录和本次响应中的有序候选交给逐项下载。 |
| 停止条件 | 查询仍在处理或出错、缺少可查询的任务 ID、无候选、账号或路径不符时，保留原作业并按原因处理。 |
| 下游 | [逐项下载与产物清单落盘](download-and-persist-artifact-manifest.md)接收有序候选与输出目录，或接收已有的聚合记录和输出根。文件通过完整性检查后，再交候选验收、模型版本登记和交付。 |

两条成功交接都发生在 Python 调用内部。业务上区分来源确认与文件发布，两步共用 `download_job`。独立 `download` 要等后续复验或下载完成才返回 `{cached, artifact}`。这里处理的是输出产物；建模主图、参考图、目标方向和必保特征继续由原生成计划追溯，下载查询只传当前作业的任务 ID。 [下载实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:175>)

## Skill 绑定

| 入口 | 选用条件与作用 |
| --- | --- |
| [Hi3D 通用 Skill](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#3d-任务工作流) | 普通照片建模选用该入口。正式 `generate_3d` 在一次调用内等待、下载；`pending` 后沿原 `jobPath` 续查，成功后使用原 `outputDir`。明确要求参数化建模、CAD 或可编辑工程参数时，由上游选其他路线。 |
| [调用参考](../upstream/1.2.11/prebuilt-skills/hi3d/references/calling.md#查询错误) | 通用 Skill 的按需参考。查询报错后，使用当前错误原因结束本轮，待用户明确要求继续再查询原任务。正常 `pending` 可继续等待。提交结果不明且缺 ID 时先核对任务历史。 |
| [免费重试桌面参考](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-free-retry.md) | 仅在从已登记版本发起免费重试时使用。原意图由 `retryRequestId` 关联，受理后用子作业的任务 ID 续查。 |

生效副本位于生产 `CODEX_HOME/skills/buildin/hi3d`。安装时按 `prebuilt.json` 安装或复用受管版本，Runtime 执行时校验入口的受管标记并从同一包定位脚本。安装包、生产副本与仓库归档的 `SKILL.md` 和 `references/calling.md` 分别字节一致。普通 3D 的来源分流由通用实现执行，装配和人像等领域 Skill 的额外规则随上游选用。生产样本通过 Shell 读取了入口，回包中文有乱码，记录中没有本轮显式 `<skill>` 或独立参考文档读取。参考文档所述恢复约定属于随包指导。 [Skill 安装和读取范围](../infrastructure/workspace/llm-context.md#阶段依赖) · [生产读取样本](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:19>)

## LLM Tools

| 工具 | 动作或用途 | 调用时机 |
| --- | --- | --- |
| [`hi3d_api`](../tools/hi3d-api.md) | `generate_3d`；已明确发起免费重试时可用 `retry` | 组合入口。在内部等待到 `success` 后进入同一个 Python `download_job`。生产样本实际使用 `generate_3d`。 |
| [`hi3d_api`](../tools/hi3d-api.md#作业持久化与恢复) | `download`、`query`、`wait`、`adopt` | 单独获取产物时用 `download`。原任务未结束或明确要求恢复时用 `query` / `wait`。可信来源找回已有任务 ID 后，才考虑用 `adopt` 建立新的本地查询记录，保留原记录。 |
| [`exec`](../tools/exec.md) · [`wait`](../tools/wait.md) | 调用嵌套 Tool、续读 Code Mode 执行单元 | 仅在本轮使用 Code Mode 时适用。`exec` 交回运行中句柄时以原 `cell_id` 调用外层 `wait`。生产样本使用了这两项。 |

`generate_3d`、`download` 等是一个动态 Tool 的动作枚举。`download_job`、`query_job` 是包内 Python 函数，`GET /v1/model3d/result` 是账号代理路由。版本登记由后续流程使用 [`workspace_commit_model`](../tools/workspace-commit-model.md)；组合调用也可能在完成下载后自动登记。 [工具注册及回包](../tools/hi3d-api.md#工具名称与注册来源)

## Hi3D 实现

### 决策

组合 `generate_3d` 的 `generate_task` 先通过 `wait_job` 观察远端成功，再转入下载。`generate_retry_task` 对子作业做同样的交接。独立 `download` 直接进入来源判断。`download_job` 先读原作业、解析工作区输出目录，再以 `job.artifact` 是否为真值决定分支。有 `artifact` 时先核对账号和环境，再检查记录文件是否落在本次输出根内，大小及 SHA-256 是否匹配。该缓存分支跳过结果 GET 和 `download_output` 等值比较；本地复验成功也只确认文件可以复用。 [组合流程](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:11>) · [子作业组合流程](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:62>) · [缓存复验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:120>)

### 执行

**根据已验证行为重建的请求示例。** `jobPath` 指向已受理的作业，`outputDir` 使用首次拟定目录或原绑定目录。

```json
{"action":"download","jobPath":"hi3d/example-job.json","outputDir":"exports/example-model"}
```

1. **分派。** Runtime 从 `item/tool/call` 的 `threadId` 找到 `assetId` 和工作区 `cwd`。`Rg.run` 在同一 Runtime 内按解析后的 `jobPath` 串行执行。`Kj` 和 `r$` 启动 `hi3d_api.py download --job <路径> --out <目录>`，独立动作预算 600 秒。子进程获得工作区根、回环代理配置及当前 `threadId`、`turnId`。Python 将后二者用于 `X-Session-Id`、`X-Turn-Id`，当前调用的关联 ID 与作业的 `task_id` 分开。 [Runtime `Rg.run` 偏移 2539575、`Kj` 2503566、`r$` 2462032](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [Python Client](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_client.py:30>)
2. **刷新。** 无聚合缓存时，`query_job` 校验当前后端、任务 ID 格式和原账号环境。3D 查询为 `GET /v1/model3d/result?jobId=<原 task_id>`。查询成功要求 HTTP `200`、业务码转为字符串后等于 `"200"`、对象型 `data`，以及严格整数 `status` 为 `0` 或 `1`，分别记录为 `processing`、`success`。作业先保存查询时间、进度和脱敏结果，再向调用者返回本次未脱敏的内存响应。 [3D 结果路由](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_client.py:10>) · [查询及落盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:269>)
3. **收集与绑定。** `result_urls` 先收集 `resultImageUrls`、`blockImageUrls`，再按 `model3ds` 顺序处理各对象中的 `model3D*Url`、`attachData*`，最后加该对象的 `url`。附件可以是对象、数组或可解析的 JSON 字符串；递归时略过键名包含 `source`、`input`、`reference` 或 `prompt` 的子树。初筛只接受小写 `https://` 前缀，按完整字符串去重，模型和预览可能同时入列。满足新鲜成功条件后，检查已绑定目录有无变更，再创建目录、保存 `download_output`。 [候选收集和目录绑定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:138>)

**实现伪代码。** `return` 标明本节点的交接。真实脚本在同一调用内进入复验或逐项循环。

```python
def confirm_source(client, job_path, requested_output):
    job = load_workspace_job(job_path)
    output = resolve_workspace_path(requested_output)

    if job.get("artifact"):
        client.check_job(job)
        return handoff_for_local_verification(job["artifact"], output)

    job, response_data = query_job(client, job_path)  # 查询观察已脱敏落盘
    urls = result_urls(response_data)
    if job.get("last_query_error") or job["state"] != "success" or not urls:
        raise ValueError("A fresh successful result with HTTPS output URLs is required")

    if job.get("download_output") and job["download_output"] != str(output):
        raise ValueError("Resume downloads in the original output directory")
    output.mkdir(parents=True, exist_ok=True)
    job["download_output"] = str(output)
    save(job_path, job)
    return handoff_for_download(job["task_id"], output, urls)
```

### 验收

- **核对来源和落盘顺序。** 本地分支把清单交给复验，文件缺失或被修改时直接报错。远端分支在目录核对前已保存新查询，因此目录冲突时仍能读回最新观察；目录冲突会保留原绑定。候选 URL 只在当次调用内使用，`job.result` 保存的 URL 已脱敏。下一步才校验完整 HTTPS URL、检查内嵌凭据，并按序号和 `SHA-256(scheme://netloc/path)` 匹配单项检查点。仅有封面或存在形态不合格的候选时，也可能先通过列表非空检查。 [脱敏与原子保存](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_storage.py:175>) · [逐项入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:192>)
- **核对治理执行点。** Runtime 和 Python 分别检查工作区路径，桌面代理检查回环 Host、Origin、令牌、允许路由和账号环境。独立下载无需新生成确认面板；既有会话门禁仍可在启进程前停止调用。`download` 只查询已有作业，处理响应中的并发、额度或 `429`，没有新生成 POST。独立刷新查询默认 90 秒，只查一次；组合 `wait_job` 按预算轮询，遇查询错误退出。桌面 `observeHost` 节流日志并记录输运故障及恢复，现有代码证据仅覆盖诊断。 [路径检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_storage.py:144>) · [Runtime 门禁 3089566、动态分派 3167092](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [ASAR `out/main/index.js` 的 `Pi` 212862、`_l.handle` 213884、`observeHost` 223651](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [查询等待](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:336>)
- **核对模型可见结果。** 组合调用先持久化查询状态，再将进度写入 `stderr`，Runtime 转成 `runtime/hi3dProgress` 给桌面。生成进度到达 `success` 后仍可再刷新来源。生产样本的运行中 `wait` 只交回 `cell_id`，最后一次才随 `text(r)` 得到 `stdout` 和累积 `stderr`。独立 `download` 无 `--progress`，缓存选择、URL 刷新和目录绑定也无单独的模型回包。下一次采样读取有效工具结果；冷恢复按原 `jobPath` 和 `task_id` 续查，桌面历史和压缩摘要可供定位，签名地址仍须重新取得。生产样本未启用独立 Memory。 [模型输入的形成](../infrastructure/workspace/llm-context.md#形成模型可见内容) · [历史恢复](../infrastructure/workspace/llm-context.md#读取线程和恢复有效历史) · [生产终态回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:103>)

## 完成与恢复

| 分支 | 触发条件 | 执行者 | 状态变化及写入顺序 | 可观察结果 | 交接或恢复方式 |
| --- | --- | --- | --- | --- | --- |
| 本地来源 | 有 `artifact` 且账号环境一致 | Python | 读清单后进入复验；原查询与绑定保留 | 完整性通过后回 `cached: true`、退出 `0` | 将清单交逐项复验。损坏时保留原记录和现有文件，先核对可恢复的原件 |
| 新鲜来源 | 本次成功、候选非空、且目录符合绑定 | Python | 保存脱敏查询 → 建目录 → 保存绑定 | 内部进入逐项下载；完整清单形成后才回 `cached: false` | 进入[逐项写入与汇总](download-and-persist-artifact-manifest.md)，随后交给产物验收 |
| `pending` 或待用户 | 作业仍在处理，或查询出错后等待用户明确要求恢复 | Python、模型 | 保存查询状态或错误，保留原作业 | `wait` 可以 `pending`、退出 `0`；直接 `download` 遇处理中通常报下载错误、退出 `2`。参数面板属于上游受理前 | 正常处理中沿原 `jobPath`、`task_id` 续 `wait` / `query`。查询错误按 Skill 指导说明原因后停止本轮 |
| 查询不可用或账号不符 | 查询超时、HTTP `429` / `5xx`、无效状态、签入或账号环境校验失败 | 桌面代理、Python | 刷新分支保存 `last_query_error`，旧观察可标为陈旧；缓存的账号校验失败直接报错 | 本次刷新错误通常为 `attention`、退出 `2` | 恢复原账号、环境或连接后查同一作业 |
| 查询业务拒绝 | HTTP `200` 的 `code` 可按 1–12 位十进制数字解析为非 200 值，且错误来源未标记为 `desktop-proxy` | Python、模型 | 写 `last_query_error.query_failed`，将本地状态设为 `failed` 并清除旧结果 | 本次刷新返回 `failed`、退出 `1`。生成引擎的实际状态需另行确认。明确的内容拒绝阻止交付 | 保留原作业和拒绝依据。已有缓存可作证据，即使复验通过也须遵守拒绝结论 |
| 来源条件失败 | 成功却无候选、绑定冲突、缓存损坏或逐项 URL 不合规 | Python | 可能已保存刷新结果或目录绑定，具体取决于失败点 | 独立 `download` 通常回通用 `phase: "download"` 错误、退出 `2` | 保留作业、原目录和检查点，到具体失败点核对来源 |
| 本地取消或超时 | 轮次中断，或子进程用完执行预算 | Runtime、Python | 停止本地调用，保留已完成的作业写入。Python 收到可处理信号时以 `130` 退出并执行清理 | 本地工具中断或超时，远端状态需另查 | 执行单元还在时可续读；句柄失效后从原作业恢复。Windows 强制中止后的磁盘状态待实测 |
| 提交不明 | `submitting` / `submission_uncertain`，缺少可信任务 ID | Runtime、模型 | 先保留原计划、作业和重试意图 | 通常为 `attention`、`canQuery: false` | 核对任务历史。找回可信 ID 后可 `adopt` 到新本地记录，并用原账号环境验证。确需新模型且已有明确授权时，才从提交入口新建远端作业 |
| 重复调用 | 同一 `jobPath` 再次进入 | Runtime、Python | 同一 Runtime 串行。完整缓存复验，未完成则刷新和核对原目录 | 文件可复用，或返回来源变动、校验异常 | 沿用原目录和检查点。逐项身份对不上时保留已下载文件 |

独立 CLI 仅在本次 `last_queried_at` 有变化且记录了查询错误时，将其包装为带 `result` 和 `phase: "download"` 的业务回包。一般本地失败走通用错误。`Tg` 通常拦截无 ID 的不明受理；精确匹配 HTTP `200`、业务码 `30010000` 且无任务 ID 回执标记的普通作业可绕过该守卫，Python 新鲜查询仍要求有效 ID。独立 `download` 接收的 `dryRun` 也不会传成 `--dry-run`，还可能跳过部分 Runtime 守卫，配置代理时仍可访问真实结果接口。 [CLI 错误封装](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_api.py:220>) · [Runtime `Tg` 2500260、分派 `Kj` 2503566、中断 3143432](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [信号处理](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_api.py:261>)

下游回填使用已通过完整性检查的实际文件引用。候选取得但几何、外观或用途验收失败时，保留来源和失败依据，从已验证清单重新选件，或回到相应业务节点修订。质量放行、版本登记结果和对话轮次终态分别验收。 [候选检查与登记](preflight-generation.md#3d-候选的检查和登记)

## Vet3D 迁移与核查范围

### 供应商无关的契约

- **先定义业务身份和交接。** 用持久化的本地作业引用固定工作区、适配器及账号作用域、供应商任务引用和输出根。来源确认可返回待复验的本地清单、待下载的有序候选，或需要恢复或停止的原因。将执行句柄和工具调用关联交由共享执行层。
- **分开观测与使用权限。** 落盘最近一次状态、观测时间、是否陈旧、脱敏的候选标识和恢复依据。可下载地址和凭据使用短期传递；恢复时按供应商能力刷新。缓存字节通过复验后，仍由独立交付规则检查是否存在拒绝结论。
- **定义清单变更策略，再接适配器。** 供应商若提供稳定产物 ID、摘要、语义角色或清单版本，优先以这些字段对账。仅有位置或地址时，为列表换序、减少、重复和签名刷新定义显式处理。Hi3D 1.2.11 按位置校验单项身份；离线复现中，尾项减少可使新聚合清单缩短，旧尾项文件仍在目录。Vet3D 应把产物集合完整性作为下游可核查的条件。

**Vet3D 设计示例。** 字段表达业务含义，供应商 API 选型后由适配器映射。示例只保存引用与观测，短期地址由当前执行传给下载处理器。

```json
{
  "jobRef": "model-job-42",
  "providerTaskRef": "existing-task-17",
  "decision": "download",
  "observation": {"status": "succeeded", "stale": false},
  "outputLocation": "artifacts/model-job-42",
  "candidates": [{"sourceRef": "candidate-1", "role": "unknown"}]
}
```

### 核查依据与缺口

- **安装包静态实现。** 复核使用 `D:/install/Hi3DAgent.__hi3d-transaction/resources` 的 Windows x64 1.2.11，随包 Codex 为 0.166.0。`runtime/dist/runtime.mjs` SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`，`app.asar` 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。本文偏移为原文件或指明的 ASAR 成员内的零起始字节偏移。 [安装版本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [归档范围](../upstream/1.2.11/README.md)
- **离线复现。** 随包 Python 使用合成作业与模拟 opener，确认请求按原 `jobId` 刷新、脱敏观察先落盘、输出目录随后绑定、带签名 URL 最后交给传输入口。旧 `success` 加本次内容拒绝会清除旧结果并停止；已有聚合 `artifact` 即使留有失败记录，也可在本地字节匹配时完成缓存复验，且无需结果 GET。随包测试 49 项通过。另用同版 Codex、本地模拟 Responses 和合成动态 Tool 验证了外层运行句柄与终态工具回包分别进入后续 `input`。 [刷新测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/tests/runtime/test_account.py:665>) · [失败分类测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/tests/runtime/test_account.py:201>) · [断点测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/tests/runtime/test_recovery.py:18>)
- **本机实际观察与关联推断。** 2026-11-11 的 `generate_3d` 样本中，桌面日志第 1506–1507 行记录同一会话在北京时间 11:43:28.092 和 11:43:28.329 收到 HTTP 200、业务码 200 的结果响应。日志只显示响应字段名，任务 ID 和数值 `data.status` 未写入该诊断。工具回包里的终态进度与同一账本的 `first_observed_terminal_at` 对应第一条时间，账本的 `result_observed_at` 与 `last_queried_at` 对应第二条时间。账本和工具回包的任务 ID 一致。结合组合调用在等待成功后刷新下载候选的静态路径，可推断两条分别对应等待终态和下载刷新。本地三项检查点按 URL 身份依次对应 `model3DGlbUrl`、`model3DPreviewUrl`、`model3ds[].url`，文件与清单的大小及哈希相符。最终回包为 `attention/register-model`，保留两份 GLB 和一份 WebP。之后模型选件并另行登记。 [结果响应诊断](<D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:1506>) · [作业账本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/hi3d/hi3d-cat-multiview.json>) · [模型候选回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:103>)
- **待验证。** 独立 `download` 在线恢复、签名失效后的实际刷新结果、真实服务的清单稳定性、限流窗口、计费与退款、Windows 强制中断后的恢复及桌面重连续报仍需实测。分别从桌面 `Nl.requestTool`、Runtime `az` / `turn/interrupt` 和 renderer 的进度消费点继续核对。Vet3D 的 LLM、生图和 3D 供应商仍待选型，质量放行须使用实际产物验证。
