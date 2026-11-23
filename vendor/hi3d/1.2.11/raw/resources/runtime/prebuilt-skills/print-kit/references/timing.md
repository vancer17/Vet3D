# 业务阶段耗时

在业务任务输出目录保存 `timing.jsonl` 和阶段摘要。按实际工作选择阶段：输入与尺寸、分件及接口方案、实体建模、导出和数字验证、试片制作、切片、视觉复查、交付；迭代回到对应阶段。记录全任务起止，阶段/任务标识、尝试号、状态、带时区起止时间和耗时秒数。未运行的切片、实体试配等明确记为跳过并说明原因。

执行者负责覆盖整个业务过程。随包 `scripts/timing.py` 只记录显式包裹的 Python 阶段；它不会自动计入对话、外部建模软件、人工审查、宿主工具或打印等待。执行者为这些阶段记录同口径事件，并在摘要说明自动/手动覆盖范围。

```python
from timing import stage, skipped

# 以下路径与 ID 由当前任务提供，日志放在任务输出目录。
with stage(log_path, task_id, 'digital-build', attempt=1) as run:
    with stage(log_path, task_id, 'geometry', parent_id=run):
        kit = build_model(parameters)
    with stage(log_path, task_id, 'export', parent_id=run):
        plan_path = kit.export(output_directory)
skipped(log_path, task_id, 'physical-fit', '尚无实体试配反馈')
```

`stage()` 使用单调时钟测进程内耗时、UTC 墙钟记起止，先追加 start，再追加 end；异常/中断记录后继续抛出。业务验证返回 `status=fail` 时执行者须标记该阶段失败或抛出相应异常，不能把进程正常返回当作业务成功。重试保留同一任务/阶段 ID，递增 attempt，追加新 run ID，不覆盖失败记录。SIGKILL 等导致仅有 start 时保留不完整记录，耗时记为缺失并说明原因和覆盖范围，不能补成 0。

`append_record()` 也可保存手动计时事件；字段与 `stage()` 一致，`clock` 写真实来源（例如 `wall-clock`）。先采集实际时间，不事后猜测。并发写入使用每个工作进程独立日志，再按 run ID 汇总。只记录必要标识与统计，不记录密钥、鉴权 token、服务请求正文或异常敏感内容。

`summarize(records, task_id)` 是纯计算：按 run ID 保留最后事件，只用显式 `scope=task` 的完整墙钟区间计算总跨度。执行者在真正业务开始/结束时提供该区间；仅包裹建模脚本时用 `scope=stage`，不能冒充整个任务。总墙钟含重试间隔及等待，不累加重叠阶段。父子阶段通过 parent_id 指向父 run ID，子耗时已含在父区间；远端服务计算耗时另列，与本地调用/等待区分。

宿主/API 若提供真实 usage，可选记录输入、输出、总 token、来源和覆盖范围，缓存/推理细项注明包含关系；未采集可省略。只有任务总量时不分摊到阶段；累计计数只在范围一致且未重置时取差值，同一调用只计一次。不用余额、额度、文字长度或耗时估算，不为补数读取凭据或重跑任务。token 缺失不影响耗时统计或交付。
