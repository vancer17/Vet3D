# wait

## 工具名称与注册来源

`wait` 是 Hi3D Agent 1.2.11（Windows x64）随包的 Codex 0.166.0 所提供的 Code Mode 函数工具。有效工具模式为 `CodeMode` 或 `CodeModeOnly` 时，Codex 将 `wait` 和 `exec` 分别注册。`wait` 接收独立的 JSON 函数调用。被续查的 JavaScript 执行单元由 Code Mode 宿主持有。 [注册来源](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/spec_plan.rs#L1018-L1105) · [exec 工具](exec.md)

## 暴露给 LLM 的描述

以下为两份本机 rollout 的 `additional_tools` 中记录的 `wait.description` 原文。

```text
Waits on a yielded `exec` cell and returns new output or completion.
- Use `wait` only after `exec` returns `Script running with cell ID ...`.
- `cell_id` identifies the running `exec` cell to resume.
- `yield_time_ms` controls how long to wait for more output before yielding again. Defaults to 10000 ms.
- `max_tokens` limits how much new output this wait call returns. Defaults to 10000 tokens.
- `terminate: true` stops the running cell; false or omitted waits for output.
- `wait` returns only the new output since the last yield, or the final completion or termination result for that cell.
- If the cell is still running, `wait` may yield again with the same `cell_id`.
- If the cell has already finished, `wait` returns the completed result and closes the cell.
```

## 参数与结果

默认模型可见参数 schema 声明 `additionalProperties: false`，工具定义的 `strict` 为 `false`，没有单独的输出 schema。代码模式注册时可以由工具目录覆盖描述及参数 schema。处理器用 Serde 将 JSON 解析为 `ExecWaitArgs`。该结构按 Serde 默认方式忽略额外键，调用方按当前公开声明构造参数。 [工具定义](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/wait_spec.rs#L6-L68) · [参数解析](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/wait_handler.rs#L29-L51)

| 参数 | 必填性、默认值与约束 |
| --- | --- |
| `cell_id` | 必填字符串。取自 `exec` 返回的 `Script running with cell ID …`。后续结果仍为运行中时，继续传同一 ID。 |
| `yield_time_ms` | 可选非负整数，处理器默认 10,000 毫秒。此值传给 Code Mode 宿主，用于计算本次续读的让出时限。`terminate` 为 `true` 时请求独立的终止接口。 |
| `max_tokens` | 可选非负整数，省略时 Codex 格式化输出的默认预算为 10,000 token。此值在宿主应答后由 Codex 应用，正常等待和终止的输出均受此预算约束。 |
| `terminate` | 可选布尔值，默认 `false`。省略或为 `false` 时等待，传 `true` 时向宿主请求终止该执行单元。 |

### 输出等待与交付时限

宿主收到 `yield_time_ms` 后，对达到 10,000 毫秒的请求加 1,000 毫秒宽限，再应用可选的 `max_yield_time_ms` 上限。单元提前完成或收到让出信号时可更早交还控制。期限到达时仍在运行的单元可交回新增输出和原 `cell_id`。每个请求的让出时限只作用于这次观察，嵌套工具的进程和网络时限由各自处理器维护。 [宽限常量](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-runtime/src/service.rs#L30-L31) · [宿主时限计算](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-runtime/src/service.rs#L204-L215) · [等待与让出信号](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-runtime/src/service.rs#L119-L151)

Codex 向宿主发送等待请求时将 `max_output_tokens` 留空，收到结果后先等当前待处理的交互请求清空，再按 `max_tokens` 格式化输出。输出预算控制交付量，交付时间也可能受交互和本地处理影响。显示耗时优先取宿主提供的时长，缺省时使用处理器实际耗时。 [等待请求的字段](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/wait_handler.rs#L129-L146) · [应答后的交付](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/wait_handler.rs#L200-L213) · [默认响应输出预算](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/unified_exec/mod.rs#L215-L217)

工具返回文本状态头和耗时，并附自上次交付后的文本、图片或音频等内容。状态头有 `Script running with cell ID <cell_id>`、`Script completed`、`Script failed` 和 `Script terminated`。脚本失败时还可附 `Script error:` 和错误内容。`Script running` 携带同一 ID，供下一次读取。宿主已缓存终态时，续查可以取得该结果并收尾。 [结果转换与输出预算](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/mod.rs#L244-L323) · [状态文本](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/output.rs#L19-L39)

参数解析失败或宿主通信失败时，处理器直接返回工具错误。ID 不存在或已收尾时，宿主返回失败结果，模型会收到 `Script failed` 和 `exec cell <cell_id> not found`。等待会交付增量输出，终止会结束当前单元的执行，已经发生的嵌套工具副作用会保留。 [续查、错误与收尾](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/wait_handler.rs#L109-L209) · [宿主等待与终止](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-runtime/src/service.rs#L111-L203) · [单元不可用的结果](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-runtime/src/service.rs#L422-L434)

### 关联、终止与恢复

每次 `wait` 按 `cell_id` 请求原 Code Mode 会话中累积的输出，返回内容与本次新的 `call_id` 配对为 `function_call_output`。Codex 将已交付的输出写入有效历史，供后续采样读取。若只收到 `Script running`，执行单元仍可续查。固定源码允许单元跨轮存活，嵌套工具按实际分派时的线程和轮次执行。本机观测的续读发生在同一轮内。 [嵌套工具的会话与轮次](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/mod.rs#L339-L362) · [输出转换与调用配对](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/context.rs#L597-L621) · [下一次采样准备](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/session/turn.rs#L547-L593)

收到 `Script completed` 后，继续检查脚本实际输出的嵌套结果。若嵌套 `exec_command` 返回 `session_id`，用 `write_stdin` 续读同一进程。取得进程终态后，按本地命令契约读取 `exit_code` 和实际产物。宿主进程型动态工具使用各自包裹的 `exitCode`、服务状态和业务字段。 [本地进程续读](write-stdin.md) · [嵌套结果交付](exec.md#嵌套路由与结果交付)

`cell_id` 不代替进程的 `session_id`，两者均不构成持久文件任务账本。句柄失效、外层失败或终止后，先核对原嵌套调用、实际进程、日志与文件；不要仅因未收到终态就重新运行写文件命令。缓存、工程与报告可能已经分步落盘，完整性、覆盖规则及能否续写以被调用程序的契约为准。 [文件结果与提交不明](exec-command.md#本地脚本的文件结果)

`wait` 的处理器为 `PreToolUse` 和 `PostToolUse` 显式返回空 payload，续读或终止的控制回包由本处理器交付。嵌套调用仍通过各自工具的正常分派和权限检查。 [等待处理器的 Hook 边界](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/wait_handler.rs#L228-L245)

`terminate: true` 调用 Code Mode 宿主的本地终止接口。宿主返回终态后，Codex 关闭该单元的嵌套分派记录。`Script terminated` 的状态头来自宿主终止结果。当结果没有脚本错误文本时，内部工具结果的成功位仍可为真。Codex 的动态工具处理器可按取消令牌结束等待宿主应答。外部工具的取消由各自宿主处理，例如 Hi3D Runtime 的整轮停止处理按线程和轮次停止本地子进程。当前生产样本尚未覆盖仅终止 cell 时，取消是否传到正在运行的 Runtime 子进程及其网络请求。旧单元失效后，按嵌套工具的契约用持久引用恢复。 [宿主终止与单元收尾](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-runtime/src/service.rs#L111-L203) · [终态与成功位](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/mod.rs#L262-L315) · [Codex 取消等待嵌套应答](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/dynamic.rs#L239-L275) · [Hi3D Runtime 的进程时限和停止](hi3d-api.md#动作的执行预算)

## 实现伪代码

**根据固定源码重建的伪代码。** `exec` 提交脚本，由宿主分配执行单元 ID。`wait` 解析 JSON 参数后，在同一 Code Mode 宿主会话中按 ID 查询或终止。可用单元的结果与本次调用 ID 关联，收到终态时关闭该单元的嵌套调用分派。宿主连接丢失后可以建立新会话，旧会话的 ID 随原会话失效。进程续接则使用 Unified Exec 单独返回的 `session_id`。 [提交处理器](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/code_mode/execute_handler.rs#L46-L170) · [宿主会话与重连](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode/src/remote_session.rs#L239-L321) · [write_stdin 工具](write-stdin.md)

```python
async def wait(arguments, context):
    args = parse_wait_arguments(arguments)
    if args.terminate:
        outcome = await context.code_mode.terminate(args.cell_id)
    else:
        outcome = await context.code_mode.wait(
            args.cell_id, yield_time_ms=args.yield_time_ms, preempt=context.preempt
        )

    response = outcome.response
    if outcome.has_live_cell:
        context.executed_calls.register_cell(response.cell_id, context.call_id)
        if response.status != "yielded":
            context.code_mode.finish_cell_dispatch(response.cell_id)

    await context.elicitations.wait_until_clear()
    return format_runtime_result(response, max_tokens=args.max_tokens)
```

## 调用示例

**根据已核查的工具声明重建的 JSON 请求。** 在 `exec` 返回运行中状态后，用状态头中的实际 ID 替换 `<cell_id>`。这次调用将请求等待时长设为 1,000 毫秒，将本次输出预算设为 256 token。

```json
{"cell_id": "<cell_id>", "yield_time_ms": 1000, "max_tokens": 256}
```

**根据已核查的工具声明重建的 JSON 请求。** 仍持有可用 ID 时，可以对原执行单元发出终止请求。

```json
{"cell_id": "<cell_id>", "terminate": true}
```

**根据已观测结果形状重建的文本示例。** 脚本收到并输出了一个报告进程结果的嵌套工具应答，JS 本身正常执行结束。调用方可以从嵌套应答中的退出码和诊断确定下一步。

```text
Script completed
{"exitCode":1,"stdout":"","stderr":"Requested file could not be opened."}
```

## 核查依据

- **同版隔离核查。** 随包 Codex 0.166.0 连接本地模拟 Responses。合成嵌套工具延迟应答，`wait` 取得含 `Script completed` 和脚本输出的终态。在后续实际 HTTP `input` 中捕获到以该 `wait` 调用 ID 配对的 `function_call_output`，其中包含合成的 `stdout` 和 `stderr`。 [隔离核查与外层输出](exec.md#核查依据)
- 本机安装包 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/codex/vendor/x86_64-pc-windows-msvc/codex-package.json` 标明 Codex 0.166.0。同目录 `bin/codex.exe` 的 SHA-256 为 `9d563ee4e0441ff9d59d612013e0460ddf8e5709735c2d9f6b98b7ef8ca4eb42`。 [Codex 固定提交](https://github.com/openai/codex/commit/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856)
- 2026-11-11 活跃样本 `rollout-2026-11-11T11-31-29-*` 与归档样本 `rollout-2026-11-11T11-24-05-*`，各取第 2 行 `response_item` 的 `additional_tools`。两份记录的 `wait.description` 一致，UTF-8 SHA-256 为 `582eb96e50ee4481cf30b33ad2358e7e24e7368aeb2cbe5122cef1912ad75385`。
- **固定源码。** 宽限、可选上限、应答后的格式化及单元终止按上述 Codex 固定提交核实。Runtime 整轮停止的本地分派见随包 `resources/runtime/dist/runtime.mjs` 的 `terminateThread/abortThreadCalls`，分别位于 UTF-8 零基字节偏移 `3142706/3155096`。 [安装包 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)
- **实际运行记录。** 活跃样本第 55→59→62 行沿同一 `cell_id` 取得 `Script completed`。另一个执行单元在第 74、82、88、94、100 行的五次 `wait` 均传入 `120000 ms/3000 token`。前四次约 121 秒后只返回运行中，与源码里的宽限一致。第 224、228、230 行另记录一次续查后仍返回同一 ID 的运行中状态。最后一次提前返回，第 102 行记录内层动态工具失败，第 103 行按第 100 行的调用 ID 交付 `Script completed` 及内层 `exitCode: 1`。 [本机 rollout](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:74>)
- **待实测。** 生产的 `max_yield_time_ms` 配置及完整出站请求正文尚未独立采集。用可控延时的嵌套调用分别触发 cell 终止和整轮停止，可核对单元终态、外部宿主取消回调、进程与网络请求，以及已写入的记录。
