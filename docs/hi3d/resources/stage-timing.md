# timing.py

## 资源身份与模型可见性

`timing.py` 是 Hi3D Agent 1.2.11 Windows x64 随包 `run-tools` 的单写入者阶段计时模块。调用方从已物化的 `scripts/` 导入，向模块提供任务、尝试和阶段身份。模型可阅读隐藏的 `run-tools` 参考入口和阶段契约。模块没有独立 LLM Tool 注册、模型可见工具 `description` 或 CLI。 [归档源码](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/timing.py) · [随包参考入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/REFERENCE.md>) · [阶段记录契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/stage-records.md>)

## 参数与结果

| 接口 | 参数和结果 |
| --- | --- |
| `StageRecorder(run_dir, task_id, attempt_id, previous_attempt_id=None, started_at=None, started_clock=None)` | 任务与尝试标识为非空字符串。可关联前次尝试。起点参数须成对传入，分别为带时区时间和同进程测得、未超过当前单调时钟的数值。默认在构造时取两个时钟，并创建 `run_dir`。 |
| `stage(name)` | 先持久化 `running`，再将可补充元数据的记录交给上下文主体。记录以单调时钟计算耗时。正常退出追加 `completed`，异常追加 `failed` 或 `interrupted`，后者用于 `KeyboardInterrupt`、`SystemExit`、`GeneratorExit`。主体异常继续抛出，终态写入失败时尽可能给原异常添加注记。 |
| `add_record(record)`、`skip(name, reason)` | 将实测或跳过的终态纳入本次尝试及摘要。调用方提供的身份若与当前尝试冲突则抛 `ValueError`。跳过需非空原因，起止和耗时为 `null`。 |
| `record_external_stage(run_dir, record)` | 校验并写入已有终态，仅接受 `completed`、`failed`、`interrupted`、`skipped`。要求 `task_id`、`attempt_id`、`stage`，时间如提供则转为 UTC，保证先起后止。非跳过记录缺任一起止时间或耗时时提供 `missing_reason`，耗时有值时须为有限非负数且提供 `timing_method`。返回规范化记录，独立调用不生成摘要。 |
| `finish(status)` | 以给定的非空状态写 `timing_summary.json` 并返回摘要。耗时取整次尝试的单调时间区间。仍有活动阶段时抛 `RuntimeError`。同一对象完成后相同状态复用摘要，改写状态或增加阶段均报错。 |
| `write_json(path, value)` | 按当前进程权限将可 JSON 序列化的值写入显式路径，非有限 JSON 数值会被拒绝。 |

每个事件在 `timings.jsonl` 追加一行，并增加写入时的 UTC `recorded_at`。实现读取已有文本，遇不完整的末行拒绝追加，然后用同目录唯一临时文件写入完整内容，经 `flush`、`fsync` 后替换。摘要使用相同的替换方式。两个文件可分别成功，运行所需目录及旧文件能否保留由调用方的写入环境决定。恢复时旧事件仍在，调用方检查中断流水和实际产物，补记有证据支持的终态并保留未知耗时。新尝试可用 `previous_attempt_id` 关联。

## 依赖与权限

依赖 Python 标准库。在指定目录执行读写，调用方提供单写入者顺序和包外任务路径。文件替换没有并发协调，调用方还须确定何时持久化摘要及是否可针对同目录创建下一次尝试。模块没有独立沙箱或前置 Hook。经 shell 调用时，外层命令沿用对应的权限策略。 [执行工具的权限与前置 Hook](../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例

**根据归档源码编写的示例。** 模块目录已加入导入路径。目录中会有阶段历史与本次尝试的摘要。

```python
from timing import StageRecorder

journal = StageRecorder("run", task_id="sample", attempt_id="attempt-1")
with journal.stage("inspect") as record:
    record["items_checked"] = len(["sample-a", "sample-b"])
journal.skip("encode", "本次未请求编码")
journal.finish("completed")
```

## 核查依据与待验证项

源码映射为 `tools/run-tools/scripts/timing.py`。已核对归档摘要，运行示例得到两个阶段的日志和含 `completed`、`skipped` 记录的摘要。真实消费者如何恢复只有起始事件的尝试、记录是否跨进程传递、文件替换中断与恢复依部署环境验证。 [资源选择与摘要](../upstream/1.2.11/extraction/priority.json)
