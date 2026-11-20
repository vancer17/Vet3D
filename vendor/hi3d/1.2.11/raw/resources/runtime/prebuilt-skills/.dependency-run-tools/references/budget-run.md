# 本地长任务预算与心跳

本页是本地无界计算的唯一运行契约。规则条款见 [AGENTS](../../.dependency-doc/repository-AGENTS.md#本地长任务预算与中断)；宿主弹窗见 [宿主编排](../../.dependency-pcg-view/references/host-orchestration.md)。`process_run.run_budgeted` 是唯一实现。

适用于可能长时间占用 CPU、且期间可以没有任何业务产物的本地子进程（几何核、重网格、离线渲染等）。不适用于 Hi3D/MDF 远端 query/wait：那些继续走各自恢复语义，不能对远端 worker 套用本地 kill。

## 不变量

1. **先落盘再进内核。** 进入可能卡住的子进程前，任务目录必须已有预算文件和心跳文件。禁止空目录长时间占进程。
2. **墙钟预算。** `max_wall_seconds` 为正数。到点后对直接子进程 terminate，再按既有 `terminate_timeout` kill/wait。不自动加时、不重试、不启第二个子进程。
3. **心跳。** `write_heartbeat` 覆盖写入 `schema=run-tools.budget.v1` 的 JSON：`status` 为 `running` / `completed` / `failed` / `timeout`，以及 `elapsed_s`、`budget_s`、`heartbeat_s`、`last_heartbeat`、`phase`、`phase_unchanged_cycles`。未显式传入 cycles 时，由上一份心跳在相同 `running`+`phase` 上递增。宿主按任务目录重投影，不靠聊天记进度。
4. **超时是中断。** 抛出 `BudgetTimeout`；阶段记录为 `interrupted`。不得把超时写成业务失败后的自动换参重跑。
5. **加时只发生在用户 option 之后。** 调用方开新输出目录、带新的 `max_wall_seconds` 再跑。实现不得在同一次 `run_budgeted` 内延长 deadline。
6. **弹窗不在本模块。** 宿主把 `pcg.session.v1` 设为 `waiting_choice`，使用当前入口 `choices_example`（2–4 项）。心跳侧只分类 `timeout` / `stall` / `exhausting`；其它决策时刻由 [宿主编排注入](../../.dependency-pcg-view/references/host-orchestration.md) 统一列出。同检查点+reason 记入 `session.popup_reasons`。长 CPU 不是新的不可逆枚举。

## 接口

| 接口 | 行为 |
| --- | --- |
| `write_heartbeat(path, **fields)` | 原子替换心跳 JSON；调用方创建父目录。省略 `phase_unchanged_cycles` 时按上一心跳递增。 |
| `load_heartbeat(path)` | 读取心跳对象；缺文件或坏 JSON 返回 None。 |
| `popup_reason(record, *, asked=())` | 只读分类：`timeout`（status=timeout）；`exhausting`（running 且 elapsed≥0.8×budget 且 phase 为 start/wait）；`stall`（running 且 cycles≥2 且 elapsed≥0.4×budget）。`asked` 抑制重复。不杀进程、不加时。其它 reason 不在此函数。 |
| `run_budgeted(command, log, *, max_wall_seconds, heartbeat_path=None, heartbeat_seconds=5, env=None, terminate_timeout=10, error_prefix=..., clock=monotonic, kill_tree=False)` | 合并日志；周期 `wait(timeout)` 并写心跳；超时 `BudgetTimeout`；子进程非零仍为 `RuntimeError`。 |
| `BudgetTimeout` | `elapsed_s`、`budget_s`；不授权重试。 |

`run_process` / `run_checked` 保持原语义，不隐含预算。未声明预算的入口不得假装已受本契约保护。默认只回收直接子进程；POSIX 调用方可显式 `kill_tree=True`，子进程建立新 session，超时/中断向进程组发送 terminate/kill。脱离该组的守护进程仍不在保证范围；非 POSIX 请求此选项会报错。

## 调用方职责

- 估算档位与默认秒数由业务入口声明，本模块不猜几何复杂度。
- 低档可直接跑；中高档先 `waiting_choice`，用户确认后再带预算启动。
- 超时后只保留心跳/日志/等待说明，不写半截业务交付物（STEP、BLEND、收费任务等）。
- 覆盖已有交付物仍用已有不可逆标志（`overwrite.source` 等）和 `confirm_required`。
- 心跳分类阈值（0.4 / 0.8 / 连续 2 拍）是本模块常量，不是对话余额百分比；宿主不得把它们改写成 n%。
