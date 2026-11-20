# 业务阶段统计契约

统计 skill 被调用时的业务执行；不要求为维护 skill 的过程另作业务计时。沿用任务范围，未取得 token usage 不影响完成。

## 自动覆盖

`parts_pipeline.run_job` 用 `timing.StageRecorder` 记录以下阶段。时间均带 UTC 时区，进程内使用 `time.monotonic()` 计算 `elapsed_seconds`。

| 阶段 | 覆盖内容 |
| --- | --- |
| `preflight` | 读取/校验 job、模块语法、标识和输出约束 |
| `runtime` | 导入 bpy，检查 window 与 Object Mode；不包含此前 Blender 进程冷启动 |
| `build` | 新建任务场景、共享 Context、逐模块创建部件 |
| `structure` | 部件/对象归属校验、创建独立根对象 |
| `layout` | 求值包围盒、移动根、记录部件清单 |
| `save` | 保存任务场景并检查签名 |
| `export_parts / export_row` | 所需导出与对应文件签名检查；preview 或未请求时 skipped |
| `restore_context` | 恢复原场景与视图层；未改变上下文时 skipped |

图像理解、规格编写、模块源码编写、人工/AI 视觉核对、渲染和 Blender 进程启动不在上述自动阶段内；发生时由执行者记录真实区间与范围。自动统计不是完整业务时间，不冒充模型服务耗时或 token 测量。

## 标识、文件和字段

`task_id` 默认由 job 的绝对路径稳定生成，也可用 `--task-id` 显式传入；每次 `run_job` 创建新的 `attempt_id` 和产物子目录。重跑沿用 task_id，并用 `--previous-attempt-id` 关联上次尝试；换路径时显式保留 task_id。此机制只保留关联，不复用几何、自动接续缓存或覆盖旧文件。

| 文件/字段 | 含义 |
| --- | --- |
| `timings.jsonl` | 追加阶段事件：开始为 running，结束为 completed/failed/interrupted；不执行为 skipped |
| `timing_summary.json` | 当前自动尝试的最终阶段列表与总墙钟；阶段耗时已包含在总区间中，不再次求和 |
| `report.json` | 路径、执行结果、质量检查、耗时摘要及其覆盖范围 |
| `task_id / attempt_id / previous_attempt_id / stage` | 任务、尝试、上次尝试和阶段身份 |
| `started_at / ended_at / elapsed_seconds` | 实际带时区起止及单调耗时秒数；不能得知的字段保留 null |
| `timing_method / timing_scope` | 计时方法与包含范围；嵌套阶段包含在父阶段中 |
| `reason / missing_reason / error_type` | 跳过原因、缺时原因或异常类型；不把缺失值补成 0 |

日志分析按任务、尝试、阶段及起始时间匹配 running/最终事件，不将两条事件重复计时。`skipped` 没有执行起止和耗时；其 null 表示未执行。失败或可捕获中断保留已测时间。硬终止可能仅留下 running 事件、旧摘要或未完成报告，此时不能宣称完成或猜测结束；如后来补充 interrupted 记录，沿用原标识/已知起点、缺失字段为 null，并注明原因。

同一产物目录使用单一写入者。JSON 报告通过同目录临时文件原子替换；JSONL 也以保留已有内容的原子替换追加事件，未实现并发合并。不要让多个代理同时写一个 journal。

## 可单独调用的原子能力

从本工作流的 `scripts/timing.py` 显式加载；不依赖 Blender。

| 入口 | 契约 |
| --- | --- |
| `StageRecorder(run_dir, task_id, attempt_id, previous_attempt_id=None, started_at=None, started_clock=None)` | 创建一次尝试；若要覆盖提前进行的预检，两个 start 参数须由同一进程实际测得且同时提供 |
| `recorder.stage(name)` | 上下文管理器；阶段开始即落盘 running，退出记录最终状态，异常/中断原样抛出 |
| `recorder.add_record(record)` | 接入已测得的阶段并纳入本次摘要；补身份并拒绝不匹配标识 |
| `recorder.skip(name, reason)` | 写未执行状态，时间为 null |
| `recorder.finish(status)` | 写本次墙钟和最终阶段摘要；不累加重叠时间，同状态重复调用返回同一摘要 |
| `record_external_stage(run_dir, record)` | 校验并追加执行者的外部阶段记录；不自动改已有摘要，不推算缺失时间 |
| `write_json(path, value)` | 用同一文件适配器原子保存 JSON；只写任务文件 |

外部阶段要提供 `task_id`、`attempt_id`、`stage`、最终 `status`、实际 `started_at/ended_at/elapsed_seconds` 和 `timing_method`。进程内实际采集采用 monotonic；跨进程按可靠的实际墙钟区间计算时明确标记 wall_clock，不能混用不同单调时钟基准。缺时间时传 null 与 `missing_reason`。skipped 则只提供原因和 null 时间。

对外部阶段应在本次执行时记时，随后随业务产物保存记录与摘要。追加到 `timings.jsonl` 不会自动扩大先前自动 summary 的范围；交付者另列这些阶段和覆盖区间。完整业务总墙钟使用已知的业务起止区间，不能把图像分析、Blender 调用及其内部阶段机械相加。

Token 字段可省略；仅在宿主/API 返回真实 usage 时记录来源、范围及输入/输出/总量，缓存和推理明细注明包含关系。同一调用不重复计数，仅有任务总量时不分摊，不以额度、字符数或耗时估算，不为补统计读取凭据或重新运行任务。
