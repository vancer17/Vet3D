# 本地运行核心

在物化包的 scripts 路径导入。`process_run.run_process(command, log, env=None, terminate_timeout=10, error_prefix="Stage exited")` 记录子进程合并输出，失败抛 RuntimeError；父级异常先 terminate，10 秒未退出则 kill/wait，重抛原异常，不重试。调用者准备日志目录、显式命令与环境策略，不传入凭据用于维护测试。

本地无界 CPU 必须改用 `run_budgeted`：墙钟 `max_wall_seconds`、可选 `heartbeat_path` / `heartbeat_seconds`，超时抛 `BudgetTimeout` 并 terminate/kill，不延长、不重试。`popup_reason` 只读心跳，分类 timeout/stall/exhausting。心跳 JSON 与调用方职责见 [预算与心跳](budget-run.md)。`run_process` / `run_checked` 不隐含预算。

`checkpoints.digest(path)` 分块 SHA-256；`artifacts_match(artifacts, base=None, expected=(), allow_empty=False)` 只读核对全部哈希及必要产物名，缺失或变化拒绝缓存。工作流另核对完整参数/输入指纹与 schema，保留自己的阶段图。不能将本地缓存命中等同远端幂等或采用本地重跑策略重复收费提交。

`stage_events.record_stage(name, emit, records, missing_reason="End not observed", timing_method="monotonic")` 输出 running/终态两事件；单调 elapsed_seconds，KeyboardInterrupt/SystemExit 为 interrupted，其余异常 failed 并重抛。emit 附加身份和持久化，records 保存终态；timing_method=None 保留 keychain 的旧字段。`utc_now()` 返回 UTC ISO 时间。此适配保留 elapsed_seconds；其他 seconds/duration_seconds profile 按自己的记录格式调用，不能静默混写。

`profiles.content_journal.Journal(root)` 保留注册工作流的 timings.jsonl/workflow.json，开始/结束事件、seconds、task_id/attempt_id 及现有状态格式；stage(name,key,outputs,action,enabled=True) 仅在签名和全部产物哈希/必要输出匹配时跳过。save 原子替换状态，append 追加事件。未结束 running 恢复为 interrupted，seconds=None 且记录原因，不补造耗时。导入时从 scripts 路径使用 profiles.content_journal；工作流物化为 content_journal.py。

frame_diy_runtime 仅保留路径保护与原 duration_seconds 计时；110 mm 圆口等配方由 frame-design/frame_recipe 唯一维护，NPZ 高度场由 relief-map/heightfield_io 维护。现有字段、异常分类和包外记录要求保持。

摘要唯一实现为 checkpoints.digest，工作流通过清单物化并导入，不另维护分块哈希。空文件也返回完整 SHA-256；读取失败传播，不触发任务重跑。

`record_stage` 可注入 now/clock，并以 wall_first 显式保持旧 profile 的起始采样顺序；缺省仍先 monotonic 后 UTC。`append_event(path,event)` 只追加严格 UTF-8 JSONL、不创建父目录，写入失败传播。两种螺旋产品 profile 通过 emit 适配 stage/stage_id、身份与 error_type=None；running 不加 error_type，终态不含 missing_reason。它们保留原调用签名和前次 attempt 字段。screw 的 skipped 继续是空时间的独立事件，不运行生命周期；无重试、无 token 推断、无远端状态决策。

`process_run.run_checked(command,env=None,terminate_timeout=10)` 使用继承的 stdout/stderr，单次运行，成功返回 None，子进程非零抛 CalledProcessError；与 run_process 共用父级异常后的有界 terminate/kill/wait，但不改变既有日志接口的 RuntimeError 口径。两者不管理孙进程，不自动重试或追加计时。

`process_run.child_environment(inherit=(),overrides=None)` 只复制显式名称的环境变量后应用覆盖字典，不遍历整份环境、不打印值。缺省为空映射，调用方选择必要非敏感键及运行标志；不得借此读取或传递维护任务无权使用的凭据。

## 写入根与受保护输入

`path_safety.paths_overlap(first, second)` 比较 resolve 后的相等、祖先或子路径，跟随已有符号链接。`validate_write_roots(write_roots, *, package_root, protected_inputs=())` 接收命名写入根、调用方包根及显式受保护文件/目录，返回解析后的写入根字典；与包或任一受保护输入重叠则抛 ValueError。已有安全输出可续写，写入根之间允许重叠。它不检查输入是否存在、不解析业务参数、不创建或改变文件；配置只有明确列入 protected_inputs 时才受该函数保护。

`config_runtime.resolve_file_request(inputs, write_roots, *, package_root)` 返回 `(解析后的输入字典, 解析后的写入根字典)`。它先要求所有命名输入均为现有文件，否则抛 FileNotFoundError，再将**全部输入**交给上述路径核心保护；模型和配置没有特殊豁免。例如传入 `{'input': model, 'config': config}` 时，config 位于任一输出根内也会被拒绝。函数不写文件；`load_config(path, required=...)` 另行检查 JSON 对象及显式必填字段，业务入口按自己的顺序完成参数预检再写入。

调用者仍控制根内输出名和覆盖策略；根预检不验证每个派生文件、硬链接或并发变化的符号链接，也不提供后续几何/I/O 异常的事务回滚。只有路径拒绝保证本函数没有写入，不能扩大成完整入口在任何失败时都不留文件。

这些 API 不能与现有 profile 直接互换：`config_runtime.validate_paths` 只规范化其已知参数、检查输入存在和 output 不在自身包内；`request_inputs.load_request` 采用新修订非空目录拒绝策略；`frame_diy_runtime.prepare_paths` 区分 raw/derived 输入。调用方须声明自己实际使用的 API、受保护对象与失败留存范围，不把一个入口的配置位置规则推广到其他入口。
