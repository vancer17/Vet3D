# exec_command

## 工具名称与注册来源

`exec_command` 由 Hi3D Agent 1.2.11（Windows x64）随包的 Codex 0.166.0 提供。Codex 在本轮启用 shell 工具、模型允许使用 shell 且满足工具策略时注册它。启用 Unified Exec 时，`exec_command` 可以返回可续接的进程会话，并与 `write_stdin` 一起注册。工具可以随本轮路由作为普通函数暴露，也可以由代码模式的 `tools.exec_command` 调用。本机核查的两份会话记录采用代码模式。 [注册分支](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/spec_plan.rs#L1223-L1274) · [代码模式工具](exec.md)

## 暴露给 LLM 的描述

以下原文对应本机样本中的可续接 Windows 版本。首句与 Windows 附段均已同随包 `codex.exe` 核对。只有一个环境且该执行器报告 Windows 时，Codex 添加 Windows 附段。有多个环境或单一执行器未报告平台时，按宿主平台决定。没有环境时省略附段。 [工具描述构造](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/shell_spec.rs#L87-L109) · [环境判断](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/spec_plan.rs#L1223-L1239)

```text
Runs a command in a PTY, returning output or a session ID for ongoing interaction.

Windows safety rules:
- Do not compose destructive filesystem commands across shells. Do not enumerate paths in PowerShell and then pass them to `cmd /c`, batch builtins, or another shell for deletion or moving. Use one shell end-to-end, prefer native PowerShell cmdlets such as `Remove-Item` / `Move-Item` with `-LiteralPath`, and avoid string-built shell commands for file operations.
- Before any recursive delete or move on Windows, verify the resolved absolute target paths stay within the intended workspace or explicitly named target directory. Never issue a recursive delete or move against a computed path if the final target has not been checked.
- When using `Start-Process` to launch a background helper or service, pass `-WindowStyle Hidden` unless the user explicitly asked for a visible interactive window. Use visible windows only for interactive tools the user needs to see or control.
```

固定源码中还有单次执行分支。当受管要求禁用 Unified Exec 且策略仍允许 shell 时，该分支使用下列首句，Windows 附段仍按上述条件添加。本机两份样本中只观察到可续接分支。 [单次执行工具定义](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/unified_exec/exec_command.rs#L279-L311)

```text
Runs a command to completion and returns its output. The process is terminated on timeout or cancellation and cannot be resumed.
```

## 参数与结果

模型可见参数 schema 要求 `cmd`，声明 `additionalProperties: false`，工具定义的 `strict` 为 `false`。调用以本轮实际暴露的字段为准。

| 参数 | 必填性、默认值与约束 |
| --- | --- |
| `cmd` | 必填字符串，交给所选 shell 解释。 |
| `workdir` | 可选字符串。省略或为空时使用所选环境的 `cwd`。相对路径以该环境的 `cwd` 为基准。 |
| `shell` | 可选字符串。省略时使用环境 shell。本地会根据给出的 shell 类型寻找可执行文件。远程环境只能使用执行器报告的 shell 类型。 |
| `login` | 可选布尔值。省略时按环境的 `allow_login_shell` 设置决定，模型可见说明给出的通常默认值是 `true`。该配置禁用登录 shell 时，显式传 `true` 会报错。 |
| `tty` | 可选布尔值，默认 `false`。启用对应特性时暴露，设为 `true` 会分配 PTY，省略时使用普通管道。 |
| `yield_time_ms` | 可续接分支的首段输出等待上限。默认 10,000 毫秒，Windows 版本将其限制在 10,000 至 30,000 毫秒之间。命令提前完成时可提前返回。 |
| `max_output_tokens` | 可选整数。普通函数输出使用默认 10,000 token 的请求预算，并受模型截断策略约束。代码模式提供显式上限时按该值截断，省略时返回采集阶段保留的输出。 |
| `environment_id` | 只在多执行环境模式暴露。省略时选择主环境。 |
| `sandbox_permissions` | 可选，默认 `use_default`。`require_escalated` 请求沙箱外执行，由审批策略约束。只有启用额外权限功能且本轮策略暴露该能力时，模型可用 `with_additional_permissions`。 |
| `justification`、`prefix_rule` | 用于 `require_escalated` 的可选参数。前者向用户说明审批请求，后者提供可复用的命令前缀。 |
| `additional_permissions` | 仅在本轮工具定义暴露时使用。与 `with_additional_permissions` 一起传递文件系统或网络权限请求。 |
| `timeout_ms` | 单次执行分支替换 `yield_time_ms` 和 `tty` 的字段。默认 10,000 毫秒，用于限定进程运行时间。 |

[参数定义](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/shell_spec.rs#L19-L109) · [权限参数](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/shell_spec.rs#L225-L329) · [参数准备](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/unified_exec/preparation.rs#L135-L318)

- **代码模式结果。** 对象始终含 `output`、`wall_time_seconds`，按实际状态附 `chunk_id`、`original_token_count`、`exit_code` 或 `session_id`。进程可续接时，`session_id` 指向 Codex 进程管理器里的条目。
- **普通函数结果。** 以对应的调用 ID 返回文本内容，包含等待时长及可用的会话 ID、退出码和输出。收到正常结构的工具结果后，仍需读取退出码判断命令退出状态。沙箱拒绝可通过带退出码的终止结果返回，参数解析、执行环境不可用、审批拒绝或启动失败也可作为工具错误返回。
- **副作用。** 命令在所选环境和权限范围内执行，可以读写文件、启动进程或发起网络请求。首段等待结束时仍存活的进程可继续运行。

[输出 schema](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/shell_spec.rs#L191-L223) · [普通函数与代码模式结果](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/context.rs#L422-L567) · [执行错误处理](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/unified_exec/exec_command.rs#L219-L278)

### 权限、沙箱与前置 Hook

1. **注册和有效策略。** 启用受管沙箱要求时，Codex 会检查当前线程及各执行环境的权限配置，再决定工具能否暴露。调用者可用 `workdir` 选择目录，文件读写和网络权限仍由所选环境的有效配置约束。本机 `config.toml` 记载 `workspace-write/on-failure`。同版留存的活跃与归档样本第 7、12 行实际记录 `read-only/on-request`，受管权限配置允许读取文件系统，网络为 `restricted`。核对具体调用时应读取该轮的 `turn_context`。 [受管沙箱注册条件](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/spec_plan.rs#L1185-L1206) · [本机配置](<D:/download/.sparc3d-runtime/environments/prod/codex-home/config.toml:9>) · [活跃轮次记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:7>) · [归档轮次记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/archived_sessions/rollout-2026-11-11T11-24-05-01a1c8a2-5bab-7df0-8557-d36af12e8411.jsonl:7>)
2. **前置 Hook。** `exec_command` 处理器将可解析的命令作为 `PreToolUse` 的 Bash 类型事件输入。本地执行环境可提供解析后的工作目录，远端工作目录不会作为宿主 Hook 的工作目录。Hi3D Runtime 启动 app-server 时启用 Hook，并配置和核对发行包的 `templates/hooks/skill-credit.cjs`。脚本将包含会话、轮次和工具输入的事件经受保护的 loopback POST 交给 Runtime。只有 HTTP 200 且 `allowed:true` 时放行，已有明确同意可附加上下文。拒绝、响应无法解析或请求错误会返回 `permissionDecision:"deny"`，阻止命令执行。脚本设置 550 秒请求超时，宿主 Hook 的执行预算为 600 秒。 [事件负载与工作目录](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/unified_exec/exec_command.rs#L336-L364) · [随包 Hook 脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/hooks/skill-credit.cjs:7>) · [Runtime 的启动配置与信任检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)
3. **审批和执行。** 前置检查通过后，Codex 准备命令和权限，按当前审批策略处理请求并在选定环境执行。Hook 的积分确认和 shell 的权限审批各有判据。常规调用使用本轮默认权限。选择扩大权限时仍需匹配本轮暴露的参数并满足审批策略。Runtime 动态工具若直接启动自己的子进程，则经过其宿主分派及网络限制，该调用链可在对应工具页核对。 [审批判定](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/unified_exec/preparation.rs#L63-L120) · [命令执行](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/unified_exec/exec_command.rs#L165-L278) · [Runtime 工具执行](hi3d-api.md#实现伪代码)

### 续接运行中的进程

Unified Exec 返回 `session_id` 时，将该整数交给独立注册的 `write_stdin`，即可读取同一进程的后续输出或向其发送输入。 [write_stdin](write-stdin.md)

调用方应从进程结果判断命令是否退出。若命令负责生成文件，可另外检查预期路径上的文件是否存在、能否打开，以及内容是否符合任务要求。图像文件可交给 `view_image` 读取。 [view_image](view-image.md)

如果命令写出结构化报告，进程的 `exit_code` 和报告中的业务结果应分别读取。程序可能用退出码 `0` 表示报告已写完，同时在报告中给出拒绝或需要修订的结论。Codex 交付进程输出，报告格式与结论由被调用程序定义。

随包脚本可按需使用本地 Python 函数 `process_run.run_budgeted`。它在调用方提供 `max_wall_seconds` 时管理子进程时限，可写心跳和日志，超时终止子进程并抛出 `BudgetTimeout`。是否使用该函数、预算文件和超时后的业务状态由实际调用方决定。Unified Exec 的 `yield_time_ms` 只控制首段工具输出的等待时间。 [本地预算契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/budget-run.md>) · [Python 函数实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/process_run.py:152>)

### 本地脚本的文件结果

启动 Blender 等会改写进程内场景的程序时，可用独立后台进程，按 `workdir` 解析相对输入与输出。命令可显式传 `--python-exit-code 1`，让未处理的 Python 异常反映到进程退出码。启动包装、可选墙钟预算及脚本自己的业务参数各有定义。 [后台启动包装](../resources/blender-execute.md) · [专项本地脚本](../resources/specialized-mesh-scripts.md)

多文件产物要按被调用程序的落盘顺序核对。工程与配套报告可能分步写出，只有部分文件时可保留已落盘内容和进程诊断。后续读取实际文件，检查预期文件是否齐全、报告是否对应，以及任务所需的内容。执行句柄失效时，同样以已经落盘的实际文件为恢复依据。程序可能直接覆盖报告路径，或在提前失败时保留旧报告。启动前可核对输入与各输出路径互异，回读时确认报告属于本次执行。 [进程续读](write-stdin.md) · [工程读取](../resources/p1/asset-scene.md)

例如，`rig_adapter cache` 先独占创建 NPZ，再计算摘要、复核源文件并写 JSON 报告；写入并非多文件事务，失败可能留下部分 NPZ 或完整 NPZ 而没有报告。其报告路径须在启动前不存在。旧版 `cache_bvh` 只写 NPZ 和标准输出摘要，没有配套 JSON 报告；输出路径未带 `.npz` 时，NumPy 自动追加后缀的实际目标还可能绕过脚本对原路径的存在性检查。`exec_command` 不为这些脚本补做文件校验、回滚或断点续写。调用方按实际脚本契约检查输出路径、格式、摘要与诊断，不能由缺少报告或外层工具错误推定命令未执行。 [求值缓存契约](../resources/specialized-mesh-scripts.md#rig_adapter-cache-求值动作缓存) · [BVH 缓存契约](../resources/specialized-mesh-scripts.md#cache_bvh-bvh-兼容缓存)

收到可续接的 `session_id` 时继续读取原进程。只有 `cell_id` 时先续查原 Code Mode 单元，取得其中的进程结果。若启动回执不明或句柄已失效，先核对原命令、日志、实际进程与已落盘文件，再决定复用完整结果或以新输出路径重做；重新提交命令不会接管原进程，也不能证明原写入尚未发生。脚本是否支持追加、分段恢复或重用由其独立契约决定。 [执行单元续查](wait.md#关联终止与恢复)

`rig_adapter calibrate/retarget` 则在保护检查后先保存候选工程，禁用嵌入脚本重开并再验，最后才普通写 JSON 报告。入口要求新的输出和报告，但不是并发独占锁，底层报告写入也不是原子替换；后段失败可留完整工程、缺失报告或部分 JSON。报告中的 `input_sha256` 是本次目标输入工程摘要，`rig_sha256` 是输入目标 rest；校准后的映射使用 `after_rig_sha256` 或重新检查所得摘要。配置 JSON 不会自动复制进报告，也没有 spec 字节摘要，调用方另保配置及其身份。stdout 的操作摘要与完整报告各有字段，不以 stdout 成功、文件存在或 `pose_qa_pending:true` 代替质量验收。 [校准与输出](../resources/specialized-mesh-scripts.md#rig_adapter-已有骨架检查与调整) · [重定向文件契约](../resources/specialized-mesh-scripts.md#rig_adapter-retarget-动作映射与烘焙)

脚本自身的路径门禁与宿主有效权限分别检查。`rig_adapter.new_path()` 解析路径并拒绝已存在或指定冲突的路径，没有工作区根归属、`hi3d-` 前缀或输出后缀门禁；也不由 `exec_command` 自动补上这些领域规则。可选专项计时日志须另选不与输入、缓存、候选或报告重叠的路径；其晚期追加失败可在主要文件已完成后令命令报错。 [本地路径及共享函数](../resources/specialized-mesh-scripts.md#动作缓存的分派与共享函数)

`stage_ops clip` 是另一种本地文件结果契约：主候选须为新路径，但可省略的报告默认取候选旁 `.report.json`，普通写入可覆盖已有报告，且该报告路径没有与输入／候选同等级的隔离门槛。候选摘要在 JSON 写入之前计算，因此不能把报告里的摘要或 stdout `complete:true` 当作工程仍可读取的保证。该路径行为来自安装源码，本次未对 clip 做同址故障注入；调用方核对实际候选、报告及退出状态后再恢复。 [裁剪参数与报告覆盖](../resources/specialized-mesh-scripts.md#stage_ops-clip-已烘焙动作裁剪)

`service_rig inspect` 在新报告路径写数值检查结果，不保存输入工程。若检查完成且 `pass:false`，先写报告再抛异常；对象、权重、求值或拓扑前提失败时，可能还没有新报告。它用同包 `atomic_json` 原子替换单份报告，但入口的“路径尚未存在”检查不是独占锁。`input_sha256` 在末尾读取一次，调用方需要执行前后身份时另行取证。 [检查与报告契约](../resources/specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查)

`service_rig repair` 要求新的候选与报告，先修改进程内权重、比较保护签名，再检查 `.blend` 后缀、保存工程并计算摘要，最后原子写报告。写回／保护失败可能留下内存修改；保存后报告失败可能留下完整候选。回执中的改动统计和 `pose_qa_pending:true` 不是姿势通过，也没有 `pass` 字段。规则、实际输入／权重版本及修后检查由调用方共同核对，`exec_command` 不补做回滚或修复验收。 [参数与失败落盘](../resources/specialized-mesh-scripts.md#service_rig-repair-局部权重修订) · [底层写回与保护](../resources/specialized-mesh-scripts.md#service_rig-权重写回与保护函数)

P1 `export_glb` 返回路径前只检查导出器含 `FINISHED`；不验证文件、skin／clip、依赖或单位，也没有 JSON 报告、原子发布或输出回滚。它会恢复记录的场景状态，恢复本身失败仍可抛错。输出覆盖规则和参数可用范围由调用方及实际导出器决定。 [选定对象导出](../resources/p1/glb-export.md)

专项 `audit_models.py` 实际重置场景并导入 GLB，整批处理完才普通覆盖写 JSON；报告无质量 `pass`，早退可留旧报告，写入中断可留部分 JSON。该入口没有报告与输入同址保护，调用方需明确独立路径。P1 `glb_bounds` 的批次报告也在末尾覆盖；`glb_clips` 的 GLB 提交与报告写入分开，可能已有新 GLB 而报告失败。`exec_command` 不补做这些脚本缺少的门槛或事务。 [专项回读与覆盖](../resources/specialized-mesh-scripts.md#audit_modelspy-独立-glb-回读) · [静态尺寸](../resources/p1/glb-bounds.md) · [容器与同时通道合并](../resources/p1/glb-clips.md)

## 实现伪代码

**根据固定源码与安装包重建的伪代码。** 工具路由先执行适用的前置 Hook。权限参数校验和命令准备完成后，处理器才分配进程 ID。统一进程管理器按审批与沙箱策略执行并收集输出，用同一 ID 关联尚可续接的进程。

```python
async def exec_command(args, context):
    environment = select_environment(context, args.get("environment_id"))
    cwd = resolve_workdir(environment, args.get("workdir"))
    await enforce_pre_tool_use_hook_if_configured(args, context, environment, cwd)
    command = prepare_shell_command(args, environment, cwd)
    permissions = validate_permissions(args, context, environment, cwd)
    patch = await intercept_apply_patch_if_applicable(command, cwd, context)
    if patch is not None:
        return format_tool_result(patch, context)

    process_id = context.manager.allocate_id()
    if context.one_shot:
        result = await context.manager.run_to_completion(
            process_id, command, cwd, permissions, args.get("timeout_ms", 10_000)
        )
    else:
        result = await context.manager.run_until_yield(
            process_id, command, cwd, permissions, args
        )
    return format_tool_result(result, context)


async def continue_exec(args, context):
    terminal = await context.manager.resolve_terminal(args["session_id"])
    result = await context.manager.write_or_poll(
        terminal, chars=args.get("chars", ""), options=args
    )
    return format_tool_result(result, context)
```

[命令处理器](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/unified_exec/exec_command.rs#L124-L278) · [续接处理器](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/unified_exec/write_stdin.rs#L68-L124)

## 调用示例

**根据已核查的工具声明重建的代码模式示例。** 假定所选环境使用 PowerShell。命令读取执行目录，若返回进程会话 ID，则继续轮询同一进程。每次返回的输出分段保留，最终一起报告退出码。

```js
let result = await tools.exec_command({
  cmd: "Get-Location",
  max_output_tokens: 256
});
const chunks = [result.output];
while (result.session_id !== undefined) {
  result = await tools.write_stdin({
    session_id: result.session_id,
    chars: "",
    max_output_tokens: 256
  });
  chunks.push(result.output);
}
text({ exit_code: result.exit_code, chunks });
```

## 核查依据

- 本机安装包文件为 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/codex/vendor/x86_64-pc-windows-msvc/bin/codex.exe`，SHA-256 为 `9d563ee4e0441ff9d59d612013e0460ddf8e5709735c2d9f6b98b7ef8ca4eb42`。随包 `codex-package.json` 标明 0.166.0。可续接首句、单次执行首句和 Windows 附段分别自二进制零基字节偏移 `292243536`、`292243618` 和 `292553314` 开始。 [Codex 固定提交](https://github.com/openai/codex/commit/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856)
- 活跃和归档两份本机 rollout 第 2 行 `exec.description` 中的嵌套声明与上面的可续接 Windows 描述逐字一致。活跃样本 `rollout-2026-11-11T11-31-29-*` 第 19、24 行记录一次命令调用及退出码，第 261、263 行记录另一次调用返回可续接的 `session_id`。单次执行、额外权限和普通函数序列化分支依据固定源码。本次未为示例启动新终端。
- **Hook 安装包与隔离验证。** `runtime.mjs` 的 `hookArguments`、`trustHook` 和将 Hook 配置合入启动参数的调用位于 UTF-8 零基字节偏移 `3095138`、`3098083`、`3115289`。生产日志第 28 行记录启动时的 Hook 信任阶段，未采集逐调用 Hook 结果。隔离运行随包脚本，以本地模拟端点验证了允许并附带同意上下文、明确拒绝、无效 JSON 和非 200 响应四种分支。记录前置拦截时应查看 Hook 决策或工具错误。收到进程结果时再用其退出码或沙箱拒绝状态判断执行。 [Runtime bundle](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [Hook 脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/hooks/skill-credit.cjs:7>) · [生产启动记录](<D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:28>)
- **实际运行记录。** 活跃样本第 282 → 284 行、第 336 → 338 行分别记录 `tools.exec_command` 以 `--background --python` 启动 Blender。两次首段输出均已暴露可续接的 `session_id`。首段证据覆盖进程启动及会话分配，文件产物另有读取记录。 [本机 rollout](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:282>) · [view_image 核查依据](view-image.md#核查依据)
- **实际文件属性查询。** 活跃样本第 154 行使用 `Get-Item -LiteralPath` 读取一个本地文件。第 159 行的命令回包记录 `exit_code: 0` 和名称、完整路径、长度。该命令输出可用于核对访问到的文件及属性。内容摘要、格式解码及视窗状态分别由相应的读取操作取得。 [调用与回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:154>)
- **本地预算辅助函数。** 随包 Python 测试在 Windows 通过五项，依平台跳过一项 POSIX 父进程中断测试。该轮测试覆盖本地子进程辅助代码。桌面取消及外部程序的进程回收仍依赖实际执行环境核验。 [随包本地进程测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/tests/test_local_process.py>)
