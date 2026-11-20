# write_stdin

## 工具名称与注册来源

`write_stdin` 由 Hi3D Agent 1.2.11（Windows x64）随包的 Codex 0.166.0 注册。当前模型和策略允许 shell 工具且启用 Unified Exec 时，Codex 同时注册 `exec_command` 和 `write_stdin`。仅允许单次执行的分支不注册此续接工具。按本轮工具路由，它可以作为普通函数暴露，也可以在 Code Mode 中通过 `tools.write_stdin` 调用。本机两份样本采用后者。 [注册分支](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/spec_plan.rs#L1223-L1274) · [exec_command 工具](exec-command.md)

## 暴露给 LLM 的描述

以下原文来自本机 rollout 中 `exec.description` 内的嵌套工具声明，已与随包二进制核对。

```text
Writes characters to an existing unified exec session and returns recent output.
```

## 参数与结果

模型可见参数 schema 要求 `session_id`，声明 `additionalProperties: false`，工具定义的 `strict` 为 `false`。工具会从当前调用解析执行环境，再用 `session_id` 取得原终端。 [工具定义](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/shell_spec.rs#L111-L152) · [会话解析](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/unified_exec.rs#L28-L61)

| 参数 | 必填性、默认值与约束 |
| --- | --- |
| `session_id` | 必填。声明类型为 `number`，处理器要求有符号 32 位整数。传入 `exec_command` 返回的进程会话 ID。 |
| `chars` | 可选字符串，默认 `""`。空字符串仅读取输出。普通非空输入要求原命令以 `tty: true` 启动并有可写 stdin。输入以 UTF-8 字节写入，需要换行时由调用方传入。管道分支支持用单个 `\u0003` 请求中断。 |
| `yield_time_ms` | 可选非负整数。处理器默认传入 250 毫秒。非空写入的有效范围是 250 至 30,000 毫秒，空轮询的有效下限是 5,000 毫秒，上限由后台终端配置决定，默认 300,000 毫秒。 |
| `max_output_tokens` | 可选非负整数。普通函数结果的默认请求预算为 10,000 token，并受模型输出截断策略约束。代码模式中，显式提供时按该值截断，省略时返回采集阶段保留的文本。 |

- **代码模式结果。** 对象包含 `output` 和 `wall_time_seconds`，按可用状态附 `chunk_id`、`original_token_count`、`exit_code`、`session_id`。只要返回 `session_id`，仍可按该 ID 续取。远程进程已经退出但还有待收集输出时，`exit_code` 与 `session_id` 可以同时出现。
- **普通函数结果。** 文本包含耗时和输出，并在可用时包含片段 ID、退出码、续接 ID 和原始 token 估算。进程退出且所需输出已收集时会话收尾，之后原 ID 无法继续查询。命令非零退出可通过带退出码的正常工具结果返回。
- **错误。** 无效参数、未知或失效 ID、管道收到普通非空输入、审批拒绝、审批失败或进程传输失败都可导致工具错误。启用 `WriteStdinApproval` 时，终端权限和当前策略决定是否需要审批。需审批的写入获批后才发送。空轮询和管道的专用中断走免审批分支。 [输入审批条件](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/unified_exec/stdin_approval.rs#L179-L225)
- **副作用。** 非空输入会交给原进程处理，单个中断字符可以触发中断。空轮询读取本次可采集的输出，终态时可能完成原会话的清理。

[输入校验、审批和错误转换](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/unified_exec/write_stdin.rs#L24-L125) · [终端收集及会话状态](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/unified_exec/process_manager.rs#L908-L1136) · [结果序列化](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/context.rs#L438-L567)

读取仍在运行的后台任务时可省略 `chars` 或传空字符串。进程终态交付后，按原命令的预期路径和实际文件检查产物。会话 ID 失效、进程异常退出或输出被截断时，也可从已落盘文件和报告核对实际进度。 [本地文件结果](exec-command.md#本地脚本的文件结果)

续读和中断都针对原进程，工具不重新执行启动命令。失效 ID、取消回包或缺少标准输出不能证明磁盘上没有结果；中断也不会撤回已经写入的文件。恢复时先核对原进程和产物，再按被调用脚本的规则选用完整结果或新的输出路径。文件是否允许覆盖、失败是否留下半成品及是否支持断点续写，由脚本定义。 [缓存脚本的落盘边界](../resources/specialized-mesh-scripts.md#rig_adapter-cache-求值动作缓存)

## 实现伪代码

**根据固定源码重建的伪代码。** `exec_command` 提交原命令，进程管理器在首段输出交付时为可续接进程返回 `session_id`。`write_stdin` 查找该会话，并用原终端的交互锁串行处理输入和轮询。审批结束后再次校验进程身份，避免将输入发给重用了 ID 的其他进程。输入处理后采集输出并刷新终态，远程进程可能在退出后继续保留会话以收集剩余输出。Codex 进程管理器重启后，原 ID 无法用来恢复该进程。 [启动处理器](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/unified_exec/exec_command.rs#L124-L278) · [进程管理器](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/unified_exec/process_manager.rs#L908-L1136)

```python
async def write_stdin(arguments, context):
    args = parse_write_stdin_arguments(arguments)
    terminal = await context.manager.resolve_terminal(args.session_id)
    async with terminal.interaction_lock:
        entry = await context.manager.require_same_process(terminal)
        await context.approve_stdin_if_required(entry, args.chars)
        entry = await context.manager.require_same_process(terminal)

        if args.chars and not entry.remote_exit_is_draining_output:
            if entry.tty:
                await entry.write(args.chars.encode("utf-8"))
            elif args.chars == "\u0003":
                await entry.interrupt()
            else:
                raise StdinClosed()

        timeout_ms = effective_yield_time(args, context.config)
        output = await entry.collect_output(timeout_ms)
        state = await context.manager.refresh_state_until_output_collected(entry)
    return format_result(output, state, args.max_output_tokens, context.route)
```

## 调用示例

**根据已核查的工具声明重建的 JSON 请求。** 用原命令返回的整数替换示例 `12345`。此请求轮询输出。若结果仍带 `session_id`，可用该 ID 继续读取。

```json
{"session_id": 12345, "chars": "", "yield_time_ms": 5000, "max_output_tokens": 256}
```

**根据已核查的工具声明重建的 Code Mode 调用。** 假定 ID 指向一个正在等待行输入的 PTY 进程，`\n` 显式随输入发送。

```js
const result = await tools.write_stdin({ session_id: 12345, chars: "sample\n" });
text(result);
```

## 核查依据

- 本机安装包 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/codex/vendor/x86_64-pc-windows-msvc/codex-package.json` 标明 Codex 0.166.0。同目录 `bin/codex.exe` 的 SHA-256 为 `9d563ee4e0441ff9d59d612013e0460ddf8e5709735c2d9f6b98b7ef8ca4eb42`，描述原文自二进制零基字节偏移 `292550484` 开始。 [Codex 固定提交](https://github.com/openai/codex/commit/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856)
- 2026-11-11 活跃样本 `rollout-2026-11-11T11-31-29-*` 与归档样本 `rollout-2026-11-11T11-24-05-*`，各取第 2 行 `response_item` 的 `additional_tools`。两份记录均在 `exec.description` 内暴露 `tools.write_stdin`，描述原文的 UTF-8 SHA-256 为 `7f2fa7791a63a2d253def4d8763a7dc06692500d48505adc86c46ecb7ce5308b`。
- 活跃样本第 261、263 行记录 `exec_command` 返回进程会话 ID。第 267、269 行使用同一 ID 续取且仍可续接，第 274、276 行再次使用该 ID，结果返回退出码，随后不再附会话 ID。普通函数序列化、输入审批及失效分支依据固定源码。本次未为示例启动新终端，也未捕获完整出站模型请求。
- **实际运行记录。** 活跃样本第 289 行使用第 284 行返回的 `session_id` 续查 Blender 进程。第二次运行以第 338 行返回的另一个 ID 在第 342 行续查，第 344 行仍带该 `session_id`，表明该次工具响应保留了后续读取入口。 [本机 rollout](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:342>)
