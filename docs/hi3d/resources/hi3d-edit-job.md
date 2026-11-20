# `hi3d-edit-job.py`

## 资源身份与模型可见方式

Hi3D Agent 1.2.11（Windows x64）内置 `run-tools` 的本地编辑任务模块。模块提供 `EditJob` 和探测 CLI，个别上游编辑包将它按原部署名随包物化。模型可以按所选 Skill 或上游使用说明查阅它，宿主允许时可通过本地执行工具启动探测或运行导入它的消费脚本。安装包证据没有该脚本的独立 LLM Tool 注册或模型可见 `description`。 [归档原件](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/hi3d-edit-job.py) · [安装包中的上游编辑任务契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/hi3d-edit-job.md>) · [执行工具](../tools/exec-command.md)

**源码 CLI `argparse` 描述原文**

```text
Probe one explicitly selected local editing executable; never install it.
```

## 参数、结果与副作用

| 接口 | 参数与返回 | 行为与错误 |
| --- | --- | --- |
| `probe(executable, args=("--version",), timeout=10)` | 可执行程序为必填参数，`args` 默认请求版本，超时默认 10 秒。子进程启动并结束后返回 `available`、`executable`、`version`、`returncode`。 | 通过 `shutil.which` 解析程序，允许显式绝对路径或从进程搜索路径定位调用者指定的名称。`available` 取决于子进程退出码。`version` 取 stdout，否则取 stderr，最多 1,500 字符。找不到与超时分别返回 `available: false` 和 `reason: executable_not_found` 或 `probe_timeout`。其他启动或输出解码错误可以向上传播。 |
| CLI `--probe`、`--version-arg` | `--probe` 必填，`--version-arg` 可选，默认 `--version`，进程输出一个 JSON 对象。 | 只提供探测入口。应检查 `available` 和回包字段，CLI 取得探测失败对象后仍可正常退出。 |
| `EditJob(output, spec, inputs, package_root, budget=120)` | 接收输出目录、可 JSON 序列化的规格、可重复迭代的输入文件路径集合、调用包根。`budget` 默认为 120 秒，须为有限正数。 | 校验写入根，从 `spec`、输入文件摘要和包内指定后缀的代码文件摘要计算任务指纹。新尝试创建目录并初始化任务记录。已有目录仅在报告为 `completed`、指纹匹配且报告中逐项产物摘要匹配时复用。解析、文件读取或摘要不匹配错误向调用者传播。 |
| `job.run(argv, phase)` | `argv` 为调用者提供的程序与参数序列，`phase` 去掉连字符后须满足 `isalnum`。正常返回 `None`。 | 对已复用任务或不合规阶段抛 `ValueError`。以所给预算执行一次子进程，合并日志和心跳。退出非零时传播 `RuntimeError`，超时传播 `BudgetTimeout`，异常更新任务记录。 |
| `job.finish(files, checks)` | 接收至少一个非空产物文件及可 JSON 序列化的 `checks`。返回写入后的 `completed` 报告。 | 复查输入摘要，各产物解析后须位于输出根内且存在。摘要变化、文件不合格或空产物列表抛 `ValueError`。报告含 `schemaVersion`、`status`、`fingerprint`、`artifacts` 和 `checks`，每项产物含相对 `path`、`sha256`、`bytes`。 |

同模块的 `number` 校验有限数字和最小值，`local_file` 解析现有本地文件且拒绝带 `://` 的输入，`digest` 分块哈希，`dump` 以同目录临时文件替换目标 JSON。运行新尝试会创建输出目录，写入 `hi3d-budget.json`、`hi3d-result.json`、`hi3d-progress.json` 和每阶段 `hi3d-<phase>.log`。复用分支的构造是只读的。调用方应直接取 `job.result`，因为构造器只设置 `reused`，`run` 拒绝复用任务，而 `finish` 和 `state` 仍可写入。上下文管理器也会在异常退出时调用 `state`。

**根据源码重建的控制流伪代码**

```text
预检输出根、输入文件、预算并计算任务指纹
如果输出目录已存在
    核对完成报告、任务指纹和该报告中逐项产物摘要
    返回已有报告，或传播错误并由调用方决定新尝试
否则
    初始化任务记录和心跳
    按阶段启动一次带预算的子进程
    超时或取消写 interrupted，其他执行异常写 failed，再传播异常
    由调用方验收内容，重新核对输入摘要和结果文件
    写 completed 报告并返回
```

调用者可以通过稳定的输出目录匹配同一任务。已有未完成或已变化的目录保留原报告和日志，脚本要求改用新输出目录。内置预算和进程清理只覆盖本地子进程，调用方负责幂等和是否重新执行的决策。

## 依赖、权限、沙箱与 Hook

该文件直接导入同目录的 `process_run.py` 和 `path_safety.py`，其余为 Python 标准库。运行阶段需要读取输入和包源码、向任务目录写入，以及启动显式指定程序的权限。它以参数数组启动程序，经 `run_budgeted` 写日志与心跳。POSIX 使用进程组回收，Windows 路径清理直接子进程。上下文管理器安装临时 `SIGTERM` 处理器，需在 Python 主线程使用。脚本无独立 Hook，宿主调用沿用本地执行入口当轮有效的沙箱与前置 Hook。被启动程序的行为及默认继承的进程环境仍受宿主及调用方控制。 [本地进程资源](process-run.md) · [路径校验资源](path-safety.md) · [执行工具](../tools/exec-command.md)

## 中性调用示例

**调用示例。** 从仓库根目录探测一份已安装且受信任的本地程序。将程序路径替换为当前环境的实际值。此命令会真实启动该程序取版本，`EditJob` 的任务目录和编辑阶段不会被触发。

```powershell
$entry = 'docs/hi3d/upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/hi3d-edit-job.py'
python -B $entry --probe 'C:/Tools/example-editor/editor.exe' --version-arg=--version
```

## 核查依据

已对照 1.2.11 发行索引复核安装原件的大小和 SHA-256，并核对入口参数、写入文件、报告字段和两个直接导入。Windows 临时目录中以 Python 子进程生成文本产物，实测 `finish` 发布完成报告、相同输入复用该报告、修改产物后拒绝复用。示例中的编辑器路径为占位。实际编辑器探测、取消、并发及模型质量验收按所选入口复测。 [P0 清单](../upstream/1.2.11/extraction/priority.json) · [发行索引](../upstream/1.2.11/inventory/inventory.jsonl)
