# 执行架构画板与决策图

`pcg-view` 产出两种投影。Python 3.9+ 标准库。不执行业务、不联网、不读凭据、不估算 ETA、不把余额差当实扣。

| 输入 | 输出 | 宿主画什么 |
| --- | --- | --- |
| `pcg.architecture.v1` + 可选 `pcg.session.v1` | `pcg.board.v1` 或 `pcg.g6.v1` | **执行画板**：语义以 board 为准；`--format g6` 再包一层 AntV G6 `{nodes, edges}` 供流程图渲染。 |
| `pcg/routes.yaml` + 可选 session | `pcg.view.v1` | **用户决策页**：检查点时间轴、回退与 option 弹窗。不是执行架构。 |

要可视化执行结构，必须先有 `pcg/architecture.yaml`，再调用 `compose_board`。skill 入库强制 `layout: linear` 且任务链与 routes 检查点同序、`rollback_to` 一致；workflow 强制 `layout: tree`。仅有 `routes.yaml` 只能出决策页。缺文件时由 [pcg_architecture.py](../.dependency-package-tools/scripts/pcg_architecture.py) 按 kind 生成，不覆盖手调文件。

全部 skill/workflow 均带 architecture；skill 为线形回退链，workflow 手调样例见 hi3d-game-demo / image-to-assembly / product-design。

## 模块与接口

### scripts/architecture_ir.py

[唯一实现](../.dependency-pcg-view/scripts/architecture_ir.py)。

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `compose_board` | `architecture`, `session=None` | 校验单树、`layout` 与 `outputs`。skill 链上额外投影 `advance`/`rollback` 边。workflow 树 `host_actions.lod` 为 `preview`/`detail`。叶子绑定 session；`catalog.artifacts` 是产物目录。`keep` 永不进入清理。 |
| `select_purge` | `architecture`, `session=None`, `semantics=()` | 选出 `retain=cache\|ephemeral` 且语义相交的文件槽。空 semantics 表示全部 cache。不删文件。 |
| `locate_board` | `board`, `task_root` | 只读探测任务根下文件是否仍在；缺文件标 `missing`，不删 session。不请求 URL。 |

tone：任务 `irreversible` 含 `hi3d.submit`/`mdf.invoke` 为 `billable`；其它已知不可逆为 `irreversible`。`color` 为占位。

### scripts/view_ir.py

[唯一实现](../.dependency-pcg-view/scripts/view_ir.py)。

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `compose_view` | `routes`, `session=None` | 校验 checkpoints/routes。`overview` 为检查点阶段组或 `session.agents` 树。`option_popup` 仅 `waiting_choice` 可见，含预算确认、心跳分类与其它宿主决策时刻。含 `hi3d.submit` 时附加参数 `web_options`（[网页 option 门禁](../hi3d/references/web-option-gates.md)）。Desktop 对话里的 Hi3D 参数面板走 dry-run 返回的 `user_interaction`，不把本投影当成聊天 overlay。缺字段、重复 id、多根或环失败。 |

不要用 `compose_view` 代替任务拆解画板。

### scripts/svg_overview.py

[唯一实现](../.dependency-pcg-view/scripts/svg_overview.py)。`layout_overview` / `svg_overview` 接受 `pcg.view.v1` 与 `pcg.board.v1`。workflow 树：节点用角色图形（编排圆角矩形、本地圆、spawn 菱形、产物方块）和 tone 色相；标签与边注放在 `class="board-detail"`，总览 LOD 隐藏。计费边标注 `Hi3D×n`/`MDF×n`；spawn 边无耗分时标注 `spawn`。skill 线形链仍在节点内写字。

### scripts/svg_board.py

[唯一实现](../.dependency-pcg-view/scripts/svg_board.py)。把计费检查点排成一行的辅助绘制，**不是**执行架构画板；默认入口不调用。

### scripts/html_view.py

[唯一实现](../.dependency-pcg-view/scripts/html_view.py)。`html_document`：`pcg.board.v1` 走 `html_board`。`layout=tree` 默认 `data-lod=preview`（无节点文字），滚轮或「细节」拉近后 `lod=detail`；`layout=linear` 为水平进程 + 虚线回退。`pcg.view.v1` 为决策页；生模 `web_options` 统一提示「请选择您要使用的 Hi3D 生成参数」，chip 展示网页短文案（v3.0 高质/大师、v2.1 极速/高质、v2.0 均衡/高质，以及几何+风格化贴图（推荐） / 几何），提交 id 仍在 `data-id`，不显示积分和估时。

### scripts/g6_graph.py

[唯一实现](../.dependency-pcg-view/scripts/g6_graph.py)。`board_to_g6(board, lod=None)` 把 `pcg.board.v1` 投影为 `pcg.g6.v1`：`g6.nodes[].id` / `g6.edges[].source|target` 符合 G6 5.x `Graph.data`；`data` 仍是本仓库字段（role、tone、entry、cost、retain、path），不含组织架构示例的 phone/position，也不规定十六进制色。tree 默认 `lod=preview`（G6 `level=overview`），`detail` 对应 `detailed`；linear 仅 `detail`，`graph.layout.rankdir=LR`。决策页 `pcg.view.v1` 不走 G6。

### scripts/view_cli.py

[唯一实现](../.dependency-pcg-view/scripts/view_cli.py)。`--architecture` 与 `--routes` 二选一；architecture 可另带 `--session`、`--task-root`（locate）、`--lod preview|detail`（仅 g6）；`--list-purge --semantics lod,cache` 只列出可清槽位。`--format json|html|svg|g6`；`--output` 必填。

## 宿主编排提示

[host-orchestration.md](../.dependency-pcg-view/references/host-orchestration.md) 是给编排 agent 的注入说明，不是 Python API。宿主加载当前 skill/workflow 后注入该页「注入块」，按 `pcg.architecture.v1` 拆解并监管阶段；决策时刻统一走 `waiting_choice`，不要每个入口复制弹窗目录；Hi3D 仅在 dry-run 返回 `consent.user_interaction` 时展示参数面板，文生图和图生图按其工具策略直接生成。注入块 §7–§8 约束 compact/断流后的短索引、load 差集注入、路径须再探测，以及不把通道错误当任务失败、不卸载电脑工具；本工具不实现跨会话记忆库。本地无界 CPU 须先读 [预算契约](../.dependency-run-tools/references/budget-run.md) 再启动内核。`compose_board` 只消费已声明的 architecture，不根据提示词自动生成 YAML。

## 验收

[tests/test_architecture.py](../.dependency-pcg-view/tests/test_architecture.py)：拆解树、产物目录、语义清理跳过 keep、session 留痕。`python3 -m unittest discover -s tests -v`。
