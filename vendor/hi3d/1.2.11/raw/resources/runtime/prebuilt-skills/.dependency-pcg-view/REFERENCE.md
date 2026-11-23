---
name: pcg-view
description: "把 skill 画成可回退的线形进程，把 workflow 画成 spawn 编排树，并可投影为 AntV G6 流程图数据；routes 检查点图仍可投影为用户决策 overview，option 弹窗同时服务选型与宿主决策时刻。提供宿主编排注入提示，供宿主嵌入，不执行 Agent。"
---

# 执行架构画板与决策图

两套输入，不要混用：

| 输入 | schema | 画什么 |
| --- | --- | --- |
| `pcg/architecture.yaml` | `pcg.architecture.v1` → `pcg.board.v1` | **画板**：`layout=tree` 的 workflow 是编排树；`layout=linear` 的 skill 是检查点链，带前进与 `rollback_to` 回退。 |
| `pcg/routes.yaml` + session | `pcg.view.v1` | **用户决策页**：检查点 rail、回退、option 弹窗。不是执行架构。 |

每个 skill/workflow 均维护 `pcg/architecture.yaml`（`pcg.architecture.v1`）。skill 必须 `layout: linear`（检查点链 + `rollback_to`）；workflow 必须 `layout: tree`（编排 agent / 本地阶段 / spawn）。经 `compose_board` 投影为 `pcg.board.v1`。**不要**用 `routes.yaml` 冒充拆解图（routes 只投影用户决策页）。加载当前入口后，把 [宿主编排提示](references/host-orchestration.md) 注入编排 agent（含 compact/断流短索引、load 差集注入、路径须再探测；不把通道错误当失败；不卸载电脑工具）。新建入口缺文件时由 [package-tools](../.dependency-package-tools/REFERENCE.md) 在 `--write` 时按 kind 生成对应 layout，本工具仍不执行 Agent。

- **spawn**：`role=subagent` 且必须有 `entry`（独立 skill/tool 名）。宿主 `host_actions.spawn_subagent`。
- **本地阶段**：`role=local`；`members` 是同一 agent 的步骤。
- **产物末梢**：`outputs[]` 叶子 + `catalog.artifacts` 产物目录，每次打开都能按最后已知 path/href 找到文件。`retain=keep|cache|ephemeral`，`semantics` 控制 cache 清理：`select_purge` 选型，`purge_under_root` 只删任务根内 cache 文件并留痕。keep 禁止清理。
- **tone / color**：`billable` / `irreversible` / `reversible` 占位色；耗分写在进入该包的 **edge.cost**。
- **编排树 LOD**：总览 `lod=preview` 只有角色图形与色相；拉近 `lod=detail` 才显示阶段名、spawn 入口与边注。skill 线形链不走这套。
- **G6 流程图**：`--format g6` 输出可交给 `new Graph({ data: g6, ...graph })`；LOD 字段 `level` 对齐 G6 示例的 overview/detailed，语义仍用本仓库 preview/detail。
- **option_popup** 只属于 routes 决策图；`waiting_choice` 同时用于用户选型与宿主注入的决策时刻（预算确认、心跳分类等）。Hi3D 参数选择写入 `option_popup.web_options`，目录来自 [hi3d-api 网页 option 门禁](../hi3d/references/web-option-gates.md)。

```bash
python3 scripts/view_cli.py --architecture architecture.json --session session.json --format g6 --lod preview --output "$TASK/board.g6.json"
python3 scripts/view_cli.py --architecture architecture.json --session session.json --list-purge --semantics lod --output "$TASK/purge.json"
python3 scripts/view_cli.py --routes routes.json --session session.json --format html --output "$TASK/view.html"
```

YAML 须先转 JSON。不执行业务、不读凭据。完整接口见 [doc](../.dependency-doc/pcg-view.md)。

<!-- managed-by: sparc3d-runtime -->
