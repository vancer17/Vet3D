# 阶段记录契约

每个工作流从业务任务实际开始记录阶段、任务/尝试标识、状态、带时区起止和耗时，记录随产物交付摘要与路径，写包外任务目录。编写、迁移、安装或维护能力仓库不要求统计业务耗时。入口明确哪些由执行者记录、哪些由脚本自动采集；局部脚本不能代表全流程覆盖。

## 事件身份、字段与恢复

执行阶段开始前先持久化 running，结束追加 completed/failed/interrupted 终态；同一组任务/阶段/尝试标识对应一次执行，不能把起止两行算成两次。已有输入可跳过不需重做的阶段，标 skipped 与原因；生成与等待可拆子阶段，不为填齐阶段列表重跑服务。

以下是必须表达的语义，不是所有 profile 通用的可直接提交 JSON schema。保留既有字段格式与文件名，不回写改造历史记录：

| 信息 | 常见字段与口径 |
| --- | --- |
| 任务、阶段、尝试 | task_id、stage_id/stage、attempt/attempt_id；恢复或已获授权重试用新尝试并关联 previous_attempt/previous_attempt_id |
| 父子关系 | parent_stage_id/parent_stage、includes_children 或明确的 timing_scope；注明是否包含子阶段/下游调用 |
| 状态 | running/completed/failed/interrupted/skipped；跳过说明未执行原因，计时状态与业务证据通过状态分别记录 |
| 真实起止 | started_at/ended_at，ISO 8601 带时区；缺失为 null，附 missing_time_reason/missing_reason 与未覆盖区间 |
| 耗时与时钟 | elapsed_seconds 或既有 seconds；clock_source/timing_method 指明进程内 monotonic、跨进程 wall_clock 或 unavailable/not_executed |
| 原因与关联 | reason、相关 job 路径/标识；只写非敏感原因，不保存请求正文、鉴权或凭据 |

异常、主动中断及获授权重试均追加保留。崩溃只剩 running 时，恢复者检查日志与原 job，再追加 interrupted 和“终态/耗时未知”的原因；缺失耗时保持 null，不虚构结束时间或填 0。既有 profile 的 unknown 表示未知事实，不能直接当作所有记录 API 的合法 status。正常 skipped 可无起止/耗时，但必须说明未执行原因；实际检查缓存花费的时间与未执行原阶段分开说明。

最小进程内方式是在开始和结束各取 `datetime.now(timezone.utc)` 与 `time.monotonic()`，以单调时钟差值为耗时。跨进程只能使用实际带时区区间，注明 wall_clock 和校时风险。文件追加由任务编排者负责，不要求额外固定框架；恢复只续接所需工作，计时记录不授权重提远端任务。

可直接使用 `scripts/timing.py` 的 StageRecorder/record_external_stage，或现有 profiles。StageRecorder 使用 task_id/attempt_id/stage、previous_attempt_id、timing_method 和 missing_reason，stage 上下文自动写 running/终态；record_external_stage 只接收实测终态，不推算时间。两者不自动找回崩溃任务，也不把记录当作缓存；调用方完成恢复和覆盖说明。按各函数契约适配上述语义，不能把说明里的别名原样混传。

## 墙钟、服务时间与可选 token

- 总墙钟取业务任务起止的实际区间，等待用户/服务也在区间内；不能累加重叠阶段，独占耗时与含子阶段耗时不能混加。
- 本地提交、轮询、下载和服务实际计算分别记录；没有服务计时字段时写未知，不能把本地等待当作服务计算。
- token 可省略或标 unavailable，不影响完成。只记录宿主/API 实际 usage 的输入/输出/总量、来源和范围；缓存/推理明细注明是否已在总数中。
- 累计计数仅在同范围且未重置时取差值；同一调用只记一次，任务总量不擅自分摊到阶段。不从余额、字符数或时间推算，也不读取密钥或重跑服务补统计。
- 最终网页、说明或制作包附阶段摘要、总体墙钟、未覆盖区间和日志位置；缺 token 仍正常交付，不将计时完整等同于业务验收通过。

## 基础交付后追加工作

已交付基础成果后新增视频等明确请求，用关联原任务的新尝试记录，只计本次新增工作；保留原基础交付的实际起止。未请求阶段记 skipped 和品类约定的原因，不启动该阶段计时或伪造 0 秒。请求与制作范围由调用方维护，计时工具不替用户选择分支。
