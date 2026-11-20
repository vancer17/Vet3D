# stage_events.py

## 资源身份与模型可见性

`stage_events.py` 是 Hi3D Agent 1.2.11 Windows x64 随包 `run-tools` 的 Python 生命周期记录 helper。它从已物化 `scripts/` 导入，用于保持采用 `elapsed_seconds` 的既有记录格式。上游契约可经 `run-tools` 参考入口读取。模块没有独立 LLM Tool 注册、模型可见工具 `description` 或 CLI。 [归档源码](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/stage_events.py) · [随包参考入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/REFERENCE.md>) · [本地运行契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/local-runtime.md>)

## 参数、事件与终态

| 接口 | 参数和结果 |
| --- | --- |
| `record_stage(name, emit, records, *, missing_reason="End not observed", timing_method="monotonic", now=None, clock=None, wall_first=False)` | `name` 为阶段名，`emit` 接收事件，`records` 的 `append` 接收终态。默认先取单调时钟再取 UTC，`wall_first=True` 调换开始采样顺序。可注入两个时钟。`timing_method=None` 省略该字段。上下文主体没有绑定值。 |
| `utc_now()` | 返回当前 UTC 时间的带时区 ISO 字符串。 |
| `append_event(path, event)` | 把一个事件追加为 UTF-8 JSONL 一行，禁止非有限数值。调用方创建父目录。序列化或读写错误直接传播。 |

进入上下文时，调用 `emit` 发送 `stage`、`started_at`、`status="running"`、`missing_reason`，此时 `ended_at`、`elapsed_seconds` 为空。结束时复用同一个字典并增补 UTC 结束时间和单调耗时，删除 `missing_reason`，再调用 `emit` 和 `records.append`。需要在内存保留起始事件时，`emit` 应复制该字典。身份、输出位置及持久化均由调用方在 `emit` 处理。

正常退出标记 `completed`。`KeyboardInterrupt` 和 `SystemExit` 标记 `interrupted`，其他异常标记 `failed`，异常终态附 `error_type` 并继续抛出。起始投递失败会阻止进入上下文，终态投递失败会阻止 `records.append`，也可能覆盖主体异常。强制终止来不及运行 `finally` 时，已有记录可能只保留 `running`，后续由调用方根据现有证据追加说明。 [阶段记录契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/stage-records.md>)

## 依赖与权限

依赖 Python 标准库。模块没有权限判断或前置 Hook。写入发生在调用方回调中，或在显式调用 `append_event` 时按当前进程的文件权限发生。使用 shell 入口时，Hook 和沙箱在外层执行工具处理。 [执行工具的权限与前置 Hook](../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例

**根据归档源码编写的示例。** 导入路径已包含该模块目录。回调负责附加任务身份。

```python
from pathlib import Path

from stage_events import append_event, record_stage

run_dir = Path("run")
run_dir.mkdir(exist_ok=True)
terminal = []

with record_stage(
    "inspect",
    lambda event: append_event(
        run_dir / "events.jsonl", {"task_id": "sample", "attempt_id": "1", **event}
    ),
    terminal,
):
    item_count = len(list(run_dir.iterdir()))
```

## 核查依据与待验证项

源码映射为 `tools/run-tools/scripts/stage_events.py`。已核对归档摘要，并用示例取得顺序正确的 `running` 和 `completed` 两行事件。异常分类和投递失败边界依据源码。真实调用方的事件投递、取消和预算超时映射仍取决于其回调与上层处理。 [资源选择与摘要](../upstream/1.2.11/extraction/priority.json)
