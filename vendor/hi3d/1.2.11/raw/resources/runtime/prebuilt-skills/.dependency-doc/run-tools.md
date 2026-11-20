# 执行与记录工具

输入为显式任务标识、路径、配置及运行时阶段。纯 Python 的路径函数拒绝输出与输入/包路径冲突，配置读取不读取凭据。StageRecorder 提供阶段日志；record_external_stage 接收真实外部记录。不同 profiles 保留原来的 JSON/JSONL 字段和调用约定，不合并成虚假的统一计时结果。

path_safety/config_runtime/frame_diy_runtime 定义不同已有调用口径；request_inputs 的 package_root 必须传调用方包根，不能使用共享工具根替代。product_cli 仅构建 argparse 参数；stage_cli 负责 Blender/Python argv 与退出码适配。事件身份与 profile 字段映射、缺失时间、崩溃恢复、父子包含、追加尝试与可选 token 的统一要求见 [stage-records](../.dependency-run-tools/references/stage-records.md)，运行记录在包外。[产品记录配置](../.dependency-run-tools/references/timing.md)、[茶壶计时补充](../.dependency-run-tools/references/teapot-design-timing.md) 保留调用方的字段与阶段边界；[运行续接约定](../.dependency-run-tools/references/runtime.md#业务阶段耗时) 与业务阶段页直接引用统一契约。各业务页继续声明实际阶段和人工覆盖范围，不表示 run-tools 自身执行产品制作。

[AI 入口](../.dependency-run-tools/REFERENCE.md)与 [独立安装](../.dependency-package-tools/references/usage.md)定义调用方式。

[显式本地执行](../.dependency-run-tools/references/runtime.md#显式本地执行) 维护物化路径、模块导入与副作用边界、原始/派生产物及工作流续接要求；各函数继续保留自己的异常、覆盖和路径预检契约。工作状态显式传参、Blender 场景串行使用及失败留存也由该契约维护；品类保留环境版本、单位和实际阶段适配。

## 模块与接口

### scripts/artifact_refs.py

[唯一实现](../.dependency-run-tools/scripts/artifact_refs.py)。 Conversation aliases on `pcg.session.v1`; local paths only.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `mark_ref` | `session, *, name, path, label=None, task=None, output=None, entry=None, at=None` | Bind `@name` to a local path; same name overwrites. Reject reserved `last`, URLs and signed hrefs. |
| `mark_slot` | `session, *, name, task, output, label=None, at=None` | Copy path from an existing artifact slot then `mark_ref`. Unknown slot fails. |
| `list_refs` | `session` | Return copies of `session.refs`. |
| `resolve_ref` | `session, token, *, task_root=None` | Resolve `@name`, `ref:name` or `@last`. Optional `task_root` sets `exists`/`resolved` and rejects paths outside the task root. A resolved path is not proof the file still exists; after compact, pass `task_root` before treating the alias as a live input. |
| `rewrite_instruction` | `text, session` | Substitute known `@name`/`@last` with paths; leave other `@` tokens unchanged. |
| `load_session` / `save_session` | `path` / `path, session` | Read or replace the task-directory session JSON. |
| `main` | `argv=None` | CLI: `mark` / `list` / `resolve` / `rewrite`. |

调用说明见 [对话产物引用](../.dependency-run-tools/references/artifact-refs.md)。

### scripts/cli_schemas.py

[唯一实现](../.dependency-run-tools/scripts/cli_schemas.py)。 Shared local CLI schemas; business callables and argv adapter are explicit.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `directory_stage` | `execute, cli_arguments, argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `json_config_stage` | `execute, cli_arguments, argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `heightfield_stage` | `build, cli_arguments, argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `animate_stage` | `animate, cli_arguments, argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `preview_stage` | `build, cli_arguments, argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `inspection_stage` | `inspect_motion, cli_arguments, argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `relief_stage` | `extract, cli_arguments, argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### scripts/config_runtime.py

[唯一实现](../.dependency-run-tools/scripts/frame_runtime.py)。 Argument/path boundaries; importing this module never starts work.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `cli_arguments` | `argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `validate_paths` | `options` | Normalize explicit paths and reject missing inputs or in-package outputs.  Mutates only the provided Namespace. No file or scene changes occur here. `frames` is a directory only in application_demo, otherwise a frame selector. |
| `load_config` | `path, *, required=()` | Read a JSON object and reject absent required fields before modeling. |

### scripts/frame_diy_runtime.py

[唯一实现](../.dependency-run-tools/scripts/frame_diy_runtime.py)。 Local staged path and timing contracts; no Blender/service calls.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `paths_overlap` | `a, b` | True for equal/resolved ancestor paths, including existing symlink aliases. |
| `prepare_paths` | `*, output, raw_inputs=None, derived_inputs=None, work=None` | Validate without writes; protect package and original input files.  Derived inputs may be in the output tree for staged replay, but callers must not overwrite the derived input itself. Raw inputs must stay outside output and work trees. Returns resolved output, work and named input paths. |
| `require_distinct_outputs` | `inputs, outputs` | Reject output files that alias any declared source before writing them. |
| `timed_stage` | `*, log, task_id, attempt_id, stage, parent_stage=None, resume_of=None` | Append actual local stage timing; caller validates the log root first. |

### scripts/path_safety.py

[唯一实现](../.dependency-run-tools/scripts/path_safety.py)。 Preflight local write roots without creating or changing any files.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `paths_overlap` | `first, second` | Whether resolved paths coincide or one contains the other; follows existing symlinks. |
| `validate_write_roots` | `write_roots, *, package_root, protected_inputs=()` | Return resolved named write roots, or raise ValueError before any write.  Roots may already exist and may overlap each other for replay. They must not overlap the skill package or explicitly protected source files/directories. This validates the declared roots; callers still control their output names. |

### scripts/product_cli.py

[唯一实现](../.dependency-run-tools/scripts/product_cli.py)。

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `product_parser` | `description` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### scripts/profiles/portrait_reconstruction_timing.py

[唯一实现](../.dependency-run-tools/scripts/profiles/portrait_reconstruction_timing.py)。 Append business stage attempts, including failures; never log exception values.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `stage` | `path, name, task_id=None, parent_id=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### scripts/profiles/print_kit_timing.py

[唯一实现](../.dependency-run-tools/scripts/profiles/print_kit_timing.py)。 Append-only timing for explicitly wrapped business stages, not an auto tracer.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `timestamp` | `` | Return an aware UTC ISO timestamp from the wall clock. |
| `append_record` | `path, record` | Append one UTF-8 JSONL event, creating its parent; IO errors propagate. |
| `stage` | `path, task_id, stage_id, *, attempt=1, parent_id=None, scope='stage'` | Yield a run ID; append start/end and measured elapsed seconds.  Exceptions are recorded by type and re-raised; their messages are not logged. SIGKILL cannot emit an end event. Each retry gets a new run ID with the same task/stage ID and a caller-supplied higher attempt. Parent is another run ID. |
| `skipped` | `path, task_id, stage_id, reason, *, attempt=1, parent_id=None` | Append an explicit unexecuted stage with null timing, not fictitious zero. |
| `summarize` | `records, task_id` | Return latest event per attempt plus whole-task wall span; no stage sums.  Only explicit scope=task intervals define overall elapsed time. An unfinished task interval yields null total. Parent/child times remain inclusive. |

### scripts/profiles/relief_palette_timing.py

[唯一实现](../.dependency-run-tools/scripts/profiles/relief_palette_timing.py)。 Append-only, single-writer business-stage timing in the external run directory.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `now` | `` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `write_json` | `path, value` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `Recorder.__init__` | `self, directory, task_id, previous_attempt_id=None` | 该记录器的显式状态操作，格式见源码与统一计时契约。 |
| `Recorder.append` | `self, record` | 该记录器的显式状态操作，格式见源码与统一计时契约。 |
| `Recorder.stage` | `self, name` | 该记录器的显式状态操作，格式见源码与统一计时契约。 |
| `Recorder.skip` | `self, name, reason` | 该记录器的显式状态操作，格式见源码与统一计时契约。 |
| `Recorder.finish` | `self, status` | 该记录器的显式状态操作，格式见源码与统一计时契约。 |

### scripts/profiles/rig_timing.py

[唯一实现](../.dependency-run-tools/scripts/profiles/rig_timing.py)。 Append stage timing without credentials, request bodies, or model usage estimates.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `record_stage` | `path, task, stage, attempt='1'` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### scripts/profiles/screw_bottle_timing.py

[唯一实现](../.dependency-run-tools/scripts/profiles/screw_bottle_timing.py)。 Business-stage timing; callers own the external task directory and identifiers.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `utc_now` | `` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `append_event` | `path, event` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `stage` | `path, task_id, attempt_id, stage_id, previous_attempt_id=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `skipped` | `path, task_id, attempt_id, stage_id, reason, previous_attempt_id=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### scripts/profiles/twisty_fidget_timing.py

[唯一实现](../.dependency-run-tools/scripts/profiles/twisty_fidget_timing.py)。 Append-only stage timing. No tokens, environment, commands or credentials are logged.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `utc_now` | `` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `append_event` | `path, event` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `stage` | `path, task_id, attempt_id, name, previous_attempt_id=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### scripts/request_inputs.py

[唯一实现](../.dependency-run-tools/scripts/request_inputs.py)。

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `load_request` | `input_path, config_path, output_path, *, package_root` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### scripts/stage_cli.py

[唯一实现](../.dependency-run-tools/scripts/stage_cli.py)。 Local stage invocation helpers. No work is performed on import.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `StageFinished.__init__` | `self, code=0` | 该记录器的显式状态操作，格式见源码与统一计时契约。 |
| `_finish_stage` | `code=0` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `cli_arguments` | `argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### scripts/timing.py

[唯一实现](../.dependency-run-tools/scripts/timing.py)。 Small, single-writer timing journal; no cache, recovery, or token estimates.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `_utc_now` | `` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `_identifier` | `value, field` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `_timestamp` | `value, field` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `_finite_number` | `value, field, nonnegative=True` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `_atomic_text` | `path, content` | Replace one file, retaining the previous complete file on write failure. |
| `_append_event` | `run_dir, record` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `write_json` | `path, value` | Atomically write a task report with the journal's shared file adapter. |
| `_validated_record` | `record` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `record_external_stage` | `run_dir, record` | Validate and append a measured external final record, without a summary.  Required identity fields are task_id, attempt_id and stage. Timestamps must include a timezone and are normalized to UTC. Missing timestamps/duration stay null and require missing_reason. Supply timing_method for a measured duration. A skipped phase instead requires reason and no execution times. This function does not derive a duration from wall-clock timestamps. |
| `StageRecorder.__init__` | `self, run_dir, task_id, attempt_id, previous_attempt_id=None, started_at=None, started_clock=None` | Record one attempt with explicit lineage and measured stage durations. |
| `StageRecorder._ensure_open` | `self` | Record one attempt with explicit lineage and measured stage durations. |
| `StageRecorder._identity` | `self, name` | Record one attempt with explicit lineage and measured stage durations. |
| `StageRecorder._complete_stage` | `self, record, clock, status` | Record one attempt with explicit lineage and measured stage durations. |
| `StageRecorder.stage` | `self, name` | Yield a record; retain failure/interruption and re-raise it unchanged. |
| `StageRecorder.add_record` | `self, record` | Append an already measured final stage to this attempt and summary. |
| `StageRecorder.skip` | `self, name, reason` | Record non-execution without fabricating a zero-duration interval. |
| `StageRecorder.finish` | `self, status` | Write this attempt's wall-clock summary; nested times are not added. |

## 验收方法

仅在仓库外的独立包和合成输入上运行。校验参数错误、输出保护、正常结果及失败传播；记录工具不通过真实任务补统计，Blender 工具不在未保存的前台工程测试，依赖打包不修改已安装目录。验证记录保存到任务目录，不将一次测试当作全部业务/线上服务的验收。

## 共享本地构建阶段

[build_stage.py](../.dependency-run-tools/scripts/build_stage.py) 的 `run_build(input_path, config_path, output_path, geometry_only=True, *, package_root, loader)` 接收调用方包根和延迟的 build 加载器；从输入校验到输出建立仍使用 request_inputs 的明确路径约束。计时从输出目录建立之后开始，包含加载器与 build 执行，成功/异常/中断都保存 stage-time.json；不把本地阶段时长当作完整产品任务总耗时。茶壶、花器和水景入口仅提供各自构建模块，统一保持原来的字段和默认值。

[tests/test_build_stage.py](../.dependency-run-tools/tests/test_build_stage.py) 验证显式参数/路径交接、成功和加载器失败计时，以及写入调用方包内路径时在运行加载器前拒绝。

## 本地进程、缓存与阶段事件

[完整调用契约](../.dependency-run-tools/references/local-runtime.md) 覆盖新核心和原 profile 的交接。

- [process_run.py](../.dependency-run-tools/scripts/process_run.py)：`run_process` 单次本地子进程、合并日志、异常时有界 terminate/kill/wait；`run_budgeted` 增加墙钟预算、心跳 JSON 与 `BudgetTimeout`；`popup_reason` 只读分类 timeout/stall/exhausting；无自动重试或加时。契约见 [预算与心跳](../.dependency-run-tools/references/budget-run.md)。
- [checkpoints.py](../.dependency-run-tools/scripts/checkpoints.py)：`digest` 分块文件哈希；`artifacts_match` 只读核对必要输出名与全部记录内容。业务指纹和依赖图在工作流。
- [session_schema.py](../.dependency-run-tools/scripts/session_schema.py)：`new_session` / `validate_session` / `append_artifact` / `apply_tool_result` / `mark_purged` / `purge_under_root` / `asked_popup_reasons` / `mark_popup_reason` / `pending_inject` / `mark_injected` / `clear_injected` / `mark_stream` / `begin_hi3d_waiting` / `record_hi3d_selected` / `grant_hi3d` / `consume_hi3d_once` / `revoke_hi3d_grants`；产物槽追加留痕，可选 `refs`、`popup_reasons`、`injected`、`stream`、`waiting_context`、`confirmations` 与 `hi3d_options`（身份/表面/kind/预填 selected 与 selected_by_kind）；compact 后清空 `injected`；按语义清理 cache 文件后仍保留最后路径；文件只写任务目录。
- [tool_result.py](../.dependency-run-tools/scripts/tool_result.py)：`tool_result` / `validate_tool_result` 约束回写 Agent 循环的短 JSON。
- [artifact_refs.py](../.dependency-run-tools/scripts/artifact_refs.py)：`mark_ref` / `mark_slot` / `list_refs` / `resolve_ref` / `rewrite_instruction`；把 `@name` / `@last` 绑到任务目录路径并替换进后续指令。契约见 [对话产物引用](../.dependency-run-tools/references/artifact-refs.md)。离线测试：[tests/test_artifact_refs.py](../.dependency-run-tools/tests/test_artifact_refs.py)。

衔接字段总表见 [pcg-loop](pcg-loop.md)。离线测试：[tests/test_session_schema.py](../.dependency-run-tools/tests/test_session_schema.py)。
- [stage_events.py](../.dependency-run-tools/scripts/stage_events.py)：`utc_now`、`record_stage` 共享带 UTC/monotonic 的起止与异常分类，由 emit/records 接收记录；keychain 与 relief_palette_timing 保留自己的字段。
- [profiles/content_journal.py](../.dependency-run-tools/scripts/profiles/content_journal.py)：`Journal.__init__` 恢复未结束事件、保留任务身份；`save` 原子状态替换，`append` 追加事件，`stage` 验证缓存/执行动作/校验产物并记录 seconds。沿用注册工作流的磁盘 schema，不执行模型或服务任务。

工具单独验证成功、失败、中断清理、缓存内容变化和缺失产物；调用方验证历史记录恢复和自身阶段失效关系。原 frame_diy_runtime 的配方/高度场入口分别移到 [frame_recipe](../frame-design/scripts/frame_recipe.py) 与 [heightfield_io](../.dependency-relief-map/scripts/heightfield_io.py)，全部原参数校验范围保持，工具无品类配方依赖。

## 内容摘要与生命周期适配

`checkpoints.digest(path)` 是文件内容 SHA-256 的唯一分块核心，空文件和大于 1 MiB 的文件都返回完整摘要；读取失败原样传播。业务文件复用该函数，服务特有脱敏摘要不变。

`stage_events.record_stage` 增加 now/clock 注入（缺省为 UTC 与 monotonic）及 wall_first=False。两个采样次序在各旧 profile 中显式保留。`stage_events.append_event(path,event)` 是追加 UTF-8 严格 JSONL 的文件适配，不创建父目录、不吞掉 IO/序列化异常。原 utc_now/record_stage 接口及 missing_reason/records 行为保持。

两个螺旋产品的 profiles.stage 仅序列化身份、stage 或 stage_id、running/terminal 字段，不重复维护生命周期；utc_now/append_event 是从共享模块导出的兼容名。screw 的 skipped 不运行上下文且时间为 None。业务异常按类型记录并原样抛出，不含异常正文，不决定远端重试。完整调用和恢复边界仍见 [本地运行核心](../.dependency-run-tools/references/local-runtime.md)。

[tests/test_stage_profiles.py](../.dependency-run-tools/tests/test_stage_profiles.py) 验证完整摘要、事件字段、成功/失败/中断、时钟注入及 skipped；历史记录无需转换。

## 多输入预检与流式子进程

[config_runtime.py](../.dependency-run-tools/scripts/frame_runtime.py) 的 resolve_file_request(inputs,write_roots,package_root) 通过 path_safety 返回已解析输入/写入根，保护全部输入文件与显式调用方包；不创建目录，允许输出续接。它不采用 request_inputs 的新目录策略，业务参数由调用者及 load_config 校验。[路径契约](../.dependency-run-tools/references/local-runtime.md#写入根与受保护输入) 逐项区分 validate_write_roots、resolve_file_request 与旧 profile，说明配置保护、已有根续接、输出名和非事务边界。各工作流的 runtime 只维护其实际保护对象与配置位置，不把派生配置通则套给受保护输入。

[process_run.py](../.dependency-run-tools/scripts/process_run.py) 新增 run_checked(command,env=None,terminate_timeout=10)，继承 stdout/stderr、成功 None、失败 CalledProcessError；run_process 继续写合并日志并抛 RuntimeError。run_budgeted 在两者之外提供墙钟上限与心跳；超时 BudgetTimeout。popup_reason 只读分类 timeout/stall/exhausting，不杀进程。_wait / _stop 共用直接子进程异常清理，不重试、不负责孙进程或业务阶段。child_environment(inherit=(),overrides=None) 只选取调用方列出的键并覆盖指定值，不遍历环境。详细边界和参数见 [随包契约](../.dependency-run-tools/references/local-runtime.md) 与 [预算与心跳](../.dependency-run-tools/references/budget-run.md)；离线验收使用临时输入/输出、真实合成子进程、非零退出、预算超时、心跳分类和父级中断，检查进程回收及原有日志行为。

[本地进程测试](../.dependency-run-tools/tests/test_local_process.py) 验证显式环境、多输入保护、安全目录续接、真实子进程退出/日志、预算超时心跳和 POSIX 父级中断后的回收；只生成临时合成输入与日志。

## 受管 Desktop 执行

[desktop-runtime.md](../.dependency-run-tools/references/desktop-runtime.md) 统一宿主账号工具、显式可执行路径、文件登记、HTML 预览及进度边界；它是运行契约，没有新增网络实现。业务入口按当前宿主能力选择分支，真实协议由各工具维护。

## 声明式编辑任务

[hi3d-edit-job.py](../.dependency-run-tools/scripts/hi3d-edit-job.py) 的全部原子接口、状态、依赖、副作用、缓存与取消边界见 [唯一契约](../.dependency-run-tools/references/hi3d-edit-job.md)。它组合已有 path_safety 与 process_run，不另写进程预算内核。验证新输出/输入保护、成功复用、素材和源码变化失效、失败与中断状态；领域适配另做真实工程回读。

`process_run.run_budgeted(..., kill_tree=False)` 新增可选 POSIX 进程组；默认保持旧调用行为，显式启用时 `_stop` 终止整个同组树。配合编辑任务主线程 SIGTERM 取消，测试直接子进程与孙进程均不会延迟写出产物；脱组守护和 Windows 树清理不在保证范围。
