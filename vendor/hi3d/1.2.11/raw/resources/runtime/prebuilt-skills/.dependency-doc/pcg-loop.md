# Agent 循环衔接（pcg）

宿主拥有 QueryEngine、流式 API、工具执行、截断、token compact 与会话保存。本仓库**不实现** Agent loop 引擎，只提供可入库校验的衔接：`skills/*/pcg/` 与 `workflows/*/pcg/` 的检查点、`load` 清单、不可逆权限、前端 option 按钮，以及任务目录里的 session/board 投影。`tools/*` 不设 pcg sidecar，也不进入 Gallery 编排。

## 宿主循环触发点

一次业务任务对应任务目录里一份 `pcg.session.v1`。宿主循环（每轮模型调用 / 工具往返）和 token compact 都必须能重新投影画板；**追加留痕**和**重新投影**不是同一件事：

| 时机 | 追加 `append_artifact` | 重新 `compose_board` / `compose_view` |
| --- | --- | --- |
| 工具回写 `pcg.tool_result.v1` 且 `artifacts` 非空 | 是，按槽位追加 traces | 是 |
| 本轮确认有新文件或稳定 `href`，即使短回写漏了槽位 | 是 | 是 |
| 每轮 loop 结束，session 无新产物 | 否，禁止空 traces | 是（幂等；前端与压缩残留读最新 board） |
| token compact / 截断上下文 | 否，禁止为压缩伪造产物 | **必须**。从任务目录 session 重投影；压缩残留优先保留 board 叶子的当前 path/href 与 traces 条数，不靠聊天记录记文件 |
| 流中断 `stream_incomplete` | 否 | **必须**重投影。`mark_stream(incomplete)`；续跑读 `stream.response_id` 与画板，不把通道错误写成 failed |
| 用户 option / 回退写回 session.checkpoint | 否 | `compose_view`；architecture 有则同时 `compose_board` |

compact 之后聊天里的路径可能消失，架构图仍以任务目录为准。没有新字节时反复 append 会污染留痕；没有重投影则压缩后画板与磁盘脱节。本仓库不调度这些时机，由宿主在 loop 与 compact 钩子里调用既有函数。

## 入库约束

`python3 tools/package-tools/scripts/usage.py --repo . --check` 在使用关系检查之后运行 `pcg_check.py`。skills 与 workflows 必须各有：

- `pcg/routes.yaml`：`kind` 为 `agent_skill` 或 `agent_workflow`；`entry` 为 `SKILL.md`；`ui.option_buttons: true`；每检查点 `load` 以 `SKILL.md` 开头且路径存在于包内（入库清单；宿主用 `pending_inject` 避免每轮重贴）；`choices_example` 2–4 项，每项恰好一个 `route` 或 `rollback_to`，供前端 option 按钮。
- `pcg/ops.lock.json`：`schema` 为 `pcg.ops.lock.v1`；`unmapped` 与检查点 id 同序；`blueprint_pcg_ops` 只列 blueprint-pcg 已有 ship op，禁止编造 op。
- `pcg/architecture.yaml`：skills 必须 `layout: linear`（任务链与检查点同序，`rollback_to` 与 routes 一致）；workflows 必须 `layout: tree`。均为 `pcg.architecture.v1`。任务 `outputs` 可声明 `kind`/`retain`/`semantics`。`keep` 不参与 cache 清理。新建入口时 `usage.py --write` 或 `pcg_check.py --write-missing-architecture` 仅在文件缺失时按 kind 生成；已有手调不覆盖。

新增、迁入及流程修订的内容要求见[阶段架构与产物说明](repository-AGENTS.md#阶段架构与产物说明)：architecture 必须反映实际阶段及产物，生成器只提供初稿。现有字段中，`function`/`members` 描述阶段操作与交接，`outputs` 声明文件或 URL 槽；workflow 的 `parent` 表示编排归属，具体先后和等待条件须在阶段描述中明确。文件路径在执行时由 session 绑定。`pcg_check` 校验存在性、布局、标识和枚举等结构约束，不验证自然语言描述的完整性或业务真实性；维护者仍须对照入口与实现复核。

不可逆标志仅允许：`hi3d.submit`、`mdf.invoke`、`blender.write`、`overwrite.source`、`publish`、`delete`、`network.write`。非空则 `confirm_required: true`。

实现：[pcg_check.py](../.dependency-package-tools/scripts/pcg_check.py)、[pcg_architecture.py](../.dependency-package-tools/scripts/pcg_architecture.py)、[pcg_yaml.py](../.dependency-package-tools/scripts/pcg_yaml.py)（标准库 YAML 子集）。

## 会话与工具回写

每次打开画板（含 loop 结束与 compact 后）必须投影 `catalog.artifacts`，用最后已知 path/href 让用户找到产物。磁盘探测用 `locate_board`；缺文件标 `missing`，清理后标 `purged`，留痕仍在。

按语义清理 cache：`select_purge(..., semantics=['lod'])` 只选 `retain=cache|ephemeral` 且标签相交的文件；空 semantics 表示全部 cache。宿主确认后 `purge_under_root` 仅删除任务根内文件并 `mark_purged`。`retain=keep` 禁止进入目标列表。URL 槽不删文件。

会话文件写在任务目录，不写回 skill/workflow 包。字段由 [session_schema.py](../.dependency-run-tools/scripts/session_schema.py) 的 `pcg.session.v1` 约束。工具回写短 JSON，由 [tool_result.py](../.dependency-run-tools/scripts/tool_result.py) 的 `pcg.tool_result.v1` 约束。禁止签名 URL 与凭据写入 `href`。对话别名 `@name` 写在同一 session 的 `refs` 上，由 [artifact_refs.py](../.dependency-run-tools/scripts/artifact_refs.py) 标记与解析；它不能代替 `task`/`output` 槽位，也不能指向任务根以外的路径。同一 session 的 `popup_reasons` 记录已弹出的检查点+reason，由 `mark_popup_reason` 去重。`injected` 记录本 compact 窗口已注入的包内路径；`stream` 记录 QueryEngine 流生命周期（`incomplete` 不是 failed）。

`pcg.session.v1` 是本任务进度索引，不是代码映射，也不是跨会话记忆库。可从当前入口、实现或 git 读到的约定不要写入 session 当事实源。压缩残留只保留 board 叶子的当前 path/href 与 traces 条数，完整留痕按需打开任务目录。session 记录的是写入时刻的观察：断言文件仍可用前执行 `locate_board` 或带 `task_root` 的 `resolve_ref`，缺文件标 `missing`。不可从仓库推导的用户纠正/肯定（含 Why 与适用范围）及绝对日期由宿主放在任务目录或宿主自有存储；禁止另建 MEMORY.md 式索引或后台提取 Agent。编排 agent 的运行时条文见 [宿主编排注入](../.dependency-pcg-view/references/host-orchestration.md) §7 与 §8。

检查点哈希仍用既有 [checkpoints.py](../.dependency-run-tools/scripts/checkpoints.py)，只核对内容，不决定远端是否可重试。

## 宿主时间轴与画板

两套图：

- **执行架构（画板）**：skill 为线形前进/回退；workflow 为 spawn 树。每次打开带 `catalog.artifacts`。`keep` 不清。
- **用户决策页**：加载 `pcg/routes.yaml` 与任务目录 `pcg.session.v1`，投影 `pcg.view.v1`。左侧 rail、检查点回退、`waiting_choice` 时的 option 弹窗。Hi3D 提交为参数选择再计费示警两阶段，目录见 [宿主编排注入](../.dependency-pcg-view/references/host-orchestration.md)。不要把它当成执行架构。

[pcg-view](../.dependency-pcg-view/REFERENCE.md) 约定：

- 计费/不可逆用占位 `tone`；耗分写在进入该主体的连线和放大后的节点上，不另开耗分画板。
- **option_popup** 只服务 routes 决策图，复用 `choices_example`；Hi3D 参数写入 `web_options`，计费示警写入 `billing`。
- 计费节点只能确认提交，不能当回退目标，也不能撤销已扣积分。

接口见 [pcg-view](pcg-view.md)。
