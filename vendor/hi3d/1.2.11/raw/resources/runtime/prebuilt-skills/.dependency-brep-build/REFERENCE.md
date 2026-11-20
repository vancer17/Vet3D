---
name: brep-build
description: 依据明确毫米配方用 CadQuery 无头构建可导出 STEP 的 B-rep 实体（盒/柱/锥、抽壳、ISO 螺纹与孔、命名布尔与倒角）。适用于机械接口与打印实体；不接收网格反求、不替代 Blender 网格原语或带 UV 布尔。
---

# 参数化 B-rep 实体

依据明确毫米配方构建可导出 STEP 的 B-rep 实体，并给出细分 STL。内核在墙钟预算下作为子进程运行，先写心跳再建模。

## 输入与完成结果

- 输入：`brep-build.v1` 配方 JSON（单位必须是 mm）、尚不存在的输出目录；中高档预算需 `--confirm-budget`。
- 输出：`budget.json`、`progress.json`；确认后由 CadQuery 写入 `parts/<id>.step`、`parts/<id>.stl` 与 `manifest.json`。中高档未确认或超时只写预算/心跳/`waiting.json`，不写半截 STEP。

使用 `$brep-build` 或显式读取本入口。先按 [打包约定](../.dependency-package-tools/references/usage.md) 物化 [package.json](package.json)，`SKILL_DIR` 为分发目录中的本 skill。Python 3.9+；建模需要 CadQuery（OCP）。无网络、不读取密钥、不调用 Hi3D。

```bash
"$PYTHON" "$SKILL_DIR/scripts/brep_build.py" --check --spec "$RUN_DIR/spec.json"

"$PYTHON" "$SKILL_DIR/scripts/brep_build.py" \
  --spec "$RUN_DIR/spec.json" --output "$RUN_DIR/brep-v1" --confirm-budget
```

`--check` 只校验配方并给出预算，不写盘。退出码 `2` 表示需要 `waiting_choice` 确认预算，`3` 表示内核超时已杀进程。字段与 `kind` 见 [配方契约](references/contract.md)；函数入口见 [代码契约](references/code-contract.md)。本地杀进程与心跳唯一实现于 [run-tools 预算契约](../.dependency-run-tools/references/budget-run.md)。`--help` 查看参数。

## 执行

按顺序读本入口、[检查点](pcg/routes.yaml) 与 [阶段产物](pcg/architecture.yaml)。GPT 只改配方 JSON，不写 CadQuery 脚本。宿主按 [编排注入](../.dependency-pcg-view/references/host-orchestration.md) 把 session 设为 `waiting_choice`，使用本入口 `choices_example`；不要另写弹窗目录。

| 阶段 | 操作与出口证据 |
| --- | --- |
| `input` | 校验 schema、单位、实体/布尔命名；估算档位；新建输出目录并写 `budget.json` 与 `progress.json`。已有合格 STEP 走 `review_only`。中高档未 `--confirm-budget` 时写 `waiting.json` 并停止。 |
| `build` | 用 `run_budgeted` 启动包内 `brep_kernel.py`。心跳覆盖 `progress.json`。超时 terminate/kill，写 `waiting.json`，不写半截 STEP。 |
| `export` | 核对 `manifest.json` 与每个导出 STEP/STL 存在、体积为正、单位 mm。数字啮合不等于实物密封或强度。 |

艺术放样/回转/板壳网格仍用 [shape-build](../.dependency-shape-build/REFERENCE.md)。带逐面 UV 的网格局部布尔仍用 [solid-edit](../.dependency-solid-edit/REFERENCE.md)。连接构型选型用 [connector-select](../.dependency-connector-select/REFERENCE.md)，本入口只按已选尺寸建牙/孔。进 Blender 由调用方把 STL 交给 [blender-tools](../.dependency-blender-tools/REFERENCE.md)。调用方若要把本入口写出的 STL 再打成 3MF，显式组合 [print-export](../.dependency-print-export/REFERENCE.md)；本入口不调用它。

## 关键边界

- 不接收 GLB/STL/网格反求、缝合或特征识别字段。螺纹必须给 `M12` 或 `M12x1.5` 这类 designation，不从三角牙型推断螺距。
- 配方建模不是 FreeCAD 装配、图纸或 BOM；BOM 仍在 [print-plan](../.dependency-print-plan/REFERENCE.md)。覆盖已有 STEP 时另开目录，或由宿主按 `overwrite.source` 确认。
- 低档（简单盒/柱、很少布尔）可直接建模；中高档（螺纹、抽壳、倒角）必须确认预算。超时只允许用户 option 后用新目录和新的 `budget.max_wall_s` 再跑，且 `extend_used` 只能一次。
- CadQuery 未安装时 `--check` 仍可用；`build` 失败并说明依赖缺失，不假装写成了 STEP。
- 文件存在不等于牙型或公差正确；须打开 STEP 或对照 manifest 体积与 bbox 验收。

<!-- managed-by: sparc3d-runtime -->
