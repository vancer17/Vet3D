# 业务阶段统计

统计 skill 实际业务运行，不要求为编写/维护 skill 自身记录业务耗时。每次业务任务在外部任务目录保存任务标识、尝试标识、阶段、状态、带时区起止时间、耗时秒数及计时来源。token 可省略，不能因无 token 数据而省略耗时。

## 脚本自动覆盖

`pipeline.run()` 使用 `Recorder` 自动记录 `preflight`、`scene`、`shell_and_accessories`、`powder_reliefs`、`hinge`、`checks`、`save`、`render`。阶段事件追加到 `timings.jsonl`，任务本地尝试摘要保存为 `timing_summary.json` 并收入 `report.json`。进程内 UTC 起止与单调时钟秒数同时记录；本地总墙钟按本次起止区间计算，不相加各阶段。

阶段开始先写 running 事件；正常结束写 completed，异常写 failed 或 interrupted，附异常类型而非可能含秘密的远程响应。未执行阶段为 skipped，起止和耗时 null 并给出原因。强制杀进程时可能只留下 running 事件，结束时间未知且有 missing_reason；恢复报告明确此缺口，不能填 0 或猜测结束时间。统计写入异常可能使报告不完整，也应如实说明。

每次尝试使用新目录和 attempt_id；重试传 `--previous-attempt-id` 关联旧尝试，并保持业务 task_id。已存在的源文件和服务 job ID 可以复用，不能为补时间重新生成。若配置在预检前无法解析 task_id，事件以配置文件名作为临时标识。记录是单写入者设计，不让多个进程并发写同一 JSONL。

## 执行者负责的阶段

产品研究、母版图像、每格变体、Hi3D 提交/等待/下载、参考专属 builder 编写、视觉验收、可选视频编码和最终交付不在 runner 内。执行者在实际开始/结束时记录这些阶段到外部 `business-timings.jsonl` 或任务报告，不能声称脚本已自动采集。可在自己的编排 Python 中复用 `Recorder.stage()` 计量显式调用；交互式工具用宿主实际时间，标注 `timing_method=wall_clock`。缺少历史时间时填 null、原因和覆盖范围，不倒推出貌似精确的数据。

手动阶段至少采用以下语义字段（值从实际运行填写）：`task_id`、`attempt_id`、`previous_attempt_id`（可空）、`stage`、`status`、`started_at`、`ended_at`、`elapsed_seconds`、`timing_method`。异常/跳过/时间缺失增加原因。原始任务 ID 可放任务记录，鉴权 token、请求签名、下载签名 URL 或秘密不可写入。

完整业务墙钟取最早实际业务开始至最终交付结束的区间；并行变体的时间不能直接累加。父阶段注明包含子阶段，本地建模总量已经包含其脚本阶段，避免重复累计。服务返回的计算时间与本地 API 调用/等待时间分开列。输入已完成时标复用/跳过并链接原尝试，不捏造其耗时。

宿主/API 真正提供 usage 时可记录输入、输出、总 token 与来源/范围；缓存、推理明细标注是否已含总数。仅有全任务 usage 时不擅自分摊阶段；累计计数仅同范围且未重置时取差值。同一调用只计一次，不用余额、字符数、耗时推算 token，也不为统计读取凭据或重跑收费任务。
