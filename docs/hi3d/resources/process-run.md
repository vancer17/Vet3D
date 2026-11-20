# process_run.py

## 资源身份与模型可见性

`process_run.py` 是 Hi3D Agent 1.2.11 Windows x64 随包 `run-tools` 的本地 Python 模块。调用方从已物化包的 `scripts/` 导入。模型可沿 `run-tools` 的隐藏参考入口读到用途和调用约定，模块没有独立 LLM Tool 注册、模型可见工具 `description` 或 CLI。此版本的 `hi3d-edit-job.py` 导入预算运行、心跳写入和超时异常。 [归档源码](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/process_run.py) · [随包参考入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/REFERENCE.md>) · [调用方源码](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/hi3d-edit-job.py)

## 参数、结果与副作用

| 接口 | 参数和结果 |
| --- | --- |
| `run_process(command, log, *, env=None, terminate_timeout=10, error_prefix="Stage exited")` | 运行一次显式子进程，合并 stdout 和 stderr 写到指定日志。日志以写模式打开，父目录由调用方创建。成功返回 `None`，非零退出抛 `RuntimeError`，附退出码与日志路径。 |
| `run_checked(command, *, env=None, terminate_timeout=10)` | 继承标准流，成功返回 `None`，非零退出抛 `subprocess.CalledProcessError`。 |
| `run_budgeted(command, log, *, env=None, max_wall_seconds, heartbeat_path=None, heartbeat_seconds=5, terminate_timeout=10, error_prefix="Stage exited", clock=time.monotonic, kill_tree=False)` | 从单调时钟起点计算墙钟截止时间。两项预算与心跳间隔要求为大于零的非布尔数值。按剩余预算和心跳间隔中较短的时长等待。成功返回 `None`，非零退出抛 `RuntimeError`。预算到期时停止子进程，并抛带 `elapsed_s`、`budget_s` 的 `BudgetTimeout`。 |
| `child_environment(*, inherit=(), overrides=None)` | 只复制当前环境中点名且存在的键，再应用显式覆盖，返回新字典。传给 `run_*` 的 `env=None` 会继承父进程环境。 |
| `load_heartbeat(path)`、`write_heartbeat(path, **fields)` | 读取 JSON 对象，缺文件、读盘异常、JSON 语法错误或非对象返回 `None`。写入使用 `run-tools.budget.v1` 结构和同目录的 `<文件名>.tmp`，替换后返回字典。省略 `phase_unchanged_cycles` 且提供状态与阶段时，会根据前一份记录计算。 |
| `popup_reason(record, *, asked=())` | 校验心跳 schema 后返回原因或 `None`。终态 `timeout` 优先。运行时，`start` 或 `wait` 已消耗至少 80% 预算为 `exhausting`，否则同阶段连续至少两次且消耗至少 40% 为 `stall`。在 `asked` 中的原因被抑制。 |

开启心跳时写入 `status`、`phase`、`elapsed_s`、`budget_s`、`heartbeat_s`、`last_heartbeat` 和阶段循环数。启动及超时等待时写 `running/start` 或 `running/wait`，正常退出和非零退出分别写 `completed/exit`、`failed/exit`，预算到期清理后写 `timeout/killed`。调用同步等待，没有查询句柄或自动重试。弹窗呈现、用户决定与新预算由调用方负责。 [本地运行契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/local-runtime.md>) · [预算与心跳契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/budget-run.md>)

## 依赖、权限与异常清理

仅依赖 Python 标准库及调用方指定的程序。子进程启动参数直接交给 `subprocess.Popen`，继承当前工作目录。进入受保护等待后，异常会尝试 `terminate`，等待默认 10 秒，再 `kill` 并等待退出。普通模式清理直接子进程。预算接口仅在 POSIX 接受 `kill_tree=True`，此时创建新进程组并按组发信号。日志或心跳写入错误会传播。

`run_budgeted` 启动进程后先写 `running/start`，随后才进入带清理的 `try` 块。Windows 隔离夹具使用存在的日志目录、父目录缺失的心跳路径和持续运行的真实 Python 子进程。首次写入抛出 `FileNotFoundError` 后，子进程仍在运行，由夹具显式终止。调用方使用此入口前需准备心跳父目录，进程回收范围还取决于宿主实际调用方式。 [归档源码的启动与清理顺序](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/process_run.py#L195-L220)

模块按装载进程的权限读写、启动和终止进程。若由 Codex shell 启动，前置 Hook、沙箱及审批在 shell 工具边界处理。模块内部的 `Popen` 没有单独的 LLM 调用或 Hook，文件写入和程序选择由上层约束。 [执行工具的权限与前置 Hook](../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例

**根据归档源码编写的示例。** 调用方已把模块所在 `scripts/` 加入导入路径。`run_dir` 是调用方指定的包外任务目录。

```python
from pathlib import Path
import sys

from process_run import run_budgeted

run_dir = Path("run")
run_dir.mkdir(exist_ok=True)
run_budgeted(
    [sys.executable, "-c", "print('local check')"],
    run_dir / "check.log",
    max_wall_seconds=15,
    heartbeat_path=run_dir / "heartbeat.json",
)
```

## 核查依据与待验证项

源码映射为 `tools/run-tools/scripts/process_run.py`。已核对归档摘要并在隔离目录运行示例，取得合并日志和 `completed` 心跳。Windows 隔离检查覆盖直接子进程的预算超时清理与 `BudgetTimeout`、`run_checked` 的退出码传播，以及上述首条心跳写入失败后子进程继续运行的情况。真实 Hi3D 宿主是否提供额外回收、Windows 孙进程回收、POSIX 进程组取消及心跳分类如何进入界面仍待验证。 [发行盘点](../upstream/1.2.11/inventory/inventory.lock.json) · [资源选择与摘要](../upstream/1.2.11/extraction/priority.json)
